"""Gate 9 EXTENSION — one test per pre-registered criterion (docs/PHASE9_PLAN.md AMENDMENT 2026-08-02,
G9.9–G9.14) for the REMOTE Streamable-HTTP transport + auth. Behavioral: spins a real HTTP server on a
localhost ephemeral port and drives it with httpx. Prints each criterion PASS/FAIL and exits 1 on any
failure (project gate-test style).

    uv run python -m tests.test_mcp_gate9_http

G9.1–G9.8 (stdio) are unchanged and covered by tests/test_mcp_gate9.py; this file is additive.
"""
from __future__ import annotations

import logging
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CONFIG, REPO_ROOT
from jobs import mcp_http as h
from jobs import mcp_server as mcp
from tests.test_mcp_gate9 import mutate_json, _bundle_fact_setter, BUNDLE, DRIFT  # reuse; restores tree

TOKEN = "gate9-http-test-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
INTERVAL_ENUM = {"DELONG_PAIRED_CI", "PERCENTILE_BOOTSTRAP_CI", "MC_PRECISION_BAND", "EXACT_CI", "NONE"}


# ---- log capture (G9.10 requires LOG-based confirmation, not code inspection) ------------------
class _Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records: list[str] = []

    def emit(self, record):
        self.records.append(record.getMessage())

    def clear(self):
        self.records.clear()


# ---- helpers ----------------------------------------------------------------------------------
def _call(base: str, name: str, arguments: dict | None = None, rid: int = 1, headers=AUTH):
    """A tools/call over HTTP; returns the full JSON-RPC response dict."""
    body = {"jsonrpc": "2.0", "id": rid, "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}}}
    return httpx.post(base, headers=headers, json=body, timeout=30.0)


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


# The fixed parity/query set (G9.9): ≥5 manifest queries spanning every REACHABLE interval_type.
# tool-call form: (label, tool_name, arguments)
PARITY_SET = [
    ("trade (MC_PRECISION_BAND)", "trade_delta", {}),
    ("archetype (DELONG + refit PERCENTILE_BOOTSTRAP)", "archetype_gap", {}),
    ("college (NONE)", "college_null", {}),
    ("startup", "startup_strategy", {}),
    ("season_state", "season_state", {"season": 2026}),
    ("answer→trade (natural language)", "answer", {"question": "is this trade good?"}),
    ("answer→archetype (natural language)", "answer", {"question": "do archetypes beat draft capital?"}),
]


# ---- G9.9  (R1: WIRING-VERIFIED, NOT PARITY-TESTED) -------------------------------------------
def g9_9(base) -> list:
    """R1 (review 2026-08-02): this is NOT a parity test. The HTTP path calls `mcp_server.handle()`
    VERBATIM, so a parity break is UNREACHABLE BY CONSTRUCTION and this check has no power to detect
    one. It records only that the HTTP transport DISPATCHES TO THE SAME HANDLER. Reported as
    WIRING-VERIFIED, and it does NOT count toward the test-backed tally (5/6)."""
    out = []
    seen_types = set()
    for label, name, args in PARITY_SET:
        stdio = mcp.handle({"tool": name, "args": args})           # the exact stdio dispatch
        http = _call(base, name, args).json()["result"]["structuredContent"]
        assert h.canonical(http) == h.canonical(stdio), f"G9.9 WIRING BROKEN on {label}"
        for e in _emit_dicts(http):
            seen_types.add(e["interval_type"])
    assert len(PARITY_SET) >= 5, "G9.9 requires >=5 manifest queries"
    out.append(f"WIRING-VERIFIED (NOT parity-tested): HTTP dispatches to the same handler across all "
               f"{len(PARITY_SET)} manifest queries; a parity break is unreachable by construction, so "
               "this has NO power to detect one")
    reachable = {"DELONG_PAIRED_CI", "PERCENTILE_BOOTSTRAP_CI", "MC_PRECISION_BAND", "NONE"}
    assert seen_types == reachable, f"G9.9 interval_type coverage {seen_types} != {reachable}"
    absent = INTERVAL_ENUM - seen_types
    out.append(f"{len(reachable)} REACHABLE interval_types wiring-verified {sorted(reachable)}")
    # R2: EXACT_CI is emitted by NO tool → its coverage is UNINFORMATIVE (untested), not passing.
    out.append(f"EXACT_CI stratum: UNINFORMATIVE — no served tool emits {sorted(absent)}; coverage of "
               "that enum value is UNTESTED, not passing (marking travels with the criterion)")
    return out


# ---- G9.10 ------------------------------------------------------------------------------------
def g9_10(base, cap: _Capture) -> list:
    out = []
    endpoints = [("POST", base, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}),
                 ("GET", base, None),
                 ("POST", base.rsplit("/", 1)[0] + "/", {"jsonrpc": "2.0", "id": 1, "method": "initialize"})]
    for meth, url, body in endpoints:
        cap.clear()
        conn_before = mcp.CONN_COUNT
        r = httpx.request(meth, url, json=body, timeout=30.0)      # NO Authorization header
        assert r.status_code in (401, 403), f"G9.10: unauth {meth} {url} got {r.status_code}"
        assert mcp.CONN_COUNT == conn_before, \
            f"G9.10: unauth {meth} opened a DuckDB connection ({mcp.CONN_COUNT - conn_before})"
        # LOG-BASED confirmation: an AUTH_REJECT was logged, and NO dispatch/auth-ok happened.
        assert any("AUTH_REJECT" in m for m in cap.records), f"G9.10: no AUTH_REJECT log for {meth}"
        assert not any(("DISPATCH" in m or "AUTH_OK" in m) for m in cap.records), \
            f"G9.10: an unauth {meth} reached dispatch/auth-ok (log: {cap.records})"
    out.append("unauth POST/GET/root → 401 before any DuckDB connection (CONN_COUNT unchanged)")
    out.append("LOG-confirmed: AUTH_REJECT logged, no DISPATCH/AUTH_OK for any unauth request")
    # a wrong token is also rejected (constant-time compare)
    cap.clear()
    r = httpx.post(base, headers={"Authorization": "Bearer WRONG"},
                   json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, timeout=30.0)
    assert r.status_code == 401 and any("AUTH_REJECT" in m for m in cap.records), "G9.10: wrong token admitted"
    out.append("wrong bearer token → 401 (AUTH_REJECT logged)")
    return out


