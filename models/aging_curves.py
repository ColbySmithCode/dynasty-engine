"""Phase 5.1 — Positional aging curves via the DELTA METHOD.

Survivorship-safe: we never regress age vs PPG cross-sectionally (only good old
players survive, which falsely flattens the top end). Instead, for every pair of
consecutive qualifying seasons for the same player we take Δ(PPG) from age a to
a+1, average the deltas by position/archetype/age (weighted by playing time), and
chain them into a curve. Report sample sizes + 95% CIs per age bucket.

All gates/params are PRE-REGISTERED in config.models.aging (locked before results).
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

log = get_logger("aging")
A = CONFIG["models"]["aging"]
EXPORTS = CONFIG.path("exports")
MODELS = CONFIG.path("models")


def _pairs() -> pl.DataFrame:
    con = duckdb.connect(str(CONFIG.path("warehouse")), read_only=True)
    s = con.execute("""
        SELECT s.player_uid, s.season, s.position, s.games, s.ppg_ppr,
               m.avg_target_share, d.birthdate
        FROM fact_player_season s
        JOIN dim_player d USING(player_uid)
        LEFT JOIN fact_player_season_metrics m
          ON m.player_uid=s.player_uid AND m.season=s.season
        WHERE s.position IN ('QB','RB','WR','TE')
    """).pl()
    con.close()
    s = s.filter(
        pl.col("birthdate").is_not_null() & (pl.col("games") >= A["min_games_per_season"])
        & ~pl.col("season").is_in(A["exclude_seasons"]))
    s = s.with_columns(
        (pl.col("season") - pl.col("birthdate").str.slice(0, 4).cast(pl.Int32)).alias("age"))
    # RB archetype at season Y
    s = s.with_columns(
        pl.when((pl.col("position") == "RB") &
                (pl.col("avg_target_share").fill_null(0) >= A["rb_receiving_target_share"]))
          .then(pl.lit("RB-receiving"))
          .when(pl.col("position") == "RB").then(pl.lit("RB-earlydown"))
          .otherwise(pl.col("position")).alias("archetype"))

    nxt = s.select(
        pl.col("player_uid"), (pl.col("season") - 1).alias("season"),
        pl.col("ppg_ppr").alias("ppg_next"), pl.col("games").alias("games_next"))
    pairs = s.join(nxt, on=["player_uid", "season"], how="inner")
    pairs = pairs.with_columns([
        (pl.col("ppg_next") - pl.col("ppg_ppr")).alias("d_ppg"),
        pl.min_horizontal("games", "games_next").alias("w"),
        pl.col("age").clip(A["age_min"], A["age_max"]).alias("age_b"),
    ])
    return pairs


def _weighted_stats(d: np.ndarray, w: np.ndarray) -> tuple[float, float, int]:
    W = w.sum()
    mean = float((w * d).sum() / W)
    var = float((w * (d - mean) ** 2).sum() / W)
    n_eff = (W ** 2) / (w ** 2).sum()
    se = float(np.sqrt(var / n_eff)) if n_eff > 1 else float("nan")
    return mean, se, int(len(d))


def build() -> None:
    pairs = _pairs()
    log.info("delta-method pairs: %d (positions/archetypes: %s)",
             pairs.height, sorted(pairs["archetype"].unique().to_list()))
    z = 1.96
    rows = []
    for arch in sorted(pairs["archetype"].unique().to_list()):
        sub = pairs.filter(pl.col("archetype") == arch)
        for age in range(A["age_min"], A["age_max"] + 1):
            g = sub.filter(pl.col("age_b") == age)
            if g.height == 0:
                continue
            mean, se, n = _weighted_stats(g["d_ppg"].to_numpy(), g["w"].to_numpy())
            rows.append({"archetype": arch, "from_age": age, "n_pairs": n,
                         "mean_dppg": round(mean, 3),
                         "ci_lo": round(mean - z * se, 3) if n >= A["min_bucket_n"] else None,
                         "ci_hi": round(mean + z * se, 3) if n >= A["min_bucket_n"] else None})
    deltas = pl.DataFrame(rows)
    deltas.write_parquet(MODELS / "aging_deltas.parquet")

    # chain deltas into a relative curve per archetype (baseline age_min = 0.0)
    curve_rows = []
    for arch in sorted(deltas["archetype"].unique().to_list()):   # determinism: unique() order is unstable
        d = deltas.filter(pl.col("archetype") == arch).sort("from_age")
        level = 0.0
        curve_rows.append({"archetype": arch, "age": A["age_min"], "rel_ppg": 0.0})
        for r in d.iter_rows(named=True):
            level += r["mean_dppg"]
            curve_rows.append({"archetype": arch, "age": r["from_age"] + 1,
                               "rel_ppg": round(level, 3)})
    curve = pl.DataFrame(curve_rows)
    curve.write_parquet(MODELS / "aging_curves.parquet")
    _write_md(deltas, curve)
    log.info("aging curves -> %s", EXPORTS / "aging_curves.md")


def _write_md(deltas: pl.DataFrame, curve: pl.DataFrame) -> None:
    lines = ["# Aging Curves (delta method) — Phase 5.1", "",
             "Δ PPG(PPR) from age a → a+1, weighted by min(games). "
             f"Pre-registered gates: ≥{A['min_games_per_season']} games/season, "
             f"RB receiving-back if season target_share ≥ {A['rb_receiving_target_share']}, "
             f"CI shown for buckets with n ≥ {A['min_bucket_n']}. 2026 excluded.", ""]
    for arch in sorted(deltas["archetype"].unique().to_list()):
        lines += [f"## {arch}", "", "| from_age | n_pairs | mean ΔPPG | 95% CI |",
                  "|--:|--:|--:|--:|"]
        for r in deltas.filter(pl.col("archetype") == arch).sort("from_age").iter_rows(named=True):
            ci = f"[{r['ci_lo']:+.2f}, {r['ci_hi']:+.2f}]" if r["ci_lo"] is not None else "— (n<min)"
            lines.append(f"| {r['from_age']} | {r['n_pairs']} | {r['mean_dppg']:+.2f} | {ci} |")
        c = curve.filter(pl.col("archetype") == arch).sort("age")
        peak = c.filter(pl.col("rel_ppg") == c["rel_ppg"].max())
        lines += ["", f"Chained relative curve (age {A['age_min']} = 0), peak at age "
                  f"{peak['age'][0]}:", "", "```",
                  "  ".join(f"{r['age']}:{r['rel_ppg']:+.1f}" for r in c.iter_rows(named=True)),
                  "```", ""]
    EXPORTS.mkdir(parents=True, exist_ok=True)
    (EXPORTS / "aging_curves.md").write_text("\n".join(lines))


if __name__ == "__main__":
    build()
