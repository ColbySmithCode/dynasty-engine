"""1B + 1G-a — MyFantasyLeague aggregate ADP sweep.

The crown jewel: a time series of consensus draft opinion, aggregated across
thousands of real leagues, back to 1999. Cartesian sweep over
    seasons x format(N/K/R) x ppr(-1/0/1) x league_size x period(~5)
Every cell is one MFL `TYPE=adp` report; MFL reports `totalDrafts` per cell =
the sample size. Idempotent: cached cells are skipped on re-run.

Formats (letter codes — numeric 0/1/2 is rejected by the current API):
    N = redraft, K = keeper/dynasty-startup, R = rookie-only.

Per MFL acceptable-use: aggregate reports ONLY. No per-league harvest (1G-d).
"""
from __future__ import annotations

import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CONFIG
from ingest._common import (
    PoliteClient, get_logger, raw_dir, record_count, write_json,
)

log = get_logger("mfl_adp")
MFL = CONFIG["mfl"]


def _client() -> PoliteClient:
    # MFL throttles bursts even at 1/sec; pace a touch slower to avoid 429 storms.
    return PoliteClient(user_agent=MFL["user_agent"], rate_per_sec=0.7)


def _cell_path(season: int, fmt_code: str, ppr: int, fcount: int, period: str) -> Path:
    fname = f"adp_{fmt_code}_ppr{ppr}_f{fcount}_{period}.json"
    return raw_dir("mfl", season) / fname


def fetch_cell(client: PoliteClient, season: int, fmt_code: str, ppr: int,
               fcount: int, period: str, force: bool = False) -> dict:
    """Fetch one ADP cell, cache raw JSON, return a summary dict."""
    path = _cell_path(season, fmt_code, ppr, fcount, period)
    if path.exists() and not force:
        raw = _read(path)
    else:
        url = f"{MFL['base_url']}/{season}/export"
        params = dict(TYPE="adp", IS_KEEPER=fmt_code, IS_PPR=ppr, FCOUNT=fcount,
                      PERIOD=period, IS_MOCK=-1, CUTOFF=MFL["cutoff"],
                      DETAILS=MFL["details"], JSON=1)
        raw = client.get_json(url, params=params)
        write_json(path, raw)
    return _summarize_cell(season, fmt_code, ppr, fcount, period, raw)


def _read(path: Path) -> dict:
    import json
    return json.loads(path.read_text())


def _summarize_cell(season, fmt_code, ppr, fcount, period, raw) -> dict:
    err = raw.get("error")
    if isinstance(err, dict):
        err = err.get("$t")
    adp = raw.get("adp", {}) or {}
    players = adp.get("player", []) if isinstance(adp, dict) else []
    if isinstance(players, dict):  # MFL returns a bare dict for single-row results
        players = [players]
    total_drafts = int(adp.get("totalDrafts") or 0) if isinstance(adp, dict) else 0
    return {
        "season": season, "format": fmt_code, "ppr": ppr, "fcount": fcount,
        "period": period, "n_players": len(players), "total_drafts": total_drafts,
        "error": err,
    }


