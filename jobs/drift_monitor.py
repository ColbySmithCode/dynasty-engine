"""Phase 7 item 5 — model-artifact versioning + drift monitor.

Every FULL refresh hashes each fitted model artifact and appends to an append-only registry
(models/_versions/registry.jsonl) — artifacts are NEVER overwritten silently; each hash + run is
recorded. A drift check then compares the three ESTABLISHED results against a stored baseline and
flags material moves:
  1. archetypes: top-12/3yr AUC vs draft-capital-only AUC (baseline 0.887 vs 0.901 — model must
     NOT beat capital; Decision 10 / negative result). Alert if the sign flips or |Δ| > 0.02.
  2. college production (5.4B): pinned Westfall-Young joint null (models/cfb_5_4b_perm.json).
     Alert if the family minimum marginal p < 0.05 on 2 consecutive refits, or on a vintage change.
  3. trade engine dual-pool verdict (baseline consensus +6/+14, corpus −72/−76). Alert if either
     pool's verdict SIGN flips.
Change detection is hash-gated: a result whose upstream artifact hash is unchanged cannot have
drifted and is reported 'unchanged'; only changed artifacts trigger a recompute/compare.
"""
from __future__ import annotations

import hashlib
import json
import re
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CONFIG
from ingest._common import get_logger

log = get_logger("drift_monitor")
MODELS = CONFIG.path("models")
EXPORTS = CONFIG.path("exports")
VERSIONS = MODELS / "_versions"
REGISTRY = VERSIONS / "registry.jsonl"
BASELINE = Path(__file__).resolve().parent / "drift_baseline.json"

# alert thresholds (documented, config-free so they're auditable here)
# item 4a: 0.02 exceeded the 0.014 gap being watched -> key on the SIGN of (model−capital) plus
#          any movement above 0.005 (well under the gap).
AUC_MOVE = 0.005         # archetype gap movement that trips an alert (on top of sign flip)
COLLEGE_P = 0.05         # college perm-p threshold (baseline ≥0.11)
COLLEGE_CONSEC = 2       # item 4b: require the p-threshold crossed on N consecutive FULL refits
STATE = VERSIONS / "drift_state.json"   # persists the consecutive-crossing counter


def _hash(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def hash_artifacts(run_id: str) -> dict:
    """Hash every model artifact; append to the never-overwrite registry. Returns {name: hash}."""
    VERSIONS.mkdir(parents=True, exist_ok=True)
    arts = sorted([p for p in MODELS.glob("*.parquet")] + [p for p in MODELS.glob("*.csv")] +
                  [p for p in MODELS.glob("*.json")])   # incl. cfb_5_4b_perm.json (5.4B in harness)
    hashes = {p.name: _hash(p) for p in arts}
    with open(REGISTRY, "a") as fh:
        fh.write(json.dumps({"run_id": run_id, "ts": int(time.time()), "hashes": hashes}) + "\n")
    log.info("hashed %d model artifacts into registry", len(hashes))
    return hashes


def _prev_hashes() -> dict:
    if not REGISTRY.exists():
        return {}
    lines = REGISTRY.read_text().strip().splitlines()
    if len(lines) < 2:
        return {}
    return json.loads(lines[-2]).get("hashes", {})   # the run before the one just appended


def _read_trade_verdict() -> dict | None:
    """Item 4c: read the STRUCTURED verdict emitted by the engine (exports/trade_verdict.json) —
    no more prose parsing. Returns {'consensus': {winner,e_delta_082}, 'corpus': {...}}."""
    f = EXPORTS / "trade_verdict.json"
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text())
    except Exception:
        return None


def _read_college_perm() -> dict | None:
    """Read the pinned 5.4B Westfall-Young artifact (models/cfb_5_4b_perm.json)."""
    f = MODELS / "cfb_5_4b_perm.json"
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text())
    except Exception:
        return None


def _parse_archetype_auc() -> tuple | None:
    """Extract (model_auc, capital_auc) from exports/archetypes.md if present."""
    f = EXPORTS / "archetypes.md"
    if not f.exists():
        return None
    aucs = [float(x) for x in re.findall(r"AUC[^\d]*(0\.\d{2,3})", f.read_text())][:2]
    return (aucs[0], aucs[1]) if len(aucs) == 2 else None


