"""G10.2 item-1 — MEASURE reconstruction fidelity (do not assert it).

Score projection.py's actual project_player() and the backtest deterministic-core reconstruction
on the SAME players, SAME target season (2025 outcome, 2024 base), MATCHED full-window fit for
both. Print AUC of each, Spearman rank correlation between the two score vectors, mean/max abs
diff, and the count of players whose per-position top-12 classification differs.
"""
from __future__ import annotations
import duckdb
import numpy as np
from sklearn.metrics import roc_auc_score
from config import CONFIG
from models import projection as PJ
from models import backtest_baselines as BT

DB = str(CONFIG.path("warehouse"))


def main():
    con = duckdb.connect(DB, read_only=True)
    df = con.execute("""
        SELECT o.player_uid AS uid, m.position AS pos, m.ppg_ppr AS ppg24, m.games AS g24,
               try_cast(substr(d.birthdate,1,4) AS INTEGER) AS birthyr,
               (o.pos_finish_ppr<=12)::INT AS target
        FROM (SELECT player_uid, pos_finish_ppr FROM fact_player_season WHERE season=2025) o
        JOIN (SELECT player_uid, position, ppg_ppr, games FROM fact_player_season_metrics
              WHERE season=2024) m USING(player_uid)
        JOIN dim_player d USING(player_uid)
        WHERE m.position IN ('QB','RB','WR','TE')
    """).pl()
    # projection.py inputs (full-window fit)
    pos_mean = {r["position"]: r["repl_ppg"] for r in PJ.con_free()}
    repl = {r["position"]: r["v"] for r in con.execute(
        "SELECT position, avg(replacement_points) v FROM fact_replacement "
        "WHERE profile='ppr' AND season>=2022 GROUP BY position").pl().iter_rows(named=True)}
    inj = {r["player_uid"]: r["inj"] for r in con.execute(
        "SELECT player_uid, count(*) inj FROM fact_injury WHERE report_status IN ('Out','Doubtful') "
        "GROUP BY player_uid").pl().iter_rows(named=True)}
    deltas = PJ._delta_lookup()
    # reconstruction inputs (full-window fit, matched)
    metrics = con.execute("SELECT player_uid, season, position, ppg_ppr, games "
                          "FROM fact_player_season_metrics WHERE position IN ('QB','RB','WR','TE')").pl()
    replt = con.execute("SELECT season, position, replacement_points FROM fact_replacement "
                        "WHERE profile='ppr'").pl()
    birth = {r["player_uid"]: r["birthyr"] for r in con.execute(
        "SELECT player_uid, try_cast(substr(birthdate,1,4) AS INTEGER) AS birthyr FROM dim_player"
        ).pl().iter_rows(named=True)}
    con.close()
    pm2, d2, dp2, rp2 = BT.fit_upto(metrics, replt, birth, 2025)   # full-window

    proj, recon, tgt, uids, poss = [], [], [], [], []
    for r in df.to_dicts():
        age = (2025 - r["birthyr"]) if r["birthyr"] else 26
        prow = {"position": r["pos"], "age": age, "ppg_ppr": r["ppg24"], "games": r["g24"]}
        pj = PJ.project_player(prow, pos_mean, repl, deltas, inj.get(r["uid"], 0))[1]["vorp_mean"]
        rc = BT.score_model({"pos": r["pos"], "games_prev": r["g24"], "lastppg": r["ppg24"],
                             "Y": 2025, "uid": r["uid"]}, birth, pm2, d2, dp2, rp2)
        proj.append(pj); recon.append(rc); tgt.append(r["target"]); uids.append(r["uid"]); poss.append(r["pos"])
    proj = np.array(proj); recon = np.array(recon); tgt = np.array(tgt); poss = np.array(poss)

    auc_p = roc_auc_score(tgt, proj); auc_r = roc_auc_score(tgt, recon)
    # Spearman via rank correlation
    rp = np.argsort(np.argsort(proj)); rr = np.argsort(np.argsort(recon))
    spearman = np.corrcoef(rp, rr)[0, 1]
    absd = np.abs(proj - recon)
    # per-position top-12 classification by each score; count disagreements
    def top12_flags(scores):
        flag = np.zeros(len(scores), dtype=int)
        for p in np.unique(poss):
            idx = np.where(poss == p)[0]
            order = idx[np.argsort(-scores[idx])][:12]
            flag[order] = 1
        return flag
    fp, fr = top12_flags(proj), top12_flags(recon)
    differ = int((fp != fr).sum())

    print("=" * 78)
    print("G10.2 ITEM 1 — RECONSTRUCTION FIDELITY (measured, matched full-window fit, 2025 target)")
    print("=" * 78)
    print(f"n players scored by both = {len(proj)}  (events={int(tgt.sum())}, base={tgt.mean():.4f})")
    print(f"AUC  projection.py        = {auc_p:.4f}")
    print(f"AUC  reconstruction       = {auc_r:.4f}   (ΔAUC recon-proj = {auc_r-auc_p:+.4f})")
    print(f"Spearman rank corr(scores)= {spearman:.4f}")
    print(f"mean |proj - recon|       = {absd.mean():.4f}")
    print(f"max  |proj - recon|       = {absd.max():.4f}")
    print(f"per-position top-12 classification DIFFERS for {differ} / {len(proj)} players "
          f"({differ/len(proj)*100:.1f}%)")
    established = spearman >= 0.95 and differ / len(proj) <= 0.05
    print("-" * 78)
    print(f"FIDELITY {'ESTABLISHED' if established else 'NOT ESTABLISHED'} "
          f"(criterion: Spearman>=0.95 AND top-12 disagreement<=5%).")
    if not established:
        print("=> G10.2's FAILS-BAR is a finding about the RECONSTRUCTION, and the verdict must say so.")
    return established


