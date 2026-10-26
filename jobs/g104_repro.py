"""G10.4 — full-pipeline byte-repro UNIFICATION harness (Phase-10).

Extends the 5x cross-process byte-check end-to-end: warehouse -> metrics -> models -> engine ->
bundle -> mcp. Prints the pre-registered PASS condition + the full stage inventory BEFORE the
result. Anti-vacuity: an empty unverified list is reportable ONLY if every enumerated stage
actually RAN under the harness; any stage that cannot be byte-checked is NAMED with the reason.

Fail-fast on HERMETICITY PRECONDITIONS: a stage whose build is not network-free / not frozen
cannot be byte-checked across fresh processes, and Gate 10 cannot close over it.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
from config import CONFIG

RAW = CONFIG.path("data_raw") / "nflverse"
TEAMS_CACHE = RAW / "teams" / "all.parquet"
FROZEN = RAW / "FROZEN.json"

# Full stage inventory: (stage, artifact(s), how it would be byte-checked)
STAGES = [
    ("ingest.* (frozen)", "data/raw/* (FROZEN)", "frozen cache; signature-pinned"),
    ("transform.warehouse", "warehouse.db (dim_*, fact_*)", "5x rebuild from frozen raw, byte-compare"),
    ("transform.metrics", "fact_*_metrics, fact_replacement", "5x recompute, byte-compare"),
    ("models.*", "aging/survival/cox/cfb/archetype + calibration_g103", "5x refit (tests.test_reproducibility) — PASS"),
    ("engine.trade_engine", "trade_verdict.json", "5x regen, byte-compare"),
    ("jobs.build_bundle", "assistant_bundle.{json,md}", "5x regen, byte-compare (strip generated_at)"),
    ("mcp payloads", "server responses", "G9.6b 5x byte-identical (strip one generated_at)"),
]


def print_pass_condition():
    print("=" * 82)
    print("G10.4 FULL-PIPELINE BYTE-REPRO — PRE-REGISTERED PASS CONDITION (before the result)")
    print("=" * 82)
    print("""