# ---- G9.11 ------------------------------------------------------------------------------------
def g9_11(base) -> list:
    """R3 (review 2026-08-02): the five canonical write vectors are run as LIVE HTTP REQUESTS (prong A),
    per-attempt. Because NO tool exposes a raw-SQL parameter, the vectors can only be submitted as tool
    ARGUMENTS — the sole caller-influenced channel over HTTP — and there is no SQL sink for them to reach
    `guarded_query` as statement text. Prong B (the `guarded_query` allowlist refusing the same five
    vectors) is verified IN-PROCESS and is LABELLED as a control-integrity check, explicitly NOT an
    HTTP-transport test. No static reasoning is offered as evidence for the HTTP prong."""
    out = []
    evil_csv, evil_db = Path("/tmp/zz_gate9_http.csv"), Path("/tmp/zz_gate9_http.db")
    for p in (evil_csv, evil_db):
        p.unlink(missing_ok=True)
    # HEADLINE SECURITY FINDING (promoted out of the caveat, per R3): the HTTP surface exposes NO SQL
    # sink — no tool advertises a sql/query/statement parameter — so the write vector is UNREACHABLE BY
    # CONSTRUCTION over HTTP. That is a STRONGER result than a passing allowlist test.
    tl = httpx.post(base, headers=AUTH, json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}).json()
    for t in tl["result"]["tools"]:
        props = set((t.get("inputSchema") or {}).get("properties", {}))
        assert not ({"sql", "query", "statement"} & props), f"G9.11: tool {t['name']} exposes raw SQL"
    out.append("FINDING: the HTTP surface exposes NO SQL sink (no tool takes a sql/query/statement "
               "param) → the write vector is UNREACHABLE BY CONSTRUCTION over HTTP")

    # (A) LIVE HTTP — each of the 5 canonical vectors submitted as tool arguments; per-attempt result.
    vectors = {
        "COPY":       f"'; COPY fact_refresh_status TO '{evil_csv}'; --",
        "ATTACH-RW":  f"'; ATTACH '{evil_db}' AS e (READ_WRITE); --",
        "INSTALL":    "'; INSTALL httpfs; --",
        "LOAD":       "'; LOAD httpfs; --",
        "DYN-COMPOSED": f"x'; COPY fact_refresh_status TO '{evil_csv}'; DROP TABLE fact_refresh_status; --",
    }
    conn_before = mcp.CONN_COUNT
    for vec, payload in vectors.items():
        # submit via BOTH caller-influenced channels: the routed NL string AND a bound query param
        r1 = _call(base, "answer", {"question": payload})
        r2 = _call(base, "season_state", {"season": payload})
        assert r1.status_code == 200 and r2.status_code == 200, \
            f"G9.11 LIVE-HTTP {vec}: transport crashed (answer {r1.status_code}, season {r2.status_code})"
        assert not evil_csv.exists() and not evil_db.exists(), \
            f"G9.11 LIVE-HTTP {vec}: a write vector touched disk"
        out.append(f"LIVE HTTP {vec}: 200, no statement executed, no disk artifact (submitted as tool "
                   "argument; never reaches DuckDB as statement text — no SQL sink)")
    # season_state DID run its own guarded, bound-param SELECT (so DuckDB was exercised, not bypassed)
    assert mcp.CONN_COUNT > conn_before, "G9.11: season_state should still open its own bound-param query"

    # (B) IN-PROCESS control-integrity check (NOT an HTTP test): guarded_query refuses the same 5 vectors
    # as STATEMENT TEXT before DuckDB. This is the backstop for internal queries; the HTTP transport has
    # no path to deliver statement text to it (that is prong A's finding).
    con = mcp.read_only_con()
    battery = {
        "COPY-TO": f"COPY fact_refresh_status TO '{evil_csv}'",
        "ATTACH-RW": f"ATTACH '{evil_db}' AS e (READ_WRITE)",
        "INSTALL": "INSTALL httpfs",
        "LOAD": "LOAD httpfs",
        "DYN-WRITE": "SELECT 1; DROP TABLE fact_refresh_status",
    }
    for vec, sql in battery.items():
        try:
            mcp.guarded_query(con, sql)
            raise AssertionError(f"G9.11: {vec} NOT refused by guarded_query")
        except mcp.BoundaryError:
            pass
    con.close()
    assert not evil_csv.exists() and not evil_db.exists(), "G9.11: battery touched disk"
    out.append(f"IN-PROCESS control-integrity check, CARRIED FROM THE STDIO GATE (G9.1 write-battery; "
               f"the G9.11 text's 'G9.6' ref), NOT an HTTP test and NOT counted in the tally: "
               f"guarded_query refuses all {len(battery)} vectors as statement text before DuckDB")
    return out


