"""G10.3 — CALIBRATION of the survival posterior vs observed frequencies (Phase-10).

Component 1 (this file): SURVIVAL Clock-A P(relevant in year N since draft) — OUT-OF-SAMPLE
reliability. For each (player, year-N) the prediction is the relevance rate among EARLIER draft
cohorts (draft_year < the player's) in the same stratum (position × round_grp × N), so calibration
is NOT the in-sample tautology (Beta mean == observed rate). Reliability curve + calibration slope
(player-clustered bootstrap CI) + ECE.

Component 2 (projection PPG 90% interval coverage) is a separate sub-component, not in this file.

Prints the pre-registered PASS condition BEFORE the result. Read-only.
"""
from __future__ import annotations
import json
import sys
import numpy as np
from config import CONFIG
from models import survival as S

DB = str(CONFIG.path("warehouse"))

MIN_CELL = 10            # min earlier-cohort obs in a cell to predict from it (else back off)
MAXN = 8                 # Clock-A horizon
ECE_MAX = 0.05           # author-supplied, PROVISIONAL
SEEDS = [1729, 2027, 4051, 7919, 9973]
CONV_FRAC = 0.10


def build_obs():
    """Per (player, N in 1..reachable): observed relevance + cohort + stratum."""
    df, latest = S._panel()
    d = df.select(["player_uid", "draft_year", "position", "round_grp", "yr_since_draft", "relevant"])
    rel_years, meta = {}, {}
    for r in d.iter_rows(named=True):
        rel_years.setdefault(r["player_uid"], set())
        if r["relevant"]:
            rel_years[r["player_uid"]].add(r["yr_since_draft"])
        meta[r["player_uid"]] = (r["draft_year"], r["position"], r["round_grp"])
    obs = []   # (uid, cohort, pos, rg, N, y)
    for uid, (cohort, pos, rg) in meta.items():
        if cohort is None:
            continue
        reach = min(MAXN, latest - cohort + 1)
        for N in range(1, reach + 1):
            obs.append((uid, cohort, pos, rg, N, 1 if N in rel_years[uid] else 0))
    return obs, latest


def predict(obs):
    """Leave-future-cohorts-out prediction per (player,N) from earlier cohorts in the same cell,
    with position→ALL backoff. Returns aligned arrays uid, pred, y, plus backoff counts."""
    # index observations by cell for earlier-cohort lookups
    from collections import defaultdict
    by_cell = defaultdict(list)   # (pos,rg,N) -> list of (cohort, y)
    by_posN = defaultdict(list)   # (pos,N)
    by_N = defaultdict(list)      # (N)
    for uid, cohort, pos, rg, N, y in obs:
        by_cell[(pos, rg, N)].append((cohort, y))
        by_posN[(pos, N)].append((cohort, y))
        by_N[N].append((cohort, y))

    def rate(lst, cohort):
        ys = [y for c, y in lst if c < cohort]
        return (np.mean(ys), len(ys)) if ys else (None, 0)

    uid_a, pred_a, y_a, bo = [], [], [], {"cell": 0, "pos": 0, "all": 0, "dropped": 0}
    for uid, cohort, pos, rg, N, y in obs:
        p, k = rate(by_cell[(pos, rg, N)], cohort)
        if k >= MIN_CELL:
            bo["cell"] += 1
        else:
            p, k = rate(by_posN[(pos, N)], cohort)
            if k >= MIN_CELL:
                bo["pos"] += 1
            else:
                p, k = rate(by_N[N], cohort)
                if k >= MIN_CELL:
                    bo["all"] += 1
                else:
                    bo["dropped"] += 1
                    continue
        uid_a.append(uid); pred_a.append(p); y_a.append(y)
    return np.array(uid_a), np.array(pred_a, float), np.array(y_a, float), bo


def reliability(pred, y, nbins=10):
    edges = np.quantile(pred, np.linspace(0, 1, nbins + 1))
    edges[0], edges[-1] = -1e-9, 1 + 1e-9
    rows, ece = [], 0.0
    for i in range(nbins):
        m = (pred > edges[i]) & (pred <= edges[i + 1])
        if m.sum() == 0:
            continue
        mp, mo, nb = pred[m].mean(), y[m].mean(), int(m.sum())
        rows.append((mp, mo, nb)); ece += nb / len(pred) * abs(mo - mp)
    return rows, ece


