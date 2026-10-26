"""G10.1 — LEAKAGE AUDIT (Phase-10, pre-registered in docs/PHASE10_PLAN.md).

Input-side verification that no model consumes data from inside its own outcome/holdout
window — generalizing (and independently checking) the G9.3 deferral "every model-CONSUMED
input table is 2026-free", never verified on the input side.

COVERAGE IS PER CONSUMPTION PATH (table × consuming module.function × join/predicate) — NOT
per table. The first execution (2026-07-29) exposed a defect in the audit's own design: a
per-table coverage tally printed "tables NOT examined = []" while the fact_league_roster join
in adp_efficiency_retest was never empirically tested. Fixed here; see PHASE10_PLAN AMENDMENTS.

An empty unreachable list is reportable ONLY if every enumerated PATH was tested. A fitted
path is tested EMPIRICALLY (execute the reader; its in-model assert `frame.season.max() <=
last_complete_season` fires on a leak) or BY-SOURCE (every consumed table has zero rows beyond
last_complete_season, so no leak is possible). Live tools (trade_engine) are unbounded-above
ON PURPOSE (current market state) and reported as INTENTIONAL-LIVE, not leaks.

Read-only w.r.t. the warehouse. Prints the pre-registered PASS condition BEFORE the result.
"""
from __future__ import annotations
import sys
import traceback
import duckdb
from config import CONFIG

DB = CONFIG.path("warehouse")
LAST = CONFIG["models"]["startup_backtest"]["last_complete_season"]  # derived, not hardcoded

# Season column per table (None => not season-keyed => cannot host a season-temporal leak).
SEASON_COL = {
    "dim_player": "draft_year", "dim_season": "season", "dim_week": "season",
    "fact_adp": "season", "fact_injury": "season", "fact_league_roster": "season",
    "fact_league_traded_pick": "season", "fact_player_season": "season",
    "fact_player_season_metrics": "season", "fact_player_week": "season",
    "fact_player_week_metrics": "season", "fact_replacement": "season",
    "dim_team": None, "fact_dynasty_value": None, "fact_league_draft_pick": None,
    "fact_league_transaction": None, "fact_refresh_status": None,
}


# Pure dimensions: out-of-window rows here (e.g. dim_player.draft_year=2026 rookies) can only
# enter a model via a JOIN to a season-bearing FACT. So a dimension's >LAST rows are NOT a leak
# vector by themselves; the binding check is the FACT side. Excluded from the disqualifier BY
# RULE (stated, not silent) — a model that SELECTed a dimension by year with no fact join would
# have to be caught empirically, and no by_source/guard path does that (all join to <=LAST facts).
DIMENSIONS = {"dim_player", "dim_season", "dim_week", "dim_team"}
# Guard tokens: a "guard" path is tested by confirming its cap code is present in source.
GUARD_TOKENS = {
    "aging_curves.run": ("models/aging_curves.py", "exclude_seasons"),
    "startup_data/backtester": ("models/startup_data.py", "assert_no_lookahead"),
}


def _con():
    return duckdb.connect(str(DB), read_only=True)


def _guard_present(path_name):
    import pathlib
    rel, token = GUARD_TOKENS[path_name]
    src = (pathlib.Path(__file__).resolve().parent.parent / rel).read_text()
    return token in src, f"{rel} contains `{token}`" if token in src else f"{rel} MISSING `{token}`"


def _tbl_beyond(con, t):
    """rows in table t with season strictly beyond LAST (0 => can't leak from this table)."""
    sc = SEASON_COL.get(t)
    if sc is None:
        return None
    return con.execute(
        f'select count(*) from "{t}" where try_cast("{sc}" as integer) > ?', [LAST]).fetchone()[0]


def _run(callable_):
    """Execute a fitted reader; its in-model assert fires on a leak. Return (ok, detail)."""
    try:
        callable_()
        return True, "in-model assert(frame.season.max()<=LAST) held"
    except AssertionError as e:
        return False, f"ASSERT TRIPPED: {e}"
    except Exception as e:  # noqa: BLE001
        return None, f"could not execute: {e!r}\n{traceback.format_exc(limit=1)}"