# ---- G9.12 ------------------------------------------------------------------------------------
def g9_12(base) -> list:
    out = []
    # schema present over HTTP: every emitted numeric carries a valid interval_type + non-empty estimand
    # (unless NONE), and NO ci_* key appears anywhere.
    for _, name, args in PARITY_SET:
        payload = _call(base, name, args).json()["result"]["structuredContent"]
        for e in _emit_dicts(payload):
            assert e["interval_type"] in INTERVAL_ENUM, f"G9.12: bad interval_type in {name}"
            if e["interval_type"] != "NONE":
                assert e.get("estimand"), f"G9.12: non-NONE interval with empty estimand in {name}"
        assert not _has_ci_key(payload), f"G9.12: a ci_* key leaked over HTTP in {name}"
    out.append("over HTTP: interval_type ∈ enum + non-empty estimand (non-NONE); no ci_* key anywhere")
    # "omit each in turn" → response construction hard-fails, surfaced over HTTP (not a silent success)
    # (a) blank the estimand of a served, non-NONE fact → hard_fail
    def blank_estimand(b):
        for f in b["mcp_facts"]:
            if f["key"] == "archetype_gap":
                f["estimand"] = ""
    with mutate_json(BUNDLE, blank_estimand):
        r = _call(base, "archetype_gap").json()["result"]
        assert r["isError"] and "hard_fail" in r["structuredContent"], \
            f"G9.12: empty estimand did not hard-fail over HTTP ({r['structuredContent']})"
    out.append("omit estimand (non-NONE) → hard_fail surfaced over HTTP")
    # (b) remove interval_type entirely → hard_fail
    def drop_it(b):
        for f in b["mcp_facts"]:
            if f["key"] == "archetype_gap":
                f.pop("interval_type", None)
    with mutate_json(BUNDLE, drop_it):
        r = _call(base, "archetype_gap").json()["result"]
        assert r["isError"] and "hard_fail" in r["structuredContent"], \
            "G9.12: missing interval_type did not hard-fail over HTTP"
    out.append("omit interval_type → hard_fail surfaced over HTTP")
    # restored → healthy again
    assert not _call(base, "archetype_gap").json()["result"]["isError"], "G9.12: state not restored"
    return out


