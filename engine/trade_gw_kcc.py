"""Trade: GIVE Garrett Wilson  /  GET KC Concepcion + 2028 late rookie 1st.

Reuses the Phase-6 trade-engine machinery (comparable-slot VORP streams, MC draws,
dual pool, delta sweep). Prospective-via-comparables (G10.3): every asset is priced by
the realized VORP distribution of COMPARABLE assets at its CURRENT market slot.

STANDING CONSTRAINT 4 respected: dual pool + CIs, never a single verdict.
"""
from __future__ import annotations
import sys, json
from pathlib import Path
import duckdb, numpy as np, polars as pl
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CONFIG
from models.adp_calibration import _forward_vorp

DRAWS = CONFIG["trade_engine"]["monte_carlo_draws"]
SEED = CONFIG["models"]["seed"]
UNKNOWN_TICK = 0.92          # engine canon: 1-draft-out pick unknowability
CUR = 2026                   # current season = ownership year 1

def pools():
    fv = _forward_vorp().select("player_uid","season","position","v0","v1","v2")
    con = duckdb.connect(str(CONFIG.path("warehouse")), read_only=True)
    kadp = con.execute("""SELECT player_uid, season, adp FROM fact_adp
        WHERE format='K' AND ppr=-1 AND period='AUG15' AND adp IS NOT NULL AND season>=2019""").pl()
    corpus = con.execute("""SELECT p.player_uid, CAST(r.season AS INT) season, p.pick_no AS adp
        FROM fact_league_draft_pick p JOIN (SELECT DISTINCT league_id,season FROM fact_league_roster) r
        USING(league_id) WHERE p.source='corpus' AND p.player_uid IS NOT NULL""").pl()
    radp = con.execute("""SELECT player_uid, season, adp FROM fact_adp
        WHERE format='R' AND ppr=-1 AND period='DRAFT' AND adp IS NOT NULL AND season>=2020""").pl()
    dim = con.execute("SELECT player_uid, position, birthdate FROM dim_player").pl()
    con.close()
    srt = ["player_uid","season"]
    cons = kadp.join(fv, on=srt, how="inner").sort(srt)
    corp = corpus.join(fv, on=srt, how="inner").sort(srt)
    rook = radp.join(fv, on=srt, how="inner").sort(srt)
    return cons, corp, rook, dim

def slot_streams(pool, lo, hi, pos=None, age_lo=None, age_hi=None, dim=None):
    s = pool.filter((pl.col("adp") >= lo) & (pl.col("adp") <= hi))
    if pos: s = s.filter(pl.col("position") == pos)
    if age_lo is not None:
        d = dim.select("player_uid", pl.col("birthdate")).drop_nulls()
        s = s.join(d, on="player_uid", how="inner").with_columns(
            (pl.col("season") - pl.col("birthdate").str.slice(0,4).cast(pl.Int32)).alias("age"))
        s = s.filter((pl.col("age") >= age_lo) & (pl.col("age") <= age_hi))
    return s.select("v0","v1","v2").fill_null(0).to_numpy()

def value(streams, start_year, delta, horizon, rng, extra=1.0, jitter=0.0):
    idx = rng.integers(0, len(streams), DRAWS)
    s = streams[idx].astype(float)
    if jitter: s = s + rng.normal(0, jitter, s.shape)
    yr = np.zeros((DRAWS, horizon))
    for k in range(3):
        t = start_year - 1 + k
        if t < horizon: yr[:, t] = s[:, k]
    if start_year == 1 and horizon > 3:
        yr[:, 3] = s[:, 2] * 0.85                     # engine canon: yr4 decay of yr3
    if start_year == 1 and horizon > 4:
        for t in range(4, horizon): yr[:, t] = yr[:, t-1] * 0.85
    disc = np.array([delta ** t for t in range(horizon)])
    return (yr * disc).sum(axis=1) * extra, yr

def evaluate(cons, corp, rook, dim, pool_key, delta, horizon, seed,
             kcc_mode="rookie", pick_extra=UNKNOWN_TICK**2, jitter=15.0,
             gw_pos=None, gw_age=None, gw_win=(24,34)):
    rng = np.random.default_rng(seed)
    startup = cons if pool_key == "consensus" else corp
    gw_s = slot_streams(startup, gw_win[0], gw_win[1], pos=gw_pos,
                        age_lo=(gw_age[0] if gw_age else None),
                        age_hi=(gw_age[1] if gw_age else None), dim=dim)
    A, A_yr = value(gw_s, 1, delta, horizon, rng)
    if kcc_mode == "rookie":       kcc_s = slot_streams(rook, 5, 11)
    elif kcc_mode == "rookie_rd1": kcc_s = slot_streams(rook, 1, 12)
    else:                          kcc_s = slot_streams(startup, 17, 27)
    B1, B1_yr = value(kcc_s, 1, delta, horizon, rng)
    pick_s = slot_streams(rook, 9, 12)                       # a LOW rookie 1st
    B2, B2_yr = value(pick_s, 3, delta, horizon, rng, extra=pick_extra, jitter=jitter)
    return dict(A=A, B=B1+B2, B1=B1, B2=B2, A_yr=A_yr, B_yr=B1_yr+B2_yr,
                n_gw=len(gw_s), n_kcc=len(kcc_s), n_pick=len(pick_s))
