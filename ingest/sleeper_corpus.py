"""1G-c — Sleeper public-league snowball (scoped dynasty corpus).

Auth-free discovery: league -> /league/{id}/users -> /user/{uid}/leagues/nfl/{season}.
Seeded from SFB Sleeper leagues (public research set); BFS expands to real DYNASTY
leagues (settings.type == 2). Hard scopes (config, all logged — never silent):
  * max_leagues (a few hundred; marginal value of #5000 is zero)
  * max_seasons_back (~7; Sleeper launched ~2017-18)
  * rate limit WELL under 1000/min
Transactions are pulled for a bounded sample of leagues (transaction_leagues).
"""
from __future__ import annotations

import json
import sys
from collections import Counter, deque
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CONFIG
from ingest._common import (
    PoliteClient, get_logger, raw_dir, record_count, resolve_current_season, write_json,
)

log = get_logger("sleeper_corpus")
CFG = CONFIG["corpus"]["sleeper_snowball"]
BASE = CONFIG["sleeper"]["base_url"]


def _seed_league_ids() -> list[str]:
    ids: list[str] = [str(x) for x in CFG.get("seed_leagues", [])]
    if CFG.get("seed_from_sfb"):
        p = CONFIG.path("data_staging") / "sfb_sleeper_leagues.parquet"
        if p.exists():
            ids += pl.read_parquet(p)["league_id"].cast(pl.Utf8).to_list()
    # de-dupe, preserve order
    seen, out = set(), []
    for i in ids:
        if i not in seen:
            seen.add(i); out.append(i)
    return out


def _cache(league_id: str, name: str, obj) -> None:
    write_json(raw_dir("sleeper_corpus", "leagues") / league_id / f"{name}.json", obj)


def run() -> None:
    if not CFG.get("enabled", True):
        log.info("snowball disabled"); return
    import os
    from ingest.freeze_corpus import is_frozen
    if is_frozen() and os.environ.get("VIGIL_UNFREEZE") != "1":
        log.warning("corpus is FROZEN (data/raw/sleeper_corpus/FROZEN.json) — refusing to "
                    "re-pull (would break reproducibility). Set VIGIL_UNFREEZE=1 to override.")
        return
    end = CONFIG["seasons"]["end"] or resolve_current_season()
    seasons = list(range(end - CFG["max_seasons_back"] + 1, end + 1))
    client = PoliteClient(user_agent=CONFIG["sleeper"]["user_agent"],
                          rate_per_sec=CFG["rate_limit_per_sec"])

    seed_leagues = _seed_league_ids()
    log.info("snowball seeds: %d leagues | seasons %s | cap %d dynasty leagues",
             len(seed_leagues), seasons, CFG["max_leagues"])

    visited_users: set[str] = set()
    kept: dict[str, dict] = {}          # dynasty league_id -> summary
    user_q: deque[str] = deque()
    league_q: deque[str] = deque(seed_leagues)
    seen_leagues: set[str] = set(seed_leagues)
    users_expanded = 0

    def enqueue_users_from_league(lid: str) -> None:
        try:
            users = client.get_json(f"{BASE}/league/{lid}/users") or []
        except Exception as e:  # noqa: BLE001
            log.warning("users fail %s: %r", lid, e); return
        for u in users:
            uid = u.get("user_id")
            if uid and uid not in visited_users:
                visited_users.add(uid); user_q.append(uid)

    def consider_user(uid: str) -> None:
        nonlocal users_expanded
        if users_expanded >= CFG["max_users_expanded"]:
            return
        users_expanded += 1
        for season in seasons:
            try:
                leagues = client.get_json(f"{BASE}/user/{uid}/leagues/nfl/{season}") or []
            except Exception:  # noqa: BLE001
                continue
            for lg in leagues:
                lid = lg.get("league_id")
                if not lid or lid in seen_leagues:
                    continue
                seen_leagues.add(lid)
                if (not CFG["dynasty_only"]) or lg.get("settings", {}).get("type") == 2:
                    league_q.append(lid)

    # BFS: alternate draining league_q (keep dynasty + expand users) and user_q
    while (league_q or user_q) and len(kept) < CFG["max_leagues"]:
        while league_q and len(kept) < CFG["max_leagues"]:
            lid = league_q.popleft()
            try:
                lg = client.get_json(f"{BASE}/league/{lid}")
            except Exception as e:  # noqa: BLE001
                log.warning("league fail %s: %r", lid, e); continue
            if not lg:
                continue
            is_dyn = lg.get("settings", {}).get("type") == 2
            enqueue_users_from_league(lid)          # expand from every seed/visited league
            if CFG["dynasty_only"] and not is_dyn:
                continue
            kept[lid] = _pull_league(client, lid, lg)
            if len(kept) % 25 == 0:
                log.info("  kept %d dynasty leagues (frontier: %d leagues, %d users)",
                         len(kept), len(league_q), len(user_q))
        if user_q and len(kept) < CFG["max_leagues"]:
            consider_user(user_q.popleft())

    _finalize(client, kept)
    client.close()