def _has_ci_key(o) -> bool:
    if isinstance(o, dict):
        return any(k.startswith("ci_") for k in o) or any(_has_ci_key(v) for v in o.values())
    if isinstance(o, list):
        return any(_has_ci_key(v) for v in o)
    return False


# ---- G9.13 ------------------------------------------------------------------------------------
def g9_13(base) -> list:
    out = []
    payload = _call(base, "trade_delta").json()["result"]["structuredContent"]["result"]
    for pool in ("corpus", "consensus"):
        assert pool in payload, f"G9.13: trade over HTTP missing the {pool} pool (single-headline path)"
        p = payload[pool]
        assert p["interval_lo"] is not None and p["interval_hi"] is not None, f"G9.13: {pool} lacks interval"
        assert p["interval_type"] == "MC_PRECISION_BAND", f"G9.13: {pool} interval_type != MC_PRECISION_BAND"
    # the natural-language trade route ALSO returns both pools (no single-verdict path anywhere)
    nl = _call(base, "answer", {"question": "is this trade good?"}).json()["result"]["structuredContent"]
    both = nl["result"]["response"]
    assert "corpus" in both and "consensus" in both, "G9.13: NL trade route dropped a pool"
    out.append(f"trade over HTTP returns BOTH pools with MC_PRECISION_BAND intervals "
               f"(corpus {payload['corpus']['point']}, consensus {payload['consensus']['point']})")
    out.append("natural-language trade route also returns both pools (no single-headline path)")
    return out


# ---- G9.14 (NON-BLOCKING) ---------------------------------------------------------------------
def g9_14(base) -> list:
    out = []
    reference = h.canonical(mcp.handle({"tool": "trade_delta"}))
    errors: list[str] = []

    def one(i):
        try:
            r = _call(base, "trade_delta", {}, rid=i)
            body = r.json()["result"]["structuredContent"]
            return h.canonical(body) == reference
        except Exception as e:  # noqa: BLE001
            errors.append(f"{type(e).__name__}: {e}")
            return False

    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(one, range(24)))
    ok = sum(1 for x in results if x)
    # NON-BLOCKING: we DOCUMENT the observed behavior; we do not assert safety a priori.
    if ok == len(results) and not errors:
        out.append(f"DOCUMENTED: {ok}/{len(results)} concurrent HTTP trade sessions succeeded, all "
                   "payload-identical. Observed behavior: the threading server opens a SEPARATE "
                   "short-lived read_only DuckDB connection per request; concurrent READ-ONLY access "
                   "to the single warehouse file succeeded in-process here. This is the OBSERVED "
                   "result under 8-way concurrency, NOT a proof of safety at higher concurrency or "
                   "across processes; DuckDB single-file multi-connection semantics beyond read-only "
                   "readers are treated as UNDEFINED and out of scope (see amendment).")
    else:
        out.append(f"DOCUMENTED (NON-BLOCKING): {ok}/{len(results)} concurrent sessions payload-identical; "
                   f"errors={errors[:3]}. Recorded as observed, not asserted safe.")
    return out


