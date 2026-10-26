"""Central config loader. Every module imports `CONFIG` from here.

No module should hardcode a path, season bound, rate limit, or scoring value —
they all live in config.yaml and are reached through this object.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = REPO_ROOT / "config.yaml"


def _load_dotenv(path: Path = REPO_ROOT / ".env") -> None:
    """Read KEY=VALUE lines from .env into the environment (no extra dependency).
    Real environment variables win over the file."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


class Config:
    """Thin, dotted-access wrapper over config.yaml with path resolution."""

    def __init__(self, raw: dict[str, Any]):
        self._raw = raw

    # --- generic access ----------------------------------------------------
    def __getitem__(self, key: str) -> Any:
        return self._raw[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self._raw.get(key, default)

    @property
    def raw(self) -> dict[str, Any]:
        return self._raw

    # --- resolved paths ----------------------------------------------------
    def path(self, key: str) -> Path:
        """Return an absolute Path for any entry under `paths:`."""
        p = Path(self._raw["paths"][key])
        return p if p.is_absolute() else (REPO_ROOT / p)

    def ensure_dirs(self) -> None:
        for key in ("data_raw", "data_staging", "models", "exports", "logs"):
            self.path(key).mkdir(parents=True, exist_ok=True)

    # --- convenience -------------------------------------------------------
    def seasons(self, end: int | None = None) -> list[int]:
        start = self._raw["seasons"]["start"]
        end = end or self._raw["seasons"]["end"]
        if end is None:
            raise ValueError(
                "seasons.end is null; pass end= (resolve from Sleeper /state/nfl)"
            )
        return list(range(start, end + 1))

    @property
    def scoring_profiles(self) -> dict[str, dict]:
        return self._raw["scoring_profiles"]


@lru_cache(maxsize=1)
def load_config(path: str | os.PathLike | None = None) -> Config:
    p = Path(path) if path else CONFIG_PATH
    with open(p, "r") as fh:
        raw = yaml.safe_load(fh)
    _load_dotenv()
    league_id = os.environ.get("SLEEPER_LEAGUE_ID")
    if league_id:
        raw["sleeper"]["league_id"] = league_id
    return Config(raw)


CONFIG = load_config()

if __name__ == "__main__":
    c = CONFIG
    print("repo root      :", REPO_ROOT)
    print("warehouse      :", c.path("warehouse"))
    print("seasons start  :", c["seasons"]["start"])
    print("scoring profiles:", list(c.scoring_profiles.keys()))
    print("mfl periods    :", c["mfl"]["periods"])
    print("trade delta    :", c["trade_engine"]["discount_delta"])
    c.ensure_dirs()
    print("dirs ensured OK")