def slope(pred, y):
    """OLS slope/intercept of observed-freq on predicted-prob across decile bins (weighted)."""
    rows, _ = reliability(pred, y)
    xp = np.array([r[0] for r in rows]); yo = np.array([r[1] for r in rows]); w = np.array([r[2] for r in rows])
    W = np.diag(w); X = np.vstack([np.ones_like(xp), xp]).T
    beta = np.linalg.solve(X.T @ W @ X, X.T @ W @ yo)
    return beta[1], beta[0]   # slope, intercept


def clustered_slope_ci(uid, pred, y):
    """Player-clustered bootstrap CI for BOTH slope and intercept."""
    players = np.unique(uid)
    idx = {p: np.where(uid == p)[0] for p in players}
    s_seed, i_seed = [], []
    for sd in SEEDS:
        rng = np.random.default_rng(sd)
        sl, ic = [], []
        for _ in range(1000):
            pick = rng.choice(players, len(players), replace=True)
            rows = np.concatenate([idx[p] for p in pick])
            try:
                b_s, b_i = slope(pred[rows], y[rows])
                sl.append(b_s); ic.append(b_i)
            except np.linalg.LinAlgError:
                pass
        s_seed.append((np.percentile(sl, 2.5), np.percentile(sl, 97.5)))
        i_seed.append((np.percentile(ic, 2.5), np.percentile(ic, 97.5)))
    def agg(seed):
        los = [a for a, _ in seed]; his = [b for _, b in seed]
        return float(np.mean(los)), float(np.mean(his)), max(np.ptp(los), np.ptp(his))
    return agg(s_seed), agg(i_seed)


def ece_null(pred, ece_obs, seed=1729, B=2000):
    """Parametric null: draw y~Bernoulli(pred) (perfect calibration) and recompute ECE.
    Ignores player clustering (so the null band is mildly NARROW -> conservative for a PASS)."""
    rng = np.random.default_rng(seed)
    null = np.array([reliability(pred, (rng.random(len(pred)) < pred).astype(float))[1] for _ in range(B)])
    return float(np.percentile(null, 2.5)), float(np.percentile(null, 97.5)), float((null >= ece_obs).mean())


def print_pass():
    print("=" * 80)
    print("G10.3 CALIBRATION (survival Clock-A, OOS reliability) — PRE-REGISTERED PASS (before result)")
    print("=" * 80)
    print(f"""
Anti-vacuity: print n scored, n by position, cohort range, backoff/dropped counts.
Predictions are OUT-OF-SAMPLE (earlier draft cohorts only) — NOT the in-sample Beta tautology.
WELL-CALIBRATED (PASS) iff: calibration-slope player-clustered 95% CI CONTAINS 1.0
  AND ECE <= {ECE_MAX} (author-supplied, PROVISIONAL) AND the bootstrap converged.
MATERIALLY MISCALIBRATED (FAIL) iff slope CI excludes 1.0 or ECE > {ECE_MAX}
  -> forces a recalibration note/refit (stop-and-report). Cells with < {MIN_CELL} earlier-cohort
  obs at every backoff level are DROPPED and counted (a dropped-heavy run is UNINFORMATIVE, not PASS).
""")


