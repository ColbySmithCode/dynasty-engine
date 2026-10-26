"""Phase 7 (3rd review, item 2) — SAMPLING variance of the two model-based negatives, by
BOOTSTRAP OVER PLAYERS (not refits), holding fold structure fixed. Refit sd is 0 (determinism);
this is the actual precision of the archetype and college claims.
    uv run python -m jobs.measure_sampling_variance --n 300
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CONFIG

SEED = CONFIG["models"]["seed"]


def archetype_bootstrap(B: int) -> dict:
    """Resample players with replacement (keeping their draft-year->fold), refit model+capital,
    report the distribution of the model-minus-capital AUC gap."""
    import polars as pl
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from models import archetypes as A
    df = A._frame()
    pos_dum = df.select([(pl.col("position") == p).cast(pl.Int8).alias(f"pos_{p}") for p in ("QB", "RB", "WR", "TE")])
    X = df.select(A.FEATS).to_pandas()
    for c in pos_dum.columns:
        X[c] = pos_dum[c].to_numpy()
    y = df["hit"].to_numpy(); yr = df["draft_year"].to_numpy()
    lo = np.log(df["draft_ovr"].to_numpy()).reshape(-1, 1)
    tr_idx = np.where(yr <= 2018)[0]; te_idx = np.where(yr >= 2019)[0]
    rng = np.random.default_rng(SEED)
    gaps, aucm, aucb = [], [], []
    for _ in range(B):
        bt = rng.choice(tr_idx, len(tr_idx), replace=True)
        be = rng.choice(te_idx, len(te_idx), replace=True)
        if y[be].sum() < 2 or y[bt].sum() < 2:
            continue
        m = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, max_depth=3,
                                           l2_regularization=1.0, min_samples_leaf=20,
                                           early_stopping=True, validation_fraction=0.15, random_state=SEED)
        m.fit(X.iloc[bt], y[bt])
        pm = m.predict_proba(X.iloc[be])[:, 1]
        b = LogisticRegression().fit(lo[bt], y[bt]); pb = b.predict_proba(lo[be])[:, 1]
        am = roc_auc_score(y[be], pm); ab = roc_auc_score(y[be], pb)
        gaps.append(am - ab); aucm.append(am); aucb.append(ab)
    g = np.array(gaps)
    return {"n_boot": len(g), "gap_mean": float(g.mean()), "gap_sd": float(g.std()),
            "gap_median": float(np.median(g)),
            "gap_ci": [float(np.percentile(g, 2.5)), float(np.percentile(g, 97.5))],
            "P(model beats capital)": float((g > 0).mean()),
            "n_above_zero": int((g > 0).sum()),
            "auc_model_mean": float(np.mean(aucm)), "auc_capital_mean": float(np.mean(aucb))}


def _college_cohort():
    """Replicate cfb_5_4b.run()'s cohort (build_features + fwd3 + top5, dom_best not null)."""
    import duckdb
    import polars as pl
    from models import cfb_5_4b as C
    base = C._frame()
    fv = C._forward_vorp().group_by("player_uid").agg(pl.col("fwd3_vorp").max())
    con = duckdb.connect(str(CONFIG.path("warehouse")), read_only=True)
    top5 = con.execute("""SELECT s.player_uid, 1 AS top5 FROM fact_player_season s
        JOIN dim_player d USING(player_uid)
        WHERE s.pos_finish_ppr<=5 AND s.season BETWEEN CAST(d.draft_year AS INTEGER)
          AND CAST(d.draft_year AS INTEGER)+2 GROUP BY s.player_uid""").pl()
    con.close()
    df = C.build_features(base).join(fv, on="player_uid", how="left").join(top5, on="player_uid", how="left")
    return df.with_columns([pl.col("top5").fill_null(0),
                            pl.col("draft_year").cast(pl.Int32, strict=False)]).filter(
        pl.col("dom_best").is_not_null())


