"""G10.6 — producer for the roster-strength design effect (models/design_effect.json).

The proxy ICC `roster_icc_2020 = 0.123` was HAND-TYPED with no producer (NOTE 0023) and no written
metric definition (NOTE 0027). This DEFINES it (NEW DEFINITION; -76.1 lesson one layer up) and builds
the reproducible producer.

PRE-REGISTERED (reviewer NOTE 0028 recommendation + Colby go-ahead; before the number was computed):
- Unit  = (manager, league) startup roster; Cluster = `manager`.
- PRIMARY metric = EX-POST roster strength = MEAN over the roster's drafted players of the player's
  3-yr forward VORP (vorp_ppr_total summed over the founding year Y..Y+2), 0-filled for drafted uids
  with no VORP row ("realized / includes luck", labeled).
- SENSITIVITIES (pre-registered, reported alongside): {ex-ante = draft capital}, {SUM vs MEAN},
  {v0 window vs 3-yr}. If a sensitivity's deff differs materially from the primary, that spread is a
  finding (feeds A18 COND-B blast radius).
- ICC via calibration_check._icc (continuous one-way ANOVA); deff = 1+(mbar-1)*ICC with mbar_arith
  (mean cluster size) AND mbar_kish (Sum ni^2 / Sum ni); eff_leagues = n_leagues/deff.
- ICC CI = manager-cluster bootstrap, 5 seeds (0..4), B=2000, percentile 2.5/97.5.
"""
import json

import numpy as np
import polars as pl
import duckdb

from config import CONFIG
from models import startup_data as D
from models.calibration_check import _icc

BLOCKS = {2020: [2020, 2021, 2022], 2021: [2021, 2022, 2023]}
BOOT_SEEDS = list(range(5))
B = 2000
ICC_HW_MAX = 0.20   # pre-registered (PHASE10_PLAN G10.5): UNESTIMABLE iff CI spans 0 OR half-width > 0.20
ART = CONFIG.path("models") / "design_effect.json"


def _forward_vorp_lookup():
    """{(player_uid, season): vorp_ppr_total} from the deterministic warehouse."""
    con = duckdb.connect(str(CONFIG.path("warehouse")), read_only=True)
    rows = con.execute("SELECT player_uid, season, vorp_ppr_total FROM fact_player_season_metrics").fetchall()
    con.close()
    return {(r[0], int(r[1])): (r[2] if r[2] is not None else 0.0) for r in rows}


def _draft_capital_lookup():
    """{player_uid: capital_value} ex-ante. Value = 261 - draft_overall (higher = earlier pick);
    undrafted (draft_overall null) -> 0 (sub-replacement ex-ante)."""
    con = duckdb.connect(str(CONFIG.path("warehouse")), read_only=True)
    rows = con.execute("""SELECT player_uid, draft_round, draft_pick FROM dim_player
                          WHERE draft_year IS NOT NULL""").fetchall()
    con.close()
    out = {}
    for uid, rnd, pk in rows:
        if rnd is not None and pk is not None:
            ovr = (int(rnd) - 1) * 32 + int(pk)
            out[uid] = max(0.0, 261.0 - ovr)
    return out


def _roster_strength(cp: pl.DataFrame, year: int, fv, cap, *, exante: bool, agg: str, window: str):
    """Return (labels=manager, y=roster strength) over (manager,league) rosters for one block-year."""
    seasons = BLOCKS[year] if window == "3yr" else [year]
    rows = []
    for (lg, mgr), grp in cp.filter(pl.col("year") == year).group_by(["league_id", "manager"]):
        if mgr is None:
            continue
        vals = []
        for uid in grp["player_uid"].to_list():
            if uid is None:
                continue
            if exante:
                vals.append(cap.get(uid, 0.0))
            else:
                vals.append(sum(fv.get((uid, s), 0.0) for s in seasons))
        if not vals:
            continue
        rows.append((str(mgr), str(lg), float(np.sum(vals) if agg == "sum" else np.mean(vals))))
    # DETERMINISM (G10.6, same class as the warehouse C2 fix): polars group_by output order is
    # nondeterministic, so the ICC's float sums (msb/msw) would be order-sensitive -> ULP drift
    # across processes (caught by the 5-process byte-check). Sort by (manager, league) so the
    # reduction order, hence the ICC, is byte-identical.
    rows.sort()
    labels = np.array([r[0] for r in rows])
    ys = np.array([r[2] for r in rows], dtype=float)
    return labels, ys