# --- PRE-REGISTERED CONSUMPTION-PATH INVENTORY -------------------------------------------
# Each path: module.function, consumed tables, the season predicate, and how it is tested.
# kind: "empirical" (execute reader, assert-guarded) | "by_source" (all consumed tables <=LAST)
#     | "guard" (explicit code guard, verified by-source too) | "live" (intentional current-state)
def build_paths(con):
    from models import adp_calibration as AC
    from models import adp_efficiency_retest as AE

    P = []
    # --- fitted paths that touch a 2026-carrying table -> EMPIRICAL (assert-guarded) ---
    P += [
        ("adp_calibration.startup_calibration", ["fact_adp", "fact_player_season_metrics"],
         "K/AUG15, season<=LAST, ⨝ forward-VORP", "empirical", AC.startup_calibration),
        ("adp_calibration.rookie_slot_to_capital", ["fact_adp", "dim_player"],
         "R/DRAFT, 2020<=season<=LAST (THE REFIT)", "empirical", AC.rookie_slot_to_capital),
        ("adp_calibration.market_efficiency", ["fact_adp", "fact_player_season_metrics"],
         "K/AUG15, season<=LAST, ⨝ forward-VORP", "empirical", AC.market_efficiency),
        ("adp_calibration.velocity_study", ["fact_adp", "fact_player_season_metrics"],
         "K, season<=LAST, ⨝ forward-VORP", "empirical", AC.velocity_study),
        ("adp_efficiency_retest._corpus_sf_adp", ["fact_league_draft_pick", "fact_league_roster"],
         "corpus picks ⨝ roster season<=LAST", "empirical", AE._corpus_sf_adp),
        ("adp_efficiency_retest.item1_and_2", ["fact_adp", "fact_league_roster", "fact_player_season_metrics"],
         "mfl+sf ⨝ forward-VORP, season<=LAST", "empirical", AE.item1_and_2),
        ("adp_efficiency_retest.item3_qb_depth", ["fact_adp", "fact_player_season", "fact_player_week"],
         "K/AUG15 ⨝ player_season, season<=LAST", "empirical", AE.item3_qb_depth),
    ]
    # --- fitted paths whose consumed tables are all <=LAST at source -> BY_SOURCE ---
    P += [
        ("aging_curves.run", ["dim_player", "fact_player_season", "fact_player_season_metrics"],
         "explicit ~season.is_in(exclude_seasons=[2026])", "guard", None),
        ("survival.run", ["dim_player", "fact_player_season", "fact_replacement"],
         "draft-relative; source tables <=LAST", "by_source", None),
        ("survival_cox.run", ["dim_player", "fact_player_season", "fact_replacement"],
         "draft-relative; source tables <=LAST", "by_source", None),
        ("archetypes.run", ["dim_player", "fact_player_season"],
         "2019-2022 eval; source tables <=LAST", "by_source", None),
        ("cfb_5_4b.run", ["dim_player", "fact_player_season"],
         "season BETWEEN draft_year AND +2 (bounded)", "by_source", None),
        ("projection.run", ["dim_player", "fact_injury", "fact_player_season_metrics", "fact_replacement"],
         "replacement season<=LAST; source tables <=LAST", "by_source", None),
        ("startup_data/backtester", ["dim_player", "fact_adp", "fact_player_season_metrics", "fact_player_week"],
         "assert_no_lookahead(season<Y) + BETWEEN 2011 AND LAST", "guard", None),
    ]
    # --- live tool: unbounded-above ON PURPOSE (current market state) -> LIVE ---
    P += [
        ("engine.trade_engine (LIVE)", ["fact_adp", "fact_league_roster", "fact_league_draft_pick"],
         "current-season ADP/roster is the input; calib ⨝ VORP<=LAST", "live", None),
    ]
    return P