def _strata_min_p(df, n_perm: int) -> float:
    """Minimum permutation p across the 5.4B strata (wr_only × round × target), on a given cohort."""
    import polars as pl
    from models.cfb_5_4b import perm_diff
    ps = []
    for wr_only in (False, True):
        d0 = df.filter(pl.col("position") == "WR") if wr_only else df
        for rd in (1, 2, 3, None):
            s = d0.filter(pl.col("draft_round") == rd) if rd else d0.filter(pl.col("draft_round") >= 4)
            if s.height < 12:
                continue
            db = s["dom_best"].to_numpy()
            hi = db >= np.nanquantile(db, 2 / 3); loq = db <= np.nanquantile(db, 1 / 3)
            for tgt in ("hit", "top5"):
                _, p = perm_diff(s.filter(pl.Series(hi))[tgt].cast(pl.Float64).to_numpy(),
                                 s.filter(pl.Series(loq))[tgt].cast(pl.Float64).to_numpy(), n=n_perm)
                if not np.isnan(p):
                    ps.append(p)
            _, pv = perm_diff(s.filter(pl.Series(hi))["fwd3_vorp"].to_numpy(),
                              s.filter(pl.Series(loq))["fwd3_vorp"].to_numpy(), n=n_perm)
            if not np.isnan(pv):
                ps.append(pv)
    return float(min(ps)) if ps else float("nan")


def college_bootstrap(B: int, n_perm: int = 2000) -> dict:
    """Bootstrap the college cohort over players; distribution of the MINIMUM permutation p across
    strata (reduced n_perm for tractability, noted)."""
    df = _college_cohort()
    rng = np.random.default_rng(SEED)
    mins = []
    for _ in range(B):
        bs = df.sample(fraction=1.0, with_replacement=True, seed=int(rng.integers(1 << 30)))
        mp = _strata_min_p(bs, n_perm)
        if not np.isnan(mp):
            mins.append(mp)
    m = np.array(mins)
    return {"n_boot": len(m), "cohort_n": df.height, "n_perm": n_perm,
            "min_p_point": _strata_min_p(df, 5000),
            "min_p_mean": float(m.mean()), "min_p_sd": float(m.std()),
            "min_p_ci": [float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))],
            "P(any stratum min_p<0.05)": float((m < 0.05).mean())}


def _midrank(x):
    """Midranks (1-based) with tie handling — for the fast DeLong algorithm (Sun & Xu 2014)."""
    J = np.argsort(x, kind="mergesort")
    Z = x[J]
    N = len(x)
    T = np.zeros(N)
    i = 0
    while i < N:
        j = i
        while j < N and Z[j] == Z[i]:
            j += 1
        T[i:j] = 0.5 * (i + j - 1) + 1
        i = j
    out = np.empty(N)
    out[J] = T
    return out


def _delong_cov(y, preds):
    """Fast DeLong: return (aucs, S) where S is the k×k covariance of the AUC estimators, computed
    on the SAME sample so the off-diagonal captures the correlation between the two AUCs."""
    y = np.asarray(y)
    pos = y == 1
    neg = ~pos
    m, n = int(pos.sum()), int(neg.sum())
    k = len(preds)
    aucs = np.empty(k)
    V10 = np.empty((k, m))
    V01 = np.empty((k, n))
    for r, p in enumerate(preds):
        p = np.asarray(p, float)
        X, Y = p[pos], p[neg]
        tx, ty = _midrank(X), _midrank(Y)
        txy = _midrank(np.concatenate([X, Y]))
        aucs[r] = (txy[:m].sum() / m - (m + 1) / 2) / n
        V10[r] = (txy[:m] - tx) / n
        V01[r] = 1.0 - (txy[m:] - ty) / m
    S10 = np.cov(V10)
    S01 = np.cov(V01)
    S = S10 / m + S01 / n
    return aucs, np.atleast_2d(S)


def _fit_archetype_once():
    """Fit HistGB (model) and logit-on-ln(ovr) (capital) ONCE on train<=2018; return test-set
    (y, model_scores, capital_scores) for the >=2019 players. Params mirror models.archetypes."""
    import polars as pl
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from models import archetypes as A
    df = A._frame()
    pos_dum = df.select([(pl.col("position") == p).cast(pl.Int8).alias(f"pos_{p}") for p in ("QB", "RB", "WR", "TE")])
    X = df.select(A.FEATS).to_pandas()
    for c in pos_dum.columns:
        X[c] = pos_dum[c].to_numpy()
    y = df["hit"].to_numpy()
    yr = df["draft_year"].to_numpy()
    lo = np.log(df["draft_ovr"].to_numpy()).reshape(-1, 1)
    tr, te = yr <= 2018, yr >= 2019
    m = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, max_depth=3,
                                       l2_regularization=1.0, min_samples_leaf=20,
                                       early_stopping=True, validation_fraction=0.15, random_state=SEED)
    m.fit(X[tr], y[tr])
    b = LogisticRegression().fit(lo[tr], y[tr])
    return y[te], m.predict_proba(X[te])[:, 1], b.predict_proba(lo[te])[:, 1]