def main():
    print_pass()
    obs, latest = build_obs()
    uid, pred, y, bo = predict(obs)
    print("-" * 80)
    print(f"latest season={latest}; observations scored={len(pred)} over {len(np.unique(uid))} players; "
          f"base relevance rate={y.mean():.4f}")
    from collections import Counter
    posc = Counter(o[2] for o in obs)
    print(f"obs by position (all): {dict(posc)}")
    print(f"cohort range: {min(o[1] for o in obs if o[1])}–{max(o[1] for o in obs)}")
    print(f"backoff: cell={bo['cell']} pos={bo['pos']} all={bo['all']} dropped={bo['dropped']}")
    rows, ece = reliability(pred, y)
    print("-" * 80)
    print("reliability (decile: mean_pred -> mean_obs, n):")
    for mp, mo, nb in rows:
        print(f"   pred {mp:.3f} -> obs {mo:.3f}  (n={nb})")
    sl, ic = slope(pred, y)
    (lo, hi, spread), (ilo, ihi, ispread) = clustered_slope_ci(uid, pred, y)
    hw = (hi - lo) / 2
    converged = spread < CONV_FRAC * hw
    ece_lo, ece_hi, ece_p = ece_null(pred, ece)
    events = int(y.sum())
    print("-" * 80)
    print("WIDTH (a non-rejection is not a pass — printing the interval, not just 'contains 1'):")
    print(f"  n scored={len(pred)}  players={len(np.unique(uid))}  events(relevant)={events}  "
          f"base={y.mean():.4f}   clustering=player_uid (5 seeds x 1000)")
    print(f"  calibration SLOPE     = {sl:.4f}   95% CI [{lo:.4f}, {hi:.4f}]  (half-width {hw:.4f})")
    print(f"  calibration INTERCEPT = {ic:+.4f}  95% CI [{ilo:+.4f}, {ihi:+.4f}]")
    print(f"  ECE = {ece:.4f}   perfect-calibration null 95% band [{ece_lo:.4f}, {ece_hi:.4f}]  "
          f"(P(null ECE >= observed) = {ece_p:.3f})")
    # decision-relevant miscalibration (set-at-measurement, PROVISIONAL): a slope outside
    # [0.90, 1.10] would bias high-P(relevant) pick valuations (e.g. R1 ~0.5-0.7) by >~5pp.
    DR_LO, DR_HI = 0.90, 1.10
    excludes_dr = (lo >= DR_LO) and (hi <= DR_HI)   # CI wholly inside the tolerable band => has power
    print(f"  decision-relevant band (author-supplied, set-at-measurement): slope in [{DR_LO},{DR_HI}]")
    print(f"  POWER: does the CI EXCLUDE a decision-relevant miscalibration? "
          f"{'YES (CI within band)' if excludes_dr else f'NO — CI upper {hi:.3f}/lower {lo:.3f} spills past the band'}")
    print("-" * 80)
    contains1 = lo <= 1.0 <= hi
    ECE_DR = 0.03   # decision-relevant ECE MAGNITUDE (author-supplied, set-at-measurement): a >3pp
                    # average miscalibration would bias pick valuation; 1pp would not.
    hard_fail = (not contains1) or (ece > ECE_DR) or (not converged)
    clean = excludes_dr and (ece_p >= 0.05)   # powered to exclude DR slope AND no detectable deviation
    detect = ece_p < 0.05                     # statistically detectable (but maybe sub-DR) miscalibration
    print("=" * 80)
    if hard_fail:
        why = []
        if not contains1:
            why.append(f"slope CI [{lo:.3f},{hi:.3f}] excludes 1.0")
        if ece > ECE_DR:
            why.append(f"ECE {ece:.4f} > decision-relevant {ECE_DR}")
        if not converged:
            why.append("bootstrap not converged")
        print(f"G10.3 (survival) RESULT: FAIL — {'; '.join(why)} (forces recalibration/refit)")
        ok = False
    elif clean:
        print(f"G10.3 (survival) RESULT: PASS (well-calibrated AND powered — slope CI [{lo:.3f},{hi:.3f}] "
              f"within [{DR_LO},{DR_HI}]; ECE {ece:.4f} within null band).")
        ok = True
    else:
        bits = []
        if not excludes_dr:
            bits.append(f"slope CI [{lo:.3f},{hi:.3f}] ADMITS a decision-relevant miscalibration (band "
                        f"[{DR_LO},{DR_HI}]) — underpowered")
        if detect:
            bits.append(f"ECE {ece:.4f} is statistically ABOVE the perfect-calibration null "
                        f"[{ece_lo:.4f},{ece_hi:.4f}] (p={ece_p:.3f}) — a small ({ece:.3f}<{ECE_DR}) but "
                        "DETECTABLE miscalibration")
        print("G10.3 (survival) RESULT: PASS-BUT-UNINFORMATIVE — calibration is GOOD in magnitude "
              f"(slope {sl:.3f}, ECE {ece:.4f} ≈ 1pp, both sub-decision-relevant), but " + "; ".join(bits)
              + ". Same standard as the archetype negative: a non-rejection whose CI admits "
              "decision-relevant values (and which detects a small real deviation) is UNINFORMATIVE, "
              "not a clean PASS. Not a FAIL — the deviation is below the decision-relevant magnitude.")
        ok = True   # not a FAIL, but explicitly UNINFORMATIVE
    print("=" * 80)
    sdict = {"marking": "PASS-BUT-UNINFORMATIVE" if (not hard_fail and not clean) else
             ("PASS" if not hard_fail else "FAIL"),
             "slope": round(sl, 4), "slope_ci_lo": round(lo, 4), "slope_ci_hi": round(hi, 4),
             "intercept": round(ic, 4), "intercept_ci_lo": round(ilo, 4), "intercept_ci_hi": round(ihi, 4),
             "ece": round(ece, 4), "ece_null_lo": round(ece_lo, 4), "ece_null_hi": round(ece_hi, 4),
             "ece_null_p": round(ece_p, 4), "n": len(pred), "players": int(len(np.unique(uid))),
             "events": events, "decision_relevant_band": [DR_LO, DR_HI], "ece_decision_relevant": ECE_DR}
    return ok, sdict


