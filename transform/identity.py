"""Phase 2 — Identity resolution -> dim_player with a stable player_uid.

Resolution order (per spec):
  1. nflverse load_ff_playerids  (spine; mfl_id is 100%-populated PK)
  2. DynastyProcess db_playerids  (fill gaps)
  3. Sleeper /players/nfl master  (bridge sleeper_id <-> gsis_id; fill sleeper gaps)
  4. Deterministic fallback: normalized name + position (+ birthdate/draft_year)
  5. Fuzzy (rapidfuzz >= threshold) -> REVIEW QUEUE, never auto-applied
  + data/manual_id_overrides.csv for the residue.

GATE 2: report match rate on fantasy-relevant players; <98% => stop and show failures.
Fantasy-relevant universes measured:
  A. MFL ADP players (market consensus)
  B. Sleeper dynasty-corpus rostered players (the dynasty market)
  C. nflverse production leaders (top-N per position per season)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import polars as pl
from rapidfuzz import fuzz, process

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CONFIG
from ingest._common import get_logger, raw_dir

log = get_logger("identity")
STG = CONFIG.path("data_staging")
FUZZY = CONFIG["identity"]["fuzzy_threshold"]
GATE = CONFIG["identity"]["match_rate_gate"]

SUFFIX = re.compile(r"\b(jr|sr|ii|iii|iv|v)\b\.?", re.I)
NONALNUM = re.compile(r"[^a-z0-9 ]")


def norm_name(name: str | None) -> str:
    if not name:
        return ""
    s = name.lower().replace(".", "").replace("'", "").replace("-", " ")
    s = SUFFIX.sub("", s)
    s = NONALNUM.sub("", s)
    return re.sub(r"\s+", " ", s).strip()


def surname(name: str | None) -> str:
    n = norm_name(name)
    return n.split()[-1] if n else ""


# full mfl_id -> canonical uid map (covers rows collapsed by _canonicalize)
_MFL_ALIAS: dict = {}

# CSV sentinels that must NOT be treated as real IDs (db_playerids uses "NA")
_SENTINELS = {"na", "null", "none", "nan", ""}
_ID_COLS = ["mfl_id", "gsis_id", "sleeper_id", "pfr_id", "espn_id", "fantasypros_id",
            "sportradar_id", "yahoo_id", "ktc_id"]


def _nullify(df: pl.DataFrame) -> pl.DataFrame:
    exprs = []
    for c in df.columns:
        exprs.append(
            pl.when(pl.col(c).cast(pl.Utf8).str.to_lowercase().str.strip_chars().is_in(list(_SENTINELS)))
              .then(None).otherwise(pl.col(c)).alias(c))
    return df.with_columns(exprs)


# --------------------------------------------------------------------------- #
# build dim_player
# --------------------------------------------------------------------------- #
def _load_crosswalk() -> pl.DataFrame:
    ff = pl.read_parquet(raw_dir("nflverse") / "ff_playerids" / "all.parquet")
    dp_files = sorted((CONFIG.path("data_raw") / "dynastyprocess").glob("*/db_playerids.csv"))
    if dp_files:
        db = pl.read_csv(dp_files[-1], infer_schema_length=0)
        # union any mfl_ids present in DP but missing from ff (gap fill)
        extra = db.filter(~pl.col("mfl_id").is_in(ff["mfl_id"].cast(pl.Utf8)))
        if extra.height:
            log.info("db_playerids adds %d mfl_ids missing from ff_playerids", extra.height)
            ff = pl.concat([ff.with_columns(pl.all().cast(pl.Utf8)),
                            extra.select(ff.columns).with_columns(pl.all().cast(pl.Utf8))],
                           how="vertical_relaxed")
    return _nullify(ff.with_columns(pl.all().cast(pl.Utf8)))  # kill "NA"/"" sentinels


def _sleeper_master() -> dict:
    p = raw_dir("sleeper") / "players_nfl.json"
    return json.loads(p.read_text()) if p.exists() else {}


def _load_overrides() -> dict:
    """manual_id_overrides.csv -> {(key_type, key): player_uid}. Human-confirmed
    residue (nicknames, name changes, suffixes) that fuzzy (>=threshold) won't auto-apply."""
    p = CONFIG.path("manual_id_overrides")
    if not p.exists():
        return {}
    df = pl.read_csv(p, infer_schema_length=0)
    return {(r["key_type"], r["key"]): r["player_uid"] for r in df.iter_rows(named=True)
            if r.get("player_uid")}


