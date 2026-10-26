"""Phase 4 — derived metrics (opportunity / efficiency / context / fantasy-native)
+ weekly replacement level per scoring profile.

Constraints (from GATE 1):
- snap-derived metrics (snap_share) are NULL pre-2013, never zero-filled.
- depth_charts is NOT consumed here (its 2025 source break must be normalized in
  Phase 5 before use); flagged in the metric dictionary.
Route-based metrics (YPRR, route_participation) need route data we don't have
league-wide; left NULL rather than zero-filled.
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CONFIG
from ingest._common import get_logger

log = get_logger("metrics")
STG = CONFIG.path("data_staging")
PROFILES = ["std", "half_ppr", "ppr", "te_premium", "superflex", "your_league"]

# replacement ranks per position for the target SF/PPR/12-team league (config-driven).
# dedicated starters + flex/superflex allocation (SF sends ~all superflex to QB).
def _replacement_ranks() -> dict[str, int]:
    r = CONFIG["roster"]; n = r["league_size"]
    s = r["starters"]; flex = s.get("FLEX", 0) * n; sflex = s.get("SUPERFLEX", 0) * n
    fill = r["sf_qb_fill_rate"]            # MEASURED from corpus, not assumed
    fsplit = r["flex_split"]; sfnq = r["sf_nonqb_split"]
    sf_nonqb = sflex * (1 - fill)          # SF slots that go to non-QB
    return {
        "QB": round(n * s.get("QB", 1) + sflex * fill),
        "RB": round(n * s.get("RB", 0) + flex * fsplit["RB"] + sf_nonqb * sfnq["RB"]),
        "WR": round(n * s.get("WR", 0) + flex * fsplit["WR"] + sf_nonqb * sfnq["WR"]),
        "TE": round(n * s.get("TE", 0) + flex * fsplit["TE"] + sf_nonqb * sfnq["TE"]),
    }


def opportunity_from_pbp(season: int) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Per player-week receiving/rushing opportunity+efficiency, and team-week totals."""
    pbp = pl.read_parquet(CONFIG.path("data_raw") / "nflverse" / "pbp" / f"{season}.parquet")
    pbp = pbp.filter(pl.col("season_type").is_in(["REG", "POST"]) | pl.col("season_type").is_null())
    wk = pl.col("week")
    rz = pl.col("yardline_100") <= 20

    rec = (pbp.filter(pl.col("pass_attempt") == 1, pl.col("receiver_player_id").is_not_null())
           .group_by([pl.col("receiver_player_id").alias("gsis_id"), "season", wk.alias("week")])
           .agg(pl.len().alias("targets"),
                pl.col("air_yards").sum().alias("air_yards"),
                (rz.cast(pl.Int32)).sum().alias("rz_targets"),
                pl.col("epa").sum().alias("rec_epa"),
                pl.col("success").mean().alias("rec_success")))
    rush = (pbp.filter(pl.col("rush_attempt") == 1, pl.col("rusher_player_id").is_not_null())
            .group_by([pl.col("rusher_player_id").alias("gsis_id"), "season", wk.alias("week")])
            .agg(pl.len().alias("carries"),
                 (rz.cast(pl.Int32)).sum().alias("rz_carries"),
                 pl.col("epa").sum().alias("rush_epa"),
                 pl.col("success").mean().alias("rush_success")))
    player = rec.join(rush, on=["gsis_id", "season", "week"], how="full", coalesce=True)

    team = (pbp.filter(pl.col("posteam").is_not_null(), (pl.col("pass_attempt") == 1) | (pl.col("rush_attempt") == 1))
            .group_by([pl.col("posteam").alias("team"), "season", wk.alias("week")])
            .agg(pl.col("pass_attempt").sum().alias("team_pass_att"),
                 pl.col("rush_attempt").sum().alias("team_rush_att"),
                 pl.col("air_yards").sum().alias("team_air_yards"),
                 pl.len().alias("team_plays"),
                 pl.col("xpass").mean().alias("team_xpass"),
                 (pl.col("pass_attempt") == 1).mean().alias("team_pass_rate"),
                 pl.col("epa").mean().alias("team_epa_play")))
    return player, team