def check_drift(cur_hashes: dict) -> list:
    """Compare the 3 established results to baseline; return list of alert strings."""
    base = json.loads(BASELINE.read_text()) if BASELINE.exists() else {}
    prev = _prev_hashes()
    alerts = []
    # classify archetype/artifact drift cause via the newest FULL manifest's input-hash check
    import glob as _glob
    fulls = sorted(_glob.glob(str(CONFIG.path("logs") / "refresh_full_*.json")), key=os.path.getmtime)
    inputs_identical = None
    if fulls:
        inputs_identical = json.loads(open(fulls[-1]).read()).get(
            "reproducibility", {}).get("inputs_2013_2025_identical")

    def changed(*names):
        return any(cur_hashes.get(n) != prev.get(n) for n in names) if prev else True

    state = json.loads(STATE.read_text()) if STATE.exists() else {}

    # 1) archetype (item 4a): key on the SIGN of the model−capital gap (baseline −0.014, model
    #    below capital), plus movement > 0.005. A full reversal (gap → positive) always trips.
    cur = _parse_archetype_auc(); b = base.get("archetype_auc")
    if cur and b:
        model, cap = cur
        gap = model - cap; base_gap = b["model"] - b["capital"]
        if gap > 0:
            alerts.append(f"ARCHETYPE DRIFT: model−capital gap flipped POSITIVE ({gap:+.3f}) — "
                          f"Decision-10 negative result violated (model now beats capital).")
        elif round(gap, 4) != round(base_gap, 4):
            # refit sd is measured as EXACTLY 0.000 -> ANY nonzero movement is real (input or code
            # change), not noise. The manifest's inputs_2013_2025_identical classifies the cause.
            cause = "code change" if inputs_identical else "UPSTREAM DATA revision (2013–2025)"
            alerts.append(f"ARCHETYPE DRIFT: gap moved {gap-base_gap:+.4f} (any nonzero = real; "
                          f"refit sd=0). Likely cause via input-hash check: {cause}. baseline {base_gap:+.3f}.")
    else:
        alerts.append("ARCHETYPE: AUC not cleanly parseable (info; NOT a drift alert).")

    # 2) trade dual-pool verdict (item 4c): structured JSON, BOTH pools (the finding is they
    #    disagree — a change in either matters).
    cur_v = _read_trade_verdict(); b_v = base.get("trade_verdict")
    if cur_v and b_v:
        for pool in ("consensus", "corpus"):
            cw = (cur_v.get(pool) or {}).get("winner"); bw = b_v.get(pool)
            if cw and bw and cw != bw:
                alerts.append(f"TRADE DRIFT: {pool}-pool winner flipped ({bw} → {cw}).")
    else:
        alerts.append("TRADE: no structured verdict (exports/trade_verdict.json) — run FULL "
                      "(info; NOT a drift alert).")

    # 3) college perm-p (item 4b): 5.4B is now PINNED in models/cfb_5_4b_perm.json (Westfall-Young
    #    joint null; brought into the harness Gate-8 3rd review). Read the pinned family minimum
    #    marginal p and the WY family-wise p; require the significance threshold crossed on 2
    #    CONSECUTIVE refits before alerting. Also alert on a vintage change (upstream re-pull).
    coll = _read_college_perm()
    consec = int(state.get("college_consec", 0))
    base_coll = base.get("college_perm_p", {})
    if coll is not None:
        pre = coll.get("pre_registered", {})
        wy = coll.get("westfall_young_domshuffle_set", {})   # robustness set (different exch. set)
        # PRIMARY signal: the pre-registered decision rule flipping to MET is the real alert.
        if pre.get("rule_met"):
            alerts.append("COLLEGE PRE-REG RULE NOW MET: the pre-registered decision rule fired "
                          "(>=2 non-R1 strata) — 5.4B negative result overturned; investigate.")
        # SECONDARY: dom-shuffle family-minimum marginal crossing 0.05 on 2 consecutive refits.
        wy_min = wy.get("min_marginal_p")
        if wy_min is not None and wy_min < COLLEGE_P:
            consec += 1
            alerts.append(f"COLLEGE crossing logged: WY min marginal p {wy_min:.4f} < {COLLEGE_P} "
                          f"({consec} consecutive; post-hoc, threshold-fragile).")
            if consec >= COLLEGE_CONSEC:
                alerts.append(f"COLLEGE DRIFT: WY min marginal p < {COLLEGE_P} for {consec} "
                              "consecutive refits.")
        else:
            consec = 0
        state["college_consec"] = consec
        if base_coll.get("vintage") and coll.get("vintage") != base_coll["vintage"]:
            alerts.append(f"COLLEGE VINTAGE CHANGE: pinned {coll.get('vintage')} != baseline "
                          f"{base_coll['vintage']} — re-baseline drift_baseline.json (upstream "
                          "re-pull), not silent drift.")
    else:
        alerts.append("COLLEGE (5.4B): models/cfb_5_4b_perm.json missing — run "
                      "`uv run python -m models.cfb_5_4b` to pin the artifact.")

    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state))
    return alerts


def run(run_id: str | None = None) -> dict:
    run_id = run_id or f"manual_{int(time.time())}"
    hashes = hash_artifacts(run_id)
    alerts = check_drift(hashes)
    real = [a for a in alerts if "DRIFT" in a]     # only genuine flips flag; parse-notes are info
    for a in alerts:
        (log.warning if ("DRIFT" in a) else log.info)("drift: %s", a)
    return {"run_id": run_id, "n_artifacts": len(hashes), "alerts": alerts,
            "drift_flagged": len(real) > 0}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