def _deffs(labels, y, n_leagues):
    icc, k = _icc(labels, y)
    ni = np.array([np.sum(labels == u) for u in np.unique(labels)], dtype=float)
    mbar_arith = float(ni.mean())
    mbar_kish = float((ni ** 2).sum() / ni.sum())
    return {
        "icc": float(icc), "n_clusters": int(k), "n_rosters": int(len(y)), "n_leagues": int(n_leagues),
        "mbar_arith": mbar_arith, "mbar_kish": mbar_kish,
        "deff_arith": 1 + (mbar_arith - 1) * float(icc),
        "deff_kish": 1 + (mbar_kish - 1) * float(icc),
        "eff_leagues_arith": n_leagues / (1 + (mbar_arith - 1) * float(icc)),
        "eff_leagues_kish": n_leagues / (1 + (mbar_kish - 1) * float(icc)),
    }


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
        per.append((np.percentile(iccs, 2.5), np.percentile(iccs, 97.5)))
    return float(np.mean([a for a, _ in per])), float(np.mean([b for _, b in per]))


def regenerate() -> dict:
    cp = D.load_corpus_startups()
    fv = _forward_vorp_lookup()
    cap = _draft_capital_lookup()
    forks = {
        "primary_expost_3yr_mean": dict(exante=False, agg="mean", window="3yr"),
        "sens_expost_3yr_sum": dict(exante=False, agg="sum", window="3yr"),
        "sens_expost_v0_mean": dict(exante=False, agg="mean", window="v0"),
        "sens_exante_capital_mean": dict(exante=True, agg="mean", window="3yr"),
    }
    out = {"_what": "roster-strength design effect (NEW DEFINITION; roster_icc had no producer).",
           "_metric": "PRIMARY = ex-post MEAN 3-yr forward VORP per (manager,league) roster, manager-clustered, 0-filled.",
           "_seed_protocol": f"ICC CI = manager-cluster bootstrap, seeds {BOOT_SEEDS}, B={B}, percentile 2.5/97.5",
           "years": {}}
    for year in (2020, 2021, "pooled"):
        if year == "pooled":
            n_leagues = cp.filter(pl.col("year").is_in([2020, 2021]))["league_id"].n_unique()
        else:
            n_leagues = cp.filter(pl.col("year") == year)["league_id"].n_unique()
        yr = {}
        for name, kw in forks.items():
            if year == "pooled":  # concatenate 2020 + 2021 rosters, clustered by manager
                l20, y20 = _roster_strength(cp, 2020, fv, cap, **kw)
                l21, y21 = _roster_strength(cp, 2021, fv, cap, **kw)
                order = np.argsort(np.concatenate([l20, l21]), kind="stable")
                labels = np.concatenate([l20, l21])[order]
                y = np.concatenate([y20, y21])[order]
            else:
                labels, y = _roster_strength(cp, year, fv, cap, **kw)
            d = _deffs(labels, y, n_leagues)
            if name.startswith("primary"):
                lo, hi = _icc_ci(labels, y)
                hw = (hi - lo) / 2
                spans0 = lo < 0 < hi
                # BOTH clauses (reviewer NOTE 0031 correction): UNESTIMABLE iff spans 0 OR HW > icc_hw_max
                unestimable = bool(spans0 or hw > ICC_HW_MAX)
                icc_cons = hi if unestimable else d["icc"]   # UNESTIMABLE->CONSERVATIVE: upper CI bound
                d.update({
                    "icc_ci_lo": lo, "icc_ci_hi": hi, "icc_ci_half_width": hw,
                    "spans_zero": spans0, "hw_exceeds_max": bool(hw > ICC_HW_MAX),
                    "estimable": not unestimable,
                    "unestimable_reason": ("spans_zero" if spans0 else "") + ("+hw>0.20" if hw > ICC_HW_MAX else ""),
                    "icc_conservative": float(icc_cons),
                    "deff_kish_conservative": 1 + (d["mbar_kish"] - 1) * float(icc_cons),
                    "eff_leagues_kish_conservative": n_leagues / (1 + (d["mbar_kish"] - 1) * float(icc_cons)),
                    "deff_arith_conservative": 1 + (d["mbar_arith"] - 1) * float(icc_cons),
                    "eff_leagues_arith_conservative": n_leagues / (1 + (d["mbar_arith"] - 1) * float(icc_cons)),
                })
            yr[name] = d
        out["years"][str(year)] = yr
    ART.write_text(json.dumps(out, indent=2, sort_keys=True))
    return out


if __name__ == "__main__":
    art = regenerate()
    for year in ("2020", "2021"):
        p = art["years"][year]["primary_expost_3yr_mean"]
        print(f"{year} PRIMARY: ICC={p['icc']:.4f} CI[{p.get('icc_ci_lo',float('nan')):.4f},{p.get('icc_ci_hi',float('nan')):.4f}] "
              f"mbar_arith={p['mbar_arith']:.3f} mbar_kish={p['mbar_kish']:.3f} "
              f"deff_kish={p['deff_kish']:.4f} eff_leagues_kish={p['eff_leagues_kish']:.2f} "
              f"(n_rosters={p['n_rosters']}, n_leagues={p['n_leagues']})")
        for s in ("sens_expost_3yr_sum", "sens_expost_v0_mean", "sens_exante_capital_mean"):
            q = art["years"][year][s]
            print(f"    {s}: ICC={q['icc']:.4f} deff_kish={q['deff_kish']:.4f}")
