"""Phase 7 item 2 — NEGATIVE test of the 2026 model guard.

`assert_no_2026_in_models()` has only ever passed vacuously (no 2026 data exists yet). This
injects a synthetic 2026 row into each guarded column (season / year / s0) of a model artifact and
confirms the assertion FAILS in every case — and passes when the row is 2025. Run:
    uv run python -m tests.test_2026_guard
"""
from __future__ import annotations

import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CONFIG
from jobs.refresh import assert_no_2026_in_models

MODELS = CONFIG.path("models")
PROBE = MODELS / "_test_2026_guard_probe.parquet"


def _write_probe(col: str, year: int):
    pl.DataFrame({col: [year, year - 1], "v": [1.0, 2.0]}).write_parquet(PROBE)


def run() -> None:
    failures = []
    try:
        # 1) baseline: guard passes with no probe (2026 absent from real artifacts)
        assert_no_2026_in_models()

        # 2) each guarded column with a 2026 row -> MUST raise
        for col in ("season", "year", "s0"):
            _write_probe(col, 2026)
            raised = False
            try:
                assert_no_2026_in_models()
            except AssertionError as e:
                raised = True
                assert "2026 GUARD TRIPPED" in str(e), f"wrong error for {col}: {e}"
            if not raised:
                failures.append(f"guard did NOT fire for injected 2026 in column '{col}'")

        # 3) a 2025 row must NOT trip the guard
        _write_probe("season", 2025)
        try:
            assert_no_2026_in_models()
        except AssertionError:
            failures.append("guard fired on a 2025 row (false positive)")
    finally:
        if PROBE.exists():
            PROBE.unlink()

    if failures:
        print("FAIL:")
        for f in failures:
            print("  -", f)
        sys.exit(1)
    print("PASS: 2026 guard fires for season/year/s0 = 2026 in a model artifact, and not for 2025.")


if __name__ == "__main__":
    run()