def _pull_league(client: PoliteClient, lid: str, lg: dict) -> dict:
    _cache(lid, "league", lg)
    users = client.get_json(f"{BASE}/league/{lid}/users") or []
    rosters = client.get_json(f"{BASE}/league/{lid}/rosters") or []
    drafts = client.get_json(f"{BASE}/league/{lid}/drafts") or []
    traded = client.get_json(f"{BASE}/league/{lid}/traded_picks") or []
    _cache(lid, "users", users); _cache(lid, "rosters", rosters)
    _cache(lid, "traded_picks", traded)
    npicks = 0
    for d in drafts:
        did = d.get("draft_id")
        if did:
            picks = client.get_json(f"{BASE}/draft/{did}/picks") or []
            npicks += len(picks)
    _cache(lid, "drafts", drafts)
    s = lg.get("settings", {})
    sc = lg.get("scoring_settings", {})
    return {
        "league_id": lid, "name": lg.get("name"), "season": lg.get("season"),
        "type": s.get("type"), "size": lg.get("total_rosters"),
        "prev": lg.get("previous_league_id"),
        "superflex": _is_superflex(lg.get("roster_positions", [])),
        "ppr": sc.get("rec"), "te_prem": sc.get("bonus_rec_te"),
        "best_ball": s.get("best_ball", 0),
        "n_users": len(users), "n_rosters": len(rosters),
        "n_draft_picks": npicks, "n_traded_picks": len(traded),
    }


def _is_superflex(positions: list[str]) -> bool:
    return any(p in ("SUPER_FLEX", "SUPERFLEX", "QB/RB/WR/TE") for p in positions)


def _finalize(client: PoliteClient, kept: dict[str, dict]) -> None:
    if not kept:
        log.warning("snowball kept 0 dynasty leagues"); record_count(
            "sleeper_corpus", "dynasty_leagues", None, 0, "warn", "no leagues found"); return
    rows = list(kept.values())
    # bounded transaction pull
    tx_cap = CFG["transaction_leagues"]; tx_weeks = CFG["transaction_weeks"]
    total_tx = 0; tx_pulled = 0
    for r in rows[:tx_cap]:
        lid = r["league_id"]; n = 0
        for wk in range(1, tx_weeks + 1):
            try:
                tx = client.get_json(f"{BASE}/league/{lid}/transactions/{wk}") or []
            except Exception:  # noqa: BLE001
                continue
            n += len(tx)
        r["n_transactions"] = n; total_tx += n; tx_pulled += 1
    for r in rows[tx_cap:]:
        r["n_transactions"] = None       # not pulled (bounded); explicit, not silent
    if tx_pulled < len(rows):
        log.info("transactions pulled for %d/%d leagues (bounded by transaction_leagues=%d)",
                 tx_pulled, len(rows), tx_cap)

    df = pl.DataFrame(rows)
    df.write_parquet(CONFIG.path("data_staging") / "sleeper_corpus_leagues.parquet")
    record_count("sleeper_corpus", "dynasty_leagues", None, df.height)
    record_count("sleeper_corpus", "draft_picks", None, int(df["n_draft_picks"].sum()))
    record_count("sleeper_corpus", "transactions_sampled", None, total_tx, "ok",
                 f"from {tx_pulled} leagues")
    log.info("snowball complete: %d dynasty leagues, %d draft picks, %d transactions (sampled %d leagues)",
             df.height, int(df["n_draft_picks"].sum()), total_tx, tx_pulled)


if __name__ == "__main__":
    run()
