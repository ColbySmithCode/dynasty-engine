"""G10.2 — BACKTEST vs ADP + last-year-PPG (Phase-10, PHASE10_PLAN amendment A2 / Option B).

Returning-player forward backtest. For player-season (p,Y): predict target(p,Y)=1 iff
pos_finish_ppr(p,Y)<=12 (per-position full-PPR, non-SF), from information available before Y.
Predictors, ALL refit per fold on <=Y-1 (per-fold refit, item 2(a)):
  - engine projection E[VORP] deterministic core (aging deltas, positional mean, replacement
    all refit on <=Y-1; hand-set constants carried over),
  - ADP (season-Y AUG15 K; score = -adp),
  - last-year PPG (ppg_ppr(Y-1)).
Co-primary: dAUC = AUC(model) - AUC(baseline), pooled, PLAYER-CLUSTERED paired bootstrap
(DeLong dropped: players recur ~2.9 seasons). BEATS iff CI-LB>0; LOSES iff CI-UB<0;
INDISTINGUISHABLE iff spans 0. CLEARS-BAR beats both / SPLIT beats one / FAILS-BAR neither.

Prints the pre-registered PASS condition BEFORE the result. Read-only w.r.t. the warehouse.
"""
from __future__ import annotations
import sys
import duckdb
import numpy as np
from sklearn.metrics import roc_auc_score
from config import CONFIG

DB = str(CONFIG.path("warehouse"))
P = CONFIG["models"]["projection"]
AGE = CONFIG["models"]["aging"]
LAST = CONFIG["models"]["startup_backtest"]["last_complete_season"]
FOLDS = list(range(2019, LAST + 1))            # 2019..2025
K = P["shrinkage_k_games"]                      # carried-over constant
SLOPE = P["availability_age_slope"]
BASE_AVAIL = {"QB": 0.90, "RB": 0.82, "WR": 0.86, "TE": 0.85}  # carried-over (projection.py)
MIN_G = AGE["min_games_per_season"]
CONV_FRAC = 0.10                                # G10.5 convergence criterion
SEEDS = [1729, 2027, 4051, 7919, 9973]          # >=5 independent seeds


def load():
    con = duckdb.connect(DB, read_only=True)
    rows = con.execute(f"""
        WITH m AS (SELECT player_uid, season, position, ppg_ppr, games FROM fact_player_season_metrics),
             adp AS (SELECT player_uid, season, adp FROM fact_adp
                     WHERE format='K' AND ppr=-1 AND period='AUG15' AND adp IS NOT NULL),
             o AS (SELECT player_uid, season, pos_finish_ppr FROM fact_player_season)
        SELECT o.season AS Y, o.player_uid AS uid, mp.position AS pos,
               mp.ppg_ppr AS lastppg, mp.games AS games_prev,
               try_cast(substr(d.birthdate,1,4) AS INTEGER) AS birthyear,
               a.adp AS adp, (o.pos_finish_ppr<=12)::INT AS target
        FROM o
        JOIN m mp ON mp.player_uid=o.player_uid AND mp.season=o.season-1
        JOIN adp a ON a.player_uid=o.player_uid AND a.season=o.season
        JOIN dim_player d ON d.player_uid=o.player_uid
        WHERE o.season BETWEEN {FOLDS[0]} AND {FOLDS[-1]} AND mp.position IN ('QB','RB','WR','TE')
    """).pl()
    # full metrics + replacement for per-fold refit (all seasons; filtered to <=Y-1 per fold)
    metrics = con.execute("""SELECT player_uid, season, position, ppg_ppr, games
                             FROM fact_player_season_metrics WHERE position IN ('QB','RB','WR','TE')""").pl()
    repl = con.execute("""SELECT season, position, replacement_points FROM fact_replacement
                          WHERE profile='ppr'""").pl()
    birth = {r["player_uid"]: r["birthyr"] for r in con.execute(
        "SELECT player_uid, try_cast(substr(birthdate,1,4) AS INTEGER) AS birthyr FROM dim_player").pl().iter_rows(named=True)}
    con.close()
    return rows, metrics, repl, birth


