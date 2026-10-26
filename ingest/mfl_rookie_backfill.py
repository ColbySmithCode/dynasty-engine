"""Pre-2020 MFL rookie-only ADP backfill (exports/prereg_market_vs_engine_v2.md).

Same request as ingest/mfl_adp.py::fetch_cell (TYPE=adp, IS_KEEPER=R, IS_PPR, FCOUNT, PERIOD,
IS_MOCK=-1, CUTOFF, DETAILS, JSON=1), but raw responses go to a SEPARATE directory
data/raw/mfl_rookie_backfill/<pull_date>/<season>/ so the original sweep cache is never overwritten.
Read-only against the warehouse: this module pulls and summarizes; it does not load fact_adp.

Usage:  uv run python -m ingest.mfl_rookie_backfill 2010 2021
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CONFIG
from ingest._common import write_json
from ingest.mfl_adp import MFL, _client, _read, _summarize_cell

PERIODS = MFL["periods"]          # DRAFT, JUNE, JULY, AUG1, AUG15 -- same as the sweep
PPR, FCOUNT = -1, 12              # the engine rookie pool reads ppr -1, f12
ROOT = CONFIG.path("data_raw") / "mfl_rookie_backfill"


def pull(client, season: int, period: str, outdir: Path, is_keeper: str = "R") -> dict:
    path = outdir / str(season) / f"adp_{is_keeper}_ppr{PPR}_f{FCOUNT}_{period}.json"
    if not path.exists():
        url = f"{MFL['base_url']}/{season}/export"
        params = dict(TYPE="adp", IS_KEEPER=is_keeper, IS_PPR=PPR, FCOUNT=FCOUNT,
                      PERIOD=period, IS_MOCK=-1, CUTOFF=MFL["cutoff"],
                      DETAILS=MFL["details"], JSON=1)
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json(path, client.get_json(url, params=params))
    s = _summarize_cell(season, is_keeper, PPR, FCOUNT, period, _read(path))
    s["path"] = str(path)
    return s


def main(first: int, last: int) -> None:
    outdir = ROOT / dt.date.today().isoformat()
    client = _client()
    try:
        print(f"LIVE PULL  {MFL['base_url']}  IS_KEEPER=R  IS_PPR={PPR}  FCOUNT={FCOUNT}  "
              f"CUTOFF={MFL['cutoff']}  -> {outdir}")
        print(f"{'class':>5s}  " + "  ".join(f"{p:>16s}" for p in PERIODS))
        for season in range(first, last + 1):
            cells = [pull(client, season, p, outdir) for p in PERIODS]
            print(f"{season:5d}  " + "  ".join(
                f"{c['n_players']:4d}p/{c['total_drafts']:5d}d" + ("!" if c["error"] else " ") for c in cells))
            for c in cells:
                if c["error"]:
                    print(f"         {c['period']}: error={c['error']}")
        # the request named IS_KEEPER=2; confirm what the live API does with the numeric code
        c = pull(client, 2018, "DRAFT", outdir, is_keeper="2")
        print(f"\nnumeric check  2018 DRAFT IS_KEEPER=2: {c['n_players']} players / "
              f"{c['total_drafts']} drafts, error={c['error']}")
    finally:
        client.close()


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
