"""G10.5 — producer for the OUTCOME win-rate ICC `d_out` (models/outcome_icc.json).

The whole project design-effect rests on a roster-strength PROXY ICC (models/design_effect.py: pooled
0.214). G10.5 is the owed VALIDATION: measure the ICC of the actual simulated OUTCOME (all-play win
rate) the proxy stood in for, and compare. This is the `win_rate_ICC_unmeasured` open item.

PRE-REGISTERED DESIGN (before the number was computed; A18 PR-1 + PHASE10 addendum, reviewer NOTE 0040
+ Colby NOTE 0038 pre-authorization to run under the narrow rule):
- UNIT      = (manager, league) actual corpus startup roster (SAME unit as the proxy).
- OUTCOME   = the roster's simulated all-play WIN RATE: fix the manager's ACTUAL drafted players as
              my_team's roster, let the 11-team field draft AROUND them, score the realized window
              seasons (`score_rosters`/`cell_metrics`), and — CRITICAL — average over sims OUTSIDE the
              manager-cluster bootstrap so simulation noise cannot inflate between-manager variance.
              One stable win rate per roster, THEN the ICC.
- CLUSTER   = manager.
- OPPONENT FAMILIES (STANDING CONSTRAINT 2 — report BOTH, ranking is family-dependent):
              (a) reach-window field (`corpus_draw`, K8 — the loose/corpus-realistic field), and
              (b) empirical field (opponents draw the real player taken at their slot).
- ICC       = calibration_check._icc (one-way ANOVA), manager-clustered; deff = 1+(mbar-1)*ICC with
              mbar_arith AND mbar_kish; eff_leagues = n_leagues/deff. IDENTICAL to design_effect.py.
- ESTIMABILITY (BOTH clauses — do NOT repeat the 2021 width-clause miss, reviewer NOTE 0031/0040):
              UNESTIMABLE iff the manager-cluster bootstrap ICC CI spans 0 OR its half-width > 0.20;
              UNESTIMABLE -> CONSERVATIVE (route to the upper CI bound, never floor to 0/deff 1).
- SEEDS     = ICC CI is a manager-cluster bootstrap, seeds 0..4, B=2000, percentile 2.5/97.5. The
              whole artifact is byte-checked across 5 fresh processes (like design_effect.json).
- CONVERGENCE = report the cross-seed CI-endpoint spread.
- COMPARISON = d_out vs the pooled PROXY ICC 0.214 (A18 PR-1 CI-vs-value). A match validates the proxy;
              a material divergence is a COND-B blast-radius finding. Either way it is a producer-backed
              measurement -> narrow rule unless it flips a headline or changes a criterion.

Determinism: rosters are processed in sorted (manager, league) order and the per-year RNG is seeded
deterministically, so the float reductions (sim win rates, ICC msb/msw) are byte-identical across
processes (same class as the design_effect.py `rows.sort()` fix).
"""
import json

import numpy as np

from config import CONFIG
from models import startup_data as D
from models import startup_backtester as BT_MOD
from models.startup_backtester import (
    N_TEAMS, BT, _snake_teams, _caps, _mins, _Avail, _best_available,
    score_rosters, cell_metrics, _build_ctx,
)
from models.calibration_check import _icc

BOOT_SEEDS = list(range(5))
B = 2000
ICC_HW_MAX = 0.20               # pre-registered (identical to design_effect.py)
N_SIMS = 120                    # sims-OUTSIDE per roster (field-draw averaging to a stable win rate)
FIELDS = {"reach_window": "corpus_draw", "empirical": "empirical"}   # the two opponent families
PROXY_POOLED_ICC = 0.214       # models/design_effect.py pooled roster-strength proxy (the comparison)
ART = CONFIG.path("models") / "outcome_icc.json"