# ---- runner -----------------------------------------------------------------------------------
GATES = [("G9.9 transport parity", "srv_cap"), ("G9.10 auth (log-confirmed)", "srv_cap"),
         ("G9.11 write battery over HTTP", "srv"), ("G9.12 schema enforcement survives", "srv"),
         ("G9.13 dual-pool intact", "srv"), ("G9.14 concurrency (non-blocking, documented)", "srv")]


def run() -> None:
    pre = {p: p.read_bytes() for p in (BUNDLE, DRIFT)}   # mutation tests must restore these byte-for-byte
    cap = _Capture()
    h.LOG.addHandler(cap)
    h.LOG.setLevel(logging.INFO)
    h.LOG.propagate = False
    srv = h.make_server("127.0.0.1", 0, token=TOKEN)
    base = f"http://127.0.0.1:{srv.server_address[1]}/mcp"
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()

    # R1: G9.9 is WIRING-VERIFIED, not a falsifiable parity test — it does NOT count toward the
    # test-backed tally. The 5 test-backed criteria are G9.10–G9.14.
    plan = [("G9.9 wiring-verified (NOT parity-tested)", lambda: g9_9(base), False),
            ("G9.10 auth (log-confirmed)", lambda: g9_10(base, cap), True),
            ("G9.11 write battery LIVE over HTTP", lambda: g9_11(base), True),
            ("G9.12 schema enforcement survives", lambda: g9_12(base), True),
            ("G9.13 dual-pool intact", lambda: g9_13(base), True),
            ("G9.14 concurrency (non-blocking, documented)", lambda: g9_14(base), True)]
    fails = 0
    test_backed_pass = 0
    wiring_ok = True
    try:
        for name, fn, test_backed in plan:
            try:
                for detail in fn():
                    print(f"  [{'PASS' if test_backed else 'WIRED'}] {name}: {detail}")
                if test_backed:
                    test_backed_pass += 1
            except Exception as e:  # noqa: BLE001
                fails += 1
                wiring_ok = wiring_ok and test_backed
                print(f"  [FAIL] {name}: {type(e).__name__}: {e}")
    finally:
        srv.shutdown()
        h.LOG.removeHandler(cap)
    residue = [p.name for p, b in pre.items() if p.read_bytes() != b]
    print(f"\nmutation tests restored all sources byte-for-byte: "
          f"{'YES' if not residue else 'NO — ' + ', '.join(residue)}")
    if residue:
        fails += 1
    print(f"\nGATE 9 (HTTP extension) — SHELVED, NOT DEPLOYED (auth is org-admin-only; see "
          "PHASE9_PLAN.md OUTCOME 2026-08-02).")
    print(f"  {test_backed_pass}/5 test-backed criteria PASS (G9.10–G9.14); "
          f"G9.9 {'WIRING-VERIFIED' if wiring_ok else 'WIRING BROKEN'}, NOT PARITY-TESTED "
          "(EXACT_CI stratum UNINFORMATIVE).")
    print("  G9.11 note: test-backed by its LIVE-HTTP portion only (5 vectors + no-SQL-sink finding); "
          "its guarded_query allowlist portion is IN-PROCESS, carried from the stdio gate, NOT counted.")
    print("  G9.11 FINDING: the HTTP surface exposes no SQL sink → the write vector is unreachable by "
          "construction over HTTP (stronger than a passing allowlist test).")
    print(f"  Result: {'OK' if not fails else 'FAIL'}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    run()
