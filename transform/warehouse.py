"""Phase 3 — build the DuckDB warehouse from staging + raw.

Applies migrations/schema.sql, then loads every dim/fact. fact_player_week is
computed from pbp under all scoring profiles (incl. live your_league).
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import duckdb
import nflreadpy as nfl
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CONFIG
from ingest._common import get_logger, resolve_current_season
from transform.identity import build_dim_player, _indexes
from transform.fantasy_points import player_week_components, score, your_league_profile

log = get_logger("warehouse")
STG = CONFIG.path("data_staging")
PROFILES = ["std", "half_ppr", "ppr", "te_premium", "superflex", "your_league"]


def _seasons() -> list[int]:
    end = CONFIG["seasons"]["end"] or resolve_current_season()
    return list(range(CONFIG["seasons"]["start"], end + 1))


SKILL = ["QB", "RB", "WR", "TE", "FB"]
NUMCOLS = ["pass_yd", "pass_td", "pass_int", "rush_yd", "rush_td", "rec", "rec_yd",
           "rec_td", "fumble_lost", "pass_2pt", "rec_2pt", "rush_2pt", "st_td"]


def _cached_nflverse(dataset: str, seasons: list) -> pl.DataFrame:
    """HERMETIC read of a per-season nflverse dataset from the FROZEN raw cache (Phase-7 Defect 2).
    Never calls nflverse live — the build must be reproducible + network-independent. Missing season
    files are logged and skipped (not fetched)."""
    base = CONFIG.path("data_raw") / "nflverse" / dataset
    allp = base / "all.parquet"
    if allp.exists() and not any((base / f"{s}.parquet").exists() for s in seasons):
        df = pl.read_parquet(allp)                       # season-less cache (e.g. schedules)
        return df.filter(pl.col("season").is_in(list(seasons))) if "season" in df.columns else df
    frames, missing = [], []
    for s in seasons:
        p = base / f"{s}.parquet"
        if p.exists():
            frames.append(pl.read_parquet(p))
        else:
            missing.append(s)
    if missing:
        log.warning("hermetic %s: %d cached season(s) missing (NOT fetched live): %s",
                    dataset, len(missing), missing)
    return pl.concat(frames, how="vertical_relaxed") if frames else pl.DataFrame()


def build_fact_player_week(dim: pl.DataFrame) -> pl.DataFrame:
    """One row per ACTIVE skill player per week (incl. zero-production), with a
    status field (for the availability model) + offense_snaps (NULL pre-2013).
    Inclusion rule = on an NFL roster that week (rosters_weekly), not "recorded a stat"."""
    yl = your_league_profile()
    if yl:
        CONFIG.scoring_profiles["your_league"] = yl
        log.info("your_league profile: rec=%s pass_int=%s te_bonus=%s st_td(ret)=%s",
                 yl["rec"], yl["pass_int"], yl.get("rec_te_bonus"), yl["st_td"])
    positions = {g: p for g, p in zip(dim["gsis_id"], dim["position"]) if g}
    g2u = {g: u for g, u in zip(dim["gsis_id"], dim["player_uid"]) if g}
    pfr2g = {p: g for p, g in zip(dim["pfr_id"], dim["gsis_id"]) if p and g}
    skill_gsis = set(dim.filter(pl.col("position").is_in(SKILL))["gsis_id"].to_list())
    seasons = _seasons()

    # bulk loads — HERMETIC (Phase-7 Defect 2): read the FROZEN raw cache, NOT live nflverse.
    # nflverse revises historical seasons; reading live made the warehouse non-reproducible and
    # network-fragile. Ingest caches these per-season to data/raw/nflverse/{dataset}/{season}.parquet.
    rw = _cached_nflverse("rosters_weekly", [s for s in seasons if s <= _max_data_season()])
    rw = rw.select("gsis_id", "season", "week", pl.col("team"), pl.col("status")).filter(
        pl.col("gsis_id").is_in(list(skill_gsis)) & pl.col("week").is_not_null()).unique(
        ["gsis_id", "season", "week"])
    snaps = _cached_nflverse("snap_counts", [s for s in seasons if s >= 2013 and s <= _max_data_season()])
    snaps = snaps.with_columns(
        pl.col("pfr_player_id").replace_strict(pfr2g, default=None).alias("gsis_id")).filter(
        pl.col("gsis_id").is_not_null()).group_by(["gsis_id", "season", "week"]).agg(
        pl.col("offense_snaps").sum().alias("offense_snaps"))
    sched = _cached_nflverse("schedules", [s for s in seasons if s <= _max_data_season()])
    games = pl.concat([
        sched.select("season", "week", pl.col("home_team").alias("team")),
        sched.select("season", "week", pl.col("away_team").alias("team"))]).unique().with_columns(
        pl.lit(True).alias("team_had_game"))

    # production components
    comp_frames = []
    for s in seasons:
        p = CONFIG.path("data_raw") / "nflverse" / "pbp" / f"{s}.parquet"
        if p.exists():
            c = player_week_components(s)
            if c.height:
                comp_frames.append(c)
    comp = pl.concat(comp_frames, how="vertical_relaxed") if comp_frames else pl.DataFrame()

    # universe = roster membership UNION production (a produced player not on the
    # weekly roster snapshot still counts as played)
    prod_keys = comp.select("gsis_id", "season", "week") if comp.height else pl.DataFrame(
        schema={"gsis_id": pl.Utf8, "season": pl.Int64, "week": pl.Int64})
    universe = pl.concat([rw.select("gsis_id", "season", "week"),
                          prod_keys.with_columns(pl.col("season").cast(pl.Int64),
                                                 pl.col("week").cast(pl.Int64))],
                         how="vertical_relaxed").unique()
    df = (universe
          .join(rw, on=["gsis_id", "season", "week"], how="left")
          .join(comp, on=["gsis_id", "season", "week"], how="left")
          .join(snaps, on=["gsis_id", "season", "week"], how="left")
          .join(games, on=["team", "season", "week"], how="left"))
    df = df.with_columns([pl.col(c).fill_null(0) for c in NUMCOLS])
    df = df.with_columns([
        pl.col("team_had_game").fill_null(False),
        pl.col("status").fill_null("UNK"),
        # played = any offensive snap (2013+) OR any production
        ((pl.col("offense_snaps").fill_null(0) > 0) |
         (pl.sum_horizontal([pl.col(c).abs() for c in NUMCOLS]) > 0)).alias("played"),
        # snaps NULL (not 0) pre-2013 — per GATE1 constraint
        pl.when(pl.col("season") < 2013).then(None).otherwise(
            pl.col("offense_snaps").fill_null(0)).alias("offense_snaps"),
    ])
    scored = score(df, positions)
    scored = scored.with_columns(
        pl.col("gsis_id").replace_strict(g2u, default=None).alias("player_uid")).filter(
        pl.col("player_uid").is_not_null())
    keep = ["player_uid", "gsis_id", "season", "week", "position", "team", "status",
            "played", "team_had_game", "offense_snaps"] + NUMCOLS + [f"fp_{p}" for p in PROFILES]
    scored = scored.select([c for c in keep if c in scored.columns])
    scored.write_parquet(STG / "fact_player_week.parquet")
    log.info("fact_player_week: %d rows (%d played, %d active-zero-prod)",
             scored.height, scored.filter(pl.col("played"))["played"].len(),
             scored.filter(~pl.col("played")).height)
    return scored


def _max_data_season() -> int:
    """Latest season with real nflverse data (offseason 2026 has none)."""
    yrs = sorted(int(p.stem) for p in (CONFIG.path("data_raw") / "nflverse" / "pbp").glob("*.parquet")
                 if pl.scan_parquet(p).select(pl.len()).collect().item() > 0)
    return yrs[-1] if yrs else 2025


def build_fact_player_season(fpw: pl.DataFrame) -> pl.DataFrame:
    # DETERMINISM (G10.4): group_by float sums are order-sensitive (non-associative) and the input
    # arrives in nondeterministic storage order -> sort by a TOTAL key so the summation order, and
    # thus the bytes, is fixed (proven byte-invariant under 1 and 8 threads). Key unique over input.
    _fk = ["player_uid", "season", "week", "position"]
    assert fpw.select(_fk).n_unique() == fpw.height, \
        "G10.4 invariant: fact_player_week key not unique before season aggregation"
    fpw = fpw.sort(_fk)
    agg = (fpw.group_by(["player_uid", "season", "position"])
              .agg([pl.col("played").sum().cast(pl.Int32).alias("games")] +
                   [pl.col(f"fp_{p}").sum().alias(f"fp_{p}") for p in PROFILES]))
    agg = agg.with_columns(
        pl.when(pl.col("games") > 0).then(pl.col("fp_ppr") / pl.col("games"))
          .otherwise(None).round(3).alias("ppg_ppr"))
    # DETERMINISM (G10.4): ordinal rank breaks fp_ppr ties by row order; pre-sort by the window
    # key + player_uid so ties resolve deterministically (player_uid asc). Tiebreak key unique
    # within (season, position).
    assert agg.select(["season", "position", "player_uid"]).n_unique() == agg.height, \
        "G10.4 invariant: (season,position,player_uid) not unique before pos_finish_ppr rank"
    agg = agg.sort(["season", "position", "player_uid"]).with_columns(
        pl.col("fp_ppr").rank("ordinal", descending=True)
          .over(["season", "position"]).cast(pl.Int32).alias("pos_finish_ppr"))
    agg.write_parquet(STG / "fact_player_season.parquet")
    log.info("fact_player_season: %d rows", agg.height)
    return agg


def build_fact_adp(by_mfl: dict) -> pl.DataFrame:
    from ingest.mfl_adp import parse_cell_players
    rows = []
    for jp in glob.glob(str(CONFIG.path("data_raw") / "mfl" / "*" / "adp_*_f12_*.json")):
        p = Path(jp); parts = p.stem.split("_"); season = int(p.parent.name)
        fmt, ppr, fcount, period = parts[1], int(parts[2][3:]), int(parts[3][1:]), parts[4]
        for r in parse_cell_players(season, fmt, ppr, fcount, period):
            uid = by_mfl.get(r["mfl_id"])
            if uid:
                rows.append({"player_uid": uid, "mfl_id": r["mfl_id"], "season": season,
                             "format": fmt, "ppr": ppr, "league_size": fcount, "period": period,
                             "adp": r["adp"], "min_pick": r["min_pick"], "max_pick": r["max_pick"],
                             "draft_pct": r["draft_pct"], "drafts_selected_in": r["drafts_selected_in"]})
    df = pl.DataFrame(rows) if rows else pl.DataFrame()
    df.write_parquet(STG / "fact_adp.parquet")
    log.info("fact_adp: %d rows", df.height)
    return df


def build_fact_injury(g2u: dict) -> pl.DataFrame:
    frames = []
    for p in glob.glob(str(CONFIG.path("data_raw") / "nflverse" / "injuries" / "*.parquet")):
        df = pl.read_parquet(p)
        gid = "gsis_id" if "gsis_id" in df.columns else "player_id"

        def col(name):
            return pl.col(name) if name in df.columns else pl.lit(None).alias(name)
        frames.append(df.select([
            col(gid).alias("gsis_id"), pl.col("season").cast(pl.Int64), pl.col("week").cast(pl.Int64),
            col("report_status").cast(pl.Utf8).alias("report_status"),
            col("practice_status").cast(pl.Utf8).alias("practice_status"),
            col("report_primary_injury").cast(pl.Utf8).alias("report_primary_injury")]))
    if not frames:
        return pl.DataFrame()
    out = pl.concat(frames, how="vertical_relaxed").with_columns(
        pl.col("gsis_id").replace_strict(g2u, default=None).alias("player_uid"))
    out = out.filter(pl.col("player_uid").is_not_null())
    out.write_parquet(STG / "fact_injury.parquet")
    log.info("fact_injury: %d rows", out.height)
    return out


def build_fact_dynasty_value(dim: pl.DataFrame) -> pl.DataFrame:
    fp2u = {f: u for f, u in zip(dim["fantasypros_id"], dim["player_uid"]) if f}
    rows = []
    for f in sorted(glob.glob(str(CONFIG.path("data_raw") / "dynastyprocess" / "*" / "values-players.csv"))):
        snap = Path(f).parent.name
        df = pl.read_csv(f, infer_schema_length=0)
        for r in df.iter_rows(named=True):
            uid = fp2u.get(r.get("fp_id"))
            if uid:
                rows.append({"player_uid": uid, "snapshot_date": snap, "source": "dynastyprocess",
                             "position": r.get("pos"),
                             "value_1qb": _f(r.get("value_1qb")), "value_2qb": _f(r.get("value_2qb")),
                             "ecr_1qb": _f(r.get("ecr_1qb")), "ecr_2qb": _f(r.get("ecr_2qb"))})
    df = pl.DataFrame(rows) if rows else pl.DataFrame()
    df.write_parquet(STG / "fact_dynasty_value.parquet")
    log.info("fact_dynasty_value: %d rows", df.height)
    return df


def build_fact_league(s2u: dict) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Rosters (dynasty corpus + your league) and draft picks (SFB flow-mechanics)."""
    roster_rows, traded_rows = [], []
    # dynasty corpus rosters
    for f in glob.glob(str(CONFIG.path("data_raw") / "sleeper_corpus" / "leagues" / "*" / "rosters.json")):
        lid = Path(f).parent.name
        lg = json.loads((Path(f).parent / "league.json").read_text())
        season = lg.get("season")
        for team in json.loads(Path(f).read_text()):
            for pid in (team.get("players") or []):
                roster_rows.append({"source": "corpus", "league_id": lid, "season": season,
                                    "roster_id": team.get("roster_id"), "owner_id": team.get("owner_id"),
                                    "player_uid": s2u.get(str(pid)), "sleeper_id": str(pid), "slot": None})
        tp = Path(f).parent / "traded_picks.json"
        if tp.exists():
            for t in json.loads(tp.read_text()):
                traded_rows.append({"source": "corpus", "league_id": lid, "season": t.get("season"),
                                    "round": t.get("round"), "roster_id": t.get("roster_id"),
                                    "owner_id": t.get("owner_id"), "previous_owner_id": t.get("previous_owner_id")})
    roster = pl.DataFrame(roster_rows) if roster_rows else pl.DataFrame()
    traded = pl.DataFrame(traded_rows) if traded_rows else pl.DataFrame()
    roster.write_parquet(STG / "fact_league_roster.parquet")
    traded.write_parquet(STG / "fact_league_traded_pick.parquet")
    log.info("fact_league_roster: %d rows | fact_league_traded_pick: %d rows", roster.height, traded.height)

    # draft picks: snowball corpus (source=corpus, DYNASTY — primary per Decision 4)
    #              + SFB (source=sfb, best-ball flow-mechanics only)
    pick_rows = []
    def _picks(files, source):
        for f in files:
            lid = Path(f).parent.name
            for pk in json.loads(Path(f).read_text()):
                pick_rows.append({"source": source, "league_id": lid, "draft_id": pk.get("draft_id"),
                                  "round": pk.get("round"), "pick_no": pk.get("pick_no"),
                                  "roster_id": pk.get("roster_id"),
                                  "player_uid": s2u.get(str(pk.get("player_id"))),
                                  "sleeper_id": str(pk.get("player_id"))})
    _picks(glob.glob(str(CONFIG.path("data_raw") / "sleeper_corpus" / "leagues" / "*" / "draft_picks.json")), "corpus")
    ncorpus = len(pick_rows)
    _picks(glob.glob(str(CONFIG.path("data_raw") / "sfb" / "*" / "sleeper" / "*" / "draft_picks.json")), "sfb")
    picks = pl.DataFrame(pick_rows) if pick_rows else pl.DataFrame()
    picks.write_parquet(STG / "fact_league_draft_pick.parquet")
    log.info("fact_league_draft_pick: %d corpus(dynasty) + %d sfb = %d rows",
             ncorpus, picks.height - ncorpus, picks.height)

    # transactions: snowball corpus (manager-tendency / FAAB priors)
    tx_rows = []
    for f in glob.glob(str(CONFIG.path("data_raw") / "sleeper_corpus" / "leagues" / "*" / "transactions.json")):
        lid = Path(f).parent.name
        for t in json.loads(Path(f).read_text()):
            wb = (t.get("settings") or {}).get("waiver_bid")
            tx_rows.append({"source": "corpus", "league_id": lid, "type": t.get("type"),
                            "status": t.get("status"), "week": t.get("leg"),
                            "roster_ids": json.dumps(t.get("roster_ids")),
                            "adds": json.dumps(t.get("adds")), "drops": json.dumps(t.get("drops")),
                            "waiver_bid": wb, "created": t.get("created")})
    tx = pl.DataFrame(tx_rows) if tx_rows else pl.DataFrame()
    tx.write_parquet(STG / "fact_league_transaction.parquet")
    log.info("fact_league_transaction: %d rows", tx.height)
    return roster, picks


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _load(con, table, parquet):
    p = STG / parquet
    if not p.exists() or pl.read_parquet(p).height == 0:
        log.warning("no data for %s (%s)", table, parquet); return 0
    con.execute(f"INSERT INTO {table} BY NAME SELECT * FROM read_parquet('{p}')")
    return con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


