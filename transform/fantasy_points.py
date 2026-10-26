"""Phase 3 core — compute fantasy points per player-week FROM play-by-play.

We never trust precomputed fantasy totals. From pbp we derive each player's weekly
box-score components (passing/rushing/receiving/2pt/fumbles/return TDs), then score
them under every profile in config (std, half_ppr, ppr, te_premium, superflex,
your_league). nflverse's own fantasy_points/_ppr are used ONLY as a reconciliation
target in the gate, never as the source.
"""
from __future__ import annotations

import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CONFIG
from ingest._common import get_logger

log = get_logger("fantasy_points")


def _agg(df, id_col, week, exprs):
    return (df.filter(pl.col(id_col).is_not_null())
              .group_by([pl.col(id_col).alias("gsis_id"), "season", week.alias("week")])
              .agg(exprs))


def player_week_components(season: int) -> pl.DataFrame:
    """Per (gsis_id, season, week) box-score components computed from pbp."""
    pbp = pl.read_parquet(CONFIG.path("data_raw") / "nflverse" / "pbp" / f"{season}.parquet")
    pbp = pbp.filter(pl.col("season_type").is_in(["REG", "POST"]) | pl.col("season_type").is_null())
    wk = pl.col("week")

    passing = (pbp.filter(pl.col("passer_player_id").is_not_null())
               .group_by([pl.col("passer_player_id").alias("gsis_id"), "season", wk.alias("week")])
               .agg(pl.col("passing_yards").sum().alias("pass_yd"),
                    pl.col("pass_touchdown").sum().alias("pass_td"),
                    pl.col("interception").sum().alias("pass_int")))
    rushing = (pbp.filter(pl.col("rusher_player_id").is_not_null())
               .group_by([pl.col("rusher_player_id").alias("gsis_id"), "season", wk.alias("week")])
               .agg(pl.col("rushing_yards").sum().alias("rush_yd"),
                    pl.col("rush_touchdown").sum().alias("rush_td")))
    receiving = (pbp.filter(pl.col("receiver_player_id").is_not_null())
                 .group_by([pl.col("receiver_player_id").alias("gsis_id"), "season", wk.alias("week")])
                 .agg(pl.col("complete_pass").sum().alias("rec"),
                      pl.col("receiving_yards").sum().alias("rec_yd"),
                      # receiving TD = pass_touchdown on a play where this player is the receiver
                      pl.col("pass_touchdown").sum().alias("rec_td")))
    # fumbles lost -> charged to the fumbler, but ONLY on offensive plays (run/pass).
    # ST fumbles (muffed punts/kick returns) are not offensive fantasy penalties and
    # nflverse excludes them from fantasy_points.
    fumbles = (pbp.filter((pl.col("fumble_lost") == 1) & pl.col("fumbled_1_player_id").is_not_null()
                          & pl.col("play_type").is_in(["run", "pass"]))
               .group_by([pl.col("fumbled_1_player_id").alias("gsis_id"), "season", wk.alias("week")])
               .agg(pl.col("fumble_lost").sum().alias("fumble_lost")))

    # 2-point conversions (successful): pass -> passer & receiver; run -> rusher
    tp = pbp.filter((pl.col("two_point_attempt") == 1) & (pl.col("two_point_conv_result") == "success"))
    tp_pass_passer = (tp.filter(pl.col("passer_player_id").is_not_null())
                      .group_by([pl.col("passer_player_id").alias("gsis_id"), "season", wk.alias("week")])
                      .agg(pl.len().alias("pass_2pt")))
    tp_pass_rec = (tp.filter(pl.col("receiver_player_id").is_not_null())
                   .group_by([pl.col("receiver_player_id").alias("gsis_id"), "season", wk.alias("week")])
                   .agg(pl.len().alias("rec_2pt")))
    tp_run = (tp.filter(pl.col("rusher_player_id").is_not_null())
              .group_by([pl.col("rusher_player_id").alias("gsis_id"), "season", wk.alias("week")])
              .agg(pl.len().alias("rush_2pt")))
    # special-teams return TDs -> scorer (matches nflverse special_teams_tds)
    st = (pbp.filter(pl.col("play_type").is_in(["kickoff", "punt"]) & pl.col("td_player_id").is_not_null())
          .group_by([pl.col("td_player_id").alias("gsis_id"), "season", wk.alias("week")])
          .agg(pl.len().alias("st_td")))

    out = passing
    for d in (rushing, receiving, fumbles, tp_pass_passer, tp_pass_rec, tp_run, st):
        out = out.join(d, on=["gsis_id", "season", "week"], how="full", coalesce=True)
    numcols = ["pass_yd", "pass_td", "pass_int", "rush_yd", "rush_td", "rec", "rec_yd",
               "rec_td", "fumble_lost", "pass_2pt", "rec_2pt", "rush_2pt", "st_td"]
    out = out.with_columns([pl.col(c).fill_null(0) for c in numcols])
    out = out.filter(pl.col("week").is_not_null() & pl.col("gsis_id").is_not_null())
    return out


