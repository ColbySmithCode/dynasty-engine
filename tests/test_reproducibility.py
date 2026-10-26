"""Phase 7 items 1&2 — verify the determinism fix: 5 INDEPENDENT fresh-process refits must produce
BYTE-IDENTICAL artifacts (to each other). This is the determinism criterion; the separate
comparison to git HEAD (data-vintage / upstream revision) is reported by jobs.repro_check.
    uv run python -m tests.test_reproducibility            # run N=5 cross-process
    uv run python -m tests.test_reproducibility --worker   # one refit -> prints artifact hashes
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

# Phase-5 refit artifacts (mutated by the refit; git-restored after) + the 5.4B WY artifact
# (deterministic, brought into the harness Gate-8 3rd review; regenerated, not git-restored).
REFIT_ART = ["aging_curves.parquet", "aging_deltas.parquet", "survival_clockA.parquet",
             "survival_clockB.parquet", "survival_curves.parquet", "cox_age_only.csv",
             "cox_age_capital.csv"]
CFB_ART = ["cfb_5_4b_perm.json", "archetype_gap.json"]   # pinned model artifacts (deterministic)
G103_ART = ["calibration_g103.json"]                     # G10.3 calibration diagnostics (deterministic)
ART = REFIT_ART + CFB_ART + G103_ART
N = 5


def _worker() -> None:
    import contextlib, io
    from models import aging_curves, survival, survival_cox, cfb_5_4b, calibration_check
    from jobs import measure_sampling_variance as msv
    with contextlib.redirect_stdout(io.StringIO()):
        aging_curves.build(); survival.build(); survival_cox.run()
        cfb_5_4b.write_perm_artifact()          # pins models/cfb_5_4b_perm.json (WY joint null)
        msv.write_archetype_gap_artifact()      # pins models/archetype_gap.json (full-precision gap)
        calibration_check.regenerate(quiet=True)  # pins models/calibration_g103.json (G10.3)
    md = CONFIG.path("models")
    print(json.dumps({a: hashlib.sha256((md / a).read_bytes()).hexdigest()[:16] for a in ART}))


def run() -> None:
    env = dict(os.environ, PATH=os.path.expanduser("~/.local/bin") + ":" + os.environ.get("PATH", ""))
    root = str(Path(__file__).resolve().parent.parent)
    runs = []
    for i in range(N):
        r = subprocess.run(["uv", "run", "python", "-m", "tests.test_reproducibility", "--worker"],
                           cwd=root, env=env, capture_output=True, text=True)
        line = [l for l in r.stdout.strip().splitlines() if l.startswith("{")]
        if not line:
            print(f"run {i} FAILED: {r.stderr[-300:]}"); sys.exit(1)
        runs.append(json.loads(line[-1]))
    print(f"{'artifact':26} match across {N} fresh processes?")
    print("-" * 50)
    fails = []
    for a in ART:
        vals = {r[a] for r in runs}
        ok = len(vals) == 1
        if not ok:
            fails.append(a)
        print(f"{a:26} {'YES' if ok else 'NO — ' + str(sorted(vals))}")
    subprocess.run(["git", "checkout", "HEAD", "--", *[f"models/{a}" for a in REFIT_ART]], cwd=root)
    print("(restored git artifacts; cfb_5_4b_perm.json is deterministic and left regenerated)")
    if fails:
        print(f"FAIL: {fails} still differ across cross-process refits"); sys.exit(1)
    print(f"PASS: all {len(ART)} artifacts byte-identical across {N} cross-process refits.")


if __name__ == "__main__":
    if "--worker" in sys.argv:
        _worker()
    else:
        run()
