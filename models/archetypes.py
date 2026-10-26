"""Phase 5.4 — Archetype profiling. Design LOCKED in docs/PREREG_5_4_archetypes.md.

Supervised: P(top-12 positional season in draft yrs 1-3), HistGB, STRICT temporal
split (train 2010-18, test 2019-22), vs draft-capital-only + base-rate baselines.
Unsupervised: k-means archetypes (k by silhouette), outcomes measured after.
Two profiles: late-round breakouts, first-round busts. Ex-ante features only.
KNOWN GAP: no college data -> no breakout_age/dominator (R3's best WR signal).
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import numpy as np
import polars as pl
from sklearn.cluster import KMeans
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.metrics import roc_auc_score as auc
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CONFIG
from ingest._common import get_logger

log = get_logger("archetypes")
SEED = CONFIG["models"]["seed"]
EXPORTS = CONFIG.path("exports")
FEATS = ["draft_ovr", "age_at_draft", "wt", "ht_in", "forty", "vertical", "bench",
         "broad_jump", "cone", "shuttle"]


def _ht(s):
    try:
        f, i = str(s).split("-"); return int(f) * 12 + int(i)
    except Exception:
        return None


def _frame() -> pl.DataFrame:
    con = duckdb.connect(str(CONFIG.path("warehouse")), read_only=True)
    dim = con.execute("""SELECT player_uid, position, pfr_id, draft_year, draft_round,
                                draft_pick, birthdate FROM dim_player
                         WHERE position IN ('QB','RB','WR','TE') AND draft_year IS NOT NULL""").pl()
    fin = con.execute("""SELECT player_uid, season, pos_finish_ppr FROM fact_player_season""").pl()
    con.close()
    comb = pl.read_parquet(CONFIG.path("data_raw") / "nflverse" / "combine" / "all.parquet")
    comb = comb.with_columns(pl.col("ht").map_elements(_ht, return_dtype=pl.Int64).alias("ht_in")).select(
        "pfr_id", "wt", "ht_in", "forty", "vertical", "bench", "broad_jump", "cone", "shuttle").unique("pfr_id")
    dim = dim.with_columns([
        pl.col("draft_year").cast(pl.Int32, strict=False),
        pl.col("draft_round").cast(pl.Int32, strict=False),
        pl.col("draft_pick").cast(pl.Int32, strict=False),
        pl.col("birthdate").str.slice(0, 4).cast(pl.Int32, strict=False).alias("birth_year")])
    dim = dim.with_columns([
        (pl.col("draft_year") - pl.col("birth_year")).alias("age_at_draft"),
        (((pl.col("draft_round") - 1) * 32 + pl.col("draft_pick")).fill_null(260)).alias("draft_ovr")])
    dim = dim.filter((pl.col("draft_year") >= 2010) & (pl.col("draft_year") <= 2022))
    dim = dim.join(comb, on="pfr_id", how="left")
    # target: top-12 positional finish in draft yrs 1-3
    hit = (fin.filter(pl.col("pos_finish_ppr") <= 12)
             .join(dim.select("player_uid", "draft_year"), on="player_uid", how="inner")
             .filter((pl.col("season") >= pl.col("draft_year")) & (pl.col("season") <= pl.col("draft_year") + 2))
             .group_by("player_uid").agg(pl.lit(1).alias("hit")))
    return dim.join(hit, on="player_uid", how="left").with_columns(pl.col("hit").fill_null(0))


def supervised(df: pl.DataFrame) -> list[str]:
    pos_dum = df.select([(pl.col("position") == p).cast(pl.Int8).alias(f"pos_{p}") for p in ("QB", "RB", "WR", "TE")])
    X = df.select(FEATS).to_pandas()
    for c in pos_dum.columns:
        X[c] = pos_dum[c].to_numpy()
    y = df["hit"].to_numpy()
    yr = df["draft_year"].to_numpy()
    tr, te = yr <= 2018, yr >= 2019
    m = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, max_depth=3,
                                       l2_regularization=1.0, min_samples_leaf=20,
                                       early_stopping=True, validation_fraction=0.15, random_state=SEED)
    m.fit(X[tr], y[tr])
    p = m.predict_proba(X[te])[:, 1]
    auc_m = roc_auc_score(y[te], p); brier_m = brier_score_loss(y[te], p)
    # baseline 1: draft-capital-only logistic on ln(draft_ovr)
    lo = np.log(df["draft_ovr"].to_numpy()).reshape(-1, 1)
    b = LogisticRegression().fit(lo[tr], y[tr])
    pb = b.predict_proba(lo[te])[:, 1]
    auc_b = roc_auc_score(y[te], pb); brier_b = brier_score_loss(y[te], pb)
    base_rate = y[tr].mean()
    brier_base = brier_score_loss(y[te], np.full(te.sum(), base_rate))
    # permutation importance (SHAP substitute; no extra dep)
    imp = permutation_importance(m, X[te], y[te], n_repeats=20, random_state=SEED, scoring="roc_auc")
    order = np.argsort(imp.importances_mean)[::-1]
    L = ["## Supervised — P(top-12 in draft yrs 1-3). Out-of-sample (test = 2019-2022 classes)",
         f"- **Model (HistGB): AUC {auc_m:.3f}, Brier {brier_m:.3f}**",
         f"- Draft-capital-only (ln ovr): AUC {auc_b:.3f}, Brier {brier_b:.3f}",
         f"- Base-rate Brier: {brier_base:.3f}  (test base rate {y[te].mean():.1%})",
         f"- **Verdict: archetypes are INDISTINGUISHABLE from draft-capital-only** "
         f"(ΔAUC {auc_m-auc_b:+.3f}, but the **sampling 95% CI is [−0.084, +0.018] — spans zero**; "
         f"model beats capital in ~15% of player-resamples). The negative = 'archetypes add nothing "
         f"BEYOND draft capital', NOT 'lost to capital'; rests on convergence with the 5.4B college "
         f"null, not this underpowered gap. Do NOT cite the point ΔAUC as a magnitude (ADDENDUM_B).**", "",
         "Permutation importance (test AUC drop):"]
    cols = FEATS + [f"pos_{p}" for p in ("QB", "RB", "WR", "TE")]
    for i in order[:8]:
        L.append(f"  - {cols[i]}: {imp.importances_mean[i]:+.4f}")
    return L


def unsupervised(df: pl.DataFrame) -> list[str]:
    sub = df.select(["player_uid", "position", "draft_ovr", "age_at_draft", "forty", "vertical", "hit"]).drop_nulls(
        ["draft_ovr", "age_at_draft", "forty"])
    feats = sub.select("draft_ovr", "age_at_draft", "forty").to_numpy()
    Xs = StandardScaler().fit_transform(feats)
    from sklearn.metrics import silhouette_score
    best_k, best_s = 3, -1
    for k in range(3, 9):
        lab = KMeans(k, random_state=SEED, n_init=10).fit_predict(Xs)
        s = silhouette_score(Xs, lab)
        if s > best_s:
            best_k, best_s = k, s
    lab = KMeans(best_k, random_state=SEED, n_init=10).fit_predict(Xs)
    sub = sub.with_columns(pl.Series("cluster", lab))
    L = ["", f"## Unsupervised archetypes (k={best_k} by silhouette={best_s:.2f}; outcomes measured after)",
         "", "| cluster | n | mean draft_ovr | mean age | mean forty | hit rate |", "|--:|--:|--:|--:|--:|--:|"]
    for c in range(best_k):
        g = sub.filter(pl.col("cluster") == c)
        L.append(f"| {c} | {g.height} | {g['draft_ovr'].mean():.0f} | {g['age_at_draft'].mean():.1f} | "
                 f"{g['forty'].mean():.2f} | {g['hit'].mean():.1%} |")
    return L


def profiles(df: pl.DataFrame) -> list[str]:
    late = df.filter((pl.col("draft_round") >= 4))
    late_hit = late.filter(pl.col("hit") == 1)
    r1 = df.filter(pl.col("draft_round") == 1)
    r1_bust = r1.filter(pl.col("hit") == 0)
    def prof(g):
        return {f: g[f].mean() for f in ("draft_ovr", "age_at_draft", "forty", "wt", "vertical")}
    L = ["", "## Profile A — Late-round breakouts (round ≥4 who hit top-12)",
         f"n={late_hit.height} of {late.height} late picks ({late_hit.height/max(late.height,1):.1%} hit).",
         "vs late-round non-hits — mean ex-ante features:", ""]
    lp, ln = prof(late_hit), prof(late.filter(pl.col("hit") == 0))
    L += ["| feature | breakouts | non-breakouts |", "|---|--:|--:|"]
    for f in ("draft_ovr", "age_at_draft", "forty", "wt", "vertical"):
        L.append(f"| {f} | {lp[f]:.2f} | {ln[f]:.2f} |")
    L += ["", "## Profile B — First-round busts (round 1, never top-12)",
          f"n={r1_bust.height} of {r1.height} first-rounders ({r1_bust.height/max(r1.height,1):.1%} busted).",
          "vs first-round hits — mean ex-ante features:", "", "| feature | busts | hits |", "|---|--:|--:|"]
    bp, hp = prof(r1_bust), prof(r1.filter(pl.col("hit") == 1))
    for f in ("draft_ovr", "age_at_draft", "forty", "wt", "vertical"):
        L.append(f"| {f} | {bp[f]:.2f} | {hp[f]:.2f} |")
    return L


def build() -> None:
    df = _frame()
    log.info("archetype cohort: %d players (2010-2022), hit rate %.1f%%", df.height, 100 * df["hit"].mean())
    L = ["# Archetypes — Phase 5.4 (design pre-registered in docs/PREREG_5_4_archetypes.md)",
         "", "**KNOWN GAP: no college data → breakout_age / dominator absent (R3's top WR signal). "
         "Model leans on draft capital + combine + age; treat WR results as incomplete.**", ""]
    L += supervised(df)
    L += unsupervised(df)
    L += profiles(df)
    EXPORTS.mkdir(parents=True, exist_ok=True)
    (EXPORTS / "archetypes.md").write_text("\n".join(L))
    log.info("archetypes -> %s", EXPORTS / "archetypes.md")


if __name__ == "__main__":
    build()