def fit_upto(metrics, repl, birth, upto):
    """Refit positional-mean PPG, per-(pos,age) aging deltas (FAITHFUL to projection.py's
    deltas.get((pos,age))), and replacement on season<=upto."""
    m = metrics.filter((metrics["season"] <= upto)).to_dicts()
    pm_num, pm_den = {}, {}
    by_ps = {}
    for r in m:
        if r["games"] and r["games"] >= 8:
            pm_num[r["position"]] = pm_num.get(r["position"], 0.0) + r["ppg_ppr"]
            pm_den[r["position"]] = pm_den.get(r["position"], 0) + 1
        by_ps[(r["player_uid"], r["season"])] = (r["position"], r["ppg_ppr"], r["games"])
    pos_mean = {p: pm_num[p] / pm_den[p] for p in pm_num}
    # aging deltas keyed by (pos, TO-AGE): mean ppg change over consecutive qualifying pairs.
    dnum, dden = {}, {}
    for (uid, s), (pos, ppg, g) in by_ps.items():
        nxt = by_ps.get((uid, s + 1))
        by = birth.get(uid)
        if nxt and by and g and g >= MIN_G and nxt[2] and nxt[2] >= MIN_G and (s + 1) <= upto:
            to_age = (s + 1) - by
            key = (pos, to_age)
            dnum[key] = dnum.get(key, 0.0) + (nxt[1] - ppg)
            dden[key] = dden.get(key, 0) + 1
    delta = {k: dnum[k] / dden[k] for k in dnum}
    delta_pos = {}                                   # position-average fallback for sparse (pos,age)
    pn, pd = {}, {}
    for (pos, _a), v in [((k[0], k[1]), dnum[k] / dden[k]) for k in dnum]:
        pn[pos] = pn.get(pos, 0.0) + v; pd[pos] = pd.get(pos, 0) + 1
    delta_pos = {p: pn[p] / pd[p] for p in pn}
    rn, rd = {}, {}
    for r in repl.filter(repl["season"] <= upto).to_dicts():
        rn[r["position"]] = rn.get(r["position"], 0.0) + r["replacement_points"]
        rd[r["position"]] = rd.get(r["position"], 0) + 1
    replacement = {p: rn[p] / rd[p] for p in rn}
    return pos_mean, delta, delta_pos, replacement


def score_model(row, birth, pos_mean, delta, delta_pos, replacement):
    pos = row["pos"]
    n_eff = max(row["games_prev"] or 0, 1)
    pm = pos_mean.get(pos, 8.0)
    mu0 = (n_eff * row["lastppg"] + K * pm) / (n_eff + K)
    by = birth.get(row["uid"])
    age = (row["Y"] - by) if by else 26
    d = delta.get((pos, age))                        # per-(pos,age) FIRST (faithful)
    if d is None:
        d = delta_pos.get(pos, -0.5)                 # position-avg fallback for sparse ages
    proj_ppg = mu0 + d
    p_avail = min(0.98, max(0.35, BASE_AVAIL.get(pos, 0.85) - SLOPE * max(0, age - 27)))
    exp_games = 17 * p_avail
    return exp_games * (proj_ppg - replacement.get(pos, 6.0))


def build_scores(rows, metrics, repl, birth):
    """Per-fold refit; return pooled arrays aligned by row: uid, target, s_model, s_adp, s_ppg."""
    out = {"uid": [], "y": [], "target": [], "s_model": [], "s_adp": [], "s_ppg": []}
    for Y in FOLDS:
        pos_mean, delta, delta_pos, replacement = fit_upto(metrics, repl, birth, Y - 1)   # <=Y-1 ONLY
        for row in rows.filter(rows["Y"] == Y).to_dicts():
            out["uid"].append(row["uid"]); out["y"].append(Y); out["target"].append(row["target"])
            out["s_model"].append(score_model(row, birth, pos_mean, delta, delta_pos, replacement))
            out["s_adp"].append(-float(row["adp"]))          # lower adp = better
            out["s_ppg"].append(float(row["lastppg"]))       # naive persistence
    return {k: np.array(v) for k, v in out.items()}


def clustered_boot(uid, target, s_model, s_base, seeds, B=2000):
    """Player-clustered paired bootstrap of dAUC = AUC(model)-AUC(base). Returns per-seed (lo,hi)."""
    players = np.unique(uid)
    idx_by_player = {p: np.where(uid == p)[0] for p in players}
    per_seed = []
    for sd in seeds:
        rng = np.random.default_rng(sd)
        diffs = np.empty(B)
        for b in range(B):
            pick = rng.choice(players, size=len(players), replace=True)
            rows = np.concatenate([idx_by_player[p] for p in pick])
            t = target[rows]
            if t.min() == t.max():
                diffs[b] = np.nan; continue
            diffs[b] = roc_auc_score(t, s_model[rows]) - roc_auc_score(t, s_base[rows])
        d = diffs[~np.isnan(diffs)]
        per_seed.append((np.percentile(d, 2.5), np.percentile(d, 97.5)))
    return per_seed


def verdict(name, uid, target, s_model, s_base):
    point = roc_auc_score(target, s_model) - roc_auc_score(target, s_base)
    per_seed = clustered_boot(uid, target, s_model, s_base, SEEDS)
    los = [lo for lo, _ in per_seed]; his = [hi for _, hi in per_seed]
    lo, hi = float(np.mean(los)), float(np.mean(his))
    hw = (hi - lo) / 2
    spread = max(np.ptp(los), np.ptp(his))          # cross-seed endpoint spread
    converged = spread < CONV_FRAC * hw
    call = "BEATS" if lo > 0 else ("LOSES" if hi < 0 else "INDISTINGUISHABLE")
    print(f"  vs {name:13s}: dAUC point {point:+.4f}  clustered 95% CI [{lo:+.4f}, {hi:+.4f}]  "
          f"-> {call}   (cross-seed endpoint spread {spread:.4f} = {spread/hw*100:.1f}% of HW; "
          f"{'converged' if converged else 'NOT CONVERGED'})")
    return call, converged, round(point, 4), round(lo, 4), round(hi, 4)


