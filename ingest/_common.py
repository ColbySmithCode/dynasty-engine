"""Shared ingestion utilities.

Design rules honored by every ingest module:
  * cache raw responses under data/raw/{source}/{season}/ (idempotent, re-runnable)
  * be polite: per-client rate limiting, retry with backoff, real User-Agent
  * log row counts for every dataset written
  * never silently swallow an error — log it and record a FAIL in the ledger
"""
from __future__ import annotations

import json
import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CONFIG  # noqa: E402

# --------------------------------------------------------------------------- #
# logging
# --------------------------------------------------------------------------- #
_LOG_DIR = CONFIG.path("logs")
_LOG_DIR.mkdir(parents=True, exist_ok=True)


def get_logger(name: str) -> logging.Logger:
    log = logging.getLogger(name)
    if log.handlers:
        return log
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(name)-18s %(levelname)-7s %(message)s")
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    log.addHandler(sh)
    fh = logging.FileHandler(_LOG_DIR / "ingest.log")
    fh.setFormatter(fmt)
    log.addHandler(fh)
    log.propagate = False
    return log


# --------------------------------------------------------------------------- #
# raw cache paths
# --------------------------------------------------------------------------- #
def raw_dir(source: str, season: int | str | None = None) -> Path:
    base = CONFIG.path("data_raw") / source
    if season is not None:
        base = base / str(season)
    base.mkdir(parents=True, exist_ok=True)
    return base


# --------------------------------------------------------------------------- #
# row-count ledger  (GATE reporting reads this)
# --------------------------------------------------------------------------- #
_LEDGER = _LOG_DIR / "ingest_counts.jsonl"


def record_count(source: str, dataset: str, season: int | str | None,
                 rows: int, status: str = "ok", note: str = "") -> None:
    rec = {
        "ts": int(time.time()),
        "source": source,
        "dataset": dataset,
        "season": season,
        "rows": rows,
        "status": status,
        "note": note,
    }
    with open(_LEDGER, "a") as fh:
        fh.write(json.dumps(rec) + "\n")


def read_ledger() -> list[dict]:
    if not _LEDGER.exists():
        return []
    out = []
    for line in _LEDGER.read_text().splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


# --------------------------------------------------------------------------- #
# polite HTTP client
# --------------------------------------------------------------------------- #
@dataclass
class PoliteClient:
    """httpx client with per-instance rate limiting + retry/backoff."""

    user_agent: str
    rate_per_sec: float = 1.0
    timeout: float = CONFIG["http"]["timeout_seconds"]
    max_retries: int = CONFIG["http"]["max_retries"]
    backoff_base: float = CONFIG["http"]["backoff_base_seconds"]

    def __post_init__(self):
        self._min_interval = 1.0 / self.rate_per_sec if self.rate_per_sec else 0.0
        self._last = 0.0
        self._client = httpx.Client(
            headers={"User-Agent": self.user_agent},
            timeout=self.timeout,
            follow_redirects=True,
        )

    def _throttle(self) -> None:
        if self._min_interval <= 0:
            return
        wait = self._min_interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()

    def get(self, url: str, params: dict | None = None) -> httpx.Response:
        last_err: Exception | None = None
        for attempt in range(self.max_retries):
            self._throttle()
            try:
                r = self._client.get(url, params=params)
                if r.status_code == 429:
                    # honor Retry-After; otherwise a real cooldown (MFL throttles bursts)
                    ra = r.headers.get("Retry-After")
                    cooldown = float(ra) if (ra and ra.isdigit()) else 30.0 * (attempt + 1)
                    time.sleep(cooldown)
                    raise httpx.HTTPStatusError("429", request=r.request, response=r)
                if r.status_code in (500, 502, 503, 504):
                    raise httpx.HTTPStatusError(
                        f"retryable {r.status_code}", request=r.request, response=r)
                return r
            except Exception as e:  # noqa: BLE001 — deliberate retry, re-raised below
                last_err = e
                time.sleep(self.backoff_base * (2 ** attempt))
        assert last_err is not None
        raise last_err

    def get_json(self, url: str, params: dict | None = None) -> Any:
        return self.get(url, params=params).json()

    def close(self) -> None:
        self._client.close()


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj))


def write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def resolve_current_season() -> int:
    """Current NFL season per Sleeper /state/nfl (authoritative for 'present')."""
    ua = CONFIG["sleeper"]["user_agent"]
    r = httpx.get(f"{CONFIG['sleeper']['base_url']}/state/nfl",
                  headers={"User-Agent": ua}, timeout=30)
    return int(r.json()["season"])