def score(components: pl.DataFrame, positions: dict[str, str]) -> pl.DataFrame:
    """Add fantasy_points_{profile} columns for every scoring profile."""
    df = components.with_columns(
        pl.col("gsis_id").replace_strict(positions, default=None).alias("position"))
    for name, s in CONFIG.scoring_profiles.items():
        rec_pts = pl.col("rec") * s.get("rec", 0.0)
        te_bonus = 0.0
        if s.get("rec_te_bonus"):
            te_bonus = pl.when(pl.col("position") == "TE").then(
                pl.col("rec") * s["rec_te_bonus"]).otherwise(0.0)
        pts = (pl.col("pass_yd") * s.get("pass_yd", 0) + pl.col("pass_td") * s.get("pass_td", 0)
               + pl.col("pass_int") * s.get("pass_int", 0)
               + pl.col("rush_yd") * s.get("rush_yd", 0) + pl.col("rush_td") * s.get("rush_td", 0)
               + rec_pts + pl.col("rec_yd") * s.get("rec_yd", 0) + pl.col("rec_td") * s.get("rec_td", 0)
               + te_bonus
               + pl.col("fumble_lost") * s.get("fumble_lost", 0)
               + (pl.col("pass_2pt") + pl.col("rec_2pt") + pl.col("rush_2pt")) * s.get("two_pt", 2)
               + pl.col("st_td") * s.get("st_td", 6))
        df = df.with_columns(pts.round(2).alias(f"fp_{name}"))
    return df


def your_league_profile() -> dict:
    """Parse the live Sleeper scoring_settings for league_id into a scoring profile."""
    import httpx, json
    lid = CONFIG["sleeper"]["league_id"]
    p = CONFIG.path("data_raw") / "sleeper" / "league.json"
    if not lid:
        # No league configured: use the bundled default scoring rules (point values only).
        default = CONFIG.path("data_raw").parent / "default_league_scoring.json"
        lg = json.loads(default.read_text())
    elif p.exists():
        lg = json.loads(p.read_text())
    else:
        lg = httpx.get(f"{CONFIG['sleeper']['base_url']}/league/{lid}",
                       headers={"User-Agent": CONFIG['sleeper']['user_agent']}, timeout=30).json()
        p.write_text(json.dumps(lg))
    sc = lg.get("scoring_settings", {})
    # Individual return TDs only count if the league scores kr_td/pr_td at the
    # player level. This league has neither (st_td/def_st_td are DST-unit slots),
    # so return TDs are EXCLUDED from your_league (kept in generic profiles).
    ret_td = sc.get("kr_td") or sc.get("pr_td") or 0.0
    return {
        "pass_yd": sc.get("pass_yd", 0.04), "pass_td": sc.get("pass_td", 4),
        "pass_int": sc.get("pass_int", -2), "rush_yd": sc.get("rush_yd", 0.1),
        "rush_td": sc.get("rush_td", 6), "rec": sc.get("rec", 1.0),
        "rec_yd": sc.get("rec_yd", 0.1), "rec_td": sc.get("rec_td", 6),
        "rec_te_bonus": sc.get("bonus_rec_te", 0.0) or 0.0,
        "fumble_lost": sc.get("fum_lost", -2), "two_pt": 2, "st_td": ret_td,
    }