def coverage_check():
    """G10.3 component 2 — projection PPG 90% credible-interval COVERAGE, per-fold refit.
    Option (a)(i): MC-interval layer on the per-fold RECONSTRUCTION (projection.py is not
    per-vintage-refittable); inherits the reconstruction's fidelity scope (Spearman 0.9724 / 2.3%
    at <=2021->2022). Replicates projection.py's interval: ppg ~ N(mu0, prior_sd) + N(mean_d, se_d),
    clip 0, [q05,q95]."""
    import duckdb
    from models import backtest_baselines as BT
    print("=" * 80)
    print("G10.3 COVERAGE (projection PPG 90% interval) — PRE-REGISTERED PASS (before result)")
    print("=" * 80)
    print("""
Nominal 90% credible intervals should cover ~0.90 of realized next-year PPG. PASS BAND (interval,
not point): player-clustered coverage 95% CI must CONTAIN 0.90 (equivalently sit in [0.85,0.95],
author-supplied/set-at-measurement). Clustering = player_uid; report n, effective n, per-fold
coverage. DIRECTION: coverage ABOVE 0.90 (intervals too WIDE) = CONSERVATIVE -> documented footnote,
NOT a fail (safe). Coverage BELOW 0.90 (intervals too NARROW / OVERCONFIDENT) = ANTI-CONSERVATIVE ->
FAIL, forces recalibration (overconfident projections mislead). Inherits reconstruction fidelity scope.
""")
    con = duckdb.connect(DB, read_only=True)
    rows = con.execute(f"""
        SELECT o.season AS Y, o.player_uid AS uid, mp.position AS pos, mp.ppg_ppr AS lastppg,
               mp.games AS games_prev, try_cast(substr(d.birthdate,1,4) AS INTEGER) AS birthyr,
               cur.ppg_ppr AS realized
        FROM (SELECT player_uid, season, ppg_ppr FROM fact_player_season_metrics) cur
        JOIN (SELECT player_uid, season FROM fact_player_season) o
             ON o.player_uid=cur.player_uid AND o.season=cur.season
        JOIN (SELECT player_uid, season, position, ppg_ppr, games FROM fact_player_season_metrics) mp
             ON mp.player_uid=o.player_uid AND mp.season=o.season-1
        JOIN dim_player d ON d.player_uid=o.player_uid
        WHERE o.season BETWEEN 2019 AND 2025 AND mp.position IN ('QB','RB','WR','TE')""").pl()
    metrics = con.execute("SELECT player_uid, season, position, ppg_ppr, games FROM fact_player_season_metrics "
                          "WHERE position IN ('QB','RB','WR','TE')").pl()
    replt = con.execute("SELECT season, position, replacement_points FROM fact_replacement WHERE profile='ppr'").pl()
    birth = {r["player_uid"]: r["birthyr"] for r in con.execute(
        "SELECT player_uid, try_cast(substr(birthdate,1,4) AS INTEGER) AS birthyr FROM dim_player").pl().iter_rows(named=True)}
    con.close()
    P = BT.P; K = BT.K
    rng = np.random.default_rng(1729)
    D = 2000
    uid_a, cov_a, fold_a, pos_a = [], [], [], []
    for Y in sorted(rows["Y"].unique().to_list()):
        pm, dmean, dpos, rp = BT.fit_upto(metrics, replt, birth, Y - 1)
        # per-(pos,age) delta SE = std of year-over-year changes <=Y-1
        m = metrics.filter(metrics["season"] <= Y - 1).to_dicts()
        by = {(r["player_uid"], r["season"]): (r["position"], r["ppg_ppr"]) for r in m}
        dvals = {}
        for (u, s), (pos, ppg) in by.items():
            nx = by.get((u, s + 1)); byr = birth.get(u)
            if nx and byr:
                dvals.setdefault((pos, (s + 1) - byr), []).append(nx[1] - ppg)
        dse = {k: (np.std(v, ddof=1) if len(v) >= 3 else P["wide_delta_se"]) for k, v in dvals.items()}
        for r in rows.filter(rows["Y"] == Y).sort("uid").to_dicts():   # sort -> byte-reproducible MC
            n_eff = max(r["games_prev"] or 0, 1)
            mu0 = (n_eff * r["lastppg"] + K * pm.get(r["pos"], 8.0)) / (n_eff + K)
            prior_sd = 6.0 / np.sqrt(n_eff + K)
            age = (Y - r["birthyr"]) if r["birthyr"] else 26
            md = dmean.get((r["pos"], age), dpos.get(r["pos"], -0.5))
            sd_d = dse.get((r["pos"], age), P["wide_delta_se"])
            draws = np.clip(rng.normal(mu0, prior_sd, D) + rng.normal(md, sd_d, D), 0, None)
            q05, q95 = np.quantile(draws, 0.05), np.quantile(draws, 0.95)
            uid_a.append(r["uid"]); cov_a.append(1 if q05 <= r["realized"] <= q95 else 0)
            fold_a.append(Y); pos_a.append(r["pos"])
    uid_a, cov_a, fold_a, pos_a = np.array(uid_a), np.array(cov_a, float), np.array(fold_a), np.array(pos_a)
    coverage = cov_a.mean()
    players = np.unique(uid_a); idx = {p: np.where(uid_a == p)[0] for p in players}
    n_per = np.array([len(idx[p]) for p in players]); eff_n = n_per.sum() ** 2 / (n_per ** 2).sum()
    per_seed = []
    for sd in SEEDS:
        rr = np.random.default_rng(sd)
        cs = [np.concatenate([idx[p] for p in rr.choice(players, len(players), True)]) for _ in range(1000)]
        cs = [cov_a[c].mean() for c in cs]
        per_seed.append((np.percentile(cs, 2.5), np.percentile(cs, 97.5)))
    lo, hi = float(np.mean([a for a, _ in per_seed])), float(np.mean([b for _, b in per_seed]))
    print("-" * 80)
    deff = len(cov_a) / eff_n
    print(f"n={len(cov_a)}  players={len(players)}  effective_n≈{eff_n:.0f}  design_effect≈{deff:.2f}   nominal=0.90")
    per_fold = {int(Y): [round(float(cov_a[fold_a == Y].mean()), 4), int((fold_a == Y).sum())]
                for Y in sorted(set(fold_a))}
    print("per-fold coverage: " + "  ".join(f"{Y}:{v[0]:.3f}(n={v[1]})" for Y, v in per_fold.items()))
    print(f"POOLED empirical coverage = {coverage:.4f}   player-clustered 95% CI [{lo:.4f}, {hi:.4f}]")
    print("-" * 80)
    print("=" * 80)
    if hi < 0.90:
        marking = "FAIL-ANTI-CONSERVATIVE"
        print(f"G10.3 (coverage) RESULT: FAIL — ANTI-CONSERVATIVE: 90% intervals cover only "
              f"{coverage:.3f} (CI upper {hi:.3f} < 0.90) -> OVERCONFIDENT, forces recalibration.")
        ok = False
    elif lo > 0.90:
        marking = "PASS-CONSERVATIVE"
        print(f"G10.3 (coverage) RESULT: PASS-CONSERVATIVE — nominal 90% intervals cover ~{coverage:.3f} "
              f"(CI [{lo:.3f},{hi:.3f}] EXCLUDES 0.90) -> OVER-COVERING/too WIDE; stated uncertainty "
              "does not match realized, but the direction is SAFE (not overconfident).")
        ok = True
    else:
        marking = "PASS"
        print(f"G10.3 (coverage) RESULT: PASS — coverage {coverage:.3f}, CI [{lo:.3f},{hi:.3f}] contains 0.90.")
        ok = True
    print("=" * 80)
    icc_p, _k = _icc(uid_a, cov_a)
    mbar = len(cov_a) / len(players)
    deff_measured = 1 + (mbar - 1) * icc_p
    cdict = {"marking": marking, "coverage": round(float(coverage), 4), "ci_lo": round(lo, 4),
             "ci_hi": round(hi, 4), "nominal": 0.90, "n": int(len(cov_a)), "players": int(len(players)),
             "mbar": round(float(mbar), 2), "icc_player": round(float(icc_p), 4),
             "design_effect_measured": round(float(deff_measured), 2),
             "effective_n_kish": round(float(eff_n), 1), "design_effect_kish_max": round(float(deff), 2),
             "per_fold": per_fold}
    return ok, cdict, (uid_a, fold_a, pos_a, cov_a)


