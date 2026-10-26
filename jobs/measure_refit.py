"""Phase 7 item 3 — quantify REFIT SPREAD of the three established results under the CURRENT
(nondeterministic) code, BEFORE the determinism fix lands (after, the measurement is impossible).

Each measurement is a FRESH PROCESS (RNG re-seeds to 1729 identically, so any variation is the
unordered-read nondeterminism, not RNG-advance). Reports the distribution of:
  - trade engine per-pool E[Δ] at δ=0.82 (the −74/+6 flip)
  - archetype model AUC and (model − capital-only) gap (the 0.014 gap)
  - college 5.4B minimum permutation p across strata (the "all p ≥ 0.11" null)

Usage:
  worker (one fresh run, prints one JSON line):  python -m jobs.measure_refit --worker {trade|archetype|college}
  orchestrate N runs and summarize:              python -m jobs.measure_refit --n 20
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CONFIG


def _worker(target: str) -> None:
    if target == "trade":
        from engine import trade_engine
        trade_engine.run()
        d = json.loads((CONFIG.path("exports") / "trade_verdict.json").read_text())
        print(json.dumps({"consensus": d["consensus"]["e_delta_082"], "corpus": d["corpus"]["e_delta_082"],
                          "cons_win": d["consensus"]["winner"], "corp_win": d["corpus"]["winner"]}))
    elif target == "archetype":
        from models import archetypes
        L = archetypes.supervised(archetypes._frame())
        txt = "\n".join(L)
        am = float(re.search(r"Model \(HistGB\): AUC (\d\.\d+)", txt).group(1))
        ab = float(re.search(r"Draft-capital-only \(ln ovr\): AUC (\d\.\d+)", txt).group(1))
        print(json.dumps({"auc_model": am, "auc_capital": ab, "gap": round(am - ab, 4)}))
    elif target == "college":
        import io, contextlib
        from models import cfb_5_4b
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cfb_5_4b.run()
        ps = [float(x) for x in re.findall(r"perm_p=(\d\.\d+)", buf.getvalue())]
        print(json.dumps({"min_p": min(ps) if ps else None, "n_strata": len(ps),
                          "n_below_05": sum(1 for p in ps if p < 0.05)}))


def _orchestrate(n: int, targets: list) -> None:
    env = dict(os.environ, PATH=os.path.expanduser("~/.local/bin") + ":" + os.environ.get("PATH", ""))
    root = str(Path(__file__).resolve().parent.parent)
    import numpy as np
    for target in targets:
        vals = []
        for i in range(n):
            r = subprocess.run(["uv", "run", "python", "-m", "jobs.measure_refit", "--worker", target],
                               cwd=root, env=env, capture_output=True, text=True)
            line = [l for l in r.stdout.strip().splitlines() if l.startswith("{")]
            if line:
                vals.append(json.loads(line[-1]))
            else:
                print(f"  [{target} {i}] no output: {r.stderr.strip()[-200:]}")
        print(f"\n===== {target}: {len(vals)}/{n} fresh-process runs =====")
        if not vals:
            continue
        keys = [k for k in vals[0] if isinstance(vals[0][k], (int, float))]
        for k in keys:
            arr = np.array([v[k] for v in vals], dtype=float)
            print(f"  {k:14} min {arr.min():+.4f}  max {arr.max():+.4f}  mean {arr.mean():+.4f}  "
                  f"sd {arr.std():.4f}  range {arr.max()-arr.min():.4f}")
        # categorical winners / crossings
        for k in vals[0]:
            if isinstance(vals[0][k], str):
                from collections import Counter
                print(f"  {k:14} {dict(Counter(v[k] for v in vals))}")
        if target == "trade":
            cross = sum(1 for v in vals if (v["corpus"] >= 0) != (vals[0]["corpus"] >= 0))
            print(f"  >>> corpus-pool sign crossings vs first run: {cross}/{len(vals)}")
        if target == "archetype":
            gaps = np.array([v["gap"] for v in vals])
            print(f"  >>> archetype gap crosses zero (model beats capital in some runs): "
                  f"{(gaps > 0).any()} (max gap {gaps.max():+.4f}, min {gaps.min():+.4f})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--worker", choices=["trade", "archetype", "college"])
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--targets", default="trade,archetype,college")
    a = ap.parse_args()
    if a.worker:
        _worker(a.worker)
    else:
        _orchestrate(a.n, a.targets.split(","))


if __name__ == "__main__":
    main()