def assert_frozen_files_exist() -> None:
    """PERMANENT hermeticity precondition (Phase-10 A13): every file the FROZEN manifest names must
    exist on disk BEFORE the build claims to be network-free. The Phase-7 'network-free after caching'
    claim went UNVERIFIED for phases 3-9 because nothing checked the teams cache was present -- so the
    warehouse build silently made a live nfl.load_teams() call every time. This assertion makes the
    manifest-existence check part of the BUILD, not a downstream gate."""
    frozen = CONFIG.path("data_raw") / "nflverse" / "FROZEN.json"
    if not frozen.exists():
        raise FileNotFoundError(f"FROZEN manifest missing: {frozen} — build is not reproducible.")
    manifest = json.loads(frozen.read_text())
    repo = Path(__file__).resolve().parent.parent
    declared = []
    tl = manifest.get("teams_lookup")
    if tl and tl.get("file"):
        declared.append(repo / tl["file"])
    missing = [str(p) for p in declared if not p.exists()]
    if missing:
        raise FileNotFoundError(
            "HERMETIC BUILD PRECONDITION FAILED — FROZEN manifest names files that do NOT exist "
            f"(the build would make a LIVE network call): {missing}. Freeze them first "
            "(see FROZEN.json.teams_lookup) — do not build non-hermetically.")