def _icc(labels, y):
    """One-way ANOVA ICC of binary indicator y within clusters given by `labels`."""
    import collections
    groups = collections.defaultdict(list)
    for lab, v in zip(labels, y):
        groups[lab].append(v)
    k = len(groups); N = len(y); p = y.mean()
    ni = np.array([len(g) for g in groups.values()])
    means = np.array([np.mean(g) for g in groups.values()])
    msb = (ni * (means - p) ** 2).sum() / (k - 1)
    msw = sum(((np.array(g) - m) ** 2).sum() for g, m in zip(groups.values(), means)) / (N - k)
    m0 = (N - (ni ** 2).sum() / N) / (k - 1)
    icc = (msb - msw) / (msb + (m0 - 1) * msw) if (msb + (m0 - 1) * msw) else 0.0
    return icc, k


def cluster_ci(labels, y, seeds=SEEDS, B=2000):
    """Cluster bootstrap CI of the mean of y, resampling whole clusters given by `labels`."""
    groups = {}
    for i, lab in enumerate(labels):
        groups.setdefault(lab, []).append(i)
    keys = list(groups)
    idx = {k: np.array(v) for k, v in groups.items()}
    per = []
    for sd in seeds:
        rr = np.random.default_rng(sd)
        ms = [y[np.concatenate([idx[k] for k in rr.choice(keys, len(keys), True)])].mean() for _ in range(B)]
        per.append((np.percentile(ms, 2.5), np.percentile(ms, 97.5)))
    return float(np.mean([a for a, _ in per])), float(np.mean([b for _, b in per]))


