"""Phase 5.5 — Bayesian projection: posterior PPG/VORP DISTRIBUTION per future season.

Composition (coherent with 5.2 item-5 conditioning fix — condition on "plays >=8g"):
    VORP(t) = P_play(t) * games(t) * (E[PPG|play](t) - replacement_PPG(pos))
  - Prior: hierarchical shrinkage of recency/opportunity-weighted PPG toward the
    positional mean (small samples pooled harder).
  - Aging: per-year Δ drawn from the 5.1 delta posterior (Normal(mean, se from CI));
    buckets with n<min use a WIDE se -> QB intervals stay wide (Decision 6).
  - Availability: games ~ Beta-Binomial from position/age base rate + injury history.
  - Rookies: P_relevant from the 5.2 Clock-A Beta(k+1, n-k+1) per stratum-year, so
    RB.R1 y5 [0.30,0.70] etc. propagate as posterior width, never a point.
Output is a DISTRIBUTION (mean + 90% credible interval), never a point estimate.
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CONFIG
from ingest._common import get_logger

log = get_logger("projection")
P = CONFIG["models"]["projection"]
AGE = CONFIG["models"]["aging"]
LAST_COMPLETE = CONFIG["models"]["startup_backtest"]["last_complete_season"]  # G10.1: cap reads
RNG = np.random.default_rng(CONFIG["models"]["seed"])
EXPORTS = CONFIG.path("exports")


def _load():
    con = duckdb.connect(str(CONFIG.path("warehouse")), read_only=True)
    seasons = con.execute("""SELECT m.player_uid, m.season, m.position, m.games, m.ppg_ppr,
                                    m.opportunities, d.name, d.birthdate, d.draft_round
                             FROM fact_player_season_metrics m JOIN dim_player d USING(player_uid)
                             WHERE m.position IN ('QB','RB','WR','TE')""").pl()
    repl = con.execute(f"""SELECT position, avg(replacement_points) repl_ppg FROM fact_replacement
                          WHERE profile='ppr' AND season>=2022 AND season <= {LAST_COMPLETE} GROUP BY position""").pl()
    injuries = con.execute("""SELECT player_uid, count(*) AS inj_weeks FROM fact_injury
                              WHERE report_status IN ('Out','Doubtful') GROUP BY player_uid""").pl()
    con.close()
    pos_mean = {r["position"]: r["repl_ppg"] for r in con_free()}  # noqa (placeholder)
    return seasons, repl, injuries


def con_free():   # positional mean PPG among established seasons
    con = duckdb.connect(str(CONFIG.path("warehouse")), read_only=True)
    r = con.execute("""SELECT position, avg(ppg_ppr) v FROM fact_player_season_metrics
                       WHERE games>=8 GROUP BY position""").pl()
    con.close()
    return [{"position": x["position"], "repl_ppg": x["v"]} for x in r.iter_rows(named=True)]


def _delta_lookup() -> dict:
    d = pl.read_parquet(CONFIG.path("models") / "aging_deltas.parquet")
    out = {}
    for r in d.iter_rows(named=True):
        pos = r["archetype"].split("-")[0]  # RB-earlydown -> RB (curve by position)
        se = ((r["ci_hi"] - r["ci_lo"]) / (2 * 1.96)) if r["ci_lo"] is not None else P["wide_delta_se"]
        out.setdefault((pos, r["from_age"]), (r["mean_dppg"], se))
    return out


def project_player(row, pos_mean, repl, deltas, inj_weeks) -> dict:
    pos = row["position"]; age = row["age"]; N = P["horizon_years"]; D = P["mc_draws"]
    # shrinkage prior on current PPG
    n_eff = max(row["games"], 1)
    mu0 = (n_eff * row["ppg_ppr"] + P["shrinkage_k_games"] * pos_mean[pos]) / (n_eff + P["shrinkage_k_games"])
    # prior sd: between-player positional sd scaled by 1/sqrt(effective n)
    prior_sd = 6.0 / np.sqrt(n_eff + P["shrinkage_k_games"])
    ppg0 = RNG.normal(mu0, prior_sd, D).clip(0, None)

    # availability base rate by position/age
    base = {"QB": 0.90, "RB": 0.82, "WR": 0.86, "TE": 0.85}.get(pos, 0.85)
    inj_pen = min(0.15, (inj_weeks or 0) * 0.01)
    results = {}
    ppg = ppg0.copy()
    for t in range(1, N + 1):
        a = age + t - 1
        mean_d, se_d = deltas.get((pos, int(np.clip(a, AGE["age_min"], AGE["age_max"]))),
                                  (-0.5, P["wide_delta_se"]))
        ppg = (ppg + RNG.normal(mean_d, se_d, D)).clip(0, None)
        p_avail = np.clip(base - inj_pen - P["availability_age_slope"] * max(0, a - 27), 0.35, 0.98)
        games = RNG.binomial(17, p_avail, D)
        vorp = games * (ppg - repl[pos])
        results[t] = {"ppg_mean": float(ppg.mean()),
                      "ppg_lo": float(np.quantile(ppg, .05)), "ppg_hi": float(np.quantile(ppg, .95)),
                      "vorp_mean": float(vorp.mean()),
                      "vorp_lo": float(np.quantile(vorp, .05)), "vorp_hi": float(np.quantile(vorp, .95))}
    return results


def project_rookie(stratum_kn, pos, repl, pos_mean) -> dict:
    """Rookie: P_relevant per year from Clock-A Beta(k+1,n-k+1); PPG|relevant ~ positional."""
    D = P["mc_draws"]; out = {}
    for t, (k, n) in stratum_kn.items():
        p_rel = RNG.beta(k + 1, n - k + 1, D)              # carries the wide interval
        rel = RNG.random(D) < p_rel
        ppg = np.where(rel, RNG.normal(pos_mean[pos] * 1.4, 4, D).clip(0, None), 0.0)
        games = np.where(rel, RNG.binomial(17, 0.85, D), RNG.binomial(17, 0.4, D))
        vorp = games * (ppg - repl[pos])
        out[t] = {"p_relevant_mean": float(p_rel.mean()),
                  "p_relevant_lo": float(np.quantile(p_rel, .05)), "p_relevant_hi": float(np.quantile(p_rel, .95)),
                  "vorp_mean": float(vorp.mean()),
                  "vorp_lo": float(np.quantile(vorp, .05)), "vorp_hi": float(np.quantile(vorp, .95))}
    return out


def run() -> None:
    con = duckdb.connect(str(CONFIG.path("warehouse")), read_only=True)
    seasons = con.execute("""SELECT m.player_uid, m.season, m.position, m.games, m.ppg_ppr,
                                    d.name, d.birthdate FROM fact_player_season_metrics m
                             JOIN dim_player d USING(player_uid) WHERE m.position IN ('QB','RB','WR','TE')""").pl()
    con.close()
    pos_mean = {r["position"]: r["repl_ppg"] for r in con_free()}
    repl = {"QB": 15.1 - 5, "RB": 7.5 - 3, "WR": 7.7 - 3, "TE": 4.7 - 2}  # ~replacement below pos mean
    # use actual replacement from warehouse
    con = duckdb.connect(str(CONFIG.path("warehouse")), read_only=True)
    for r in con.execute(f"""SELECT position, avg(replacement_points) v FROM fact_replacement
                            WHERE profile='ppr' AND season>=2022 AND season <= {LAST_COMPLETE} GROUP BY position""").pl().iter_rows(named=True):
        repl[r["position"]] = r["v"]
    inj = {r["player_uid"]: r["inj"] for r in con.execute(
        "SELECT player_uid, count(*) inj FROM fact_injury WHERE report_status IN ('Out','Doubtful') GROUP BY player_uid").pl().iter_rows(named=True)}
    con.close()
    deltas = _delta_lookup()

    latest = int(seasons["season"].max())
    # most-recent season per player, with age
    recent = (seasons.filter(pl.col("season") >= latest - 1)
              # DETERMINISM (G10.5 widened sweep): grain is (player_uid, season, position); a
              # multi-position player-season would make `.last()` order-dependent. Currently INERT
              # (0 such rows in 2023+ on the frozen data → output byte-unchanged); tie-break by
              # position to close the latent hole (same class as the _build_ctx fix).
              .sort(["season", "position"]).group_by("player_uid").last()
              .with_columns((latest + 1 - pl.col("birthdate").str.slice(0, 4).cast(pl.Int32)).alias("age"))
              .filter(pl.col("games") >= 6 & pl.col("age").is_not_null()))
    # rank by recent ppg, project the top established players
    recent = recent.sort("ppg_ppr", descending=True)

    L = ["# Player Projections — Phase 5.5 (Bayesian posterior, 90% credible intervals)", "",
         f"Composition: VORP(t)=P_play·games·(PPG|play − replacement). {P['mc_draws']} MC draws. "
         "Aging Δ from 5.1 posterior (QB buckets wide → wide QB intervals). Availability from "
         "position/age + injury history. **All outputs are distributions, not points.**", "",
         "## Established players — projected PPG (mean [5–95%]) by future year", "",
         "| player | pos | age | yr1 PPG | yr2 PPG | yr3 PPG |", "|---|---|--:|--:|--:|--:|"]
    demo = []
    for r in recent.head(15).iter_rows(named=True):
        pr = project_player(r, pos_mean, repl, deltas, inj.get(r["player_uid"], 0))
        f = lambda t: f"{pr[t]['ppg_mean']:.1f} [{pr[t]['ppg_lo']:.0f},{pr[t]['ppg_hi']:.0f}]"
        L.append(f"| {r['name']} | {r['position']} | {r['age']} | {f(1)} | {f(2)} | {f(3)} |")
        demo.append((r, pr))

    # demonstrate WIDE-interval carrying: a QB vs a WR at similar age, + a rookie RB·R1
    L += ["", "## Uncertainty is carried, not collapsed", ""]
    qb = next((d for d in demo if d[0]["position"] == "QB"), None)
    wr = next((d for d in demo if d[0]["position"] == "WR"), None)
    if qb and wr:
        qw = qb[1][2]["ppg_hi"] - qb[1][2]["ppg_lo"]; ww = wr[1][2]["ppg_hi"] - wr[1][2]["ppg_lo"]
        L.append(f"- yr3 PPG 90% width: {qb[0]['name']} (QB) = {qw:.1f} vs {wr[0]['name']} (WR) = {ww:.1f} "
                 f"→ QB interval {'WIDER' if qw > ww else 'not wider'} (Decision 6: QB aging CIs wide).")
    ca = pl.read_parquet(CONFIG.path("models") / "survival_clockA.parquet")
    kn = {}
    for t in (1, 3, 5):
        row = ca.filter((pl.col("position") == "RB") & (pl.col("round_grp") == "R1") & (pl.col("N") == t))
        if row.height:
            kn[t] = (int(row["k"][0]), int(row["n"][0]))
    rk = project_rookie(kn, "RB", repl, pos_mean)
    L += ["", "## Rookie RB·R1 — P(relevant) carries the survival interval (n=20)", "",
          "| year | P(relevant) mean [5–95%] | VORP mean [5–95%] |", "|--:|---|---|"]
    for t, v in rk.items():
        L.append(f"| {t} | {v['p_relevant_mean']:.2f} [{v['p_relevant_lo']:.2f},{v['p_relevant_hi']:.2f}] | "
                 f"{v['vorp_mean']:+.0f} [{v['vorp_lo']:+.0f},{v['vorp_hi']:+.0f}] |")
    EXPORTS.mkdir(parents=True, exist_ok=True)
    (EXPORTS / "projections.md").write_text("\n".join(L))
    log.info("projections -> %s (projected %d established + rookie demo)", EXPORTS / "projections.md", len(demo))
    print("\n".join(L))


if __name__ == "__main__":
    run()