def build_dim_player() -> pl.DataFrame:
    cw = _load_crosswalk().unique(subset=["mfl_id"], keep="first")
    cw = cw.with_columns([
        ("M" + pl.col("mfl_id")).alias("player_uid"),
        pl.col("name").map_elements(norm_name, return_dtype=pl.Utf8).alias("norm_name"),
    ])
    keep = ["player_uid", "mfl_id", "gsis_id", "sleeper_id", "pfr_id", "espn_id",
            "fantasypros_id", "sportradar_id", "yahoo_id", "ktc_id", "name",
            "norm_name", "position", "team", "birthdate", "draft_year",
            "draft_round", "draft_pick", "college"]
    dim = cw.select([c for c in keep if c in cw.columns])

    # Sleeper master bridge: sleeper_id -> gsis_id (+ name/pos). Fill dim.sleeper_id
    # where a crosswalk gsis_id matches a sleeper master gsis_id.
    master = _sleeper_master()
    s_by_gsis = {}
    for sid, v in master.items():
        g = v.get("gsis_id")
        if g:
            s_by_gsis[g] = sid
    filled = (dim.with_columns(
        pl.when(pl.col("sleeper_id").is_null() & pl.col("gsis_id").is_not_null())
          .then(pl.col("gsis_id").replace_strict(s_by_gsis, default=None))
          .otherwise(pl.col("sleeper_id")).alias("sleeper_id")))
    n_added = (filled["sleeper_id"].is_not_null().sum() - dim["sleeper_id"].is_not_null().sum())
    log.info("sleeper master bridged %d additional sleeper_ids onto dim_player", n_added)
    dim = filled

    # (a) Null BAD attachments: a sleeper_id whose master surname != crosswalk surname
    #     is a mis-link (e.g., Marshall Faulk carrying Darrell Williams's sleeper_id).
    bad = 0
    fix_sid = []
    for row in dim.iter_rows(named=True):
        sid = row["sleeper_id"]
        v = master.get(sid) if sid else None
        if v and surname(v.get("full_name")) and surname(row["name"]) \
                and surname(v.get("full_name")) != surname(row["name"]):
            fix_sid.append(row["player_uid"]); bad += 1
    if fix_sid:
        dim = dim.with_columns(
            pl.when(pl.col("player_uid").is_in(fix_sid)).then(None)
              .otherwise(pl.col("sleeper_id")).alias("sleeper_id"))
        log.info("nulled %d mis-attached sleeper_ids (surname mismatch)", bad)

    # (b) Collapse over-splits: rows sharing a real gsis_id AND surname are one player.
    dim = _canonicalize(dim)

    STG.mkdir(parents=True, exist_ok=True)
    dim.write_parquet(STG / "dim_player.parquet")
    log.info("dim_player: %d rows -> %s", dim.height, STG / "dim_player.parquet")
    return dim


def _canonicalize(dim: pl.DataFrame) -> pl.DataFrame:
    """Merge same-person duplicates that share a real gsis_id (or sleeper_id) AND
    surname into one uid. Guarded by surname so a bad shared id across two DIFFERENT
    names (e.g. Fred Williams/Kevin Smith sharing a gsis) is NOT merged — flagged instead."""
    rows = dim.to_dicts()
    parent = {r["player_uid"]: r["player_uid"] for r in rows}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x

    for keycol in ("gsis_id", "sleeper_id"):
        from collections import defaultdict
        idx = defaultdict(list)
        for r in rows:
            if r.get(keycol):
                idx[r[keycol]].append(r)
        for grp in idx.values():
            if len(grp) < 2:
                continue
            # DETERMINISM (G10.4): incoming row order is not stable across (or within)
            # processes -- polars unique/sort do not preserve order -- so pin the canonical
            # base to the smallest mfl_id in the collision group, not the arbitrary first row.
            grp = sorted(grp, key=lambda r: r["mfl_id"])
            base = grp[0]
            for r in grp[1:]:
                if surname(r["name"]) == surname(base["name"]):
                    parent[find(r["player_uid"])] = find(base["player_uid"])
    canon = {u: find(u) for u in parent}
    # preserve mfl_id -> canonical uid for EVERY row so collapsed mfl_ids still resolve
    _MFL_ALIAS.clear()
    for r in rows:
        if r.get("mfl_id"):
            _MFL_ALIAS[r["mfl_id"]] = canon[r["player_uid"]]
    merged = sum(1 for u, c in canon.items() if u != c)
    if merged:
        log.info("canonicalized %d over-split duplicate rows into their base uid", merged)
    dim = dim.with_columns(
        pl.col("player_uid").replace_strict(canon, default=pl.col("player_uid")).alias("player_uid"))
    # keep the most-populated row per canonical uid.
    # DETERMINISM (G10.4): polars' default sort is unstable/parallel and reorders rows tied
    # on _pop nondeterministically even on byte-identical input, so the surviving
    # representative (hence which id columns populate dim_player) flipped within and across
    # processes. Impose a TOTAL order via mfl_id -- unique and non-null for every row at this
    # stage -- with keep="first" under maintain_order, so the pick is fully determined by
    # (_pop desc, mfl_id asc), independent of any incoming or internal ordering.
    assert dim["mfl_id"].null_count() == 0, \
        "G10.4 invariant: null mfl_id before representative pick"
    assert dim["mfl_id"].n_unique() == dim.height, \
        "G10.4 invariant: mfl_id not unique before representative pick"
    dim = (dim.with_columns(
        pl.sum_horizontal([pl.col(c).is_not_null().cast(pl.Int8) for c in _ID_COLS]).alias("_pop"))
        .sort(["_pop", "mfl_id"], descending=[True, False])
        .unique(subset=["player_uid"], keep="first", maintain_order=True).drop("_pop"))
    return dim