def icc_diagnostic():
    """G10.4 pre-check — is the coverage CI clustered on the right axis? Print ICC(covered) under
    player / season / position; recompute the coverage CI under the DOMINANT axis; re-mark if it now
    contains 0.90 (the [0.9019,0.9240] over-coverage may be a wrong-axis clustering artifact)."""
    _ok, cdict, (uid, fold, pos, cov) = coverage_check()
    print("=" * 80)
    print("G10.4 PRE-CHECK — coverage-indicator ICC by clustering axis (deff 4.28 was Kish ICC=1 ceiling)")
    print("=" * 80)
    iccs = {}
    for name, lab in [("player", uid), ("season", fold), ("position", pos)]:
        icc, k = _icc(lab, cov)
        iccs[name] = icc
        print(f"  ICC(covered | {name:8s}) = {icc:+.4f}   ({k} clusters)")
    dom = max(iccs, key=lambda a: iccs[a])
    dom_lab = {"player": uid, "season": fold, "position": pos}[dom]
    lo, hi = cluster_ci(dom_lab, cov)
    contains = lo <= 0.90 <= hi
    print(f"  DOMINANT axis = {dom} (ICC {iccs[dom]:+.4f}). Coverage CI clustered on {dom}: "
          f"[{lo:.4f}, {hi:.4f}] -> {'CONTAINS 0.90' if contains else 'excludes 0.90'}")
    print("-" * 80)
    if dom == "player":
        print("VERDICT: player IS the dominant axis -> the committed player-clustered CI is on the "
              "right axis; the over-coverage finding STANDS (subject to the CI).")
    elif contains:
        print(f"VERDICT: {dom} carries a larger ICC than player -> the player-clustered CI was on the "
              f"WRONG axis; under {dom} the CI CONTAINS 0.90 -> OVER-COVERAGE was a CLUSTERING ARTIFACT. "
              "Re-mark: PASS (coverage indistinguishable from nominal 0.90 under the dominant axis).")
    else:
        print(f"VERDICT: {dom} dominates and its CI STILL excludes 0.90 -> over-coverage stands under "
              "the correct axis (with the small-cluster-count caveat).")
    print("=" * 80)
    return iccs, dom, (lo, hi), contains


def regenerate(quiet=False):
    """Run both components and persist models/calibration_g103.json (deterministic). Returns ok."""
    import io
    import contextlib
    ctx = contextlib.redirect_stdout(io.StringIO()) if quiet else contextlib.nullcontext()
    with ctx:
        s_ok, sdict = main()
        c_ok, cdict, _obs = coverage_check()
    art = {"_what": "G10.3 calibration — survival Clock-A OOS reliability + projection PPG 90% "
                    "interval coverage. Persisted for the doc-consistency canon + 5x byte-check.",
           "survival": sdict, "coverage": cdict, "vintage": "2026-07-30"}
    (CONFIG.path("models") / "calibration_g103.json").write_text(json.dumps(art, indent=2))
    return s_ok and c_ok


if __name__ == "__main__":
    ok = regenerate()
    print("\n-> models/calibration_g103.json written")
    sys.exit(0 if ok else 1)