def run() -> None:
    assert_frozen_files_exist()   # hermeticity precondition — fail loudly, never silently go live
    dbp = CONFIG.path("warehouse")
    if dbp.exists():
        dbp.unlink()
    con = duckdb.connect(str(dbp))
    con.execute((Path(__file__).resolve().parent.parent / "migrations" / "schema.sql").read_text())

    dim = build_dim_player()
    by_mfl, by_sleeper, by_gsis, _ = _indexes(dim)
    g2u = {g: u for g, u in zip(dim["gsis_id"], dim["player_uid"]) if g}
    s2u = {s: u for s, u in zip(dim["sleeper_id"], dim["player_uid"]) if s}

    dim.write_parquet(STG / "dim_player.parquet")
    fpw = build_fact_player_week(dim)
    build_fact_player_season(fpw)
    build_fact_adp(by_mfl)
    build_fact_injury(g2u)
    build_fact_dynasty_value(dim)
    build_fact_league(s2u)

    # dims — teams lookup for dim_team.
    # CORRECTION (Phase-10 A13, 2026-07-30): the original comment claimed "cache once so the build is
    # network-free after", but the cache file was NEVER PERSISTED/committed, so this branch fell
    # through to a LIVE nfl.load_teams() network call on EVERY build for phases 3-9. The claim was
    # UNVERIFIED and FALSE. Now the cache is frozen (data/raw/nflverse/teams/all.parquet, in
    # FROZEN.json.teams_lookup) and its existence is asserted at build start (assert_frozen_files_exist).
    teams_cache = CONFIG.path("data_raw") / "nflverse" / "teams" / "all.parquet"
    if teams_cache.exists():
        raw_teams = pl.read_parquet(teams_cache)   # hermetic path (now the only path in normal builds)
    else:
        # only reachable if the freeze is missing; assert_frozen_files_exist() should have caught it.
        raw_teams = nfl.load_teams()
        teams_cache.parent.mkdir(parents=True, exist_ok=True)
        raw_teams.write_parquet(teams_cache)
        log.warning("teams cache was MISSING -> made a LIVE nfl.load_teams() call and re-froze %s "
                    "(NOT hermetic this build)", teams_cache)
    teams = raw_teams.select(
        pl.col("team_abbr").alias("team"), pl.col("team_name").alias("name"),
        pl.col("team_conf").alias("conf"), pl.col("team_division").alias("division")).unique("team")
    teams.write_parquet(STG / "dim_team.parquet")
    pl.DataFrame({"season": _seasons()}).write_parquet(STG / "dim_season.parquet")
    wk = fpw.select("season", "week").unique().with_columns(pl.lit("REG+POST").alias("season_type"))
    wk.write_parquet(STG / "dim_week.parquet")

    counts = {}
    for tbl, pq in [("dim_player", "dim_player.parquet"), ("dim_team", "dim_team.parquet"),
                    ("dim_season", "dim_season.parquet"), ("dim_week", "dim_week.parquet"),
                    ("fact_player_week", "fact_player_week.parquet"),
                    ("fact_player_season", "fact_player_season.parquet"),
                    ("fact_adp", "fact_adp.parquet"), ("fact_injury", "fact_injury.parquet"),
                    ("fact_dynasty_value", "fact_dynasty_value.parquet"),
                    ("fact_league_roster", "fact_league_roster.parquet"),
                    ("fact_league_draft_pick", "fact_league_draft_pick.parquet"),
                    ("fact_league_traded_pick", "fact_league_traded_pick.parquet"),
                    ("fact_league_transaction", "fact_league_transaction.parquet")]:
        counts[tbl] = _load(con, tbl, pq)
    con.close()
    print("\n===== WAREHOUSE ROW COUNTS =====")
    for t, n in counts.items():
        print(f"  {t:26s} {n:>10,}")


if __name__ == "__main__":
    run()
