"""5.4 refit with college production (item 1). Match cfbfastR dominator -> NFL
players, compute peak_dominator + breakout_age, refit the top-12 model, and re-run
the beat-the-baseline test (full + college-covered subset). Guardrails unchanged:
strict temporal split, locked hyperparameters, honest reporting.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import polars as pl
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CONFIG
from ingest._common import get_logger
from models.archetypes import _frame, FEATS
from transform.identity import norm_name

log = get_logger("cfb_refit")
SEED = CONFIG["models"]["seed"]
THRESH = {"WR": 0.20, "TE": 0.15, "RB": 0.15, "QB": 0.15}


def _college_features(df: pl.DataFrame) -> pl.DataFrame:
    cfb = pl.read_parquet(CONFIG.path("data_staging") / "cfb_dominator.parquet")
    cfb = cfb.with_columns(pl.col("player").map_elements(norm_name, return_dtype=pl.Utf8).alias("nn"))
    # collapse a player's multi-team season (transfers) to their max share that season
    cfb = cfb.group_by(["nn", "season"]).agg(
        pl.col("rec_share").max().alias("rec_share"),
        pl.col("scrimmage_share").max().alias("scr_share"),
        pl.col("rec_yds").max().alias("rec_yds"),
        pl.col("rush_yds").max().alias("rush_yds"))

    dnn = df.with_columns(pl.col("player_uid"))  # base
    d = df.select("player_uid", "position", "draft_year",
                  pl.col("player_uid").alias("_u")).drop("_u")
    # need name + birth_year from dim (already in _frame? _frame drops name) — rejoin
    import duckdb
    con = duckdb.connect(str(CONFIG.path("warehouse")), read_only=True)
    meta = con.execute("""SELECT player_uid, name, birthdate FROM dim_player""").pl()
    con.close()
    d = df.join(meta, on="player_uid", how="left").with_columns([
        pl.col("name").map_elements(norm_name, return_dtype=pl.Utf8).alias("nn"),
        pl.col("birthdate").str.slice(0, 4).cast(pl.Int32, strict=False).alias("byr")])

    rows = []
    cfb_by_nn = cfb.partition_by("nn", as_dict=True)
    for r in d.iter_rows(named=True):
        key = (r["nn"],)
        seasons = cfb_by_nn.get(key)
        peak_dom, breakout_age = None, None
        if seasons is not None and r["draft_year"] is not None:
            pos = r["position"]
            share_col = "rec_share" if pos in ("WR", "TE") else "scr_share"
            minyds = 200 if pos in ("WR", "TE") else 400
            yd_col = "rec_yds" if pos in ("WR", "TE") else "rush_yds"
            # college seasons strictly before draft, within a 6-yr window
            sw = seasons.filter((pl.col("season") < r["draft_year"]) &
                                (pl.col("season") >= r["draft_year"] - 6))
            if sw.height:
                peak_dom = float(sw[share_col].max())
                bk = sw.filter((pl.col(share_col) >= THRESH.get(pos, 0.15)) &
                               (pl.col(yd_col) >= minyds)).sort("season")
                if bk.height and r["byr"]:
                    breakout_age = int(bk["season"][0] - r["byr"])
        rows.append({"player_uid": r["player_uid"], "peak_dominator": peak_dom,
                     "breakout_age": breakout_age})
    feat = pl.DataFrame(rows)
    matched = feat.filter(pl.col("peak_dominator").is_not_null()).height
    log.info("college match: %d/%d players (%.0f%%) have college production",
             matched, feat.height, 100 * matched / feat.height)
    return df.join(feat, on="player_uid", how="left"), matched / feat.height


def _auc(df, cols, tr, te, y):
    X = df.select(cols).to_pandas()
    m = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, max_depth=3,
                                       l2_regularization=1.0, min_samples_leaf=20,
                                       early_stopping=True, validation_fraction=0.15, random_state=SEED)
    m.fit(X[tr], y[tr])
    return roc_auc_score(y[te], m.predict_proba(X[te])[:, 1])


def run() -> None:
    df, match_rate = _college_features(_frame())
    # spot check
    for nm in ("jamarr chase", "jaxon smith njigba", "puka nacua"):
        r = df.join(
            df.select("player_uid"), on="player_uid", how="inner")
    y = df["hit"].to_numpy()
    yr = df["draft_year"].to_numpy()
    tr, te = yr <= 2018, yr >= 2019

    pos_dum = {f"pos_{p}": (df["position"] == p).cast(pl.Int8) for p in ("QB", "RB", "WR", "TE")}
    df = df.with_columns(**pos_dum)
    base = ["draft_ovr"]
    combine = FEATS + list(pos_dum)
    college = combine + ["peak_dominator", "breakout_age"]

    # draft-capital-only logistic
    lo = np.log(df["draft_ovr"].to_numpy()).reshape(-1, 1)
    b = LogisticRegression().fit(lo[tr], y[tr])
    auc_cap = roc_auc_score(y[te], b.predict_proba(lo[te])[:, 1])
    auc_comb = _auc(df, combine, tr, te, y)
    auc_coll = _auc(df, college, tr, te, y)

    print("=== 5.4 REFIT with college production — out-of-sample (test=2019-2022) ===")
    print(f"college match rate: {match_rate:.0%} of drafted skill players")
    print(f"  draft-capital-only        AUC {auc_cap:.3f}")
    print(f"  + combine + age (5.4)     AUC {auc_comb:.3f}  (Δ {auc_comb-auc_cap:+.3f})")
    print(f"  + college (dom+breakout)  AUC {auc_coll:.3f}  (Δ {auc_coll-auc_cap:+.3f})")

    # WR-only + college-covered subset (2017+ draftees, full college coverage)
    for label, mask in [("WR only", df["position"] == "WR"),
                        ("2017+ college-covered", pl.Series(yr) >= 2017)]:
        sub = df.filter(mask); ys = sub["hit"].to_numpy(); yrs = sub["draft_year"].to_numpy()
        trs, tes = yrs <= 2018, yrs >= 2019
        if tes.sum() < 20 or ys[tes].sum() < 3:
            print(f"  [{label}] insufficient test events"); continue
        los = np.log(sub["draft_ovr"].to_numpy()).reshape(-1, 1)
        bl = LogisticRegression().fit(los[trs], ys[trs])
        acap = roc_auc_score(ys[tes], bl.predict_proba(los[tes])[:, 1])
        acol = _auc(sub, college, trs, tes, ys)
        print(f"  [{label}] cap {acap:.3f} -> +college {acol:.3f}  (Δ {acol-acap:+.3f}), test n={tes.sum()}")

    verdict = "BEATS" if auc_coll > auc_cap + 0.01 else "still DOES NOT beat"
    print(f"\nVERDICT: with college production the model {verdict} draft-capital-only OOS.")


if __name__ == "__main__":
    run()