def archetype_testonly(B: int = 2000, seeds=(1729, 2, 3, 4, 5)) -> dict:
    """TEST-ONLY fixed-model bootstrap of the archetype gap: models fit ONCE on train<=2018, resample
    only the >=2019 test players (B per seed, 5 seeds). Plus the DeLong paired SE + correlation of
    the two correlated AUCs. Isolates test-set sampling variance (no refit-on-resample degradation)."""
    from sklearn.metrics import roc_auc_score
    y, pm, pb = _fit_archetype_once()
    point = float(roc_auc_score(y, pm) - roc_auc_score(y, pb))
    idx = np.arange(len(y))
    per_seed = []
    for s in seeds:
        rng = np.random.default_rng(s)
        g = np.empty(B)
        for i in range(B):
            bi = rng.choice(idx, len(idx), replace=True)
            if y[bi].sum() < 2 or (1 - y[bi]).sum() < 2:
                g[i] = np.nan
                continue
            g[i] = roc_auc_score(y[bi], pm[bi]) - roc_auc_score(y[bi], pb[bi])
        g = g[~np.isnan(g)]
        per_seed.append({"seed": s, "ci_lo": float(np.percentile(g, 2.5)),
                         "ci_hi": float(np.percentile(g, 97.5)), "sd": float(g.std()),
                         "frac_above_0": float((g > 0).mean())})
    los = [d["ci_lo"] for d in per_seed]
    his = [d["ci_hi"] for d in per_seed]
    aucs, S = _delong_cov(y, [pm, pb])
    var_diff = float(S[0, 0] + S[1, 1] - 2 * S[0, 1])
    de_se = var_diff ** 0.5
    corr = float(S[0, 1] / (S[0, 0] * S[1, 1]) ** 0.5)
    return {"n_test": int(len(y)), "n_hits": int(y.sum()), "B": B, "seeds": list(seeds),
            "gap_point": point, "per_seed": per_seed,
            "ci_lo_spread": [min(los), max(los)], "ci_hi_spread": [max(his), min(his)],
            "endpoint_spread_lo": float(max(los) - min(los)), "endpoint_spread_hi": float(max(his) - min(his)),
            "bootstrap_sd_mean": float(np.mean([d["sd"] for d in per_seed])),
            "frac_above_0_mean": float(np.mean([d["frac_above_0"] for d in per_seed])),
            "auc_model": float(aucs[0]), "auc_capital": float(aucs[1]),
            "delong_paired_se": de_se, "delong_corr": corr,
            "delong_z": float(point / de_se) if de_se else float("nan")}


def write_archetype_gap_artifact() -> dict:
    """Pin the full-precision archetype gap (fixed-model, single train<=2018 / test>=2019 split) to
    models/archetype_gap.json, so the doc-consistency guard can compare doc/registry against a LIVE
    value (closing the ~4e-6 blind spot where the gap had no live source). Deterministic (seed)."""
    import json

    from sklearn.metrics import roc_auc_score
    y, pm, pb = _fit_archetype_once()
    m, c = float(roc_auc_score(y, pm)), float(roc_auc_score(y, pb))
    frozen = json.loads((CONFIG.path("data_raw") / "nflverse" / "FROZEN.json").read_text())
    art = {"_what": "archetype supervised gap — full precision, fixed-model OOS (test>=2019).",
           "vintage": frozen["vintage"], "n_test": int(len(y)), "n_hits": int(y.sum()),
           "model_auc": m, "capital_auc": c, "gap": m - c}
    (CONFIG.path("models") / "archetype_gap.json").write_text(json.dumps(art, indent=2, sort_keys=True))
    return art


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    a = ap.parse_args()
    import json
    print("=== ARCHETYPE gap — sampling variance (bootstrap over players, fold fixed) ===")
    print(json.dumps(archetype_bootstrap(a.n), indent=1))
    print("\n=== COLLEGE 5.4B min perm-p — sampling variance ===")
    print(json.dumps(college_bootstrap(min(a.n, 100)), indent=1))


if __name__ == "__main__":
    main()
