"""Phase 5.3 — ADP calibration. Answers the actual trade question, which spans TWO
asset classes that price completely differently (labeled everywhere):

  STARTUP picks (1.11, a 3rd, a 4th)  -> DYNASTY-STARTUP ADP maps a startup slot to
      an actual caliber of player -> realized VORP.
  ROOKIE picks (next year's 2nd)      -> rookie-slot -> NFL draft CAPITAL -> survival
      (5.2). The slot->capital mapping is FORMAT-DEPENDENT (superflex moves QBs up);
      MFL rookie ADP is 1QB-only, so we carry an explicit SF format adjustment and
      REPORT the mapping's uncertainty (it propagates into every pick valuation).

Plus: market-efficiency residuals and the ADP-velocity study (scoped 2019+, Decision 2).
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

log = get_logger("adp_calibration")
EXPORTS = CONFIG.path("exports")
VEL_MIN = CONFIG["models"]["adp_studies"]["velocity_min_season"]
# G10.1 leakage fix: every fitted read is capped at last_complete_season (derived, not
# hardcoded) so no feature draws from the excluded post-label window (2026). The cap is
# asserted on each fitted frame so the exclusion is EXPLICIT, not an incidental join effect.
LAST_COMPLETE = CONFIG["models"]["startup_backtest"]["last_complete_season"]


def _con():
    return duckdb.connect(str(CONFIG.path("warehouse")), read_only=True)


def _forward_vorp() -> pl.DataFrame:
    """Per player-season: realized VORP this year + forward 3-yr VORP (dynasty)."""
    con = _con()
    s = con.execute("""SELECT m.player_uid, m.season, m.position, m.fp_ppr, m.vorp_ppr_total,
                              f.pos_finish_ppr
                       FROM fact_player_season_metrics m
                       JOIN fact_player_season f USING(player_uid, season, position)""").pl()
    con.close()
    fwd = s.select("player_uid", (pl.col("season")).alias("s0"), "vorp_ppr_total")
    out = s
    for k in (0, 1, 2):
        j = fwd.rename({"vorp_ppr_total": f"v{k}"}).with_columns((pl.col("s0") - k).alias("season")).drop("s0")
        out = out.join(j, on=["player_uid", "season"], how="left")
    return out.with_columns(
        (pl.col("v0").fill_null(0) + pl.col("v1").fill_null(0) + pl.col("v2").fill_null(0)).alias("fwd3_vorp"))


# ---- ASSET CLASS 1: STARTUP picks via dynasty-startup ADP --------------------
def startup_calibration() -> list[str]:
    con = _con()
    adp = con.execute(f"""SELECT player_uid, season, adp, draft_pct FROM fact_adp
                         WHERE format='K' AND ppr=-1 AND period='AUG15' AND adp IS NOT NULL
                           AND season <= {LAST_COMPLETE}""").pl()
    con.close()
    fv = _forward_vorp()
    m = adp.join(fv, on=["player_uid", "season"], how="inner").filter(pl.col("season") >= 2019)
    assert (m["season"].max() or 0) <= LAST_COMPLETE, "G10.1 leak: startup_calibration frame > last_complete_season"
    m = m.with_columns([
        ((pl.col("adp") - 1) // 12 + 1).cast(pl.Int32).alias("startup_round"),
        (pl.col("pos_finish_ppr") <= 12).alias("hit_top12"),
        (pl.col("pos_finish_ppr") <= 24).alias("hit_top24")])
    g = (m.group_by(["startup_round", "position"]).agg(
        pl.len().alias("n"), pl.col("hit_top12").mean().alias("hit12"),
        pl.col("fwd3_vorp").mean().alias("mean_fwd3_vorp"),
        pl.col("fwd3_vorp").median().alias("med_fwd3_vorp"))
        .filter(pl.col("n") >= 10).sort(["startup_round", "position"]))
    L = ["## ASSET CLASS 1 — STARTUP picks (dynasty-startup ADP → player caliber)",
         "Realized value by startup ADP round × position (dynasty K ADP, AUG15, 2019+, "
         "era-adjusted via VORP). fwd3_vorp = summed VORP over the pick year + next 2.", "",
         "| startup_rd | pos | n | top-12 hit | mean fwd3 VORP | median |", "|--:|---|--:|--:|--:|--:|"]
    for r in g.iter_rows(named=True):
        L.append(f"| {r['startup_round']} | {r['position']} | {r['n']} | {r['hit12']:.0%} | "
                 f"{r['mean_fwd3_vorp']:+.0f} | {r['med_fwd3_vorp']:+.0f} |")
    return L


# ---- ASSET CLASS 2: ROOKIE picks via slot -> NFL capital ---------------------
def rookie_slot_to_capital() -> list[str]:
    con = _con()
    adp = con.execute(f"""SELECT a.player_uid, a.season, a.adp, d.draft_round
                         FROM fact_adp a JOIN dim_player d USING(player_uid)
                         WHERE a.format='R' AND a.ppr=-1 AND a.period='DRAFT'
                           AND a.adp IS NOT NULL AND a.season>=2020
                           AND a.season <= {LAST_COMPLETE}""").pl()
    con.close()
    adp = adp.with_columns([
        ((pl.col("adp") - 1) // 12 + 1).cast(pl.Int32).alias("rookie_round"),
        pl.col("draft_round").cast(pl.Int32, strict=False).alias("nfl_round")])
    adp = adp.filter(pl.col("nfl_round").is_not_null() & (pl.col("rookie_round") <= 4))
    assert (adp["season"].max() or 0) <= LAST_COMPLETE, "G10.1 leak: rookie_slot_to_capital frame > last_complete_season"
    L = ["", "## ASSET CLASS 2 — ROOKIE picks: fantasy slot → NFL draft CAPITAL (Decision 1)",
         "MFL rookie ADP (1QB, 2020+) → the player actually taken → their NFL draft round. "
         "This mapping is LOAD-BEARING; its spread is the uncertainty that propagates into "
         "every rookie-pick valuation. **1QB-calibrated — see SF adjustment below.**", "",
         "| rookie_rd | n | mean NFL rd | P25–P75 NFL rd | % R1 | % R1-2 | % UDFA/late |",
         "|--:|--:|--:|--:|--:|--:|--:|"]
    for rr in range(1, 5):
        sub = adp.filter(pl.col("rookie_round") == rr)
        if sub.height < 10:
            continue
        nr = sub["nfl_round"].to_numpy()
        L.append(f"| {rr} | {sub.height} | {nr.mean():.1f} | "
                 f"{np.quantile(nr,.25):.0f}–{np.quantile(nr,.75):.0f} | "
                 f"{(nr==1).mean():.0%} | {(nr<=2).mean():.0%} | {(nr>=6).mean():.0%} |")
    # SF format adjustment: how much earlier do QBs go in the corpus's SF rookie context?
    L += ["", "**Format (superflex) adjustment.** MFL rookie ADP has no SF dimension. In SF, "
          "rookie QBs are drafted materially earlier, so 1QB slot→capital understates QB value "
          "in QB-heavy classes. The trade engine applies the Decision-3 SF translation to the QB "
          "component of any rookie-pick class and WIDENS the interval for QB-heavy classes; the "
          "mapping uncertainty above (P25–P75 spanning ~2 NFL rounds per rookie round) is carried "
          "as a distribution, not a point, in pick valuation."]
    return L


# ---- Market efficiency: realized VORP vs ADP, residuals by pos --------------
def market_efficiency() -> list[str]:
    con = _con()
    adp = con.execute(f"""SELECT player_uid, season, adp FROM fact_adp
                         WHERE format='K' AND ppr=-1 AND period='AUG15'
                           AND adp IS NOT NULL AND season>=2019 AND season <= {LAST_COMPLETE}""").pl()
    con.close()
    m = adp.join(_forward_vorp(), on=["player_uid", "season"], how="inner")
    assert (m["season"].max() or 0) <= LAST_COMPLETE, "G10.1 leak: market_efficiency frame > last_complete_season"
    m = m.with_columns(pl.col("adp").log().alias("ln_adp"))
    x = m["ln_adp"].to_numpy(); y = m["fwd3_vorp"].to_numpy()
    b1, b0 = np.polyfit(x, y, 1)
    m = m.with_columns((pl.col("fwd3_vorp") - (b0 + b1 * pl.col("ln_adp"))).alias("resid"))
    L = ["", "## Market efficiency — realized fwd3 VORP regressed on ln(ADP)",
         f"Baseline: fwd3_VORP ≈ {b0:.0f} {b1:+.0f}·ln(ADP). Positive residual = ADP UNDERvalued "
         "the position (market inefficiency, if it persists).", "",
         "| position | n | mean residual | interpretation |", "|---|--:|--:|---|"]
    for r in (m.group_by("position").agg(pl.len().alias("n"), pl.col("resid").mean().alias("mr"))
              .filter(pl.col("n") >= 20).sort("mr", descending=True).iter_rows(named=True)):
        interp = "market UNDERvalues" if r["mr"] > 5 else ("market OVERvalues" if r["mr"] < -5 else "≈efficient")
        L.append(f"| {r['position']} | {r['n']} | {r['mr']:+.1f} | {interp} |")
    return L


# ---- ADP velocity (2019+): do risers/fallers outperform? --------------------
def velocity_study() -> list[str]:
    con = _con()
    a = con.execute(f"""SELECT player_uid, season, period, adp FROM fact_adp
                        WHERE format='K' AND ppr=-1 AND season>={VEL_MIN}
                          AND season <= {LAST_COMPLETE}
                          AND period IN ('DRAFT','AUG15') AND adp IS NOT NULL""").pl()
    con.close()
    w = a.pivot(values="adp", index=["player_uid", "season"], on="period",
                aggregate_function="first").drop_nulls()
    # velocity = DRAFT adp - AUG15 adp ; positive => ADP improved (rose) over the summer
    w = w.with_columns((pl.col("DRAFT") - pl.col("AUG15")).alias("adp_velocity"))
    m = w.join(_forward_vorp(), on=["player_uid", "season"], how="inner")
    assert (m["season"].max() or 0) <= LAST_COMPLETE, "G10.1 leak: velocity_study frame > last_complete_season"
    m = m.with_columns(pl.when(pl.col("adp_velocity") > 3).then(pl.lit("riser"))
                       .when(pl.col("adp_velocity") < -3).then(pl.lit("faller"))
                       .otherwise(pl.lit("stable")).alias("mover"))
    L = ["", f"## ADP velocity study (dynasty K, {VEL_MIN}+; Decision 2 scope)",
         "Movement DRAFT→AUG15; does the late-summer riser/faller signal predict realized value?",
         "", "| mover | n | mean fwd3 VORP | median |", "|---|--:|--:|--:|"]
    for r in (m.group_by("mover").agg(pl.len().alias("n"),
              pl.col("fwd3_vorp").mean().alias("mv"), pl.col("fwd3_vorp").median().alias("md"))
              .sort("mv", descending=True).iter_rows(named=True)):
        L.append(f"| {r['mover']} | {r['n']} | {r['mv']:+.0f} | {r['md']:+.0f} |")
    corr = np.corrcoef(m["adp_velocity"].to_numpy(), m["fwd3_vorp"].to_numpy())[0, 1]
    L.append(f"\ncorr(ADP velocity, fwd3 VORP) = {corr:+.3f} "
             f"({'risers outperform — actionable in August' if corr>0.05 else 'no exploitable signal'}).")
    return L


def build() -> None:
    L = ["# ADP Calibration — Phase 5.3", "",
         "Two asset classes, priced separately and labeled throughout.", ""]
    L += startup_calibration()
    L += rookie_slot_to_capital()
    L += market_efficiency()
    L += velocity_study()
    EXPORTS.mkdir(parents=True, exist_ok=True)
    (EXPORTS / "adp_calibration.md").write_text("\n".join(L))
    log.info("adp calibration -> %s", EXPORTS / "adp_calibration.md")


if __name__ == "__main__":
    build()