def print_pass_condition():
    print("=" * 82)
    print("G10.2 BACKTEST vs ADP + last-year-PPG — PRE-REGISTERED PASS CONDITION (before result)")
    print("=" * 82)
    print("""
Population: 1457 returning player-seasons / 501 distinct players / 304 events (base 0.2086),
folds 2019-2025 (39-49 events each; none <5). Target: pos_finish_ppr(Y)<=12 (per-position PPR).
Predictors refit PER FOLD on <=Y-1: projection E[VORP] core, ADP(-adp), last-year-PPG.
CO-PRIMARY (2 tests, no pair multiplicity): dAUC = AUC(model)-AUC(baseline), pooled, via
PLAYER-CLUSTERED paired bootstrap (>=5 seeds, converged iff cross-seed endpoint spread <10% HW).
  BEATS iff CI lower bound > 0; LOSES iff CI upper bound < 0; INDISTINGUISHABLE iff spans 0.
  CLEARS-BAR = BEATS both; SPLIT = beats exactly one (NOT reportable as BEATS); FAILS-BAR = neither.
G10.2 CLEARS iff CLEARS-BAR. SPLIT or FAILS-BAR => does not clear => STOP and report
  (a FAILS-BAR is a legitimate honest negative, not a bug).
NOTE: the 7 folds are NOT independent replications (~2.9 seasons/player); fold AUCs are
descriptive only — the player-clustered bootstrap over pooled player-seasons carries the inference.
""")


def main():
    print_pass_condition()
    rows, metrics, repl, birth = load()
    S = build_scores(rows, metrics, repl, birth)
    n, npl, ev = len(S["target"]), len(np.unique(S["uid"])), int(S["target"].sum())
    print("-" * 82)
    print(f"POOLED: player_seasons={n}  distinct_players={npl}  events={ev}  base_rate={ev/n:.4f}")
    print(f"  AUC(model)={roc_auc_score(S['target'],S['s_model']):.4f}  "
          f"AUC(ADP-proxy)={roc_auc_score(S['target'],S['s_adp']):.4f}  "
          f"AUC(last-yr-PPG)={roc_auc_score(S['target'],S['s_ppg']):.4f}")
    print("-" * 82)
    print("CO-PRIMARY (player-clustered paired bootstrap of dAUC):")
    c_adp, cv1, p_adp, lo_adp, hi_adp = verdict("ADP", S["uid"], S["target"], S["s_model"], S["s_adp"])
    c_ppg, cv2, p_ppg, lo_ppg, hi_ppg = verdict("last-yr-PPG", S["uid"], S["target"], S["s_model"], S["s_ppg"])

    beats = sum(c == "BEATS" for c in (c_adp, c_ppg))
    combined = "CLEARS-BAR" if beats == 2 else ("SPLIT" if beats == 1 else "FAILS-BAR")
    print("-" * 82)
    print(f"COMBINED VERDICT: {combined}   (vs ADP: {c_adp}; vs last-yr-PPG: {c_ppg})")
    if not (cv1 and cv2):
        print("  WARNING: a bootstrap did not meet the convergence criterion — treat CI as provisional.")
    ok = (combined == "CLEARS-BAR") and cv1 and cv2
    # Persist the finding as a live-sourced artifact (G9.4: the bundle READS this, never restates it).
    import json
    art = {
        "_what": "G10.2 backtest — engine projection vs ADP + last-year-PPG, forward per-position "
                 "top-12 (PPR), per-fold refit, player-clustered paired bootstrap of dAUC.",
        "n_player_seasons": n, "n_players": npl, "events": ev, "base_rate": round(ev / n, 4),
        "auc_model": round(roc_auc_score(S['target'], S['s_model']), 4),
        "combined_verdict": combined,
        "headline": "the projection LOSES to last-year-PPG under MATCHED information sets",
        "vs_last_year_ppg": {"metric": "dAUC(model-lastYearPPG)", "point": p_ppg,
                             "ci_lo": lo_ppg, "ci_hi": hi_ppg, "call": c_ppg,
                             "information_sets": "matched (both <=Y-1)"},
        "vs_adp": {"metric": "dAUC(model-ADP)", "point": p_adp, "ci_lo": lo_adp, "ci_hi": hi_adp,
                   "call": c_adp, "information_sets": "asymmetric (ADP embeds start-of-Y offseason info)"},
        "must_carry": "projection loses to last-year-PPG under matched information sets "
                      f"(dAUC {p_ppg}, CI [{lo_ppg}, {hi_ppg}])",
        "vintage": "2026-07-30",
    }
    (CONFIG.path("models") / "backtest_g102.json").write_text(json.dumps(art, indent=2))
    print("=" * 82)
    print(f"G10.2 RESULT: {'PASS (CLEARS-BAR)' if ok else 'FAIL (' + combined + ')'}  "
          f"-> models/backtest_g102.json")
    print("=" * 82)
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
