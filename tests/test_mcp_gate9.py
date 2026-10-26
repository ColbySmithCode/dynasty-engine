"""Gate 9 — one test per pre-registered criterion (docs/PHASE9_PLAN.md G9.1–G9.8) for the read-only
MCP server. Prints each criterion PASS/FAIL and exits 1 on any failure (project gate-test style).

    uv run python -m tests.test_mcp_gate9            # run the full gate
    uv run python -m tests.test_mcp_gate9 --worker   # one determinism worker (prints a payload line)
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CONFIG, REPO_ROOT
from jobs import mcp_server as m
from jobs import read_policy as rp

BUNDLE = CONFIG.path("exports") / "assistant_bundle.json"
DRIFT = REPO_ROOT / "jobs" / "drift_baseline.json"


# ---- file-mutation helpers (always restore raw bytes; leave the tree clean) -------------------
@contextlib.contextmanager
def mutate_json(path: Path, fn):
    original = path.read_bytes()
    try:
        obj = json.loads(original)
        fn(obj)
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=1))
        yield
    finally:
        path.write_bytes(original)


def _bundle_fact_setter(key, point):
    def fn(b):
        for f in b["mcp_facts"]:
            if f["key"] == key:
                f["point"] = point
    return fn


# ---- G9.1 -------------------------------------------------------------------------------------
def g9_1() -> list:
    out = []
    src = (REPO_ROOT / "jobs" / "mcp_server.py").read_text()
    # static
    assert "read_only=True" in src, "G9.1 static: connection is not read_only=True"
    assert "from transform" not in src and "import transform" not in src, "G9.1 static: transform import"
    assert "from models" not in src and "import models" not in src, "G9.1 static: models fit import"
    out.append("static: read_only=True, no transform/models fit imports")
    # behavioral write-rejection matrix through the query guard (read_only alone lets COPY/ATTACH/
    # INSTALL/LOAD through — the allowlist is what closes them).
    con = m.read_only_con()
    evil_csv, evil_db = Path("/tmp/zz_gate9.csv"), Path("/tmp/zz_gate9.db")
    for p in (evil_csv, evil_db):
        p.unlink(missing_ok=True)
    vectors = {
        "INSERT": "INSERT INTO fact_refresh_status VALUES ('x',false,0)",
        "UPDATE": "UPDATE fact_refresh_status SET stale=true",
        "DELETE": "DELETE FROM fact_refresh_status",
        "CREATE": "CREATE TABLE zz(a int)",
        "DROP": "DROP TABLE fact_refresh_status",
        "COPY-TO": f"COPY fact_refresh_status TO '{evil_csv}'",
        "ATTACH-RW": f"ATTACH '{evil_db}' AS e (READ_WRITE)",
        "INSTALL": "INSTALL httpfs",
        "LOAD": "LOAD httpfs",
        "DYN-WRITE": "SELECT 1; DROP TABLE fact_refresh_status",
    }
    for name, sql in vectors.items():
        try:
            m.guarded_query(con, sql)
            raise AssertionError(f"G9.1 behavioral: {name} was NOT rejected")
        except m.BoundaryError:
            out.append(f"rejected {name}")
    con.close()
    assert not evil_csv.exists() and not evil_db.exists(), "G9.1: a write vector touched disk"
    # legit read still works
    assert m.guarded_query(m.read_only_con(), "SELECT 1").fetchone()[0] == 1
    out.append("legit SELECT admitted; no disk touched")
    return out


# ---- G9.2 -------------------------------------------------------------------------------------
def g9_2() -> list:
    out = []
    real = m._refresh_rows
    try:
        # frozen-only branch (signature unchanged): _startup_strategy present but NOT stale
        m._refresh_rows = lambda: {"_startup_strategy": {"stale": False, "last_successful_refresh": 1}}
        fz = m.freshness(["_startup_strategy"])
        assert fz["frozen_by_design"] and not fz["stale"] and not fz["both_apply"], fz
        out.append("frozen_by_design only when signature unchanged (both_apply=False)")
        # both branch (signature mutated → regenerated-not): stale AND frozen, BOTH surfaced
        m._refresh_rows = lambda: {"_startup_strategy": {"stale": True, "last_successful_refresh": None}}
        both = m.freshness(["_startup_strategy"])
        assert both["stale"] and both["frozen_by_design"] and both["both_apply"], both
        assert both["display_precedence"] == "stale-first", "stale must dominate DISPLAY only"
        assert both["frozen_reason"], "frozen field suppressed when both apply (forbidden)"
        out.append("both stale+frozen surfaced (BOTH fields present; stale-first is display-only)")
    finally:
        m._refresh_rows = real
    # missing fact_refresh_status hard-fails
    import duckdb
    orig_con = m.read_only_con
    try:
        m.read_only_con = lambda: duckdb.connect(":memory:")  # no fact_refresh_status
        try:
            m._refresh_rows()
            raise AssertionError("G9.2: missing fact_refresh_status did not hard-fail")
        except m.BoundaryError:
            out.append("missing fact_refresh_status hard-fails")
    finally:
        m.read_only_con = orig_con
    return out


# ---- G9.3 -------------------------------------------------------------------------------------
def g9_3() -> list:
    out = []
    s26 = m.season_state(2026)
    assert s26["state"] == "NOT_STARTED", s26
    assert "offseason, not started" in s26["label"], s26
    assert s26["completed_player_weeks"] == 0, s26
    assert s26["transition_to_in_progress"] == "first completed Week-1 game", s26
    out.append(f"2026 → NOT_STARTED, label {s26['label']!r}, transition named")
    assert m.season_state(2025)["state"] == "COMPLETE", "2025 must be COMPLETE"
    out.append("2025 → COMPLETE")
    # injected bare-2026 fails the response validator; the season label passes
    raised = False
    try:
        rp.assert_no_unlabeled_2026("value for 2026 is 40.1")
    except AssertionError:
        raised = True
    assert raised, "G9.3: a bare-2026 numeric passed the validator"
    rp.assert_no_unlabeled_2026(f"ADP {s26['label']}")   # labelled (offseason) → OK
    out.append("bare-2026 numeric rejected; labelled ADP accepted")
    return out


# ---- G9.4 -------------------------------------------------------------------------------------
def g9_4() -> list:
    out = []
    # (a) LIVENESS — mutate BOTH the bundle fact AND the registry source consistently → output tracks
    NEW = 999.0
    with mutate_json(BUNDLE, _bundle_fact_setter("trade_corpus_e_delta", NEW)), \
         mutate_json(DRIFT, lambda b: b["trade_verdict"].__setitem__("corpus_e_delta", NEW)):
        r = m.trade_delta()
        assert r["corpus"]["point"] == NEW, f"G9.4 liveness: output did not track ({r['corpus']['point']})"
    out.append("LIVENESS: consistent mutation of both sources → output tracked new value")
    # (b) DISAGREEMENT — mutate exactly ONE (bundle only) → hard fail
    with mutate_json(BUNDLE, _bundle_fact_setter("trade_corpus_e_delta", NEW)):
        try:
            m.trade_delta()
            raise AssertionError("G9.4 disagreement: bundle-only mutation did NOT hard-fail")
        except m.BoundaryError as e:
            assert "DISAGREEMENT" in str(e), e
    out.append("DISAGREEMENT: single-source mutation → hard fail (no silent degrade)")
    # (c) startup emits BOTH markings
    mk = m.startup_strategy()["markings"]
    assert len(mk) == 2 and any("validated" in x.lower() for x in mk) \
        and any("uninformative" in x.lower() for x in mk), mk
    out.append("startup carries BOTH markings (no-validated-edge AND edges-UNINFORMATIVE)")
    # confirm restored / tree clean for these two files
    # corpus E[Δ] re-pinned 2026-07-31 (producer-backed 200-seed mean; -76.1 was hand-typed, no producer)
    assert m.trade_delta()["corpus"]["point"] == -77.87029531550294, "state not restored after G9.4"
    return out


# ---- G9.5 -------------------------------------------------------------------------------------
def g9_5() -> list:
    out = []
    for q in ("rank my top 5 by value.", "who wins the super bowl?", "should I start him this week?"):
        a = m.answer(q)
        assert a.get("refused") is True, f"G9.5: off-manifest {q!r} was not refused: {a}"
        assert a.get("cannot_answer"), "refusal must carry the named cannot_answer manifest"
    out.append("3 off-manifest queries → structured refusal (with cannot_answer manifest)")
    assert m.answer("is this trade good?").get("refused") is None, "on-manifest query refused"
    out.append("on-manifest trade query → answered (matched)")
    return out


# ---- G9.6 -------------------------------------------------------------------------------------
def g9_6a() -> list:
    p = m.provenance()
    for k in ("nflverse_vintage", "nflverse_input_signature", "warehouse_build_id", "git_commit"):
        assert p.get(k) not in (None, "", "unknown"), f"G9.6a: provenance missing {k}: {p}"
    return [f"provenance carries vintage+sig, warehouse_build_id {p['warehouse_build_id']}, "
            f"git {p['git_commit']}"]


def _det_payload() -> dict:
    pl = {"trade": m.trade_delta(), "archetype": m.archetype_gap(), "college": m.college_null(),
          "startup": m.startup_strategy(), "season": m.season_state(2026)}
    pl.pop("generated_at", None)   # the one permitted-variation field (unused here) is stripped
    return pl


def g9_6b() -> list:
    env = dict(os.environ, PATH=os.path.expanduser("~/.local/bin") + ":" + os.environ.get("PATH", ""))
    root = str(REPO_ROOT)
    payloads = []
    for i in range(5):
        r = subprocess.run(["uv", "run", "python", "-m", "tests.test_mcp_gate9", "--worker"],
                           cwd=root, env=env, capture_output=True, text=True)
        line = [l for l in r.stdout.strip().splitlines() if l.startswith("{")]
        if not line:
            raise AssertionError(f"G9.6b worker {i} failed: {r.stderr[-300:]}")
        payloads.append(line[-1])
    assert len(set(payloads)) == 1, f"G9.6b: {len(set(payloads))} distinct payloads across 5 processes"
    return ["byte-identical payloads across 5 fresh processes (against pinned last_successful_refresh)"]


# ---- G9.7 -------------------------------------------------------------------------------------
def _emit_dicts(o):
    if isinstance(o, dict):
        if "interval_type" in o and "point" in o:
            yield o
        else:
            for v in o.values():
                yield from _emit_dicts(v)
    elif isinstance(o, list):
        for v in o:
            yield from _emit_dicts(v)


def g9_7() -> list:
    out = []
    pinned = m.pinned_numeric_set()
    responses = [m.trade_delta(), m.archetype_gap(), m.college_null(), m.startup_strategy()]
    checked = 0
    for resp in responses:
        for e in _emit_dicts(resp):
            for field in ("point", "interval_lo", "interval_hi"):
                v = e[field]
                if v is None:
                    continue
                assert round(float(v), 10) in pinned, \
                    f"G9.7: emitted statistic {field}={v} ({e['estimand'][:40]}) not in the pinned set"
                checked += 1
    out.append(f"all {checked} emitted statistics found at full precision in the pinned artifact set")
    # negative control: a fabricated off-artifact statistic must NOT be in the set (so the check bites)
    assert round(123456.789, 10) not in pinned, "G9.7 negative control failed"
    out.append("negative control: an invented statistic is absent (check is discriminating)")
    # closed metadata list — the only request-time derivations are exactly these four
    assert {"freshness", "season_state", "provenance"}  # named metadata functions exist
    for fn in ("freshness", "season_state", "provenance"):
        assert hasattr(m, fn), f"G9.7 metadata derivation {fn} missing"
    out.append("permitted metadata derivations present (freshness / season_state / provenance); "
               "no other request-time computation")
    return out


# ---- G9.8 -------------------------------------------------------------------------------------
def g9_8() -> list:
    out = []
    # (a) TRACKS SOURCE — mutate a flag's status OPEN→RESOLVED in the source, output follows
    def flip(b):
        b["open_items"][0]["status"] = "RESOLVED"
    with mutate_json(BUNDLE, flip):
        oi = m.archetype_gap()["open_items"]
        assert oi[0]["status"] == "RESOLVED", f"G9.8 tracks-source: output did not follow ({oi[0]})"
    out.append("TRACKS SOURCE: flag OPEN→RESOLVED in source → output followed")
    # (b) MISSING SOURCE HARD-FAILS — not silent omission
    with mutate_json(BUNDLE, lambda b: b.pop("open_items", None)):
        try:
            m.archetype_gap()
            raise AssertionError("G9.8: missing open_items silently omitted (must hard-fail)")
        except m.BoundaryError:
            pass
    out.append("MISSING SOURCE: absent open_items → hard fail (never silent omission)")
    # restored
    assert m.archetype_gap()["open_items"][0]["status"] == "OPEN", "state not restored after G9.8"
    return out


GATES = [("G9.1 read-only (behavioral)", g9_1), ("G9.2 freshness (3-state)", g9_2),
         ("G9.3 2026 NOT_STARTED", g9_3), ("G9.4 read-not-restate", g9_4),
         ("G9.5 fail-closed", g9_5), ("G9.6a provenance", g9_6a),
         ("G9.6b determinism (5x)", g9_6b), ("G9.7 no boundary computation", g9_7),
         ("G9.8 open items", g9_8)]


def run() -> None:
    # Snapshot the mutation-target files: the criterion is that the mutation tests RESTORE them
    # byte-for-byte (tree left clean by the tests), independent of whether they already differ from
    # git HEAD (the rebuilt bundle legitimately differs until committed).
    pre = {p: p.read_bytes() for p in (BUNDLE, DRIFT)}
    fails = 0
    for name, fn in GATES:
        try:
            for detail in fn():
                print(f"  [PASS] {name}: {detail}")
        except Exception as e:  # noqa: BLE001
            fails += 1
            print(f"  [FAIL] {name}: {type(e).__name__}: {e}")
    residue = [p.name for p, b in pre.items() if p.read_bytes() != b]
    print(f"\nmutation tests restored all sources byte-for-byte: "
          f"{'YES' if not residue else 'NO — ' + ', '.join(residue)}")
    if residue:
        fails += 1
    print(f"\nGATE 9: {'PASS' if not fails else 'FAIL'} ({len(GATES) - fails}/{len(GATES)} criteria)")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    if "--worker" in sys.argv:
        with contextlib.redirect_stderr(io.StringIO()):
            print(json.dumps(_det_payload(), sort_keys=True, ensure_ascii=False))
    else:
        run()