def parse_cell_players(season, fmt_code, ppr, fcount, period) -> list[dict]:
    """Return per-player ADP rows for one cached cell (for warehouse load)."""
    path = _cell_path(season, fmt_code, ppr, fcount, period)
    if not path.exists():
        return []
    raw = _read(path)
    adp = raw.get("adp", {}) or {}
    players = adp.get("player", [])
    if isinstance(players, dict):
        players = [players]
    rows = []
    for p in players:
        rows.append({
            "season": season, "format": fmt_code, "ppr": ppr, "fcount": fcount,
            "period": period,
            "mfl_id": p.get("id"),
            "adp": _f(p.get("averagePick")),
            "min_pick": _f(p.get("minPick")),
            "max_pick": _f(p.get("maxPick")),
            "draft_pct": _f(p.get("draftSelPct")),
            "drafts_selected_in": _i(p.get("draftsSelectedIn")),
            "rank": _i(p.get("rank")),
        })
    return rows


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _i(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def run_sweep(seasons: list[int], force: bool = False,
              fcounts: list[int] | None = None, pprs: list[int] | None = None,
              periods: list[str] | None = None) -> pl.DataFrame:
    formats = MFL["formats"]          # {redraft:N, dynasty:K, rookie:R}
    pprs = pprs if pprs is not None else MFL["is_ppr"]
    fcounts = fcounts if fcounts is not None else MFL["fcount"]
    periods = periods if periods is not None else MFL["periods"]
    total_cells = len(seasons) * len(formats) * len(pprs) * len(fcounts) * len(periods)
    log.info("MFL ADP sweep: %d cells (%d seasons x %d fmt x %d ppr x %d size x %d period)",
             total_cells, len(seasons), len(formats), len(pprs), len(fcounts), len(periods))
    client = _client()
    summaries: list[dict] = []
    done = 0
    try:
        for season in seasons:
            for fmt_name, fmt_code in formats.items():
                for ppr in pprs:
                    for fcount in fcounts:
                        for period in periods:
                            done += 1
                            try:
                                s = fetch_cell(client, season, fmt_code, ppr,
                                               fcount, period, force=force)
                            except Exception as e:  # noqa: BLE001 — cell fail never kills sweep
                                log.error("cell FAIL %s %s ppr%s f%s %s: %r",
                                          season, fmt_code, ppr, fcount, period, e)
                                s = {"season": season, "format": fmt_code, "ppr": ppr,
                                     "fcount": fcount, "period": period, "n_players": 0,
                                     "total_drafts": 0, "error": repr(e)[:120]}
                            s["format_name"] = fmt_name
                            summaries.append(s)
                            if done % 50 == 0 or done == total_cells:
                                log.info("  %d/%d cells (%s %s ppr%s f%s %s -> %s drafts)",
                                         done, total_cells, season, fmt_code, ppr,
                                         fcount, period, s["total_drafts"])
    finally:
        client.close()
    df = pl.DataFrame(summaries)
    out = CONFIG.path("data_staging") / "mfl_adp_matrix.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(out)
    # ledger: one row per (season,format) aggregate
    agg = (df.group_by(["season", "format"])
             .agg(pl.col("total_drafts").max().alias("max_drafts"),
                  pl.col("n_players").sum().alias("player_rows")))
    for r in agg.iter_rows(named=True):
        record_count("mfl", f"adp_{r['format']}", r["season"],
                     r["player_rows"], note=f"max_drafts={r['max_drafts']}")
    log.info("sweep complete -> %s (%d cell rows)", out, len(df))
    return df


def rebuild_matrix_from_cache(fcounts: list[int] | None = None) -> pl.DataFrame:
    """Reconstruct the sweep matrix from cached cell JSONs (resilience: use if
    the live sweep is interrupted before its final parquet write)."""
    fcounts = fcounts or [12]
    rows = []
    for season_dir in sorted((CONFIG.path("data_raw") / "mfl").glob("*")):
        if not season_dir.is_dir():
            continue
        season = int(season_dir.name)
        for jp in season_dir.glob("adp_*.json"):
            # adp_{fmt}_ppr{ppr}_f{fcount}_{period}.json
            stem = jp.stem  # adp_K_ppr-1_f12_DRAFT
            parts = stem.split("_")
            fmt_code = parts[1]
            ppr = int(parts[2].replace("ppr", ""))
            fcount = int(parts[3].replace("f", ""))
            period = parts[4]
            if fcount not in fcounts:
                continue
            rows.append(_summarize_cell(season, fmt_code, ppr, fcount, period, _read(jp)))
    df = pl.DataFrame(rows)
    out = CONFIG.path("data_staging") / "mfl_adp_matrix.parquet"
    df.write_parquet(out)
    log.info("rebuilt matrix from cache: %d cells -> %s", df.height, out)
    return df


if __name__ == "__main__":
    end = CONFIG["seasons"]["end"] or __import__("ingest._common", fromlist=["x"]).resolve_current_season()
    seasons = list(range(CONFIG["seasons"]["start"], end + 1))
    run_sweep(seasons)
