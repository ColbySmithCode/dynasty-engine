"""1A — nflverse backbone via nflreadpy (Polars-native).

Ground truth. Play-by-play is the source from which we compute fantasy points
ourselves under each scoring profile — we never trust precomputed fantasy totals.

Per-season pulls so coverage anomalies surface per season. Season-gated datasets
are guarded by a min-season. Everything cached to data/raw/nflverse/{dataset}/.
Idempotent: existing parquet is skipped unless force=True.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

import nflreadpy as nfl
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CONFIG
from ingest._common import get_logger, raw_dir, record_count, resolve_current_season

log = get_logger("nflverse")

# dataset registry: name -> (loader, min_season | None for season-less)
# season-less datasets (draft/combine/contracts/ids/players/schedules) pulled whole.
SEASON_SCOPED: dict[str, tuple[Callable, int]] = {
    "pbp": (nfl.load_pbp, 2010),
    "player_stats": (nfl.load_player_stats, 2010),
    "rosters": (nfl.load_rosters, 2010),
    "rosters_weekly": (nfl.load_rosters_weekly, 2010),
    "snap_counts": (nfl.load_snap_counts, 2012),
    "depth_charts": (nfl.load_depth_charts, 2010),
    "injuries": (nfl.load_injuries, 2010),
    "ftn_charting": (nfl.load_ftn_charting, 2022),
}
# nextgen has 3 stat types, gated 2016+
NEXTGEN_TYPES = ["passing", "receiving", "rushing"]


def _out(dataset: str, season: int | str) -> Path:
    return raw_dir("nflverse") / dataset / f"{season}.parquet"


def _save(df: pl.DataFrame, dataset: str, season: int | str) -> int:
    p = _out(dataset, season)
    p.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(p)
    return df.height


def pull_season_scoped(seasons: list[int], force: bool = False) -> None:
    for dataset, (loader, min_season) in SEASON_SCOPED.items():
        for season in seasons:
            if season < min_season:
                record_count("nflverse", dataset, season, 0, "skip",
                             f"pre-min-season({min_season})")
                continue
            p = _out(dataset, season)
            if p.exists() and not force:
                rows = pl.scan_parquet(p).select(pl.len()).collect().item()
                log.info("cached %s %s (%d rows)", dataset, season, rows)
                continue
            try:
                df = loader(seasons=season)
                rows = _save(df, dataset, season)
                record_count("nflverse", dataset, season, rows)
                log.info("pulled %s %s -> %d rows", dataset, season, rows)
            except Exception as e:  # noqa: BLE001 — log, record, continue
                log.error("FAIL %s %s: %r", dataset, season, e)
                record_count("nflverse", dataset, season, 0, "fail", repr(e)[:200])


def pull_nextgen(seasons: list[int], force: bool = False) -> None:
    for stat_type in NEXTGEN_TYPES:
        dataset = f"nextgen_{stat_type}"
        for season in seasons:
            if season < 2016:
                record_count("nflverse", dataset, season, 0, "skip", "pre-2016")
                continue
            p = _out(dataset, season)
            if p.exists() and not force:
                rows = pl.scan_parquet(p).select(pl.len()).collect().item()
                log.info("cached %s %s (%d rows)", dataset, season, rows)
                continue
            try:
                df = nfl.load_nextgen_stats(seasons=season, stat_type=stat_type)
                rows = _save(df, dataset, season)
                record_count("nflverse", dataset, season, rows)
                log.info("pulled %s %s -> %d rows", dataset, season, rows)
            except Exception as e:  # noqa: BLE001
                log.error("FAIL %s %s: %r", dataset, season, e)
                record_count("nflverse", dataset, season, 0, "fail", repr(e)[:200])


def pull_seasonless(force: bool = False) -> None:
    jobs: dict[str, Callable[[], pl.DataFrame]] = {
        "draft_picks": lambda: nfl.load_draft_picks(seasons=True),
        "combine": lambda: nfl.load_combine(seasons=True),
        "contracts": nfl.load_contracts,
        "ff_playerids": nfl.load_ff_playerids,
        "schedules": lambda: nfl.load_schedules(seasons=True),
        "players": nfl.load_players,
    }
    for dataset, fn in jobs.items():
        p = _out(dataset, "all")
        if p.exists() and not force:
            rows = pl.scan_parquet(p).select(pl.len()).collect().item()
            log.info("cached %s (%d rows)", dataset, rows)
            continue
        try:
            df = fn()
            rows = _save(df, dataset, "all")
            record_count("nflverse", dataset, "all", rows)
            log.info("pulled %s -> %d rows", dataset, rows)
        except Exception as e:  # noqa: BLE001
            log.error("FAIL %s: %r", dataset, e)
            record_count("nflverse", dataset, "all", 0, "fail", repr(e)[:200])


def run(seasons: list[int] | None = None, force: bool = False) -> None:
    if seasons is None:
        end = CONFIG["seasons"]["end"] or resolve_current_season()
        seasons = list(range(CONFIG["seasons"]["start"], end + 1))
    log.info("nflverse ingest: seasons %s-%s", seasons[0], seasons[-1])
    pull_seasonless(force=force)
    pull_season_scoped(seasons, force=force)
    pull_nextgen(seasons, force=force)
    log.info("nflverse ingest complete")


if __name__ == "__main__":
    run()