# --------------------------------------------------------------------------- #
# resolution indexes
# --------------------------------------------------------------------------- #
def _indexes(dim: pl.DataFrame):
    def idx(col):
        d = dim.filter(pl.col(col).is_not_null())
        return dict(zip(d[col].to_list(), d["player_uid"].to_list()))
    by_mfl = {**_MFL_ALIAS, **idx("mfl_id")}   # include collapsed mfl_ids
    by_sleeper = idx("sleeper_id")
    by_gsis = idx("gsis_id")
    # name+pos -> LIST of uids; ambiguous keys (>1) must NOT auto-resolve
    from collections import defaultdict
    by_namepos = defaultdict(list)
    for nm, pos, uid in zip(dim["norm_name"], dim["position"], dim["player_uid"]):
        if nm:
            by_namepos[(nm, pos)].append(uid)
    return by_mfl, by_sleeper, by_gsis, by_namepos


# --------------------------------------------------------------------------- #
# fantasy-relevant universes
# --------------------------------------------------------------------------- #
SKILL = {"QB", "RB", "WR", "TE"}


def _mfl_players_map() -> dict:
    """mfl_id -> {name, pos} via MFL TYPE=players export (cached). Lets us scope
    the ADP universe to real player positions (drop coaches / team-units / DST/K)."""
    import httpx
    p = raw_dir("mfl") / "players_2025.json"
    if p.exists():
        raw = json.loads(p.read_text())
    else:
        r = httpx.get("https://api.myfantasyleague.com/2025/export",
                      params=dict(TYPE="players", DETAILS=1, JSON=1),
                      headers={"User-Agent": CONFIG["mfl"]["user_agent"]},
                      timeout=60, follow_redirects=True)
        raw = r.json()
        p.write_text(json.dumps(raw))
    return {pp["id"]: {"name": pp.get("name"), "pos": pp.get("position")}
            for pp in raw["players"]["player"]}


def _mfl_universe() -> list[dict]:
    """Distinct SKILL-position mfl_ids in ADP with draft_pct>=5 (market-relevant),
    recent well-populated seasons. Coaches/team-units/DST/K are NOT players."""
    from ingest.mfl_adp import parse_cell_players
    pmap = _mfl_players_map()
    seen = {}
    for jp in (CONFIG.path("data_raw") / "mfl").glob("*/adp_*_f12_*.json"):
        parts = jp.stem.split("_")
        season = int(jp.parent.name)
        if season < 2019:
            continue
        fmt, ppr, fcount, period = parts[1], int(parts[2][3:]), int(parts[3][1:]), parts[4]
        for r in parse_cell_players(season, fmt, ppr, fcount, period):
            mid = r["mfl_id"]
            if (r["draft_pct"] or 0) >= 5 and mid and pmap.get(mid, {}).get("pos") in SKILL:
                seen[mid] = pmap[mid]["name"]
    return [{"mfl_id": k, "name": v} for k, v in seen.items()]


def _corpus_sleeper_universe() -> set[str]:
    seen = set()
    for f in (CONFIG.path("data_raw") / "sleeper_corpus" / "leagues").glob("*/rosters.json"):
        for team in json.loads(f.read_text()):
            for pid in (team.get("players") or []):
                seen.add(str(pid))
    return seen


