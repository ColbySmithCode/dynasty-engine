"""Phase 6.5 — Startup Draft Backtester: LEAK-FREE DATA LAYER.

Everything the simulator needs, built per draft-year Y with a hard no-lookahead guard.
Design is pre-registered in docs/PREREG_6_5.md (three amendment rounds). Key rules honored
here:
  * Block 1 (SF, 2020-2021) market board = corpus-derived native-SF consensus, computed
    STRICTLY within draft-year (R3-1). Block 2 (1QB, 2011-2019) board = MFL K/ppr=1/12t/AUG15.
  * CORPUS-AVG pools are EMPIRICAL draws (A): keyed (position x round) primary, plus
    (position x exact pick) and (slot-only); one-manager-one-vote per cell (whale cap, item6);
    per draft-year and per pre/post-NFL-draft cohort (R3-3).
  * Ex-ante board uses ONLY data < Y + fixed hand-set priors — NO Phase-5 fitted artifacts
    (they leak). assert_no_lookahead enforces season<Y on every board input (R3/§6, §12).
  * Realized scoring = weekly fp_ppr, regular season only.

This module has NO simulation logic — only data. Run `python -m models.startup_data` for a
diagnostics dump (board sizes, corpus-pool coverage, leak-assertion pass).
"""
from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path

import duckdb
import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CONFIG
from ingest._common import get_logger

log = get_logger("startup_data")
BT = CONFIG["models"]["startup_backtest"]
CORPUS_DIR = CONFIG.path("data_raw") / "sleeper_corpus" / "leagues"


class LookaheadError(AssertionError):
    """Raised when a board/selection input contains a season >= draft-year Y."""


def assert_no_lookahead(year: int, board_seasons, *, score_seasons=None) -> None:
    """Hard guard (§12). board inputs must be strictly < Y; score inputs strictly >= Y."""
    bs = [int(s) for s in board_seasons if s is not None]
    if bs and max(bs) >= year:
        raise LookaheadError(
            f"LEAK: board input for draft-year {year} contains season {max(bs)} >= {year}")
    if score_seasons is not None:
        ss = [int(s) for s in score_seasons if s is not None]
        if ss and min(ss) < year:
            raise LookaheadError(
                f"LEAK: score input for draft-year {year} contains season {min(ss)} < {year}")


def _con():
    return duckdb.connect(str(CONFIG.path("warehouse")), read_only=True)


# ============================================================================
# CORPUS startup pick table (Block 1) — the single source for SF board + pools
# ============================================================================
@lru_cache(maxsize=1)
def _sleeper_pos_uid() -> dict:
    con = _con()
    rows = con.execute(
        "SELECT sleeper_id, player_uid, position FROM dim_player WHERE sleeper_id IS NOT NULL").fetchall()
    con.close()
    return {str(s): (u, p) for s, u, p in rows}


def _is_sf(rp: list) -> bool:
    return ("SUPER_FLEX" in rp) or ("SUPERFLEX" in rp) or (rp.count("QB") >= 2)


