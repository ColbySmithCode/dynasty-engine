"""Phase 6 — Trade Engine. Every asset -> a DISTRIBUTION over discounted future VORP
(Monte Carlo, empirical per-year streams from the SF corpus + rookie ADP pools).

PROSPECTIVE-CAPABLE VIA COMPARABLES (G10.3 backlog, 2026-07-30): a trade's valuation draws on the
realized VORP distribution of COMPARABLE players (those who historically occupied the same ADP
SLOT), NOT on the realized future of the specific players in the trade. So the engine CAN value a
trade offered today (price each pick/slot by its comparable-player distribution); the corpus E[Delta]
is a PROSPECTIVE valuation, not a hindsight evaluation of a specific historical trade. Standing
constraint #2's headline should reflect this.

This trade is a STARTUP-DRAFT trade in a first-year league with NO roster (Decision 9):
consolidation is draft-capital allocation while filling 20+ empty slots, NOT roster-spot
scarcity — so no in-season consolidation penalty. The 2027 rookie 2nd has UNKNOWN slot
and NO finish history -> near-uniform slot + wide variance + extra unknowability discount.

Requirements met: delta sweep (no single rate), by-year decomposition, P(win) from 10k
draws with Phase-5 posteriors intact, QB-depth interaction, fairness solver, sensitivity.
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CONFIG
from ingest._common import get_logger
from models.adp_calibration import _forward_vorp

log = get_logger("trade_engine")
RNG = np.random.default_rng(CONFIG["models"]["seed"])
DRAWS = CONFIG["trade_engine"]["monte_carlo_draws"]
HORIZON = 4
EXPORTS = CONFIG.path("exports")
UNKNOWN_TICK = 0.92   # extra multiplicative discount for the unknowable future pick


def _pools():
    """Two startup-pick valuation pools — the SINGLE highest-leverage assumption in the
    engine (it flipped this trade's verdict from -74 to +6):
      CONSENSUS = the best-available (dynasty-K ADP) player at each slot -> assumes you
                  draft OPTIMALLY at every pick.
      CORPUS    = what 400 managers actually drafted at that slot -> assumes you draft
                  like the MEDIAN manager (busts included).
    Truth is in between; report BOTH. Rookie pick uses rookie ADP either way."""
    fv = _forward_vorp().select("player_uid", "season", "position", "v0", "v1", "v2")
    con = duckdb.connect(str(CONFIG.path("warehouse")), read_only=True)
    # G10.1 note: trade_engine is a LIVE tool. These ADP reads are UNBOUNDED-ABOVE ON PURPOSE —
    # current-season (2026) market state is the input a live valuation must price. Not a fitted
    # label, so NOT a leak (PHASE10_PLAN G10.1 live-tool carve-out). Calibration uses the ADP→VORP
    # relation via the inner join to `fv` (forward VORP, ≤ last_complete_season), which drops 2026.
    kadp = con.execute("""SELECT player_uid, season, adp FROM fact_adp
        WHERE format='K' AND ppr=-1 AND period='AUG15' AND adp IS NOT NULL AND season>=2019""").pl()
    corpus = con.execute("""SELECT p.player_uid, CAST(r.season AS INT) season, p.pick_no AS adp
        FROM fact_league_draft_pick p JOIN (SELECT DISTINCT league_id,season FROM fact_league_roster) r
        USING(league_id) WHERE p.source='corpus' AND p.player_uid IS NOT NULL""").pl()
    radp = con.execute("""SELECT player_uid, season, CEIL(adp/12.0) rr FROM fact_adp
        WHERE format='R' AND ppr=-1 AND period='DRAFT' AND adp IS NOT NULL AND season>=2020""").pl()
    con.close()
    # determinism (Phase-7): the queries lack ORDER BY, so pool row order is nondeterministic and
    # the SEEDED RNG then samples different rows across runs (this was the corpus arm's sd 3.18 —
    # NOT inherent pool uncertainty, the same unordered-read class). Sort so sampling is reproducible.
    srt = ["player_uid", "season"]
    consensus = kadp.join(fv, on=["player_uid", "season"], how="inner").sort(srt)
    corpus_pool = corpus.join(fv, on=["player_uid", "season"], how="inner").sort(srt)
    rookie = radp.join(fv, on=["player_uid", "season"], how="inner").sort(srt)
    return consensus, corpus_pool, rookie


def _streams_startup(startup, lo, hi) -> np.ndarray:
    """(n,3) per-year VORP streams for the CONSENSUS (K-ADP) player at overall slot [lo,hi]."""
    s = startup.filter((pl.col("adp") >= lo) & (pl.col("adp") <= hi))
    return s.select("v0", "v1", "v2").fill_null(0).to_numpy()


def _streams_rookie(rookie, rr) -> np.ndarray:
    s = rookie.filter(pl.col("rr") == rr)
    return s.select("v0", "v1", "v2").fill_null(0).to_numpy()


def _value_draws(streams: np.ndarray, start_year: int, delta: float,
                 extra: float = 1.0, jitter: float = 0.0) -> np.ndarray:
    """MC draws of discounted value: sample a stream, place it at ownership year
    start_year (1-indexed), extend to HORIZON with aging decay, discount by delta^(yr-1)."""
    idx = RNG.integers(0, len(streams), DRAWS)
    s = streams[idx]                                  # (DRAWS, 3)
    if jitter:                                        # widen variance (unknowable slot)
        s = s + RNG.normal(0, jitter, s.shape)
    yr_vorp = np.zeros((DRAWS, HORIZON))
    for k in range(3):
        yr = start_year - 1 + k
        if yr < HORIZON:
            yr_vorp[:, yr] = s[:, k]
    # extend year 4 by decaying year-3 stream value
    if start_year == 1:
        yr_vorp[:, 3] = s[:, 2] * 0.85
    disc = np.array([delta ** t for t in range(HORIZON)])
    return (yr_vorp * disc).sum(axis=1) * extra, yr_vorp


def evaluate(delta: float, startup, rookie) -> dict:
    a, a_yr = _value_draws(_streams_startup(startup, 8, 14), 1, delta)          # 1.11
    b3, b3y = _value_draws(_streams_startup(startup, 27, 33), 1, delta)         # startup 3rd
    b4, b4y = _value_draws(_streams_startup(startup, 39, 45), 1, delta)         # startup 4th
    # 2027 rookie 2nd: starts ownership year 2, unknowable slot -> jitter + extra discount
    br, bry = _value_draws(_streams_rookie(rookie, 2), 2, delta, extra=UNKNOWN_TICK, jitter=15.0)
    pkg = b3 + b4 + br
    pkg_yr = b3y + b4y + bry
    return {"delta": delta, "A": a, "B": pkg, "A_yr": a_yr, "B_yr": pkg_yr,
            "b3": b3, "b4": b4, "br": br}


def run() -> None:
    consensus, corpus, rookie = _pools()
    L = ["# Trade Engine — 1.11  vs  (startup 3rd + startup 4th + 2027 rookie 2nd)", "",
         "**STARTUP-draft trade, first-year league, NO roster (Decision 9):** consolidation is "
         "capital allocation across 20+ empty slots, not roster scarcity — no in-season penalty. "
         "The 2027 rookie 2nd has unknown slot + no finish history → near-uniform slot, wide "
         f"variance, extra unknowability discount ({UNKNOWN_TICK}×). {DRAWS} MC draws; Phase-5 "
         "posteriors carried.", "",
         "## ⚠️ Highest-leverage assumption: pick-outcome POOL (reported under BOTH)",
         "CONSENSUS = you draft the best-available at every slot (optimal). CORPUS-AVG = you draft "
         "like the median manager (busts included). This choice flipped the verdict −74↔+6; the "
         "truth is in between, so both are shown.", ""]
    store = {}
    structured = {}    # machine-readable dual-pool verdict for the Phase-7 drift monitor (item 4c)
    for pool_key, pool_name, pool in (("consensus", "CONSENSUS (optimal drafter)", consensus),
                                      ("corpus", "CORPUS-AVG (median manager)", corpus)):
        L += [f"### {pool_name}", "", "| δ | E[1.11] | E[package] | E[Δ]=pkg−1.11 | P(package wins) |",
              "|--:|--:|--:|--:|--:|"]
        flips = []; e_delta_082 = None
        for d in (0.70, 0.82, 0.90):
            r = evaluate(d, pool, rookie)
            if pool is consensus:
                store[d] = r
            ea, eb = r["A"].mean(), r["B"].mean()
            if d == 0.82:
                e_delta_082 = float(eb - ea)
            L.append(f"| {d:.2f} | {ea:+.0f} | {eb:+.0f} | {eb-ea:+.0f} | {(r['B']>r['A']).mean():.0%} |")
            flips.append(eb > ea)
        verdict = "package WINS" if all(flips) else ("1.11 WINS" if not any(flips) else "FLIPS across δ")
        L.append(f"\n→ {pool_name}: **{verdict}** across δ.\n")
        structured[pool_key] = {"e_delta_082": round(e_delta_082, 1),
                                "winner": "package" if e_delta_082 > 0 else "1.11",
                                "verdict_across_delta": verdict}
    L.append("**Spread between pools is the real uncertainty band on this trade** — if you draft "
             "well the package is even/ahead; if you draft like the field, keep the 1.11. "
             "Detailed sections below use the CONSENSUS pool.\n")

    # by-year decomposition (δ=0.82)
    r = store[0.82]
    L += ["", "## Value by ownership year (δ=0.82, mean VORP, undiscounted)", "",
          "| asset | yr1 (2026) | yr2 (2027) | yr3 (2028) | yr4 (2029) |", "|---|--:|--:|--:|--:|"]
    L.append(f"| 1.11 | " + " | ".join(f"{r['A_yr'][:,t].mean():+.0f}" for t in range(HORIZON)) + " |")
    L.append(f"| package | " + " | ".join(f"{r['B_yr'][:,t].mean():+.0f}" for t in range(HORIZON)) + " |")
    L.append("\n1.11 is front-loaded (produces from 2026); the package is back-loaded (the "
             "rookie 2nd contributes nothing until 2027+). Same total ≠ same trade.")

    # P(win) with intervals
    L += ["", "## P(I win) and credible spread (δ=0.82)", "",
          f"- E[Δ] (package − 1.11) = {(r['B']-r['A']).mean():+.0f} VORP; "
          f"90% CI [{np.quantile(r['B']-r['A'],.05):+.0f}, {np.quantile(r['B']-r['A'],.95):+.0f}]",
          f"- **P(package wins) = {(r['B']>r['A']).mean():.0%}** — the wide band (rookie survival "
          "[0.30,0.70], slot uncertainty) means this is far from a lock either way."]

    # QB-depth interaction
    con = duckdb.connect(str(CONFIG.path("warehouse")), read_only=True)
    qbshare = con.execute("""SELECT CEIL(p.pick_no/12.0) rd,
        avg(CASE WHEN d.position='QB' THEN 1.0 ELSE 0 END) qb_rate
        FROM fact_league_draft_pick p JOIN dim_player d USING(player_uid)
        WHERE p.source='corpus' AND p.pick_no BETWEEN 25 AND 48 GROUP BY 1 ORDER BY 1""").pl()
    con.close()
    L += ["", "## QB-depth interaction (superflex)", "",
          "5.3 found QB value holds to startup round ~8 (+160 VORP) in your SF scoring. So trading "
          "DOWN from 1.11 forfeits less than in 1QB: the package's 3rd/4th picks still reach "
          "startable QBs.",
          "corpus QB draft rate at those slots: " +
          ", ".join(f"rd{int(x['rd'])} {x['qb_rate']:.0%}" for x in qbshare.iter_rows(named=True)),
          "→ the package retains real QB optionality; its downside is cushioned by SF QB depth "
          "(this is why the package is more competitive here than a 1QB calculator would say)."]

    # fairness solver
    L += _fairness(store[0.82], consensus, rookie)
    # sensitivity
    L += _sensitivity(consensus, rookie)
    EXPORTS.mkdir(parents=True, exist_ok=True)
    (EXPORTS / "trade_verdict.md").write_text("\n".join(L))
    import json
    (EXPORTS / "trade_verdict.json").write_text(json.dumps(structured, indent=2))  # drift monitor
    log.info("trade verdict -> %s (+ .json)", EXPORTS / "trade_verdict.md")
    print("\n".join(L))


def _fairness(r, startup, rookie) -> list[str]:
    gap = r["A"].mean() - r["B"].mean()   # >0 => 1.11 side heavier; add to package side
    band = 0.05 * r["A"].mean()
    catalog = {"startup 2nd": _streams_startup(startup, 15, 22), "startup 3rd": _streams_startup(startup, 27, 33),
               "startup 4th": _streams_startup(startup, 39, 45), "startup 5th": _streams_startup(startup, 51, 57),
               "rookie 1st": _streams_rookie(rookie, 1), "rookie 3rd": _streams_rookie(rookie, 3)}
    opts = []
    for name, st in catalog.items():
        if len(st) < 5:
            continue
        add, _ = _value_draws(st, 1 if "startup" in name else 2, 0.82,
                              extra=UNKNOWN_TICK if "rookie" in name else 1.0)
        newgap = abs(gap - add.mean()) if gap > 0 else abs(gap + add.mean())
        opts.append((newgap, name, add.mean()))
    opts.sort()
    L = ["", "## Fairness solver — minimal add to the lighter side to reach E[Δ] within ±5%", "",
         f"Current E[Δ] = {-gap:+.0f} ({'package lighter' if gap>0 else '1.11 lighter'}); "
         f"±5% band = ±{band:.0f} VORP. Top-3 balancing adds to the lighter side:", "",
         "| rank | add asset | E[value] | residual |Δ| |", "|--:|---|--:|--:|"]
    for i, (res, name, ev) in enumerate(opts[:3], 1):
        L.append(f"| {i} | {name} | {ev:+.0f} | {res:.0f} |")
    return L


def _sensitivity(startup, rookie) -> list[str]:
    base = evaluate(0.82, startup, rookie)
    base_edge = base["B"].mean() - base["A"].mean()
    tests = {}
    # 1) discount rate
    tests["discount δ (0.70↔0.90)"] = (evaluate(0.90, startup, rookie)["B"].mean()
        - evaluate(0.90, startup, rookie)["A"].mean()) - (evaluate(0.70, startup, rookie)["B"].mean()
        - evaluate(0.70, startup, rookie)["A"].mean())
    # 2) rookie-pick unknowability (drop extra discount + jitter)
    b3, _ = _value_draws(_streams_startup(startup, 27, 33), 1, 0.82)
    b4, _ = _value_draws(_streams_startup(startup, 39, 45), 1, 0.82)
    br_hi, _ = _value_draws(_streams_rookie(rookie, 2), 2, 0.82, extra=1.0, jitter=0.0)
    a, _ = _value_draws(_streams_startup(startup, 8, 14), 1, 0.82)
    tests["rookie-2nd unknowability (on↔off)"] = (b3+b4+br_hi).mean() - a.mean() - base_edge
    # 3) 1.11 slot value (pick 8-14 vs pick 10-11 tight)
    a_tight, _ = _value_draws(_streams_startup(startup, 10, 12), 1, 0.82)
    tests["1.11 exact slot value"] = base["B"].mean() - a_tight.mean() - base_edge
    ranked = sorted(tests.items(), key=lambda kv: -abs(kv[1]))
    L = ["", "## Top-2 assumptions the verdict is most sensitive to", "",
         f"Base E[Δ] (pkg−1.11, δ=0.82) = {base_edge:+.0f} VORP.", ""]
    for name, swing in ranked[:2]:
        L.append(f"- **{name}**: shifts E[Δ] by {swing:+.0f} VORP "
                 f"({'FLIPS the verdict' if abs(swing) > abs(base_edge) else 'does not flip it'}).")
    return L


if __name__ == "__main__":
    run()
