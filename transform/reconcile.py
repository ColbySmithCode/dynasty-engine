"""GATE 3 reconciliation — pbp-computed fantasy points vs nflverse's own
fantasy_points / fantasy_points_ppr, for every player-week 2010-2025.

Reports the delta distribution AND whether deltas cluster by SEASON (unhandled
rule change) or by PLAYER (specific play-type mis-attribution).
"""
from __future__ import annotations

import sys
from pathlib import Path

import nflreadpy as nfl
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CONFIG

STG = CONFIG.path("data_staging")


def run() -> None:
    fpw = pl.read_parquet(STG / "fact_player_week.parquet").select(
        "gsis_id", "season", "week", "fp_std", "fp_ppr")
    seasons = sorted(fpw["season"].unique().to_list())
    ps = nfl.load_player_stats(seasons=seasons).select(
        pl.col("player_id").alias("gsis_id"), "season", "week",
        "fantasy_points", "fantasy_points_ppr")
    # keep nflverse rows that actually score (or that we produced) to avoid 0=0 noise
    ps = ps.filter((pl.col("fantasy_points") != 0) | (pl.col("fantasy_points_ppr") != 0))

    m = fpw.join(ps, on=["gsis_id", "season", "week"], how="full", coalesce=True)
    matched = m.filter(pl.col("fp_std").is_not_null() & pl.col("fantasy_points").is_not_null())
    only_mine = m.filter(pl.col("fantasy_points").is_null())
    only_nfl = m.filter(pl.col("fp_std").is_null())

    d = matched.with_columns([
        (pl.col("fp_std") - pl.col("fantasy_points")).round(2).alias("d_std"),
        (pl.col("fp_ppr") - pl.col("fantasy_points_ppr")).round(2).alias("d_ppr")])

    print("===== GATE 3 reconciliation: pbp-computed vs nflverse =====")
    print(f"matched player-weeks: {matched.height:,} | only in mine: {only_mine.height:,} "
          f"| only in nflverse: {only_nfl.height:,}")
    for c in ("d_std", "d_ppr"):
        s = d[c]
        print(f"\n{c}: mean={s.mean():.4f} std={s.std():.4f} "
              f"median={s.median():.2f} p1={s.quantile(.01):.2f} p99={s.quantile(.99):.2f}")
        for thr in (0.5, 1, 3, 6):
            n = (s.abs() > thr).sum()
            print(f"   |{c}|>{thr}: {n:,} ({n/matched.height:.3%})")

    # ---- exact-match rate ----
    exact = (d["d_std"].abs() <= 0.02).sum()
    print(f"\nexact (|d_std|<=0.02): {exact:,}/{matched.height:,} = {exact/matched.height:.3%}")

    # ---- CLUSTERING: season vs player ----
    print("\n----- clustering diagnosis -----")
    off = d.filter(pl.col("d_std").abs() > 0.02)   # the disagreements
    print(f"disagreeing player-weeks: {off.height:,}")

    by_season = (off.group_by("season").agg(
        pl.len().alias("n_off"), pl.col("d_std").abs().sum().alias("abs_delta")).sort("season"))
    tot_by_season = matched.group_by("season").agg(pl.len().alias("n_tot"))
    by_season = by_season.join(tot_by_season, on="season").with_columns(
        (pl.col("n_off") / pl.col("n_tot")).alias("off_rate"))
    print("\nper-season disagreement rate (season-clustering signal):")
    print(by_season.select("season", "n_off", "n_tot", "off_rate", "abs_delta").sort("season"))

    # player concentration: share of total abs-delta from top-K players
    by_player = (off.group_by("gsis_id").agg(pl.col("d_std").abs().sum().alias("abs_delta"),
                                             pl.len().alias("weeks")).sort("abs_delta", descending=True))
    total_abs = by_player["abs_delta"].sum()
    for k in (10, 50, 100):
        share = by_player.head(k)["abs_delta"].sum() / total_abs if total_abs else 0
        print(f"top-{k} players hold {share:.1%} of all |d_std| "
              f"({by_player.height:,} players disagree at all)")

    # verdict metric: coefficient of variation of per-season off_rate
    rates = by_season["off_rate"]
    cv = rates.std() / rates.mean() if rates.mean() else 0
    span = rates.max() / rates.min() if rates.min() else float("inf")
    print(f"\nper-season off_rate: min={rates.min():.4f} max={rates.max():.4f} CV={cv:.2f} span={span:.1f}x")
    top10_share = by_player.head(10)["abs_delta"].sum() / total_abs if total_abs else 0
    print("VERDICT:",
          "SEASON-clustered (investigate rule change)" if cv > 0.6 and span > 3
          else "PLAYER-clustered (play-type attribution); not a systematic rule gap")

    # what play types drive it: recompute components for the worst offenders
    print("\ntop-8 disagreeing players (for play-type inspection):")
    print(by_player.head(8).join(
        pl.read_parquet(STG / "dim_player.parquet").select(
            pl.col("gsis_id"), "name", "position"), on="gsis_id", how="left"))


if __name__ == "__main__":
    run()