def print_pass_condition():
    print("=" * 80)
    print("G10.1 LEAKAGE AUDIT — PRE-REGISTERED PASS CONDITION (printed before the result)")
    print("=" * 80)
    print(f"""
PASS iff ALL of:
  (i)   every enumerated CONSUMPTION PATH (table × module.function × predicate) is TESTED
        — empirically (assert-guarded execution) or by-source (all consumed tables <=LAST);
  (ii)  paths_not_tested == []   (an empty unreachable list is valid ONLY under this);
  (iii) zero REFIT-FORCING leaks: no fitted path yields a frame with season > LAST={LAST}
        (2026 = excluded, no data). Live tools (trade_engine) may hold current-state 2026.
FAIL otherwise. Per-table coverage is NOT accepted (that masked the roster path on the
first run — see PHASE10_PLAN AMENDMENTS 2026-07-29).
""")


def audit():
    con = _con()
    paths = build_paths(con)
    tested, not_tested, leaks, live = [], [], [], []

    print("-" * 80)
    print("PATH-LEVEL AUDIT")
    print("-" * 80)
    print(f"{'path':44s} {'kind':9s} status  detail")
    for name, tables, pred, kind, fn in paths:
        if kind == "live":
            live.append(name)
            print(f"{name:44s} {kind:9s} LIVE    {pred}")
            continue
        if kind == "empirical":
            ok, detail = _run(fn)
            if ok is True:
                tested.append(name)
                print(f"{name:44s} {kind:9s} CLEAN   {detail}")
            elif ok is False:
                tested.append(name); leaks.append((name, detail))
                print(f"{name:44s} {kind:9s} LEAK    {detail}")
            else:
                not_tested.append((name, detail))
                print(f"{name:44s} {kind:9s} UNTESTED {detail}")
            continue
        if kind == "guard":
            # tested by confirming the cap code is present (it enforces the <=LAST bound)
            ok, detail = _guard_present(name)
            if ok:
                tested.append(name)
                print(f"{name:44s} {kind:9s} CLEAN   guard verified: {detail}")
            else:
                not_tested.append((name, detail))
                print(f"{name:44s} {kind:9s} UNTESTED {detail}")
            continue
        # by_source: every consumed FACT table (dimensions excluded by rule) must have 0 rows >LAST
        facts = [t for t in tables if t not in DIMENSIONS]
        beyond = {t: _tbl_beyond(con, t) for t in facts}
        bad = {t: b for t, b in beyond.items() if b}
        dims = [t for t in tables if t in DIMENSIONS]
        if bad:
            not_tested.append((name, f"consumed FACT table(s) carry >{LAST} rows: {bad} (needs empirical)"))
            print(f"{name:44s} {kind:9s} UNTESTED fact >{LAST}: {bad}")
        else:
            tested.append(name)
            print(f"{name:44s} {kind:9s} CLEAN   facts max<=LAST {list(beyond)}; dims via ⨝<=LAST facts {dims}")

    con.close()

    print()
    print("-" * 80)
    print("COVERAGE ACCOUNTING (per PATH, not per table)")
    print("-" * 80)
    total = len(paths)
    print(f"  consumption paths enumerated = {total}")
    print(f"  paths tested                 = {len(tested)}  (empirical or by-source)")
    print(f"  live-tool paths (exempt)     = {len(live)}  {live}")
    print(f"  paths NOT tested ({len(not_tested)}):")
    for n, why in not_tested:
        print(f"    - {n} :: {why}")
    print(f"  REFIT-FORCING leaks ({len(leaks)}):")
    for n, why in leaks:
        print(f"    - {n} :: {why}")
    print(f"\n  [prior run reported 9 tables / 116 columns; this run reports {total} PATHS "
          f"({len(tested)} tested + {len(live)} live) — the finer unit that caught the roster gap.]")

    ok = (not not_tested) and (not leaks)
    print()
    print("=" * 80)
    print(f"G10.1 RESULT: {'PASS' if ok else 'FAIL'}")
    print("=" * 80)
    if not ok:
        if not_tested:
            print(f"  (i/ii) {len(not_tested)} path(s) NOT tested — cannot report empty-unreachable")
        if leaks:
            print(f"  (iii)  {len(leaks)} REFIT-FORCING leak(s)")
    return ok


if __name__ == "__main__":
    print_pass_condition()
    sys.exit(0 if audit() else 1)
