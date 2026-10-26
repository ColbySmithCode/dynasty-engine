"""1G-b — Scott Fish Bowl public datasets (draft-behavior corpus).

The SFB data repos publish curated LISTS of league IDs (Sleeper + MFL) per year.
- Sleeper leagues: auth-free, so we pull full draft results (thousands of teams).
- MFL leagues: we store the ID list for provenance but DO NOT harvest them
  (1G-d: MFL per-league harvest is forbidden by their AUP).

SFB is best-ball with idiosyncratic (TE-premium) scoring, so treat DRAFT BEHAVIOR
as signal and its scoring as non-representative. Format skew: type 0 (redraft).
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CONFIG
from ingest._common import PoliteClient, get_logger, raw_dir, record_count, write_json

log = get_logger("sfb")
SFB = CONFIG["corpus"]["sfb"]
GH_RAW = SFB["base_url"]
GH_API = SFB["api_url"]


def discover_repos(client: PoliteClient) -> list[str]:
    """Config repos plus any org repo whose name contains 'sfb'."""
    repos = set(SFB["repos"])
    try:
        org = SFB["org_scan"]
        data = client.get_json(f"{GH_API}/orgs/{org}/repos?per_page=100")
        for r in data:
            if "sfb" in r["full_name"].lower() and "data" in r["full_name"].lower():
                repos.add(r["full_name"])
    except Exception as e:  # noqa: BLE001
        log.warning("org scan failed: %r", e)
    return sorted(repos)


def _league_ids(client: PoliteClient, repo: str, kind: str) -> pl.DataFrame | None:
    url = f"{GH_RAW}/{repo}/HEAD/league_ids_{kind}.csv"
    r = client.get(url)
    if r.status_code != 200:
        return None
    return pl.read_csv(io.BytesIO(r.content), infer_schema_length=0)


def pull_sleeper_league(client: PoliteClient, league_id: str, repo: str) -> dict | None:
    """Fetch one SFB Sleeper league's metadata + draft picks. Cached."""
    dest_dir = raw_dir("sfb", repo.split("/")[-1]) / "sleeper" / league_id
    lg_path = dest_dir / "league.json"
    picks_path = dest_dir / "draft_picks.json"
    if lg_path.exists() and picks_path.exists():
        import json
        lg = json.loads(lg_path.read_text())
        picks = json.loads(picks_path.read_text())
        return {"league_id": league_id, "n_picks": len(picks),
                "type": lg.get("settings", {}).get("type"),
                "size": lg.get("total_rosters")}
    base = CONFIG["sleeper"]["base_url"]
    lg = client.get_json(f"{base}/league/{league_id}")
    if not lg:
        return None
    write_json(lg_path, lg)
    drafts = client.get_json(f"{base}/league/{league_id}/drafts") or []
    all_picks = []
    for d in drafts:
        did = d.get("draft_id")
        if did:
            all_picks.extend(client.get_json(f"{base}/draft/{did}/picks") or [])
    write_json(picks_path, all_picks)
    return {"league_id": league_id, "n_picks": len(all_picks),
            "type": lg.get("settings", {}).get("type"),
            "size": lg.get("total_rosters")}


def run() -> None:
    if not SFB.get("enabled", True):
        log.info("SFB disabled"); return
    client = PoliteClient(user_agent=CONFIG["sleeper"]["user_agent"],
                          rate_per_sec=CONFIG["corpus"]["sleeper_snowball"]["rate_limit_per_sec"])
    try:
        repos = discover_repos(client)
        log.info("SFB repos: %s", repos)
        manifest = {"sleeper": [], "mfl_ids_stored_not_harvested": {}}
        for repo in repos:
            # Sleeper: pull drafts
            sl = _league_ids(client, repo, "sleeper")
            if sl is not None:
                ids = sl["league_id"].cast(pl.Utf8).to_list()
                record_count("sfb", f"{repo}:sleeper_league_ids", None, len(ids))
                log.info("%s sleeper: %d leagues", repo, len(ids))
                pulled = 0
                for lid in ids:
                    info = pull_sleeper_league(client, lid, repo)
                    if info:
                        info["repo"] = repo
                        manifest["sleeper"].append(info)
                        pulled += 1
                record_count("sfb", f"{repo}:sleeper_drafts", None, pulled)
            # MFL: store list ONLY (1G-d)
            mf = _league_ids(client, repo, "mfl")
            if mf is not None:
                mids = mf["league_id"].cast(pl.Utf8).to_list()
                manifest["mfl_ids_stored_not_harvested"][repo] = len(mids)
                write_json(raw_dir("sfb", repo.split("/")[-1]) / "mfl_league_ids.json", mids)
                record_count("sfb", f"{repo}:mfl_ids_NOT_harvested", None, len(mids), "skip",
                             "1G-d: MFL per-league harvest forbidden")
        # summary parquet
        if manifest["sleeper"]:
            df = pl.DataFrame(manifest["sleeper"])
            df.write_parquet(CONFIG.path("data_staging") / "sfb_sleeper_leagues.parquet")
            log.info("SFB done: %d sleeper leagues, %d total picks",
                     df.height, int(df["n_picks"].sum()))
    finally:
        client.close()


if __name__ == "__main__":
    run()
