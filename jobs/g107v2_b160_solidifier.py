import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
import numpy as np
import models.startup_backtester as BT
NON_MODEL = [s for s in BT.STRATEGIES if s not in BT.MODEL_STRATS]
Bc = 160; BSc = BT.BT.get("corr_boot_sims", 40)
p = 0.116
los, his = [], []
for sd in range(5):
    rng = np.random.default_rng(sd)
    W, _ = BT._joint_boot(2020, NON_MODEL, Bc, BSc, rng, unit="league")
    d = np.asarray(W["youth"]) - np.asarray(W["balanced_adp"])
    los.append(float(np.percentile(d, 2.5))); his.append(float(np.percentile(d, 97.5)))
    print(f"seed {sd}: L0={los[-1]:+.4f} hi={his[-1]:+.4f}", flush=True)
los = np.array(los); his = np.array(his)
L0 = los.mean(); spread = los.max() - los.min(); HW = 0.140
print(f"B={Bc} sims_each={BSc}")
print(f"L0(mean)={L0:+.4f} spread={spread:.4f}={100*spread/HW:.1f}%HW (conv_frac 10%)")
print(f"upper(mean)={his.mean():+.4f} spread={his.max()-his.min():.4f}={100*(his.max()-his.min())/HW:.1f}%HW")
ds = lambda l: (p/(p-l))**2 if (p-l)!=0 else float('inf')
print(f"deff* at L0={L0:+.4f}: {ds(L0):.3f}")
print(f"deff* interval [{ds(L0-spread):.3f} (L0-spread {L0-spread:+.4f}), {ds(L0+spread):.3f} (L0+spread {L0+spread:+.4f})]")