def _nflverse_leaders() -> set[str]:
    """Top-36 per skill position per season by fantasy_points_ppr (relevance proxy).
    HERMETIC (Phase-7 Defect 2): read the cached raw player_stats, never live nflverse."""
    end = CONFIG["seasons"]["end"] or 2025
    seasons = list(range(2010, min(end, 2025) + 1))
    base = CONFIG.path("data_raw") / "nflverse" / "player_stats"
    frames = [pl.read_parquet(base / f"{s}.parquet") for s in seasons if (base / f"{s}.parquet").exists()]
    ps = pl.concat(frames, how="vertical_relaxed")
    ps = ps.filter(pl.col("position").is_in(["QB", "RB", "WR", "TE"]))
    agg = (ps.group_by(["season", "player_id", "position"])
             .agg(pl.col("fantasy_points_ppr").sum().alias("pts")))
    caps = {"QB": 24, "RB": 48, "WR": 60, "TE": 24}
    keep = set()
    for pos, n in caps.items():
        sub = agg.filter(pl.col("position") == pos)
        top = (sub.sort(["season", "pts"], descending=[False, True])
                  .group_by("season").head(n))
        keep |= set(top["player_id"].to_list())
    return keep


# --------------------------------------------------------------------------- #
# resolve + measure
# --------------------------------------------------------------------------- #
def _resolve_sleeper(sid, master, by_sleeper, by_gsis, by_namepos):
    if sid in by_sleeper:
        return by_sleeper[sid]
    v = master.get(sid, {})
    g = v.get("gsis_id")
    if g and g in by_gsis:
        return by_gsis[g]
    nm = norm_name(v.get("full_name") or f"{v.get('first_name','')} {v.get('last_name','')}")
    pos = v.get("position")
    cands = by_namepos.get((nm, pos), [])
    if len(cands) == 1:          # unique name+pos -> safe
        return cands[0]
    return None                 # ambiguous (>1) or none -> defer to fuzzy/review, never guess


