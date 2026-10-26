"""Phase 7 items 3 & 6b — READ-SIDE policy primitives (enforced, not just documented).

The 2026 guard (`assert_no_2026_in_models`) protects the WRITE side (model fits). But 2026 is
allowed into `fact_player_week` / `fact_adp`, which Phase 8 exports and the Phase 9 MCP server read
DIRECTLY. Without a read-side rule, 2026 (an incomplete season) reaches user-facing output through
a path the write-guard doesn't watch. These primitives make the policy code, so Phase 8/9 wrap
their output with them and the tests below fail if they don't.

Policy: user-facing output either (a) filters to season <= COMPLETE_SEASON, or (b) LABELS any 2026
row explicitly as in-progress. And every user-facing output surfaces table freshness from
`fact_refresh_status` (the machine-readable staleness signal written by jobs/refresh.py).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CONFIG

COMPLETE_SEASON = CONFIG["models"]["startup_backtest"]["last_complete_season"]  # 2025
LABEL = "2026 (in-progress)"   # the only acceptable way 2026 may appear in user-facing text


def filter_complete(df):
    """Return only complete-season rows (season <= COMPLETE_SEASON). For any polars/pandas df with
    a 'season' column. Phase 8/9 default path."""
    import polars as pl
    if hasattr(df, "filter") and "season" in getattr(df, "columns", []):
        try:
            return df.filter(pl.col("season") <= COMPLETE_SEASON)
        except Exception:
            return df[df["season"] <= COMPLETE_SEASON]      # pandas fallback
    return df


def assert_no_unlabeled_2026(text: str) -> None:
    """Raise if a user-facing string mentions a bare '2026' season without the in-progress label.
    (b)-path enforcement for prose exports / MCP responses."""
    for m in re.finditer(r"\b2026\b", text or ""):
        window = text[max(0, m.start() - 40): m.end() + 40]
        if "in-progress" not in window and "in progress" not in window and "offseason" not in window:
            raise AssertionError(
                "READ-SIDE 2026 POLICY: user-facing output mentions season 2026 without the "
                f"'{LABEL}' label near it. Filter to season<={COMPLETE_SEASON} or label it.")


def freshness_banner() -> str:
    """Read fact_refresh_status and render a one-line freshness banner. EVERY Phase 8/9 output MUST
    prepend this (the contract). Raises if the status table is missing — fail-soft would be silent
    corruption otherwise."""
    import duckdb
    con = duckdb.connect(str(CONFIG.path("warehouse")), read_only=True)
    try:
        rows = con.execute("SELECT table_name, stale, last_successful_refresh "
                           "FROM fact_refresh_status").fetchall()
    except Exception as e:  # noqa: BLE001
        raise AssertionError(
            "READ-SIDE FRESHNESS CONTRACT: fact_refresh_status is missing — run jobs.refresh "
            f"first; consumers must not emit output without a freshness signal ({e!r}).")
    finally:
        con.close()
    stale = [r[0] for r in rows if r[1]]
    if not rows:
        return "⚠ data freshness unknown (no refresh recorded)"
    return ("data fresh" if not stale else f"⚠ STALE tables: {', '.join(stale)}") + \
           f" (as of {max((r[2] or 0) for r in rows)})"


def emit(text: str, df=None) -> str:
    """Convenience wrapper a Phase 8/9 consumer uses: enforces the 2026 label rule and prepends the
    freshness banner. Returns the safe, freshness-annotated text."""
    assert_no_unlabeled_2026(text)
    return f"[{freshness_banner()}]\n{text}"