def build(seasons: list[int]) -> None:
    con = duckdb.connect(str(CONFIG.path("warehouse")))
    fpw = con.execute("SELECT * FROM fact_player_week").pl()

    pw_frames, team_frames = [], []
    for s in seasons:
        if not (CONFIG.path("data_raw") / "nflverse" / "pbp" / f"{s}.parquet").exists():
            continue
        pl_df, tm = opportunity_from_pbp(s)
        pw_frames.append(pl_df); team_frames.append(tm)
    opp = pl.concat(pw_frames, how="vertical_relaxed")
    team = pl.concat(team_frames, how="vertical_relaxed")

    # map gsis->uid; join opportunity onto fact_player_week (which has team + snaps)
    dim = con.execute("SELECT player_uid, gsis_id FROM dim_player").pl()
    g2u = {g: u for g, u in zip(dim["gsis_id"], dim["player_uid"]) if g}
    opp = opp.with_columns(pl.col("gsis_id").replace_strict(g2u, default=None).alias("player_uid"))

    m = fpw.join(opp.drop("gsis_id"), on=["player_uid", "season", "week"], how="left")
    m = m.join(team, on=["team", "season", "week"], how="left")
    # team offensive snaps for snap share (2013+) = team offensive PLAYS, proxied by
    # the MAX offense_snaps on the team that week (a full-time OL plays every play).
    team_snaps = (fpw.filter(pl.col("offense_snaps").is_not_null())
                  .group_by(["team", "season", "week"]).agg(pl.col("offense_snaps").max().alias("team_off_snaps")))
    m = m.join(team_snaps, on=["team", "season", "week"], how="left")

    for c in ["targets", "air_yards", "carries", "rz_targets", "rz_carries", "rec_epa", "rush_epa"]:
        m = m.with_columns(pl.col(c).fill_null(0))

    m = m.with_columns([
        # opportunity
        (pl.col("targets") / pl.col("team_pass_att")).alias("target_share"),
        (pl.col("air_yards") / pl.col("team_air_yards")).alias("air_yards_share"),
        (pl.col("carries") / pl.col("team_rush_att")).alias("rush_share"),
        (pl.col("air_yards") / pl.when(pl.col("targets") > 0).then(pl.col("targets"))).alias("adot"),
        (pl.col("rec_yd") / pl.when(pl.col("air_yards") != 0).then(pl.col("air_yards"))).alias("racr"),
        (pl.col("targets") + pl.col("carries")).alias("opportunities"),
        (pl.col("rec") + pl.col("carries")).alias("touches"),
        (pl.col("rz_targets") + pl.col("rz_carries")).alias("rz_opportunities"),
        # snap share — NULL pre-2013 (offense_snaps already NULL there)
        (pl.col("offense_snaps") / pl.col("team_off_snaps")).alias("snap_share"),
        # efficiency
        (pl.col("rec_epa") / pl.when(pl.col("targets") > 0).then(pl.col("targets"))).alias("epa_per_target"),
        (pl.col("rush_epa") / pl.when(pl.col("carries") > 0).then(pl.col("carries"))).alias("epa_per_rush"),
        # context (team)
        (pl.col("team_pass_rate") - pl.col("team_xpass")).alias("team_proe"),
        # route metrics unavailable -> explicit NULL (never zero)
        pl.lit(None, dtype=pl.Float64).alias("yprr"),
        pl.lit(None, dtype=pl.Float64).alias("route_participation"),
    ])
    m = m.with_columns([
        (1.5 * pl.col("target_share").fill_null(0) + 0.7 * pl.col("air_yards_share").fill_null(0)).alias("wopr"),
        # fantasy-native per-week
        (pl.col("fp_ppr") / pl.when(pl.col("offense_snaps") > 0).then(pl.col("offense_snaps"))).alias("pts_per_snap"),
        (pl.col("fp_ppr") / pl.when(pl.col("opportunities") > 0).then(pl.col("opportunities"))).alias("pts_per_opp"),
    ])

    # weekly positional finish + replacement level + VORP per profile
    ranks = _replacement_ranks()
    # DETERMINISM (G10.4): the weekly ordinal ranks below break fp ties by row order; sort m by
    # the window key + player_uid ONCE so every profile's rank resolves ties deterministically
    # (player_uid asc). This sort also fixes the order feeding the downstream float aggregations
    # (replacement mean, season sums) whose subsets inherit it. Tiebreak key unique over m.
    assert m.select(["season", "week", "position", "player_uid"]).n_unique() == m.height, \
        "G10.4 invariant: (season,week,position,player_uid) not unique before weekly ranks"
    m = m.sort(["season", "week", "position", "player_uid"])
    repl_rows = []
    for prof in PROFILES:
        fp = f"fp_{prof}"
        m = m.with_columns(
            pl.col(fp).rank("ordinal", descending=True).over(["season", "week", "position"])
              .cast(pl.Int32).alias(f"wk_pos_rank_{prof}"))
        # replacement points = MEAN fp over a 3-player band at the replacement line
        # [N, N+2] (robust to single-player noise + weeks with slightly <N played)
        # DETERMINISM (G10.4): the band membership is now deterministic (weekly ranks fixed above);
        # sort the band before the mean so the float reduction order is fixed too. The band is a
        # subset of m, so its (season,week,position,player_uid) key inherits m's uniqueness.
        band = (m.filter(pl.col("played") & pl.col("position").is_in(list(ranks)))
                .with_columns(pl.col("position").replace_strict(ranks, default=999).alias("_N"))
                .filter((pl.col(f"wk_pos_rank_{prof}") >= pl.col("_N")) &
                        (pl.col(f"wk_pos_rank_{prof}") <= pl.col("_N") + 2))
                .sort(["season", "week", "position", "player_uid"]))
        repl = (band.group_by("season", "week", "position")
                .agg(pl.col(fp).mean().alias("replacement_points"))
                .with_columns(pl.lit(prof).alias("profile")))
        repl_rows.append(repl)
    replacement = pl.concat(repl_rows, how="vertical_relaxed")
    replacement.write_parquet(STG / "fact_replacement.parquet")

    # VORP (ppr) per week using ppr replacement
    repl_ppr = replacement.filter(pl.col("profile") == "ppr").select(
        "season", "week", "position", pl.col("replacement_points").alias("_repl_ppr"))
    m = m.join(repl_ppr, on=["season", "week", "position"], how="left").with_columns(
        (pl.col("fp_ppr") - pl.col("_repl_ppr")).alias("vorp_ppr"))

    keepnum = ["player_uid", "gsis_id", "season", "week", "position", "played",
               "targets", "air_yards", "carries", "rz_targets", "rz_carries",
               "target_share", "air_yards_share", "rush_share", "adot", "racr",
               "wopr", "opportunities", "touches", "rz_opportunities", "snap_share",
               "epa_per_target", "epa_per_rush", "rec_success", "rush_success",
               "team_proe", "yprr", "route_participation",
               "pts_per_snap", "pts_per_opp", "vorp_ppr",
               "wk_pos_rank_ppr", "wk_pos_rank_your_league"]
    mweek = m.select([c for c in keepnum if c in m.columns])
    mweek.write_parquet(STG / "fact_player_week_metrics.parquet")
    con.execute("DROP TABLE IF EXISTS fact_player_week_metrics")
    con.execute(f"CREATE TABLE fact_player_week_metrics AS SELECT * FROM read_parquet('{STG/'fact_player_week_metrics.parquet'}')")
    con.execute("DROP TABLE IF EXISTS fact_replacement")
    con.execute(f"CREATE TABLE fact_replacement AS SELECT * FROM read_parquet('{STG/'fact_replacement.parquet'}')")
    log.info("fact_player_week_metrics: %d rows | fact_replacement: %d rows", mweek.height, replacement.height)

    _season_metrics(con, m, ranks)
    con.close()


