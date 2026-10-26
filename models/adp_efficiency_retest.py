"""5.3 re-tests (items 1-3):
 1. Market efficiency against ACTUAL superflex draft position (corpus, 55k picks,
    96% SF) — not 1QB MFL ADP (which makes the QB residual tautological). Report both.
 2. Edge decay: residuals split by era (pre-2022 vs 2022+) — is the QB edge (or the
    TE/RB traps) being arbitraged as SF adoption grew?
 3. "QB holds value deep": sensitivity of deep-QB VORP to the 78.3%-adjusted
    replacement level (rank 21) vs the 100%-fill assumption (rank 24).
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
from models.adp_calibration import _forward_vorp

log = get_logger("adp_retest")
# G10.1 leakage fix: cap every fitted read at last_complete_season (derived) + assert.
LAST_COMPLETE = CONFIG["models"]["startup_backtest"]["last_complete_season"]


def _con():
    return duckdb.connect(str(CONFIG.path("warehouse")), read_only=True)


def _corpus_sf_adp() -> pl.DataFrame:
    """Consensus superflex startup draft position per player-season from the corpus.
    Startup draft per league = the draft with the most picks (initial roster draft)."""
    con = _con()
    picks = con.execute(f"""SELECT p.league_id, p.draft_id, p.pick_no, p.player_uid,
                                  r.season
                           FROM fact_league_draft_pick p
                           JOIN (SELECT DISTINCT league_id, season FROM fact_league_roster
                                 WHERE try_cast(season AS INTEGER) <= {LAST_COMPLETE}) r
                             USING(league_id)
                           WHERE p.source='corpus' AND p.player_uid IS NOT NULL""").pl()
    con.close()
    # identify the startup draft (largest) per league
    sizes = picks.group_by(["league_id", "draft_id"]).agg(pl.len().alias("npicks"))
    startup = sizes.sort("npicks", descending=True).group_by("league_id").first().select("league_id", "draft_id")
    su = picks.join(startup, on=["league_id", "draft_id"], how="inner")
    # consensus SF startup ADP = mean overall pick across leagues, per player-season
    su = su.with_columns(pl.col("season").cast(pl.Int32, strict=False))
    out = (su.group_by(["player_uid", "season"]).agg(
        pl.col("pick_no").mean().alias("sf_adp"), pl.len().alias("n_leagues"))
        .filter(pl.col("n_leagues") >= 5))
    assert (out["season"].max() or 0) <= LAST_COMPLETE, "G10.1 leak: _corpus_sf_adp frame > last_complete_season"
    return out


def _residuals(m: pl.DataFrame, price_col: str) -> pl.DataFrame:
    m = m.filter(pl.col(price_col) > 0).with_columns(pl.col(price_col).log().alias("lnp"))
    x = m["lnp"].to_numpy(); y = m["fwd3_vorp"].to_numpy()
    b1, b0 = np.polyfit(x, y, 1)
    return m.with_columns((pl.col("fwd3_vorp") - (b0 + b1 * pl.col("lnp"))).alias("resid"))


def _report(m: pl.DataFrame, label: str) -> None:
    print(f"\n{label} (n={m.height})")
    g = (m.group_by("position").agg(pl.len().alias("n"), pl.col("resid").mean().round(1).alias("mr"))
         .filter(pl.col("n") >= 15).sort("mr", descending=True))
    for r in g.iter_rows(named=True):
        v = "UNDERvalued" if r["mr"] > 5 else ("OVERvalued" if r["mr"] < -5 else "≈efficient")
        print(f"   {r['position']:3s} n={r['n']:>4} resid={r['mr']:+7.1f}  {v}")


def item1_and_2() -> None:
    fv = _forward_vorp()
    # --- 1QB MFL ADP (tautological baseline) ---
    con = _con()
    mfl = con.execute(f"""SELECT player_uid, season, adp FROM fact_adp
                         WHERE format='K' AND ppr=-1 AND period='AUG15'
                           AND adp IS NOT NULL AND season>=2019 AND season <= {LAST_COMPLETE}""").pl()
    con.close()
    m1 = _residuals(mfl.join(fv, on=["player_uid", "season"], how="inner"), "adp")
    assert (m1["season"].max() or 0) <= LAST_COMPLETE, "G10.1 leak: item1 mfl frame > last_complete_season"
    print("=== ITEM 1: which residual tells the truth? ===")
    _report(m1, "A) vs 1QB MFL ADP  [TAUTOLOGICAL — SF value vs 1QB price]")

    # --- actual superflex draft position (the real test) ---
    sf = _corpus_sf_adp()
    m2 = _residuals(sf.join(fv, on=["player_uid", "season"], how="inner"), "sf_adp")
    _report(m2, "B) vs ACTUAL superflex draft position  [THE REAL TEST]")

    print("\n=== ITEM 2: edge decay by era (actual SF draft position) ===")
    for era, lo, hi in [("pre-2022", 2020, 2021), ("2022+", 2022, 2025)]:
        sub = m2.filter((pl.col("season") >= lo) & (pl.col("season") <= hi))
        if sub.height:
            _report(_residuals(sub, "sf_adp"), f"SF residuals {era}")


def item3_qb_depth() -> None:
    print("\n=== ITEM 3: is 'QB holds value deep' real or a replacement artifact? ===")
    con = _con()
    # startup QB fwd3 VORP by startup round, recomputed under two QB replacement ranks
    m = con.execute(f"""SELECT a.player_uid, a.season, a.adp, s.fp_ppr, s.games
                       FROM fact_adp a JOIN fact_player_season s USING(player_uid, season)
                       WHERE a.format='K' AND a.ppr=-1 AND a.period='AUG15' AND s.position='QB'
                         AND a.adp IS NOT NULL AND a.season>=2019 AND a.season <= {LAST_COMPLETE}""").pl()
    assert (m["season"].max() or 0) <= LAST_COMPLETE, "G10.1 leak: item3 qb frame > last_complete_season"
    # weekly QB fp to build replacement at ranks 21 vs 24
    wk = con.execute("""SELECT season, week, fp_ppr,
                          rank() OVER (PARTITION BY season,week ORDER BY fp_ppr DESC) rk
                        FROM fact_player_week WHERE position='QB' AND played""").pl()
    con.close()
    def repl_ppg(N):
        band = wk.filter((pl.col("rk") >= N) & (pl.col("rk") <= N + 2))
        return band.group_by("season").agg(pl.col("fp_ppr").mean().alias("r")).select(
            (pl.col("r")).mean()).item()  # avg weekly replacement across seasons
    r21 = repl_ppg(21) * 17   # season replacement points (~17 games)
    r24 = repl_ppg(24) * 17
    m = m.with_columns([((pl.col("adp") - 1) // 12 + 1).cast(pl.Int32).alias("startup_round")])
    print(f"   season QB replacement points: rank21(78% fill)={r21:.0f}  rank24(100% fill)={r24:.0f}")
    print("   startup_rd | n | mean fp | VORP@rank21 | VORP@rank24")
    g = m.filter(pl.col("games") >= 8).group_by("startup_round").agg(
        pl.len().alias("n"), pl.col("fp_ppr").mean().alias("mfp")).sort("startup_round")
    for r in g.filter(pl.col("n") >= 8).iter_rows(named=True):
        print(f"   {r['startup_round']:>2} | {r['n']:>3} | {r['mfp']:6.0f} | "
              f"{r['mfp']-r21:+7.0f} | {r['mfp']-r24:+7.0f}")
    print("   → if deep-round QB VORP is positive at rank24 too, the depth is REAL; if only at")
    print("     rank21, 'holds deep' is an artifact of the 78%-fill replacement.")


if __name__ == "__main__":
    item1_and_2()
    item3_qb_depth()
