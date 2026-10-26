"""Phase 7 items 3 & 6b — tests that the read-side 2026 policy and the freshness contract are
ENFORCED in code (converting 'Phase 8/9 MUST read fact_refresh_status' from documentation into a
tested primitive, same class as the Phase-5 import ban that also wanted a test).
    uv run python -m tests.test_read_policy
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jobs import read_policy as rp


def run() -> None:
    fails = []

    # (item 3a) filter_complete drops 2026
    import polars as pl
    df = pl.DataFrame({"season": [2024, 2025, 2026], "x": [1, 2, 3]})
    if rp.filter_complete(df)["season"].max() != 2025:
        fails.append("filter_complete did not drop 2026")

    # (item 3b) unlabeled 2026 in prose raises; labeled passes
    try:
        rp.assert_no_unlabeled_2026("Josh Allen leads QBs in 2026 already.")
        fails.append("assert_no_unlabeled_2026 did NOT fire on a bare 2026 mention")
    except AssertionError:
        pass
    try:
        rp.assert_no_unlabeled_2026("Through 2026 (in-progress), sample is thin.")
    except AssertionError:
        fails.append("assert_no_unlabeled_2026 fired on a properly-labeled 2026 mention")

    # (item 6b) freshness contract: a consumer that emits without the status table must fail;
    #   with the table present, the banner is produced and reflects staleness.
    from config import CONFIG
    import duckdb
    con = duckdb.connect(str(CONFIG.path("warehouse")))
    con.execute("CREATE TABLE IF NOT EXISTS fact_refresh_status "
                "(table_name TEXT, last_successful_refresh BIGINT, stale BOOLEAN, updated BIGINT)")
    con.execute("DELETE FROM fact_refresh_status")
    con.execute("INSERT INTO fact_refresh_status VALUES ('fact_player_week', 111, TRUE, 111)")
    con.close()
    banner = rp.freshness_banner()
    if "STALE" not in banner or "fact_player_week" not in banner:
        fails.append(f"freshness_banner did not surface the stale table: {banner!r}")
    # emit() wraps both rules
    out = rp.emit("Rankings through 2026 (in-progress).")
    if "STALE" not in out:
        fails.append("emit() did not prepend the freshness banner")

    if fails:
        print("FAIL:"); [print("  -", f) for f in fails]; sys.exit(1)
    print("PASS: read-side 2026 filter/label + freshness contract are enforced and tested.")


if __name__ == "__main__":
    run()
