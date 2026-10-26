"""5.1 follow-ups (items 2 & 3):
 2. RB aging as a CONTINUOUS target_share interaction (Δ ~ age + age×target_share),
    replacing the pre-registered binary split — not loosening the threshold.
 3. Per-opportunity aging (pts/opportunity) alongside per-game; divergence flags
    usage-driven vs ability-driven decline. Cross-checked vs research/R2.md.
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import numpy as np
import polars as pl
import statsmodels.api as sm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CONFIG
from ingest._common import get_logger

log = get_logger("aging_followups")
A = CONFIG["models"]["aging"]


def _season_panel() -> pl.DataFrame:
    con = duckdb.connect(str(CONFIG.path("warehouse")), read_only=True)
    df = con.execute("""
        SELECT s.player_uid, s.season, s.position, s.games, s.ppg_ppr, s.fp_ppr,
               m.avg_target_share, m.opportunities, d.birthdate
        FROM fact_player_season s JOIN dim_player d USING(player_uid)
        LEFT JOIN fact_player_season_metrics m ON m.player_uid=s.player_uid AND m.season=s.season
        WHERE s.position IN ('QB','RB','WR','TE')
    """).pl()
    con.close()
    df = df.filter(pl.col("birthdate").is_not_null() & (pl.col("games") >= A["min_games_per_season"])
                   & ~pl.col("season").is_in(A["exclude_seasons"]) & (pl.col("opportunities") > 0))
    df = df.with_columns([
        (pl.col("season") - pl.col("birthdate").str.slice(0, 4).cast(pl.Int32)).alias("age"),
        (pl.col("fp_ppr") / pl.col("opportunities")).alias("pts_per_opp")])
    return df


def _pairs(df: pl.DataFrame) -> pl.DataFrame:
    nxt = df.select(pl.col("player_uid"), (pl.col("season") - 1).alias("season"),
                    pl.col("ppg_ppr").alias("ppg_next"), pl.col("pts_per_opp").alias("ppo_next"),
                    pl.col("games").alias("games_next"))
    p = df.join(nxt, on=["player_uid", "season"], how="inner")
    return p.with_columns([
        (pl.col("ppg_next") - pl.col("ppg_ppr")).alias("d_ppg"),
        (pl.col("ppo_next") - pl.col("pts_per_opp")).alias("d_ppo"),
        pl.min_horizontal("games", "games_next").alias("w"),
        pl.col("age").clip(A["age_min"], A["age_max"]).alias("age_b")])


def item2_continuous_rb(pairs: pl.DataFrame) -> None:
    rb = pairs.filter((pl.col("position") == "RB") & pl.col("avg_target_share").is_not_null())
    age_c = rb["age"].to_numpy() - 26.0            # center at 26
    ts_c = rb["avg_target_share"].to_numpy() - rb["avg_target_share"].mean()
    X = np.column_stack([np.ones(len(rb)), age_c, ts_c, age_c * ts_c])
    y = rb["d_ppg"].to_numpy(); w = rb["w"].to_numpy()
    res = sm.WLS(y, X, weights=w).fit()
    names = ["intercept", "age", "target_share", "age×target_share"]
    print("\n=== ITEM 2: RB aging as continuous target_share interaction (WLS, n=%d) ===" % len(rb))
    print("  Δppg ~ age(centered@26) + target_share(centered) + interaction")
    for n, b, p, se in zip(names, res.params, res.pvalues, res.bse):
        print(f"    {n:18s} coef={b:+.3f}  se={se:.3f}  p={p:.3f}")
    inter = res.params[3]
    print(f"  → interaction {inter:+.3f}: higher target_share makes the per-year age slope "
          f"{'FLATTER (receiving backs age better)' if inter>0 else 'STEEPER (receiving backs decline faster)'}")
    print(f"  (binary split kept as pre-registered; this continuous model supersedes it for 5.5)")


def item3_per_opportunity(pairs: pl.DataFrame) -> None:
    print("\n=== ITEM 3: per-GAME vs per-OPPORTUNITY aging (divergence = usage-driven) ===")
    for pos in ["RB", "WR", "TE"]:
        sub = pairs.filter(pl.col("position") == pos)
        print(f"\n  {pos}: from_age | n | Δ pts/GAME | Δ pts/OPP | signal")
        for age in range(23, 33):
            g = sub.filter(pl.col("age_b") == age)
            if g.height < 15:
                continue
            w = g["w"].to_numpy()
            dg = float((w * g["d_ppg"].to_numpy()).sum() / w.sum())
            do = float((w * g["d_ppo"].to_numpy()).sum() / w.sum())
            sig = "USAGE (game↓ opp~)" if (dg < -0.3 and do > dg + 0.2) else \
                  ("ABILITY (both↓)" if (dg < -0.3 and do <= dg + 0.2) else "")
            print(f"    {age:>2} | {g.height:>3} | {dg:+6.2f} | {do:+6.3f} | {sig}")


def run() -> None:
    df = _season_panel()
    pairs = _pairs(df)
    item2_continuous_rb(pairs)
    item3_per_opportunity(pairs)
    print("\n=== R2.md cross-check (RB cliff) ===")
    print("  R2: cliff causation (biological vs survivorship vs USAGE) is genuinely unresolved;")
    print("  'teams stop feeding older backs' = usage hypothesis. Above: if RB per-game drops")
    print("  at 28+ while per-opportunity holds, that supports USAGE, not ability — matching")
    print("  R2's recommendation to sell on age 26-27 + role erosion, not raw touches.")


if __name__ == "__main__":
    run()
