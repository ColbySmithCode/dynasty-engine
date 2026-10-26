"""Backfill snowball-corpus draft picks + transactions (bodies were counted in
Phase 1G but not persisted). Draft picks feed fact_league_draft_pick(source=corpus),
transactions feed fact_league_transaction (ADDENDUM_A A5 manager-tendency data).
Idempotent: cached files are skipped.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CONFIG
from ingest._common import PoliteClient, get_logger, write_json

log = get_logger("corpus_backfill")
CFG = CONFIG["corpus"]["sleeper_snowball"]
BASE = CONFIG["sleeper"]["base_url"]
LEAGUES = CONFIG.path("data_raw") / "sleeper_corpus" / "leagues"


def backfill_picks(client: PoliteClient) -> int:
    total = 0
    dirs = sorted(LEAGUES.glob("*"))
    for i, d in enumerate(dirs):
        drafts_p = d / "drafts.json"
        picks_p = d / "draft_picks.json"
        if picks_p.exists():
            total += len(json.loads(picks_p.read_text())); continue
        if not drafts_p.exists():
            continue
        picks = []
        for draft in json.loads(drafts_p.read_text()):
            did = draft.get("draft_id")
            if did:
                picks.extend(client.get_json(f"{BASE}/draft/{did}/picks") or [])
        write_json(picks_p, picks)
        total += len(picks)
        if (i + 1) % 50 == 0:
            log.info("picks: %d/%d leagues, %d picks", i + 1, len(dirs), total)
    log.info("corpus draft picks backfilled: %d", total)
    return total


def backfill_transactions(client: PoliteClient) -> int:
    """Transactions for the same bounded 150-league sample used in the gate."""
    parq = CONFIG.path("data_staging") / "sleeper_corpus_leagues.parquet"
    order = pl.read_parquet(parq)["league_id"].cast(pl.Utf8).to_list()[:CFG["transaction_leagues"]]
    weeks = CFG["transaction_weeks"]
    total = 0
    for i, lid in enumerate(order):
        out = LEAGUES / lid / "transactions.json"
        if out.exists():
            total += len(json.loads(out.read_text())); continue
        tx = []
        for wk in range(1, weeks + 1):
            tx.extend(client.get_json(f"{BASE}/league/{lid}/transactions/{wk}") or [])
        write_json(out, tx)
        total += len(tx)
        if (i + 1) % 25 == 0:
            log.info("transactions: %d/%d leagues, %d tx", i + 1, len(order), total)
    log.info("corpus transactions backfilled: %d", total)
    return total


def run() -> None:
    import os
    from ingest.freeze_corpus import is_frozen
    if is_frozen() and os.environ.get("VIGIL_UNFREEZE") != "1":
        log.warning("corpus FROZEN — refusing backfill (reproducibility). VIGIL_UNFREEZE=1 to override.")
        return
    client = PoliteClient(user_agent=CONFIG["sleeper"]["user_agent"],
                          rate_per_sec=CFG["rate_limit_per_sec"])
    try:
        backfill_picks(client)
        backfill_transactions(client)
    finally:
        client.close()
    log.info("corpus backfill complete")


if __name__ == "__main__":
    run()