def truncated(fit_upto_year=2021, score_year=2022):
    """Item 4a — fidelity under a TRUNCATED (per-fold-like) fit: both projection.py and the
    reconstruction fit on <=fit_upto_year, score score_year. Establishes per-fold-refit fidelity."""
    con = duckdb.connect(DB, read_only=True)
    df = con.execute(f"""
        SELECT o.player_uid AS uid, m.position AS pos, m.ppg_ppr AS ppg, m.games AS g,
               try_cast(substr(d.birthdate,1,4) AS INTEGER) AS birthyr,
               (o.pos_finish_ppr<=12)::INT AS target
        FROM (SELECT player_uid, pos_finish_ppr FROM fact_player_season WHERE season={score_year}) o
        JOIN (SELECT player_uid, position, ppg_ppr, games FROM fact_player_season_metrics
              WHERE season={score_year-1}) m USING(player_uid)
        JOIN dim_player d USING(player_uid) WHERE m.position IN ('QB','RB','WR','TE')""").pl()
    metrics = con.execute("SELECT player_uid, season, position, ppg_ppr, games "
                          "FROM fact_player_season_metrics WHERE position IN ('QB','RB','WR','TE')").pl()
    replt = con.execute("SELECT season, position, replacement_points FROM fact_replacement WHERE profile='ppr'").pl()
    birth = {r["player_uid"]: r["birthyr"] for r in con.execute(
        "SELECT player_uid, try_cast(substr(birthdate,1,4) AS INTEGER) AS birthyr FROM dim_player"
        ).pl().iter_rows(named=True)}
    con.close()
    # TRUNCATED projection.py inputs (<=fit_upto_year): pos_mean, repl, deltas keyed (pos, from_age)
    m = metrics.filter(metrics["season"] <= fit_upto_year).to_dicts()
    pm_n, pm_d, by_ps = {}, {}, {}
    for r in m:
        if r["games"] and r["games"] >= 8:
            pm_n[r["position"]] = pm_n.get(r["position"], 0.0) + r["ppg_ppr"]; pm_d[r["position"]] = pm_d.get(r["position"], 0) + 1
        by_ps[(r["player_uid"], r["season"])] = (r["position"], r["ppg_ppr"], r["games"])
    pos_mean = {p: pm_n[p] / pm_d[p] for p in pm_n}
    dn, dd = {}, {}
    for (uid, s), (pos, ppg, g) in by_ps.items():
        nxt = by_ps.get((uid, s + 1)); byr = birth.get(uid)
        if nxt and byr and (s + 1) <= fit_upto_year:
            fa = s - byr
            dn[(pos, fa)] = dn.get((pos, fa), 0.0) + (nxt[1] - ppg); dd[(pos, fa)] = dd.get((pos, fa), 0) + 1
    proj_deltas = {k: (dn[k] / dd[k], PJ.P["wide_delta_se"]) for k in dn}   # (pos,from_age)->(mean,se)
    rn, rd = {}, {}
    for r in replt.filter(replt["season"] <= fit_upto_year).to_dicts():
        rn[r["position"]] = rn.get(r["position"], 0.0) + r["replacement_points"]; rd[r["position"]] = rd.get(r["position"], 0) + 1
    repl = {p: rn[p] / rd[p] for p in rn}
    pm2, d2, dp2, rp2 = BT.fit_upto(metrics, replt, birth, fit_upto_year)   # reconstruction, matched
    proj, recon, tgt, poss = [], [], [], []
    for r in df.to_dicts():
        age = (score_year - r["birthyr"]) if r["birthyr"] else 26
        pj = PJ.project_player({"position": r["pos"], "age": age, "ppg_ppr": r["ppg"], "games": r["g"]},
                               pos_mean, repl, proj_deltas, 0)[1]["vorp_mean"]
        rc = BT.score_model({"pos": r["pos"], "games_prev": r["g"], "lastppg": r["ppg"],
                             "Y": score_year, "uid": r["uid"]}, birth, pm2, d2, dp2, rp2)
        proj.append(pj); recon.append(rc); tgt.append(r["target"]); poss.append(r["pos"])
    proj, recon, tgt, poss = np.array(proj), np.array(recon), np.array(tgt), np.array(poss)
    rp, rr = np.argsort(np.argsort(proj)), np.argsort(np.argsort(recon))
    sp = np.corrcoef(rp, rr)[0, 1]
    def t12(sc):
        f = np.zeros(len(sc), dtype=int)
        for p in np.unique(poss):
            idx = np.where(poss == p)[0]; f[idx[np.argsort(-sc[idx])][:12]] = 1
        return f
    differ = int((t12(proj) != t12(recon)).sum())
    print("=" * 78)
    print(f"ITEM 4a — TRUNCATED-WINDOW FIDELITY (fit <={fit_upto_year}, score {score_year}; n={len(proj)})")
    print(f"  Spearman rank corr = {sp:.4f}   top-12 disagreement = {differ}/{len(proj)} "
          f"({differ/len(proj)*100:.1f}%)   -> per-fold-refit fidelity "
          f"{'HOLDS' if sp>=0.95 and differ/len(proj)<=0.05 else 'DEGRADES'}")