def run() -> dict:
    dim = build_dim_player()
    # enrich dim with human-confirmed overrides (e.g., attach sleeper_id to the
    # existing uid) BEFORE indexing, so the mapping both resolves and joins.
    ovr = _load_overrides()
    for (ktype, key), uid in ovr.items():
        if ktype in dim.columns:
            dim = dim.with_columns(
                pl.when(pl.col("player_uid") == uid).then(pl.lit(key))
                  .otherwise(pl.col(ktype)).alias(ktype))
    dim.write_parquet(STG / "dim_player.parquet")
    by_mfl, by_sleeper, by_gsis, by_namepos = _indexes(dim)
    master = _sleeper_master()

    results = {}
    review_rows = []

    # A. MFL ADP
    mfl_u = _mfl_universe()
    miss = [r["mfl_id"] for r in mfl_u if r["mfl_id"] not in by_mfl]
    results["MFL_ADP"] = (len(mfl_u) - len(miss), len(mfl_u), miss)

    # fuzzy suggester over existing dim names
    name_choices = {uid: nm for uid, nm in zip(dim["player_uid"], dim["norm_name"]) if nm}
    choice_list = list(name_choices.values())
    choice_uids = list(name_choices.keys())

    def fuzzy_suggest(nm):
        if not nm or not choice_list:
            return None, 0
        m = process.extractOne(nm, choice_list, scorer=fuzz.token_sort_ratio)
        if m and m[1] >= FUZZY:
            return choice_uids[m[2]], m[1]
        return None, (m[1] if m else 0)

    # B. Corpus rostered sleeper players. Unmatched -> if fuzzy>=threshold it's an
    # AMBIGUOUS possible-duplicate (review, counts against gate); if fuzzy<threshold
    # it's a confidently-NEW Sleeper-only player -> MINT a new identity (resolved).
    overrides = _load_overrides()
    uid_bd = {u: b for u, b in zip(dim["player_uid"], dim["birthdate"])}
    corpus = _corpus_sleeper_universe()
    minted, ambiguous, overridden = [], [], 0
    for sid in corpus:
        if ("sleeper_id", sid) in overrides:   # human-confirmed mapping — never mint
            overridden += 1
            continue
        if _resolve_sleeper(sid, master, by_sleeper, by_gsis, by_namepos) is not None:
            continue
        v = master.get(sid, {})
        pos = v.get("position")
        if pos not in SKILL:            # non-skill roster cruft (K/DEF/picks) — not a player id
            continue
        nm = norm_name(v.get("full_name") or f"{v.get('first_name','')} {v.get('last_name','')}")

        def _mint():
            minted.append({"player_uid": "S" + sid, "sleeper_id": sid, "name": v.get("full_name"),
                           "norm_name": nm, "position": pos, "gsis_id": v.get("gsis_id"),
                           "team": v.get("team"), "draft_year": None})

        # ambiguous name+pos: disambiguate by birthdate before guessing
        cands = by_namepos.get((nm, pos), [])
        if len(cands) > 1:
            sbd = (v.get("birth_date") or "")[:10]
            bd_match = [c for c in cands if sbd and (uid_bd.get(c) or "")[:10] == sbd]
            if len(bd_match) == 1:            # birthdate pins the right one -> resolved
                continue
            if sbd and not bd_match:          # matches no candidate -> distinct NEW player
                _mint(); continue
            ambiguous.append({"source": "corpus", "key_type": "sleeper_id", "key": sid,
                              "name": v.get("full_name"), "position": pos,
                              "fuzzy_uid": ";".join(cands), "fuzzy_score": 100})
            continue

        uid, score = fuzzy_suggest(nm)
        if uid is not None:             # fuzzy>=92 -> ambiguous, needs human, DO NOT auto-merge
            ambiguous.append({"source": "corpus", "key_type": "sleeper_id", "key": sid,
                              "name": v.get("full_name"), "position": pos,
                              "fuzzy_uid": uid, "fuzzy_score": score})
        else:                           # confidently new -> mint
            _mint()
    # add minted identities to dim_player
    if minted:
        mdf = pl.DataFrame(minted)
        for c in dim.columns:
            if c not in mdf.columns:
                mdf = mdf.with_columns(pl.lit(None).cast(pl.Utf8).alias(c))
        dim = pl.concat([dim, mdf.select(dim.columns)], how="vertical_relaxed")
        dim.write_parquet(STG / "dim_player.parquet")
        log.info("minted %d new Sleeper-only identities into dim_player", len(minted))
    # skill-scoped corpus universe = resolvable via existing + minted (all get identities)
    corpus_skill = sum(1 for s in corpus if master.get(s, {}).get("position") in SKILL)
    resolved_corpus = corpus_skill - len(ambiguous)
    results["CORPUS_ROSTERS"] = (resolved_corpus, corpus_skill, [a["key"] for a in ambiguous])

    # C. nflverse production leaders
    leaders = _nflverse_leaders()
    lmiss = [g for g in leaders if g not in by_gsis]
    results["NFLVERSE_LEADERS"] = (len(leaders) - len(lmiss), len(leaders), lmiss)

    review_rows = ambiguous + [{"source": "mfl_adp", "key_type": "mfl_id", "key": m,
                                "name": None, "position": None,
                                "fuzzy_uid": None, "fuzzy_score": 0} for m in miss]
    if review_rows:
        pl.DataFrame(review_rows).write_csv(CONFIG.path("id_review_queue"))
    else:  # write empty queue with header for provenance
        pl.DataFrame(schema={"source": pl.Utf8, "key_type": pl.Utf8, "key": pl.Utf8,
                             "name": pl.Utf8, "position": pl.Utf8,
                             "fuzzy_uid": pl.Utf8, "fuzzy_score": pl.Float64}
                     ).write_csv(CONFIG.path("id_review_queue"))
    _print_report(results, minted=len(minted), ambiguous=len(ambiguous))
    return results


def _print_report(results: dict, minted: int = 0, ambiguous: int = 0) -> None:
    print("\n===== GATE 2 — Identity resolution match rates (skill players only) =====")
    overall_ok = True
    for name, (matched, total, misses) in results.items():
        rate = matched / total if total else 1.0
        flag = "OK " if rate >= GATE else "FAIL"
        if rate < GATE:
            overall_ok = False
        print(f"  [{flag}] {name:18s} {matched}/{total} = {rate:6.2%}  (gate {GATE:.0%})")
    print(f"\n  minted new Sleeper-only identities: {minted} | ambiguous(>= {FUZZY} fuzzy)"
          f" -> review: {ambiguous}")
    print(f"\nGATE 2 {'PASSED' if overall_ok else 'FAILED — stop and fix'} "
          f"(threshold {GATE:.0%} on every fantasy-relevant universe)")
    print("Review queue: data/id_review_queue.csv | overrides: data/manual_id_overrides.csv")


if __name__ == "__main__":
    run()