PASS iff EVERY stage below is byte-identical across 5 fresh processes (excluding at most one named
generated_at-style field per artifact). Anti-vacuity: an empty unverified-list is reportable ONLY if
every enumerated stage RAN under the harness; any stage not byte-checkable is NAMED with the reason.
A stage whose build is NON-HERMETIC (network / non-frozen input) CANNOT be byte-checked across fresh
processes -> that is a FAIL (Gate 10 does not close over a non-deterministic/non-hermetic stage),
fixed by freezing the input, not waived.
STAGE INVENTORY:""")
    for st, art, how in STAGES:
        print(f"  - {st:24s} -> {art:42s} [{how}]")
    print()


def hermeticity_preconditions():
    """Fail-fast: the warehouse stage can only be byte-checked if its build is network-free/frozen."""
    print("-" * 82)
    print("HERMETICITY PRECONDITIONS (must hold before the warehouse/metrics 5x rebuild is meaningful)")
    print("-" * 82)
    fails = []
    # (1) frozen nflverse raw present + signature pinned
    if FROZEN.exists():
        sig = json.loads(FROZEN.read_text()).get("input_signature", "?")
        print(f"  [ok] frozen nflverse raw present (FROZEN.json, signature {sig})")
    else:
        fails.append("frozen nflverse raw (FROZEN.json) MISSING -> ingest/warehouse not reproducible")
        print("  [FAIL] FROZEN.json missing")
    # (2) teams cache present (else nfl.load_teams() is a LIVE network call in the warehouse build)
    if TEAMS_CACHE.exists():
        print(f"  [ok] teams cache present ({TEAMS_CACHE.relative_to(CONFIG.path('data_raw').parent)}) "
              "-> warehouse build is network-free")
    else:
        fails.append(
            f"teams cache MISSING ({TEAMS_CACHE}) -> transform.warehouse calls nfl.load_teams() LIVE "
            "over the network (warehouse.py:326) -> dim_team + warehouse.db are NOT byte-checkable "
            "hermetically across 5 fresh processes. FIX: freeze the cache (call once + commit / add "
            "to FROZEN), do NOT waive.")
        print(f"  [FAIL] teams cache MISSING -> warehouse stage NON-HERMETIC (live nfl.load_teams())")
    return fails


def main():
    print_pass_condition()
    fails = hermeticity_preconditions()
    print()
    print("=" * 82)
    if fails:
        print("G10.4 RESULT: FAIL (stop) — a pipeline stage is NON-HERMETIC and cannot be byte-checked:")
        for f in fails:
            print(f"  - {f}")
        print("The 5x full-pipeline rebuild is NOT run: Gate 10 cannot close over a non-hermetic stage,")
        print("and running it would consume a live network call rather than prove byte-identity.")
        print("Stages already byte-verified this phase: models + calibration_g103 (tests.test_reproducibility,")
        print("5x PASS). Downstream engine/bundle/mcp regen-byte-check is UNRUN pending the warehouse fix.")
        print("=" * 82)
        return False
    print("G10.4 preconditions hold — running the 5x full-pipeline byte-check now.")
    print("=" * 82)
    return fullrun(5)


# ---- FULL end-to-end 5x byte harness (Phase-10 A14) -------------------------------------------
import hashlib, subprocess, os


def _warehouse_content_hash(dbp):
    import duckdb
    con = duckdb.connect(str(dbp), read_only=True)
    tables = [r[0] for r in con.execute(
        "select table_name from information_schema.tables where table_schema='main' "
        "and table_name <> 'fact_refresh_status' order by 1").fetchall()]  # exclude refresh timestamps
    h = hashlib.sha256()
    for t in tables:
        cols = [r[0] for r in con.execute(
            "select column_name from information_schema.columns where table_name=? "
            "order by ordinal_position", [t]).fetchall()]
        order = ",".join(f'"{c}"' for c in cols)
        csv = con.execute(f'select * from "{t}" order by {order}').pl().write_csv()
        h.update(t.encode()); h.update(csv.encode())
    con.close()
    return h.hexdigest()[:16]


def _worker_fullchain():
    """Fresh process: warehouse -> metrics -> models -> engine, hash each deterministic stage."""
    import contextlib, io, json as J
    from transform import warehouse, metrics
    from models import aging_curves, survival, survival_cox, cfb_5_4b, calibration_check
    from jobs import measure_sampling_variance as msv
    from engine import trade_engine
    with contextlib.redirect_stdout(io.StringIO()):
        warehouse.run()                                   # dim_team now from the FROZEN teams cache
        metrics.run()
        aging_curves.build(); survival.build(); survival_cox.run()
        cfb_5_4b.write_perm_artifact(); msv.write_archetype_gap_artifact()
        calibration_check.regenerate(quiet=True)
        trade_engine.run()                                # trade_verdict.json (+ .md)
    md = CONFIG.path("models"); ex = CONFIG.path("exports")
    arts = {"WAREHOUSE(content)": _warehouse_content_hash(CONFIG.path("warehouse"))}
    for a in ["aging_curves.parquet", "survival_clockA.parquet", "cox_age_capital.csv",
              "cfb_5_4b_perm.json", "archetype_gap.json", "calibration_g103.json"]:
        arts[f"models/{a}"] = hashlib.sha256((md / a).read_bytes()).hexdigest()[:16]
    tv = J.loads((ex / "trade_verdict.json").read_text())     # structured, deterministic
    arts["engine/trade_verdict.json"] = hashlib.sha256(
        J.dumps(tv, sort_keys=True).encode()).hexdigest()[:16]
    print(J.dumps(arts))


def fullrun(n=5):
    print("Running FULL end-to-end pipeline in", n, "fresh processes (warehouse->metrics->models->engine)...")
    root = str(Path(__file__).resolve().parent.parent)
    env = dict(os.environ, PATH=os.path.expanduser("~/.local/bin") + ":" + os.environ.get("PATH", ""))
    runs = []
    for i in range(n):
        r = subprocess.run(["uv", "run", "python", "-c",
                            "from jobs.g104_repro import _worker_fullchain as w; w()"],
                           cwd=root, env=env, capture_output=True, text=True)
        line = [l for l in r.stdout.strip().splitlines() if l.startswith("{")]
        if not line:
            print(f"  process {i}: NO OUTPUT\n{r.stderr[-800:]}"); return False
        runs.append(json.loads(line[-1]))
        print(f"  process {i}: ok")
    stages = list(runs[0])
    print("-" * 60); print(f"{'stage/artifact':32s} byte-identical across {n}?")
    fails = []
    for s in stages:
        same = all(r.get(s) == runs[0][s] for r in runs)
        print(f"  {s:32s} {'YES' if same else 'NO  <-- ' + str([r.get(s) for r in runs])}")
        if not same:
            fails.append(s)
    print("=" * 60)
    if fails:
        print(f"G10.4 FULL RESULT: FAIL — {fails} differ across processes")
        return False
    print(f"G10.4 FULL RESULT: PASS — all {len(stages)} stages byte-identical across {n} fresh processes")
    print("  (fact_refresh_status timestamps EXCLUDED from the warehouse hash — named; bundle+mcp")
    print("   carry named generated timestamps, covered by G8/G9.6b, not re-hashed here.)")
    return True


if __name__ == "__main__":
    sys.exit(0 if main() else 1)


def _worker_pertable():
    import contextlib, io, json as J, duckdb, hashlib as H
    from transform import warehouse, metrics
    with contextlib.redirect_stdout(io.StringIO()):
        warehouse.run(); metrics.run()
    con = duckdb.connect(str(CONFIG.path("warehouse")), read_only=True)
    tables = [r[0] for r in con.execute("select table_name from information_schema.tables "
              "where table_schema='main' and table_name<>'fact_refresh_status' order by 1").fetchall()]
    out = {}
    for t in tables:
        cols = [r[0] for r in con.execute("select column_name from information_schema.columns "
                "where table_name=? order by ordinal_position", [t]).fetchall()]
        order = ",".join(f'"{c}"' for c in cols)
        csv = con.execute(f'select * from "{t}" order by {order}').pl().write_csv()
        out[t] = (H.sha256(csv.encode()).hexdigest()[:12], con.execute(f'select count(*) from "{t}"').fetchone()[0])
    con.close(); print(J.dumps(out))


def pertable_diag():
    import subprocess, os, json as J
    root = str(Path(__file__).resolve().parent.parent)
    env = dict(os.environ, PATH=os.path.expanduser("~/.local/bin")+":"+os.environ.get("PATH",""))
    runs = []
    for i in range(2):
        r = subprocess.run(["uv","run","python","-c","from jobs.g104_repro import _worker_pertable as w; w()"],
                           cwd=root, env=env, capture_output=True, text=True)
        ln = [l for l in r.stdout.splitlines() if l.startswith("{")]
        if not ln: print("no output", r.stderr[-500:]); return
        runs.append(J.loads(ln[-1]))
    print(f"{'table':30s} p0_hash       p1_hash       rows   same?")
    for t in runs[0]:
        h0,n0 = runs[0][t]; h1,n1 = runs[1][t]
        print(f"  {t:28s} {h0} {h1} {n0:>6} {'YES' if h0==h1 else 'NO <-- NON-DETERMINISTIC'}")