def simulate_fixed(ctx, roster_idx, field, rng):
    """my_team (slot 0) roster FIXED to `roster_idx` (the manager's actual drafted players); the other
    11 teams draft around them via the opponent `field`. Returns rosters (list[list[idx]])."""
    rounds = BT["draft_rounds"]
    my_team = 0
    teams = _snake_teams(rounds)
    caps = _caps(); mins = _mins(1)
    av = _Avail(ctx)
    rosters = [[] for _ in range(N_TEAMS)]
    counts = np.zeros((N_TEAMS, 4), dtype=np.int32)
    for i in roster_idx:                     # pre-place my_team's actual roster, remove from the board
        av.take(i)
        rosters[my_team].append(i)
        if ctx.pos[i] >= 0:
            counts[my_team][ctx.pos[i]] += 1
    for p, t in enumerate(teams):
        if t == my_team:                     # my_team is pre-filled — skip its snake slots
            continue
        pick_no = p + 1
        rnd = p // N_TEAMS + 1
        picks_left = rounds - len(rosters[t])
        if field == "empirical":             # EMPIRICAL family (simulate_one branch, opponents only)
            need = np.maximum(mins - counts[t], 0)
            i = -1
            if need.sum() < picks_left:
                so = ctx.pool_so.get(pick_no)
                if so is not None:
                    avp = [j for j in so[av.avail[so]] if counts[t][ctx.pos[j]] < caps[ctx.pos[j]]]
                    if avp:
                        i = int(rng.choice(avp))
            if i < 0:
                i = _best_available(av, counts[t], caps, mins, picks_left)
        else:                                # REACH-WINDOW family (K from BT["reach_window"][field])
            need = np.maximum(mins - counts[t], 0)
            if need.sum() >= picks_left:
                i = _best_available(av, counts[t], caps, mins, picks_left)
            else:
                k = BT["reach_window"][field]
                window = av.next_k_available(k, counts[t], caps)
                i = int(rng.choice(window)) if window else _best_available(
                    av, counts[t], caps, mins, picks_left)
        if i < 0:
            continue
        av.take(i); rosters[t].append(i)
        if ctx.pos[i] >= 0:
            counts[t][ctx.pos[i]] += 1
    return rosters


def _roster_winrate(ctx, roster_idx, field, n_sims, rng):
    """Stable per-roster win rate = MEAN over n_sims of the fixed-roster all-play win rate (sims
    OUTSIDE: the averaging happens here, BEFORE the ICC, so sim noise cannot inflate the ICC)."""
    wr = np.empty(n_sims)
    for s in range(n_sims):
        rosters = simulate_fixed(ctx, roster_idx, field, rng)
        scores = score_rosters(ctx, rosters, 1, weekly=False)
        w, _, _ = cell_metrics(scores, 0)
        wr[s] = w
    return float(wr.mean())


def _year_labels_winrates(cp, year, field, n_sims, seed):
    """(labels=manager, y=stable win rate) over (manager,league) rosters for one block-year."""
    ctx = _build_ctx(year, 1, 5, None)
    idx = {u: i for i, u in enumerate(ctx.uids)}
    rows = []
    for (lg, mgr), grp in cp.filter(cp["year"] == year).group_by(["league_id", "manager"]):
        if mgr is None:
            continue
        roster_idx = [idx[u] for u in grp["player_uid"].to_list() if u in idx]
        if not roster_idx:
            continue
        rows.append((str(mgr), str(lg), roster_idx))
    rows.sort(key=lambda r: (r[0], r[1]))         # DETERMINISM: fixed reduction order (design_effect class)
    labels, ys = [], []
    for k, (mgr, lg, roster_idx) in enumerate(rows):
        rng = np.random.default_rng((seed, year, k))   # per-roster deterministic stream
        labels.append(mgr)
        ys.append(_roster_winrate(ctx, roster_idx, field, n_sims, rng))
    return np.array(labels), np.array(ys, dtype=float)


def _deffs(labels, y, n_leagues):
    icc, k = _icc(labels, y)
    ni = np.array([np.sum(labels == u) for u in np.unique(labels)], dtype=float)
    mbar_arith = float(ni.mean())
    mbar_kish = float((ni ** 2).sum() / ni.sum())
    return {"icc": float(icc), "n_clusters": int(k), "n_rosters": int(len(y)),
            "n_leagues": int(n_leagues), "mbar_arith": mbar_arith, "mbar_kish": mbar_kish,
            "deff_arith": 1 + (mbar_arith - 1) * float(icc),
            "deff_kish": 1 + (mbar_kish - 1) * float(icc),
            "eff_leagues_arith": n_leagues / (1 + (mbar_arith - 1) * float(icc)),
            "eff_leagues_kish": n_leagues / (1 + (mbar_kish - 1) * float(icc))}


def _icc_ci(labels, y):
    us = np.unique(labels)
    idx = {u: np.where(labels == u)[0] for u in us}
    per = []
    for sd in BOOT_SEEDS:
        rr = np.random.default_rng(sd)
        iccs = []
        for _ in range(B):
            chosen = rr.choice(us, len(us), replace=True)
            take = np.concatenate([idx[u] for u in chosen])
            lab_b = np.concatenate([[i] * len(idx[u]) for i, u in enumerate(chosen)])
            iccs.append(_icc(lab_b, y[take])[0])
        per.append((float(np.percentile(iccs, 2.5)), float(np.percentile(iccs, 97.5))))
    los = [a for a, _ in per]; his = [b for _, b in per]
    return (float(np.mean(los)), float(np.mean(his)),
            float(max(los) - min(los)), float(max(his) - min(his)))   # + cross-seed endpoint spreads