def insample_gap():
    """Item 5 — isolate optimism: reconstruction full-window (in-sample) AUC on the SAME 1454
    backtest population, vs the per-fold pooled OOS AUC (0.7179)."""
    rows, metrics, repl, birth = BT.load()
    pm, d, dp, rp = BT.fit_upto(metrics, repl, birth, 2025)   # full window = in-sample
    sc, tg = [], []
    for row in rows.to_dicts():
        sc.append(BT.score_model({"pos": row["pos"], "games_prev": row["games_prev"], "lastppg": row["lastppg"],
                                  "Y": row["Y"], "uid": row["uid"]}, birth, pm, d, dp, rp))
        tg.append(row["target"])
    auc_is = roc_auc_score(np.array(tg), np.array(sc))
    print("=" * 78)
    print("ITEM 5 — IN-SAMPLE vs OUT-OF-SAMPLE optimism (SAME 1454 population)")
    print(f"  full-window in-sample AUC = {auc_is:.4f}   per-fold pooled OOS AUC = 0.7179   "
          f"optimism gap = {auc_is-0.7179:+.4f}")
    print(f"  (the 571-population full-window AUC 0.8868 is HIGHER due to a DIFFERENT, lower-base-rate "
          f"population; same-population optimism is the {auc_is-0.7179:+.4f} above, not the 0.17 headline gap)")


if __name__ == "__main__":
    main()
    truncated()
    insample_gap()
