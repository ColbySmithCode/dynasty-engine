"""Trade E[Δ] 200-seed MC producer + persisted distribution artifact + cross-process byte-check.

The canon `trade_verdict` E[Δ] (corpus/consensus mean + CI) had NO producer in the repo or its
history — it was hand-typed. This DEFINES the canonical 200-seed distribution (seed protocol:
numpy default_rng(s) for s in range(200), delta=0.82, on the deterministic warehouse), PERSISTS the
full distribution (all 200 seed values + mean/sd/CI) to models/trade_mc200.json, and byte-checks that
artifact across N fresh processes — the same bar that marked G10.4. This is a NEW DEFINITION, not a
recovery of -76.1.
"""
import hashlib
import json
import os
import subprocess
from pathlib import Path

import numpy as np

from config import CONFIG

SEEDS = list(range(200))
DELTA = 0.82
ART = CONFIG.path("models") / "trade_mc200.json"


def _dist(pool, rookie, te):
    vals = []
    for s in SEEDS:
        te.RNG = np.random.default_rng(s)
        r = te.evaluate(DELTA, pool, rookie)
        vals.append(float(r["B"].mean() - r["A"].mean()))
    a = np.array(vals)
    lo, hi = (float(x) for x in np.percentile(a, [2.5, 97.5]))
    return {"mean": float(a.mean()), "sd": float(a.std(ddof=1)),
            "ci_lo": lo, "ci_hi": hi,
            "sign_neg": int((a < 0).sum()), "sign_pos": int((a > 0).sum()),
            "values": vals}


def regenerate() -> dict:
    """Rebuild the deterministic warehouse in THIS process, compute + persist the 200-seed
    distribution for both pools. Deterministic → byte-identical across fresh processes."""
    import contextlib
    import io
    from transform import warehouse, metrics
    with contextlib.redirect_stdout(io.StringIO()):
        warehouse.run()
        metrics.run()
    import importlib
    import engine.trade_engine as te
    importlib.reload(te)
    consensus, corpus, rookie = te._pools()
    art = {
        "_what": "trade E[Δ] 200-seed MC distribution (NEW DEFINITION; -76.1/+8.6 had no producer).",
        "seed_protocol": "numpy.random.default_rng(s) for s in range(200)",
        "delta": DELTA,
        "corpus": _dist(corpus, rookie, te),
        "consensus": _dist(consensus, rookie, te),
    }
    ART.write_text(json.dumps(art, indent=2, sort_keys=True))
    return art


def _worker():
    art = regenerate()
    blob = json.dumps(art, sort_keys=True).encode()
    print("ARThash=%s corpus_mean=%r corpus_ci=(%r,%r) cons_mean=%r cons_ci=(%r,%r)" % (
        hashlib.sha256(blob).hexdigest()[:16],
        art["corpus"]["mean"], art["corpus"]["ci_lo"], art["corpus"]["ci_hi"],
        art["consensus"]["mean"], art["consensus"]["ci_lo"], art["consensus"]["ci_hi"]))


def bytecheck(n=5):
    root = str(Path(__file__).resolve().parent.parent)
    env = dict(os.environ, PATH=os.path.expanduser("~/.local/bin") + ":" + os.environ.get("PATH", ""))
    out = []
    for i in range(n):
        r = subprocess.run(["uv", "run", "python", "-c",
                            "from jobs.g104_trade200 import _worker as w; w()"],
                           cwd=root, env=env, capture_output=True, text=True)
        line = [l for l in r.stdout.splitlines() if l.startswith("ARThash=")]
        if not line:
            print(f"process {i} FAILED\n{r.stderr[-1200:]}")
            return
        out.append(line[0])
        print(f"process {i}: {line[0]}")
    print("=" * 60)
    print(f"FULL-DISTRIBUTION artifact byte-identical across {n} processes: "
          f"{'YES' if len(set(out)) == 1 else 'NO'}")


if __name__ == "__main__":
    bytecheck()