def _stats(labels, y, n_leagues, field, n_sims):
    """Full d_out stats block for a (labels, win-rate) set: ICC + deff + estimability + PR-1."""
    d = _deffs(labels, y, n_leagues)
    lo, hi, lo_spread, hi_spread = _icc_ci(labels, y)
    hw = (hi - lo) / 2
    spans0 = lo < 0 < hi
    unestimable = bool(spans0 or hw > ICC_HW_MAX)      # BOTH clauses (2021 width-clause NOT missed)
    icc_cons = hi if unestimable else d["icc"]         # UNESTIMABLE -> CONSERVATIVE upper bound
    d.update({
        "field_family": field, "n_sims": n_sims, "win_rate_mean": float(np.mean(y)),
        "icc_ci_lo": lo, "icc_ci_hi": hi, "icc_ci_half_width": hw,
        "icc_ci_lo_seed_spread": lo_spread, "icc_ci_hi_seed_spread": hi_spread,
        "spans_zero": spans0, "hw_exceeds_max": bool(hw > ICC_HW_MAX),
        "estimable": not unestimable,
        "unestimable_reason": ("spans_zero" if spans0 else "") + ("+hw>0.20" if hw > ICC_HW_MAX else ""),
        "icc_conservative": float(icc_cons),
        "deff_kish_conservative": 1 + (d["mbar_kish"] - 1) * float(icc_cons),
        "eff_leagues_kish_conservative": n_leagues / (1 + (d["mbar_kish"] - 1) * float(icc_cons)),
        # PR-1 comparison to the roster-strength PROXY (pooled 0.214)
        "proxy_pooled_icc": PROXY_POOLED_ICC,
        "d_out_minus_proxy": float(d["icc"]) - PROXY_POOLED_ICC,
        "proxy_in_icc_ci": bool(lo <= PROXY_POOLED_ICC <= hi),
    })
    return d


def regenerate(seed: int = 0, n_sims: int = N_SIMS) -> dict:
    cp = D.load_corpus_startups()
    out = {"_what": "outcome win-rate ICC d_out (G10.5 design-effect VALIDATION of the roster-strength "
                    "proxy). Fixed actual corpus roster vs field; sims-OUTSIDE; manager-clustered.",
           "_metric": "PRIMARY per-roster outcome = MEAN over sims of the fixed-roster all-play win "
                      "rate; ICC clustered by manager. Compared to the pooled proxy ICC 0.214.",
           "_seed_protocol": f"ICC CI = manager-cluster bootstrap seeds {BOOT_SEEDS}, B={B}; "
                             f"per-roster sim stream seeded (seed,year,k); n_sims={n_sims}",
           "proxy_pooled_icc": PROXY_POOLED_ICC, "years": {}}
    for fam, field in FIELDS.items():
        # Compute each year's per-roster win-rate vector ONCE (the heavy sim); pooled REUSES them
        # (concat) instead of re-simulating — halves the sim cost, and pooled is byte-identical to the
        # union of the two single-year vectors.
        vecs = {y: _year_labels_winrates(cp, y, field, n_sims, seed) for y in (2020, 2021)}
        nlg = {y: int(cp.filter(cp["year"] == y)["league_id"].n_unique()) for y in (2020, 2021)}
        for year in (2020, 2021):
            labels, y = vecs[year]
            out["years"].setdefault(fam, {})[str(year)] = _stats(labels, y, nlg[year], field, n_sims)
        (l20, y20), (l21, y21) = vecs[2020], vecs[2021]
        order = np.argsort(np.concatenate([l20, l21]), kind="stable")
        labels = np.concatenate([l20, l21])[order]
        y = np.concatenate([y20, y21])[order]
        n_leagues_pool = int(cp.filter(cp["year"].is_in([2020, 2021]))["league_id"].n_unique())
        out["years"][fam]["pooled"] = _stats(labels, y, n_leagues_pool, field, n_sims)
    ART.write_text(json.dumps(out, indent=2, sort_keys=True))
    return out


if __name__ == "__main__":
    art = regenerate()
    for fam in FIELDS:
        print(f"\n=== opponent family: {fam} ===")
        for year in ("2020", "2021", "pooled"):
            p = art["years"][fam][year]
            print(f"{year:>7}: d_out ICC={p['icc']:.4f} CI[{p['icc_ci_lo']:.4f},{p['icc_ci_hi']:.4f}] "
                  f"HW={p['icc_ci_half_width']:.4f} {'ESTIMABLE' if p['estimable'] else 'UNESTIMABLE('+p['unestimable_reason']+')'} "
                  f"| deff_kish={p['deff_kish']:.3f} eff_lg={p['eff_leagues_kish']:.1f} "
                  f"| vs proxy 0.214: Δ={p['d_out_minus_proxy']:+.4f} proxy_in_CI={p['proxy_in_icc_ci']} "
                  f"(win_rate_mean={p['win_rate_mean']:.3f}, n_rosters={p['n_rosters']})")
