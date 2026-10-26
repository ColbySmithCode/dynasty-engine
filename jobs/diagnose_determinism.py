"""Phase 7 item 1 — diagnose WHICH mechanism makes the model refits nondeterministic, before/after
the ORDER BY fix. Runs the refit twice (fresh processes) under each control and reports whether the
artifact bytes match: (a) DuckDB threads=1; (b) pinned PYTHONHASHSEED; (c) single-thread BLAS.
    uv run python -m jobs.diagnose_determinism            # run the matrix
    uv run python -m jobs.diagnose_determinism --worker   # one refit, prints artifact hashes
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CONFIG

ART = ["aging_curves.parquet", "survival_clockA.parquet", "cox_age_capital.csv", "aging_deltas.parquet"]


def _worker() -> None:
    if os.environ.get("DUCKDB_SINGLE") == "1":
        import duckdb
        _orig = duckdb.connect
        def _c(*a, **k):
            con = _orig(*a, **k)
            try:
                con.execute("SET threads TO 1")
            except Exception:
                pass
            return con
        duckdb.connect = _c
    import contextlib, io
    from models import aging_curves, survival, survival_cox
    with contextlib.redirect_stdout(io.StringIO()):
        aging_curves.build(); survival.build(); survival_cox.run()
    md = CONFIG.path("models")
    print(json.dumps({a: hashlib.sha256((md / a).read_bytes()).hexdigest()[:12] for a in ART}))


def _run(env_extra: dict) -> dict:
    env = dict(os.environ, PATH=os.path.expanduser("~/.local/bin") + ":" + os.environ.get("PATH", ""),
               **env_extra)
    r = subprocess.run(["uv", "run", "python", "-m", "jobs.diagnose_determinism", "--worker"],
                       cwd=str(Path(__file__).resolve().parent.parent), env=env, capture_output=True, text=True)
    line = [l for l in r.stdout.strip().splitlines() if l.startswith("{")]
    return json.loads(line[-1]) if line else {"_err": r.stderr[-200:]}


def _matrix() -> None:
    BLAS = {k: "1" for k in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                             "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS")}
    configs = {
        "baseline": {},
        "PYTHONHASHSEED=0": {"PYTHONHASHSEED": "0"},
        "BLAS=1": BLAS,
        "duckdb_threads=1": {"DUCKDB_SINGLE": "1"},
        "ALL (hashseed+blas+duckdb1)": {"PYTHONHASHSEED": "0", "DUCKDB_SINGLE": "1", **BLAS},
    }
    print(f"{'config':30} {'match?':7} artifacts that DIFFER across 2 fresh runs")
    print("-" * 90)
    for name, env in configs.items():
        h1 = _run(env); h2 = _run(env)
        diff = [a for a in ART if h1.get(a) != h2.get(a)]
        print(f"{name:30} {'YES' if not diff else 'no':7} {diff}")
    subprocess.run(["git", "checkout", "HEAD", "--", *[f"models/{a}" for a in ART]],
                   cwd=str(Path(__file__).resolve().parent.parent))
    print("(restored git artifacts)")


if __name__ == "__main__":
    if "--worker" in sys.argv:
        _worker()
    else:
        _matrix()
