"""1D — DynastyProcess market values (GitHub raw files).

Snapshot weekly, keep EVERY version — value *history* is how we detect market
inefficiency; a single current snapshot is nearly worthless for that.
Snapshots are date-stamped under data/raw/dynastyprocess/{YYYY-MM-DD}/.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CONFIG
from ingest._common import PoliteClient, get_logger, raw_dir, record_count, write_bytes

log = get_logger("dynastyprocess")
DP = CONFIG["dynastyprocess"]


def run(snapshot_date: str | None = None, force: bool = False) -> None:
    snapshot_date = snapshot_date or dt.date.today().isoformat()
    outdir = raw_dir("dynastyprocess") / snapshot_date
    outdir.mkdir(parents=True, exist_ok=True)
    client = PoliteClient(user_agent=CONFIG["mfl"]["user_agent"], rate_per_sec=2)
    try:
        for key, fname in DP["files"].items():
            dest = outdir / fname
            if dest.exists() and not force:
                log.info("cached %s (%s)", key, snapshot_date)
                rows = _rowcount(dest)
                record_count("dynastyprocess", key, snapshot_date, rows, "cached")
                continue
            url = f"{DP['base_url']}/{fname}"
            try:
                r = client.get(url)
                r.raise_for_status()
                write_bytes(dest, r.content)
                rows = _rowcount(dest)
                record_count("dynastyprocess", key, snapshot_date, rows)
                log.info("pulled %s -> %d rows (%d bytes)", key, rows, len(r.content))
            except Exception as e:  # noqa: BLE001
                log.error("FAIL %s: %r", key, e)
                record_count("dynastyprocess", key, snapshot_date, 0, "fail", repr(e)[:200])
    finally:
        client.close()


def _rowcount(path: Path) -> int:
    try:
        if path.suffix == ".parquet":
            return pl.scan_parquet(path).select(pl.len()).collect().item()
        return pl.scan_csv(path, infer_schema_length=0).select(pl.len()).collect().item()
    except Exception:  # noqa: BLE001
        return -1


if __name__ == "__main__":
    run()
