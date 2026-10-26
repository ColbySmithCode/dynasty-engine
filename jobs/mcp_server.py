"""Phase 9 — read-only MCP server over the warehouse. Pre-registration: docs/PHASE9_PLAN.md (G9.1-8).

READ-ONLY. Serves the Phase-3→8 outputs to an MCP client. It NEVER writes the warehouse, NEVER
computes/rescales a statistic at request time (G9.7), and reads every estimand / interval_type /
uncertainty_status from the pinned bundle (never restates them in code, G9.4). Metadata derivations
are a CLOSED list: freshness-state, max(last_successful_refresh), git ancestry/HEAD, season-state.

Tools return the G9 numeric SCHEMA:
  {point, interval_lo, interval_hi, interval_type, estimand, uncertainty_status}
Trade uses interval_type=MC_PRECISION_BAND and never a ci_* key. `interval_type != NONE` with an
empty `estimand` is a hard fail.

    uv run python -m jobs.mcp_server              # stdio JSON-lines dispatch (minimal)
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CONFIG, REPO_ROOT
from jobs import read_policy as rp
from jobs import check_doc_consistency as reg
from jobs.build_bundle import FROZEN_BY_DESIGN

# Serve-time reconciliation tolerance: the bundle mcp_fact.point and the doc-consistency registry
# canonical are two INDEPENDENT pinned copies of the same number; they must agree to full artifact
# precision. 1e-6 matches the registry's own sub-milli drift tolerance.
_REGISTRY_TOL = 1e-6

BUNDLE_PATH = CONFIG.path("exports") / "assistant_bundle.json"
INTERVAL_TYPES = {"DELONG_PAIRED_CI", "PERCENTILE_BOOTSTRAP_CI", "MC_PRECISION_BAND", "EXACT_CI", "NONE"}
STATUSES = {"ESTIMATED", "UNINFORMATIVE", "AT_RISK", "OVERTURNED", "UNPROPAGATED", "OPEN"}


class BoundaryError(Exception):
    """A read-side/serving invariant was violated — the tool HARD-FAILS rather than degrading."""


# ---- read-only warehouse access (G9.1) --------------------------------------------------------
# read_only=True blocks INSERT/UPDATE/DELETE/CREATE/DROP, but NOT filesystem/side-channel writes
# (COPY … TO, ATTACH … READ_WRITE, INSTALL, LOAD) — those don't write the read-only db, so DuckDB
# permits them. Defense-in-depth: the server executes NO caller-supplied SQL, and every internal
# query is routed through `guarded_query`, an ALLOWLIST that admits only read statements. Together
# these close the full G9.1 matrix.
_READ_STMT = re.compile(r"^\s*(?:select|with|pragma\s+table_info|pragma\s+database_list)\b", re.I)
_FORBIDDEN = re.compile(
    r"\b(?:insert|update|delete|drop|create|alter|truncate|replace|merge|copy|attach|detach|"
    r"install|load|export|import|call|vacuum|checkpoint|reset|set)\b", re.I)


# G9.10 instrumentation (added by the 2026-08-02 remote-transport extension): a monotone counter of
# warehouse connections opened. NOT query/schema logic — it lets the HTTP gate prove behaviorally
# that an unauthenticated request opens ZERO DuckDB connections (auth precedes any tool handler).
CONN_COUNT = 0


def read_only_con():
    """The ONLY warehouse access path. read_only=True; no write/DDL is reachable through any tool."""
    global CONN_COUNT
    CONN_COUNT += 1
    import duckdb
    return duckdb.connect(str(CONFIG.path("warehouse")), read_only=True)


def guarded_query(con, sql: str, params=None):
    """Statement allowlist (G9.1): admit ONLY a read statement (SELECT/WITH/PRAGMA table_info); refuse
    anything carrying a write/DDL/side-channel token (COPY TO, ATTACH, INSTALL, LOAD, …) that a
    read_only connection would otherwise let through. Raises before touching the connection."""
    if not _READ_STMT.match(sql) or _FORBIDDEN.search(sql):
        raise BoundaryError(f"non-read statement refused: {sql.strip().split(None, 1)[0].upper()}")
    return con.execute(sql, params or [])


# ---- pinned sources (no restating; G9.4/G9.7) -------------------------------------------------
def _bundle() -> dict:
    if not BUNDLE_PATH.exists():
        raise BoundaryError(f"pinned bundle missing: {BUNDLE_PATH}")
    return json.loads(BUNDLE_PATH.read_text())


def _registry_value(registry_key: str):
    for c in reg.numeric_canonicals():
        if c["name"] == registry_key:
            return c["value"]
    raise BoundaryError(f"registry canonical '{registry_key}' not found — cannot reconcile")


def _reconcile(fact: dict) -> None:
    """G9.4 DISAGREEMENT: the served point must agree with the doc-consistency registry canonical
    (a second, independently-pinned copy). Any divergence HARD-FAILS — the server never picks a
    winner between two disagreeing sources of truth."""
    rk = fact.get("registry_key")
    if not rk:
        raise BoundaryError(f"mcp_fact '{fact['key']}' has no registry_key — unreconcilable")
    rv = _registry_value(rk)
    if abs(float(fact["point"]) - float(rv)) > _REGISTRY_TOL:
        raise BoundaryError(
            f"DISAGREEMENT on '{fact['key']}': bundle point {fact['point']} vs registry "
            f"'{rk}' {rv} (> {_REGISTRY_TOL}); refusing to serve a contested value")


def _fact(key: str) -> dict:
    for f in _bundle().get("mcp_facts", []):
        if f["key"] == key:
            _reconcile(f)          # bundle-vs-registry cross-check before the value can be served
            return f
    raise BoundaryError(f"no pinned mcp_fact '{key}' — cannot restate at the boundary")


def emit(fact: dict) -> dict:
    """Map a pinned mcp_fact to the G9 SCHEMA, enforcing the shape invariants (no ci_*; interval_type
    with an empty estimand hard-fails). All fields are READ from the fact, none typed here."""
    it, est = fact["interval_type"], fact.get("estimand", "")
    if it not in INTERVAL_TYPES:
        raise BoundaryError(f"bad interval_type {it!r}")
    if fact["uncertainty_status"] not in STATUSES:
        raise BoundaryError(f"bad uncertainty_status {fact['uncertainty_status']!r}")
    if it != "NONE" and not est:
        raise BoundaryError(f"interval_type {it} with EMPTY estimand ({fact['key']})")
    out = {"point": fact["point"], "interval_lo": fact["interval_lo"],
           "interval_hi": fact["interval_hi"], "interval_type": it, "estimand": est,
           "uncertainty_status": fact["uncertainty_status"]}
    if any(k.startswith("ci_") for k in out):     # G9 SCHEMA: no ci_* field names
        raise BoundaryError("ci_* field name is forbidden in a G9 response")
    return out


def pinned_numeric_set() -> set:
    """Every statistical numeric across the pinned artifact set (G9.7 check target)."""
    vals = set()

    def walk(o):
        if isinstance(o, (int, float)) and not isinstance(o, bool):
            vals.add(round(float(o), 10))
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(_bundle())
    for name in ("cfb_5_4b_perm.json", "archetype_gap.json"):
        walk(json.loads((CONFIG.path("models") / name).read_text()))
    walk(json.loads((REPO_ROOT / "jobs" / "drift_baseline.json").read_text()))
    return vals


# ---- metadata derivations — CLOSED list (G9.7) ------------------------------------------------
def _refresh_rows():
    con = read_only_con()
    try:
        rows = guarded_query(con, "SELECT table_name, stale, last_successful_refresh "
                             "FROM fact_refresh_status").fetchall()
    except BoundaryError:
        raise
    except Exception as e:  # noqa: BLE001
        raise BoundaryError(f"fact_refresh_status missing — freshness mandatory ({e!r})")
    finally:
        con.close()
    return {r[0]: {"stale": bool(r[1]), "last_successful_refresh": r[2]} for r in rows}


def freshness(source_tables: list) -> dict:
    """3-state per the Phase-8 logic, but BOTH fields always surfaced (G9.2): a table can be
    frozen_by_design AND stale. 'stale dominates' governs display order only, never suppression."""
    refresh = _refresh_rows()
    stale = sorted(t for t in source_tables if refresh.get(t, {}).get("stale"))
    frozen = sorted(t for t in source_tables if t in FROZEN_BY_DESIGN)
    return {
        "stale": bool(stale), "stale_tables": stale,
        "frozen_by_design": bool(frozen),
        "frozen_reason": {t: FROZEN_BY_DESIGN[t] for t in frozen},
        "display_precedence": "stale-first" if stale else ("frozen-by-design" if frozen else "fresh"),
        "both_apply": bool(stale and frozen),
    }


def season_state(season: int = 2026) -> dict:
    """NOT_STARTED / IN_PROGRESS / COMPLETE from the count of completed 2026 games (metadata)."""
    con = read_only_con()
    try:
        n = guarded_query(con, "SELECT count(*) FROM fact_player_week WHERE season = ?",
                          [season]).fetchone()[0]
    finally:
        con.close()
    state = "COMPLETE" if season <= CONFIG["models"]["startup_backtest"]["last_complete_season"] else \
            ("NOT_STARTED" if n == 0 else "IN_PROGRESS")
    return {"season": season, "completed_player_weeks": int(n), "state": state,
            "transition_to_in_progress": "first completed Week-1 game",
            "label": (rp.LABEL if state == "IN_PROGRESS" else f"{season} (offseason, not started)"
                      if state == "NOT_STARTED" else str(season))}


def provenance() -> dict:
    b = _bundle()
    refresh = _refresh_rows()
    build_id = max((r["last_successful_refresh"] or 0) for r in refresh.values()) if refresh else None
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(REPO_ROOT),
                          capture_output=True, text=True).stdout.strip() or "unknown"
    prov = dict(b["provenance"])
    prov["warehouse_build_id"] = build_id           # max(last_successful_refresh) — metadata
    prov["git_commit"] = head
    return prov


def open_items() -> list:
    b = _bundle()
    if "open_items" not in b:
        raise BoundaryError("open_items source missing from the pinned bundle (G9.8)")
    return b["open_items"]


# ---- tools ------------------------------------------------------------------------------------
def trade_delta() -> dict:
    return {
        "consensus": emit(_fact("trade_consensus_e_delta")),
        "corpus": emit(_fact("trade_corpus_e_delta")),
        "rule": "Standing Constraint #4: BOTH pools, always. Bands are MC PRECISION BANDS — "
                "input-posterior uncertainty is UNPROPAGATED (magnitude unknown).",
        "freshness": freshness(["fact_player_season", "fact_adp", "fact_replacement"]),
        "provenance": provenance(),
    }


def archetype_gap() -> dict:
    return {
        "verdict": "INDISTINGUISHABLE from draft-capital-only (equivalent within ~0.03 AUC)",
        "gap": emit(_fact("archetype_gap")),
        "refit_estimand": emit(_fact("archetype_gap_refit")),
        "freshness": freshness(["fact_player_season", "dim_player"]),
        "provenance": provenance(),
        "open_items": open_items(),          # G9.8: touches the archetype negative
    }


def college_null() -> dict:
    return {
        "verdict": "no signal demonstrated; the pre-registered test was UNINFORMATIVE at these "
                   "event counts (NOT a null)",
        "family_wise_p": emit(_fact("college_wy_family_wise_p")),
        "freshness": freshness(["fact_player_season", "dim_player"]),
        "provenance": provenance(),
        "open_items": open_items(),          # G9.8: touches the college negative
    }


def startup_strategy() -> dict:
    return {
        "markings": ["no startup strategy has a VALIDATED edge (direction-safe; a non-validation "
                     "statement, NOT 'no edge exists')",
                     "individual strategy edges are UNINFORMATIVE (CIs admit every decision-relevant "
                     "value at the effective league count)"],
        "youth_2020_status": "UNADJUDICATED-AND-CLOSED (corpus-limited) — the apparent youth-2020 "
                             "Δ_bal edge was a SINGLE-SEED (1729) ARTIFACT, NEVER established (its "
                             "lower bound straddles 0 across 5 seeds; B=160 5-seed mean −0.0146). Do "
                             "NOT present it as a real, marginal, or validated effect; retired as a "
                             "served numeric 2026-07-31. Reopens only if the corpus grows (Colby "
                             "NOTE 0038, G10.7v COND-A).",
        "freshness": freshness(["_startup_strategy"]),      # frozen_by_design
        "provenance": provenance(),
        "open_items": open_items(),          # G9.8: touches Gate-6.5
    }


MANIFEST = [("trade", trade_delta), ("archetype", archetype_gap), ("college", college_null),
            ("startup", startup_strategy), ("strategy", startup_strategy),
            ("youth", startup_strategy), ("draft capital", archetype_gap)]


def answer(question: str) -> dict:
    """Fail-CLOSED router (G9.5): match the manifest, else return a structured refusal — never a
    best-effort answer."""
    ql = (question or "").lower()
    for kw, tool in MANIFEST:
        if kw in ql:
            return {"matched": kw, "response": tool()}
    b = _bundle()
    hit = next((e for e in b["cannot_answer"]
                if any(w in ql for w in ("rank", "value", "who", "start", "sit", "waiver",
                                         "lineup", "guarant", "kicker", "dst", "idp"))), None)
    return {"refused": True,
            "reason": (hit or {"reason": "not supported by the bundle"})["reason"],
            "cannot_answer": b["cannot_answer"]}


TOOLS = {"trade_delta": trade_delta, "archetype_gap": archetype_gap, "college_null": college_null,
         "startup_strategy": startup_strategy, "season_state": season_state, "answer": answer}


def handle(request: dict) -> dict:
    tool = request.get("tool")
    if tool not in TOOLS:
        return {"error": f"unknown tool {tool!r}; read-only server exposes {sorted(TOOLS)}"}
    args = request.get("args") or {}
    try:
        return {"result": TOOLS[tool](**args)}
    except BoundaryError as e:
        return {"hard_fail": str(e)}


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            print(json.dumps({"error": "bad json"}), flush=True)
            continue
        print(json.dumps(handle(req), ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
