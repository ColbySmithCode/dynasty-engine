"""1F (college production) — cfbfastR bulk player stats -> college dominator.

Downloads sportsdataverse/cfbfastR-data player_stats parquet (play-level, 2014+),
aggregates to per (player, team, season) receiving/rushing yards + team totals,
and computes yards-share dominators. No scraping. Cached raw + staged parquet.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import httpx
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CONFIG
from ingest._common import get_logger, raw_dir, record_count

log = get_logger("cfb")
BASE = "https://raw.githubusercontent.com/sportsdataverse/cfbfastR-data/main/player_stats/parquet"
UA = {"User-Agent": CONFIG["mfl"]["user_agent"]}


def _season(year: int) -> pl.DataFrame:
    dest = raw_dir("cfb", year) / f"player_stats_{year}.parquet"
    if dest.exists():
        raw = pl.read_parquet(dest)
    else:
        r = httpx.get(f"{BASE}/player_stats_{year}.parquet", headers=UA, timeout=120)
        r.raise_for_status()
        dest.write_bytes(r.content)
        raw = pl.read_parquet(dest)
    # aggregate play-level -> player-team-season
    rec = (raw.filter(pl.col("reception_player").is_not_null())
           .group_by(["reception_player", "team"]).agg(pl.col("reception_yds").sum().alias("rec_yds")))
    rush = (raw.filter(pl.col("rush_player").is_not_null())
            .group_by(["rush_player", "team"]).agg(pl.col("rush_yds").sum().alias("rush_yds")))
    team_rec = raw.group_by("team").agg(pl.col("reception_yds").sum().alias("team_rec_yds"))
    team_rush = raw.group_by("team").agg(pl.col("rush_yds").sum().alias("team_rush_yds"))
    p = (rec.rename({"reception_player": "player"})
         .join(rush.rename({"rush_player": "player"}), on=["player", "team"], how="full", coalesce=True)
         .join(team_rec, on="team", how="left").join(team_rush, on="team", how="left"))
    p = p.with_columns([pl.col("rec_yds").fill_null(0), pl.col("rush_yds").fill_null(0),
                        pl.lit(year).alias("season")])
    p = p.with_columns([
        (pl.col("rec_yds") / pl.col("team_rec_yds")).alias("rec_share"),
        ((pl.col("rec_yds") + pl.col("rush_yds")) /
         (pl.col("team_rec_yds") + pl.col("team_rush_yds"))).alias("scrimmage_share")])
    return p.select("player", "team", "season", "rec_yds", "rush_yds", "rec_share", "scrimmage_share")


def run(years: range = range(2014, 2025)) -> None:
    frames = []
    for y in years:
        try:
            df = _season(y)
            frames.append(df)
            record_count("cfb", "player_season", y, df.height)
            log.info("cfb %d -> %d player-team-seasons", y, df.height)
        except Exception as e:  # noqa: BLE001
            log.error("cfb %d FAIL: %r", y, e)
            record_count("cfb", "player_season", y, 0, "fail", repr(e)[:150])
    allp = pl.concat(frames, how="vertical_relaxed")
    out = CONFIG.path("data_staging") / "cfb_dominator.parquet"
    allp.write_parquet(out)
    log.info("cfb dominator staged: %d rows -> %s", allp.height, out)


if __name__ == "__main__":
    run()