def _season_metrics(con, m, ranks) -> None:
    """Season aggregates + fantasy-native: PPG, boom/bust, volatility, consistency, VORP."""
    # DETERMINISM (G10.4): these season aggregates are float sums/means/std (order-sensitive); sort
    # the input by a TOTAL key so the reduction order is fixed. Key unique over played.
    played = m.filter(pl.col("played")).sort(["player_uid", "season", "week", "position"])
    assert played.select(["player_uid", "season", "week", "position"]).n_unique() == played.height, \
        "G10.4 invariant: (player_uid,season,week,position) not unique in _season_metrics input"
    agg = (played.group_by(["player_uid", "season", "position"]).agg(
        pl.len().alias("games"),
        pl.col("fp_ppr").sum().alias("fp_ppr"),
        pl.col("fp_ppr").mean().alias("ppg_ppr"),
        pl.col("fp_ppr").std().alias("stdev_ppr"),
        pl.col("vorp_ppr").sum().alias("vorp_ppr_total"),
        pl.col("target_share").mean().alias("avg_target_share"),
        pl.col("wopr").mean().alias("avg_wopr"),
        pl.col("snap_share").mean().alias("avg_snap_share"),
        pl.col("opportunities").sum().alias("opportunities"),
        # boom = top-5 positional week; bust = outside top-36 in a played week
        (pl.col("wk_pos_rank_ppr") <= 5).mean().alias("boom_rate"),
        (pl.col("wk_pos_rank_ppr") > 36).mean().alias("bust_rate")))
    agg = agg.with_columns([
        (pl.col("stdev_ppr") / pl.when(pl.col("ppg_ppr") > 0).then(pl.col("ppg_ppr"))).alias("cv_ppr"),
    ]).with_columns((1 - pl.col("cv_ppr").clip(0, 1)).alias("consistency"))
    agg.write_parquet(STG / "fact_player_season_metrics.parquet")
    con.execute("DROP TABLE IF EXISTS fact_player_season_metrics")
    con.execute(f"CREATE TABLE fact_player_season_metrics AS SELECT * FROM read_parquet('{STG/'fact_player_season_metrics.parquet'}')")
    log.info("fact_player_season_metrics: %d rows", agg.height)


def run() -> None:
    end = CONFIG["seasons"]["end"] or 2025
    seasons = [s for s in range(CONFIG["seasons"]["start"], end + 1)
               if (CONFIG.path("data_raw") / "nflverse" / "pbp" / f"{s}.parquet").exists()]
    log.info("metrics: seasons %s replacement_ranks=%s", (seasons[0], seasons[-1]), _replacement_ranks())
    build(seasons)


if __name__ == "__main__":
    run()