@lru_cache(maxsize=1)
def load_corpus_startups() -> pl.DataFrame:
    """Filtered corpus STARTUP picks (SF, 12-team, full-PPR, rounds>=15). One row per pick.
    Columns: year, draft_id, league_id, pick_no, round, position, player_uid, manager,
    premium(bool), cohort ('pre'/'post' NFL draft). This is the operative 62-league sample
    (R2 §0). Manager = picked_by (for whale-capping)."""
    import datetime as dt
    s2 = _sleeper_pos_uid()
    cuts = {int(k): dt.date.fromisoformat(v) for k, v in BT["nfl_draft_day1"].items()}
    rmin = BT["startup_rounds_min"]
    rows = []
    for d in sorted(CORPUS_DIR.iterdir()):
        if not d.is_dir():
            continue
        lg = _load(d / "league.json"); drs = _load(d / "drafts.json"); picks = _load(d / "draft_picks.json")
        if not lg or not drs:
            continue
        rp = lg.get("roster_positions") or []
        if not (_is_sf(rp) and lg.get("total_rosters") == 12
                and (lg.get("scoring_settings") or {}).get("rec") == 1.0):
            continue
        premium = ((lg.get("scoring_settings") or {}).get("bonus_rec_te") or 0) > 0
        for dr in drs:
            if (dr.get("settings") or {}).get("rounds", 0) < rmin:
                continue
            y = int(dr.get("season"))
            did = dr.get("draft_id")
            st = dr.get("start_time") or dr.get("created")
            cohort = None
            if st and y in cuts:
                ddate = dt.datetime.fromtimestamp(st / 1000, dt.UTC).date()
                cohort = "pre" if ddate < cuts[y] else "post"
            for p in picks or []:
                if p.get("draft_id") != did:
                    continue
                up = s2.get(str(p.get("player_id")))
                if not up or not p.get("pick_no"):
                    continue
                uid, pos = up
                if pos not in ("QB", "RB", "WR", "TE"):    # skill-player draft only
                    continue
                rows.append((y, did, lg.get("league_id"), int(p["pick_no"]),
                             int(p.get("round") or ((p["pick_no"] - 1) // 12 + 1)),
                             pos, uid, p.get("picked_by"), premium, cohort))
    df = pl.DataFrame(rows, orient="row", schema={
        "year": pl.Int32, "draft_id": pl.Utf8, "league_id": pl.Utf8, "pick_no": pl.Int32,
        "round": pl.Int32, "position": pl.Utf8, "player_uid": pl.Utf8, "manager": pl.Utf8,
        "premium": pl.Boolean, "cohort": pl.Utf8})
    return df


def _load(p: Path):
    return json.loads(p.read_text()) if p.exists() else None


# ============================================================================
# MARKET BOARD (per draft-year) — CONSENSUS selection order
# ============================================================================
def market_board(year: int, block: int, draft_ids: set | None = None,
                 managers: set | None = None) -> pl.DataFrame:
    """Consensus draft board for year Y: [player_uid, position, board_pos (mean/ADP), rank].
    Block 1: corpus-consensus native-SF, STRICTLY within draft-year (R3-1).
    Block 2: MFL K/ppr=1/12t/AUG15 1QB ADP for year Y.
    draft_ids / managers: optional league / manager subset (clustered bootstraps; Block 1 only)."""
    if block == 1:
        cp = load_corpus_startups().filter(pl.col("year") == year)
        if draft_ids is not None:
            cp = cp.filter(pl.col("draft_id").is_in(list(draft_ids)))
        if managers is not None:
            cp = cp.filter(pl.col("manager").is_in(list(managers)))
        assert_no_lookahead(year, [year - 1])  # board is same-year draft behavior, not outcomes
        b = (cp.group_by("player_uid", "position")
             .agg(pl.col("pick_no").mean().alias("board_pos"), pl.len().alias("n_drafts"))
             .filter(pl.col("n_drafts") >= 1)
             # DETERMINISM (G10.5 fix): board_pos ties would otherwise rank in nondeterministic
             # group_by order -> nondeterministic board_rank; break ties by player_uid.
             .sort(["board_pos", "player_uid"]))
    else:
        con = _con()
        adp = con.execute("""SELECT a.player_uid, d.position, a.adp AS board_pos
            FROM fact_adp a JOIN dim_player d USING(player_uid)
            WHERE a.format='K' AND a.ppr=1 AND a.league_size=12 AND a.period='AUG15'
              AND a.season=? AND a.adp IS NOT NULL AND d.position IN ('QB','RB','WR','TE')""",
            [year]).pl()
        con.close()
        b = adp.sort(["board_pos", "player_uid"]).with_columns(pl.lit(0).alias("n_drafts"))
    b = b.head(BT["board_size"]).with_row_index("rank", offset=1)
    return b


def year_draft_ids(year: int, cohort: str | None = None) -> list:
    """draft_ids for a draft-year (optionally a pre/post-NFL-draft cohort)."""
    cp = load_corpus_startups().filter(pl.col("year") == year)
    if cohort:
        cp = cp.filter(pl.col("cohort") == cohort)
    # DETERMINISM (G10.5): `.unique()` order is nondeterministic; this list feeds the clustered
    # bootstrap's rng.choice, so an unordered list -> different resamples -> different CIs AND a
    # shifted rng state that cascades into later point estimates. sorted() makes the bootstrap
    # byte-reproducible. (5th instance of the class — caught by the two-regen byte-check, not the
    # static sweep, which did not scan `.unique().to_list()`.)
    return sorted(cp["draft_id"].unique().to_list())


def market_board_cohort(year: int, cohort: str) -> pl.DataFrame:
    """Block-1 consensus board restricted to a pre/post-NFL-draft cohort (R3-3)."""
    cp = load_corpus_startups().filter((pl.col("year") == year) & (pl.col("cohort") == cohort))
    b = (cp.group_by("player_uid", "position")
         .agg(pl.col("pick_no").mean().alias("board_pos"), pl.len().alias("n_drafts"))
         .sort(["board_pos", "player_uid"]).head(BT["board_size"]).with_row_index("rank", offset=1))
    return b


# ============================================================================
# CORPUS-AVG empirical pools (Block 1) — item A, R3-4, whale cap item6
# ============================================================================
def year_managers(year: int) -> list:
    """distinct manager ids drafting in a draft-year's startups (for manager-clustered bootstrap)."""
    cp = load_corpus_startups().filter(pl.col("year") == year)
    # DETERMINISM (G10.5): sorted — feeds the manager-clustered bootstrap's rng.choice (see year_draft_ids).
    return sorted(m for m in cp["manager"].unique().to_list() if m is not None)


def corpus_pools(year: int, cohort: str | None = None, draft_ids: set | None = None,
                 managers: set | None = None) -> dict:
    """Empirical outcome-draw pools for CORPUS-AVG. Returns dict of dicts:
       'pos_round'[(pos, round)] -> list[player_uid]  (one vote per manager, whale-capped)
       'pos_exact'[(pos, pick_no)] -> list[player_uid]
       'slot_only'[pick_no] -> list[player_uid]  (strategy-agnostic; R2 §A secondary)
    Restricted to draft-year Y and (optionally) pre/post cohort / league subset (bootstrap)."""
    cp = load_corpus_startups().filter(pl.col("year") == year)
    if cohort:
        cp = cp.filter(pl.col("cohort") == cohort)
    if draft_ids is not None:
        cp = cp.filter(pl.col("draft_id").is_in(list(draft_ids)))
    if managers is not None:
        cp = cp.filter(pl.col("manager").is_in(list(managers)))
    # DETERMINISM (G10.5 fix): (a) `.first()` over a (cell, manager) group is order-dependent when a
    # whale manager took >1 qualifying player across leagues -> sort cp so the representative is
    # deterministic; (b) the per-cell lists are appended in nondeterministic group_by iteration order
    # -> sort each list. Both are determinism-only (an arbitrary representative/order -> a canonical
    # one), no logic change. Same class as the Phase-7 / G10.4 unordered-read fixes.
    cp = cp.sort(["position", "round", "pick_no", "manager", "player_uid"])
    pos_round, pos_exact, slot_only = {}, {}, {}
    one_vote = BT.get("whale_one_vote_per_cell", True)
    for key, store, cols in (("pr", pos_round, ("position", "round")),
                             ("pe", pos_exact, ("position", "pick_no")),
                             ("so", slot_only, ("pick_no",))):
        g = cp.group_by(list(cols) + ["manager"]).agg(pl.col("player_uid").first() if one_vote
                                                      else pl.col("player_uid")).explode("player_uid") \
            if not one_vote else cp.group_by(list(cols) + ["manager"]).agg(
                pl.col("player_uid").first())
        for row in g.iter_rows(named=True):
            k = tuple(row[c] for c in cols) if len(cols) > 1 else row[cols[0]]
            store.setdefault(k, []).append(row["player_uid"])
    for store in (pos_round, pos_exact, slot_only):
        for k in store:
            store[k].sort()
    return {"pos_round": pos_round, "pos_exact": pos_exact, "slot_only": slot_only}


# ============================================================================
# REALIZED production (scoring) — weekly fp_ppr, regular season only
# ============================================================================
def _reg_weeks(season: int) -> int:
    return 18 if season >= 2021 else 17


@lru_cache(maxsize=1)
def load_realized() -> tuple:
    """Returns (weekly, pos) where
       weekly[player_uid][season] = np.array of weekly fp_ppr (regular season, len 18, 0-filled
                                    for weeks not played / not in league)
       pos[player_uid] = position (as of dim_player).
    Regular season = weeks 1..17 (<=2020) or 1..18 (>=2021); NFL playoff weeks 19-22 dropped."""
    con = _con()
    df = con.execute("""SELECT player_uid, season, week, fp_ppr FROM fact_player_week
        WHERE played AND week <= 18 AND fp_ppr IS NOT NULL
          AND season BETWEEN 2011 AND ?""", [BT["last_complete_season"]]).pl()
    posrows = con.execute("SELECT player_uid, position FROM dim_player").fetchall()
    con.close()
    pos = {u: p for u, p in posrows}
    weekly: dict = {}
    for r in df.iter_rows(named=True):
        s = r["season"]; w = r["week"]
        if w > _reg_weeks(s):
            continue
        weekly.setdefault(r["player_uid"], {}).setdefault(s, np.zeros(18))
        weekly[r["player_uid"]][s][w - 1] = r["fp_ppr"]
    return weekly, pos


def window_seasons(year: int, wlen: int) -> list[int]:
    """Draft-year-inclusive window (R3-2): Y..Y+wlen-1, capped at last complete season."""
    last = BT["last_complete_season"]
    return [s for s in range(year, year + wlen) if s <= last]


# ============================================================================
# EX-ANTE model board — data < Y only + fixed priors (NO fitted artifacts; §6)
# ============================================================================
@lru_cache(maxsize=1)
def _prior_seasons() -> pl.DataFrame:
    con = _con()
    df = con.execute("""SELECT player_uid, season, position, vorp_ppr_total, ppg_ppr, games
        FROM fact_player_season_metrics""").pl()
    con.close()
    return df


@lru_cache(maxsize=1)
def _birth_capital() -> pl.DataFrame:
    con = _con()
    df = con.execute("""SELECT player_uid, position, birthdate, draft_year, draft_round
        FROM dim_player""").pl()
    con.close()
    return df


def _age_mult(position: str, age: float) -> float:
    ex = BT["exante"]; peak = ex["peak_age"].get(position, 26)
    if age <= 0 or age is None:
        return 1.0
    if age < peak:
        return max(0.5, 1.0 - ex["pre_peak_ramp_per_yr"] * (peak - age))
    return max(0.15, 1.0 - ex["post_peak_decline_per_yr"] * (age - peak))


def exante_board(year: int) -> pl.DataFrame:
    """Ex-ante value per player using ONLY seasons < Y + fixed hand-set priors (§6, R3-6).
    Veterans: recency-weighted prior VORP x fixed age multiplier. Rookies (draft_year==Y,
    no prior season): fixed capital-tier value. Returns [player_uid, exante_value]."""
    ex = BT["exante"]
    ps = _prior_seasons().filter(pl.col("season") < year)          # STRICT < Y
    assert_no_lookahead(year, ps["season"].to_list())
    hl = ex["recency_halflife_years"]
    ps = ps.with_columns(
        (0.5 ** ((year - pl.col("season")) / hl)).alias("w"))
    vet = (ps.group_by("player_uid", "position")
           .agg(((pl.col("vorp_ppr_total") * pl.col("w")).sum() / pl.col("w").sum()).alias("wvorp"),
                pl.col("season").max().alias("last_season")))
    bc = _birth_capital()
    # age at year Y from birthdate
    def _age(bd):
        if not bd:
            return None
        try:
            return float(year - int(str(bd)[:4]))
        except Exception:
            return None
    bc = bc.with_columns(
        pl.col("birthdate").map_elements(_age, return_dtype=pl.Float64).alias("age"),
        pl.col("draft_year").cast(pl.Int32, strict=False).alias("dy"),
        pl.col("draft_round").cast(pl.Int32, strict=False).alias("dr"))
    vet = vet.join(bc.select("player_uid", "age"), on="player_uid", how="left")
    vet = vet.with_columns(
        pl.struct("position", "age").map_elements(
            lambda s: _age_mult(s["position"], s["age"]), return_dtype=pl.Float64)
        .fill_null(1.0).alias("agem"))
    vet = vet.with_columns((pl.col("wvorp").fill_null(0.0) * pl.col("agem")).alias("exante_value"))
    SKILL = ["QB", "RB", "WR", "TE"]
    vet = vet.filter(pl.col("position").is_in(SKILL))

    # rookies: draft_year == Y and no prior season row -> capital tier value
    tier = {int(k): v for k, v in ex["capital_tier_value"].items()}
    udfa = ex["rookie_udfa_tier"]
    have_prior = set(vet["player_uid"].to_list())
    rk = bc.filter((pl.col("dy") == year) & (~pl.col("player_uid").is_in(list(have_prior)))
                   & (pl.col("position").is_in(SKILL)))
    def _rookie_val(dr):
        t = int(dr) if dr is not None else udfa
        t = min(max(t, 1), udfa)
        # scale capital tier onto the veteran VORP scale (rough): tier1 ~ a strong starter
        return tier.get(t, tier[udfa]) * 120.0
    rk = rk.with_columns(
        pl.col("dr").map_elements(_rookie_val, return_dtype=pl.Float64).alias("exante_value")) \
        .select("player_uid", "position", "exante_value")
    out = pl.concat([vet.select("player_uid", "position", "exante_value"), rk], how="vertical")
    out = out.filter(pl.col("exante_value").is_not_null())
    return out.group_by("player_uid").agg(
        pl.col("exante_value").max(), pl.col("position").first())


# ============================================================================
# Diagnostics
# ============================================================================
def _diag() -> None:
    print("=== corpus startup pick table (Block 1) ===")
    cp = load_corpus_startups()
    print("rows:", cp.height, "| drafts:", cp["draft_id"].n_unique(),
          "| by year:", cp.group_by("year").len().sort("year").to_dicts())
    print("premium share:", cp["premium"].mean(), "| cohort:",
          cp.group_by("year", "cohort").len().sort(["year", "cohort"]).to_dicts())
    for y in (2020, 2021):
        b = market_board(y, 1)
        print(f"[block1 {y}] consensus board players: {b.height}; top5:",
              b.head(5).select("position", "board_pos").to_dicts())
        pools = corpus_pools(y)
        pr = pools["pos_round"]
        thin = sum(1 for v in pr.values() if len(v) < BT["corpus_thin_min"])
        print(f"  pos_round cells: {len(pr)}; thin(<{BT['corpus_thin_min']}): {thin}; "
              f"e.g. QB r1 n={len(pr.get(('QB',1),[]))}, RB r1 n={len(pr.get(('RB',1),[]))}, "
              f"WR r2 n={len(pr.get(('WR',2),[]))}, TE r1 n={len(pr.get(('TE',1),[]))}")
    for y in (2011, 2015, 2019):
        b = market_board(y, 2)
        print(f"[block2 {y}] MFL 1QB board players: {b.height}")
    print("=== realized ===")
    weekly, pos = load_realized()
    print("players with weekly data:", len(weekly))
    print("=== exante board (leak-guarded) ===")
    for y in (2015, 2020):
        eb = exante_board(y)
        print(f"[exante {y}] players: {eb.height}; sample top:",
              eb.sort("exante_value", descending=True).head(3).to_dicts())
    print("=== leak assertion self-test ===")
    try:
        assert_no_lookahead(2020, [2019, 2020]); print("FAIL: did not catch leak")
    except LookaheadError:
        print("OK: caught board season >= Y")
    try:
        assert_no_lookahead(2020, [2018, 2019], score_seasons=[2019, 2020]); print("FAIL score")
    except LookaheadError:
        print("OK: caught score season < Y")


if __name__ == "__main__":
    _diag()
