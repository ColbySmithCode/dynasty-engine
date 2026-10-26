"""5.2 item 1 — disentangle age-at-entry from draft capital with a Cox PH model.

Early declarers who are good get drafted higher, so age-at-entry and draft capital
are correlated marginals. Stratified KM can't separate them (cells → n~5). A Cox PH
on the full sample with both covariates gives each one's INDEPENDENT contribution.
Report hazard ratios and how much of the age effect survives controlling for capital.
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import polars as pl
from lifelines import CoxPHFitter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CONFIG
from ingest._common import get_logger

log = get_logger("survival_cox")
MIN_GAMES = CONFIG["models"]["relevance"]["min_games"]


def _cox_frame() -> pl.DataFrame:
    con = duckdb.connect(str(CONFIG.path("warehouse")), read_only=True)
    repl = con.execute("""SELECT season, position, avg(replacement_points) repl_ppg
                          FROM fact_replacement WHERE profile='ppr' GROUP BY season, position""").pl()
    s = con.execute("""SELECT s.player_uid, s.season, s.position, s.games, s.ppg_ppr,
                              d.draft_year, d.draft_round, d.draft_pick, d.birthdate
                       FROM fact_player_season s JOIN dim_player d USING(player_uid)
                       WHERE s.position IN ('QB','RB','WR','TE')
                       ORDER BY s.player_uid, s.season""").pl()   # determinism: .first() below
    con.close()
    latest = int(s["season"].max())
    # overall pick # from round+pick (UDFA/missing -> 260); ~32 picks/round
    df = s.join(repl, on=["season", "position"], how="left").with_columns([
        pl.col("draft_year").cast(pl.Int32, strict=False),
        ((pl.col("draft_round").cast(pl.Int32, strict=False) - 1) * 32
         + pl.col("draft_pick").cast(pl.Int32, strict=False)).alias("draft_ovr")])
    df = df.filter(pl.col("draft_year") >= 2010).with_columns(
        ((pl.col("games") >= MIN_GAMES) & (pl.col("ppg_ppr") >= pl.col("repl_ppg"))).alias("relevant"))
    rel = df.filter(pl.col("relevant")).group_by("player_uid", maintain_order=True).agg(
        pl.col("season").max().alias("last_rel"))
    meta = df.group_by("player_uid", maintain_order=True).agg(   # ordered read -> .first() deterministic
        pl.col("position").first(), pl.col("draft_year").min().alias("entry"),
        pl.col("draft_ovr").min().alias("draft_ovr"), pl.col("birthdate").first(),
        pl.col("relevant").any().alias("ever"),
        (pl.col("relevant") & (pl.col("season") == latest)).any().alias("rel_latest"))
    m = meta.join(rel, on="player_uid", how="left").with_columns([
        # reach = draft -> last relevant year; never-relevant -> 0.5 (near-immediate exit)
        pl.when(pl.col("ever")).then(pl.col("last_rel") - pl.col("entry") + 1)
          .otherwise(0.5).alias("duration"),
        (~pl.col("rel_latest")).cast(pl.Int8).alias("event"),
        (pl.col("entry") - pl.col("birthdate").str.slice(0, 4).cast(pl.Int32)).alias("age_entry"),
        # UDFA / missing overall pick -> 260 (just past the last pick)
        pl.col("draft_ovr").fill_null(260.0).alias("ovr"),
    ]).filter(pl.col("age_entry").is_not_null() & (pl.col("duration") > 0))
    return m


def run() -> None:
    m = _cox_frame().to_pandas()
    print(f"Cox sample: {len(m)} drafted players (2010+), events={int(m.event.sum())}, "
          f"latest-censored={len(m)-int(m.event.sum())}")

    print("\n=== Model A: age_entry only (baseline hazard stratified by position) ===")
    a = CoxPHFitter()
    a.fit(m[["duration", "event", "age_entry", "position"]], "duration", "event",
          strata=["position"])
    hr_a = float(a.summary.loc["age_entry", "exp(coef)"])
    lo_a = float(a.summary.loc["age_entry", "exp(coef) lower 95%"])
    hi_a = float(a.summary.loc["age_entry", "exp(coef) upper 95%"])
    print(f"  age_entry HR = {hr_a:.3f}  [{lo_a:.3f}, {hi_a:.3f}]  (per +1 yr older at entry)")

    print("\n=== Model B: age_entry + draft capital (overall pick #) ===")
    b = CoxPHFitter()
    b.fit(m[["duration", "event", "age_entry", "ovr", "position"]], "duration", "event",
          strata=["position"])
    hr_ab = float(b.summary.loc["age_entry", "exp(coef)"])
    lo_ab = float(b.summary.loc["age_entry", "exp(coef) lower 95%"])
    hi_ab = float(b.summary.loc["age_entry", "exp(coef) upper 95%"])
    hr_ovr = float(b.summary.loc["ovr", "exp(coef)"])
    print(f"  age_entry HR = {hr_ab:.3f}  [{lo_ab:.3f}, {hi_ab:.3f}]  (controlling for capital)")
    print(f"  draft_ovr HR = {hr_ovr:.4f} per pick  = {hr_ovr**32:.3f} per ~round (32 picks)")

    # how much of the age effect survives capital control?
    excess_a = hr_a - 1.0
    excess_ab = hr_ab - 1.0
    survive = excess_ab / excess_a if excess_a else float("nan")
    print(f"\n  age effect (excess hazard over 1.0): raw {excess_a:+.3f} -> adjusted {excess_ab:+.3f}")
    print(f"  => {survive:.0%} of the raw age-at-entry effect SURVIVES controlling for draft capital")
    print(f"  => ~{1-survive:.0%} of the marginal age signal was actually draft capital (confound).")
    print("\n  TRADE-ENGINE RULE: apply age-at-entry and draft capital JOINTLY via this Cox model,")
    print("  NOT as two independent multipliers — the latter double-counts the shared signal and")
    print("  overvalues young first-rounders.")
    a.summary.to_csv(CONFIG.path("models") / "cox_age_only.csv")
    b.summary.to_csv(CONFIG.path("models") / "cox_age_capital.csv")


if __name__ == "__main__":
    run()
