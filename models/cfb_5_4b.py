"""5.4B — final college-production attempt. Design LOCKED in docs/PREREG_5_4B.md.
Proper dominator (yards + TD share), ceiling targets, within-stratum tertile lift.
Run once; report honestly.
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
from models.archetypes import _frame
from models.adp_calibration import _forward_vorp
from transform.identity import norm_name

log = get_logger("cfb_5_4b")
RNG = np.random.default_rng(CONFIG["models"]["seed"])


def proper_dominator() -> pl.DataFrame:
    frames = []
    for y in range(2014, 2025):
        p = CONFIG.path("data_raw") / "cfb" / str(y) / f"player_stats_{y}.parquet"
        if not p.exists():
            continue
        raw = pl.read_parquet(p)
        rec = (raw.filter(pl.col("reception_player").is_not_null())
               .group_by(["reception_player", "team"]).agg(pl.col("reception_yds").sum().alias("rec_yds")))
        # receiving TD: reception play where the receiver is the TD scorer
        rec_td = (raw.filter(pl.col("reception_player").is_not_null() &
                             (pl.col("touchdown_player") == pl.col("reception_player")))
                  .group_by(["reception_player", "team"]).agg(pl.len().alias("rec_td")))
        rush = (raw.filter(pl.col("rush_player").is_not_null())
                .group_by(["rush_player", "team"]).agg(pl.col("rush_yds").sum().alias("rush_yds")))
        rush_td = (raw.filter(pl.col("rush_player").is_not_null() &
                              (pl.col("touchdown_player") == pl.col("rush_player")))
                   .group_by(["rush_player", "team"]).agg(pl.len().alias("rush_td")))
        tm = raw.group_by("team").agg(
            pl.col("reception_yds").sum().alias("t_rec_yds"), pl.col("rush_yds").sum().alias("t_rush_yds"),
            (pl.col("reception_player").is_not_null() & (pl.col("touchdown_player") == pl.col("reception_player")))
              .sum().alias("t_rec_td"),
            (pl.col("rush_player").is_not_null() & (pl.col("touchdown_player") == pl.col("rush_player")))
              .sum().alias("t_rush_td"))
        p2 = (rec.rename({"reception_player": "player"})
              .join(rec_td.rename({"reception_player": "player"}), on=["player", "team"], how="left")
              .join(rush.rename({"rush_player": "player"}), on=["player", "team"], how="left")
              .join(rush_td.rename({"rush_player": "player"}), on=["player", "team"], how="left")
              .join(tm, on="team", how="left"))
        for c in ("rec_yds", "rec_td", "rush_yds", "rush_td"):
            p2 = p2.with_columns(pl.col(c).fill_null(0))
        p2 = p2.with_columns([
            pl.lit(y).alias("season"),
            (0.5 * pl.col("rec_yds") / pl.col("t_rec_yds") +
             0.5 * pl.col("rec_td") / pl.when(pl.col("t_rec_td") > 0).then(pl.col("t_rec_td")).otherwise(1)).alias("dom_rec"),
            (0.5 * (pl.col("rec_yds") + pl.col("rush_yds")) / (pl.col("t_rec_yds") + pl.col("t_rush_yds")) +
             0.5 * (pl.col("rec_td") + pl.col("rush_td")) /
             pl.when(pl.col("t_rec_td") + pl.col("t_rush_td") > 0).then(pl.col("t_rec_td") + pl.col("t_rush_td")).otherwise(1)).alias("dom_scr"),
            (pl.col("rec_yds") + pl.col("rush_yds")).alias("tot_yds")])
        frames.append(p2.select("player", "team", "season", "dom_rec", "dom_scr", "rec_yds", "tot_yds"))
    allp = pl.concat(frames, how="vertical_relaxed")
    return allp.group_by([pl.col("player").map_elements(norm_name, return_dtype=pl.Utf8).alias("nn"), "season"]).agg(
        pl.col("dom_rec").max(), pl.col("dom_scr").max(),
        pl.col("rec_yds").max(), pl.col("tot_yds").max())


def build_features(df: pl.DataFrame) -> pl.DataFrame:
    cfb = proper_dominator()
    con = duckdb.connect(str(CONFIG.path("warehouse")), read_only=True)
    meta = con.execute("SELECT player_uid, name, birthdate FROM dim_player").pl()
    con.close()
    d = df.join(meta, on="player_uid", how="left").with_columns([
        pl.col("name").map_elements(norm_name, return_dtype=pl.Utf8).alias("nn"),
        pl.col("birthdate").str.slice(0, 4).cast(pl.Int32, strict=False).alias("byr")])
    by = cfb.partition_by("nn", as_dict=True)
    rows = []
    for r in d.iter_rows(named=True):
        pos = r["position"]
        dcol = "dom_rec" if pos in ("WR", "TE") else "dom_scr"
        ycol = "rec_yds" if pos in ("WR", "TE") else "tot_yds"
        miny = 200 if pos in ("WR", "TE") else 400
        out = {"player_uid": r["player_uid"], "dom_best": None, "dom_final": None,
               "breakout_age_20": None, "breakout_age_30": None}
        s = by.get((r["nn"],))
        if s is not None and r["draft_year"]:
            s = s.filter((pl.col("season") < r["draft_year"]) & (pl.col("season") >= r["draft_year"] - 6)).sort("season")
            if s.height:
                out["dom_best"] = float(s[dcol].max())
                out["dom_final"] = float(s[dcol][-1])
                for thr, key in ((0.20, "breakout_age_20"), (0.30, "breakout_age_30")):
                    bk = s.filter((pl.col(dcol) >= thr) & (pl.col(ycol) >= miny))
                    if bk.height and r["byr"]:
                        out[key] = int(bk["season"][0] - r["byr"])
        rows.append(out)
    return df.join(pl.DataFrame(rows), on="player_uid", how="left")


def perm_diff(a: np.ndarray, b: np.ndarray, n=20000) -> tuple[float, float]:
    a = a[~np.isnan(a)]; b = b[~np.isnan(b)]
    if len(a) < 3 or len(b) < 3:
        return float("nan"), float("nan")
    obs = a.mean() - b.mean()
    pool = np.concatenate([a, b]); na = len(a)
    d = np.array([(lambda s: s[:na].mean() - s[na:].mean())(RNG.permutation(pool)) for _ in range(n)])
    return obs, float((np.abs(d) >= abs(obs)).mean())


def build_cohort() -> pl.DataFrame:
    """The 5.4B college-matched cohort: dominator features + ceiling targets (hit12, top5,
    fwd3_vorp), filtered to players with a college dom_best. Single source used by run() and the
    Westfall-Young joint-null below (keeps the two in lockstep)."""
    base = _frame()
    fv = _forward_vorp().group_by("player_uid").agg(pl.col("fwd3_vorp").max())  # collapse dup
    con = duckdb.connect(str(CONFIG.path("warehouse")), read_only=True)
    top5 = con.execute("""SELECT s.player_uid, 1 AS top5 FROM fact_player_season s
        JOIN dim_player d USING(player_uid)
        WHERE s.pos_finish_ppr<=5
          AND s.season BETWEEN CAST(d.draft_year AS INTEGER) AND CAST(d.draft_year AS INTEGER)+2
        GROUP BY s.player_uid""").pl()
    con.close()
    df = build_features(base).join(fv, on="player_uid", how="left").join(top5, on="player_uid", how="left")
    df = df.with_columns([pl.col("top5").fill_null(0), pl.col("draft_year").cast(pl.Int32, strict=False)])
    # deterministic row order => the WY permutation arrays are byte-reproducible cross-process
    # (unordered DuckDB/join reads would otherwise reorder players and perturb the 4th decimal).
    return df.filter(pl.col("dom_best").is_not_null()).sort("player_uid")


# ------------------------------------------------------------------------------------------------
# Two permutation nulls for the SAME hypothesis (dom_best ⊥ outcome), differing only in the
# EXCHANGEABLE SET (NOT in the observed statistic or the stratification):
#
#   PRE-REGISTERED (PREREG_5_4B, `perm_diff`) — the PRIMARY test. Tertiles are FIXED from the
#     observed dom_best; the OUTCOME labels are permuted WITHIN the top∪bottom pool, so the MIDDLE
#     THIRD is EXCLUDED from the exchangeable set; each of the 24 tests is independent. The
#     pre-registered DECISION RULE is evaluated on these marginals.
#
#   WESTFALL-YOUNG dom-shuffle — a POST-HOC joint null (methodological AMENDMENT §A3). dom_best is
#     permuted over the WHOLE stratum and tertiles are RE-DERIVED each draw, so the MIDDLE THIRD
#     PARTICIPATES; the SAME shuffle drives all 24 tests, giving the correlation-aware joint null of
#     the family minimum (a Westfall-Young single-step family-wise p).
#
# WHY THE MARGINALS DIFFER between the two: it is the exchangeable-set change (middle-third excluded
# vs included / fixed vs re-derived tertiles) — NOT the cross-test coupling, which by construction
# leaves every per-test marginal null unchanged. Same H0, two different nulls.
# ------------------------------------------------------------------------------------------------
STRATA = [(1, "R1"), (2, "R2"), (3, "R3"), (None, "R4-7")]
NON_R1 = [(2, "R2"), (3, "R3"), (None, "R4-7")]
TARGETS = ("hit", "top5", "fwd3_vorp")
CEILING_TARGETS = ("top5", "fwd3_vorp")     # PREREG_5_4B ceiling targets for the decision rule
WY_B = 20000       # permutation draws (matches perm_diff n); seeded => byte-reproducible
WY_MIN_STRATUM_N = 12


def _perm_diff_p(top, bot, rng, B):
    """Pre-registered marginal: |mean(top)-mean(bot)| vs permuting labels within the top∪bottom pool
    (middle excluded). add-one p = (1+#{|perm|>=|obs|})/(B+1). Returns (obs_diff, p)."""
    top = top[~np.isnan(top)]
    bot = bot[~np.isnan(bot)]
    if len(top) < 3 or len(bot) < 3:
        return float("nan"), float("nan")
    obs = top.mean() - bot.mean()
    pool = np.concatenate([top, bot])
    na = len(top)
    perm = rng.permuted(np.tile(pool, (B, 1)), axis=1)
    d = perm[:, :na].mean(1) - perm[:, na:].mean(1)
    return float(obs), float((1 + np.sum(np.abs(d) >= abs(obs))) / (B + 1))


def pre_registered_marginals(df: pl.DataFrame, B: int = WY_B, seed: int | None = None) -> dict:
    """PRE-REGISTERED (PREREG_5_4B) test — the PRIMARY result. Fixed tertiles, outcome-label
    permutation within top∪bottom (middle excluded), per-test independent. Evaluates the
    pre-registered DECISION RULE. Deterministic given `seed` (fresh generator, fixed test order)."""
    seed = CONFIG["models"]["seed"] if seed is None else seed
    rng = np.random.default_rng(seed)
    marg, direction = {}, {}
    for wr_only in (False, True):                              # fixed order => reproducible RNG use
        d0 = df.filter(pl.col("position") == "WR") if wr_only else df
        for rd, name in STRATA:
            s = d0.filter(pl.col("draft_round") == rd) if rd else d0.filter(pl.col("draft_round") >= 4)
            if s.height < WY_MIN_STRATUM_N:
                continue
            db = s["dom_best"].to_numpy().astype(float)
            hi, lo = db >= np.quantile(db, 2 / 3), db <= np.quantile(db, 1 / 3)
            for t in TARGETS:
                o = s[t].cast(pl.Float64).to_numpy()
                obs, p = _perm_diff_p(o[hi], o[lo], rng, B)
                key = f"{'WR' if wr_only else 'ALL'}|{name}|{t}"
                marg[key] = round(p, 4)
                direction[key] = obs            # obs = mean_top - mean_bot ; >0 == helps
    # DECISION RULE: ALL-skill, ceiling target (top5|fwd3_vorp) p<0.05 AND directional, in >=2 of 3
    # non-R1 strata (R2, R3, R4-7).
    strata_sig = {}
    for _, name in NON_R1:
        strata_sig[name] = any(
            marg.get(f"ALL|{name}|{t}", 1.0) < 0.05 and direction.get(f"ALL|{name}|{t}", 0) > 0
            for t in CEILING_TARGETS)
    n_hit = sum(strata_sig.values())
    vals = [v for v in marg.values() if not np.isnan(v)]
    return {
        "_scheme": "PRE-REGISTERED (PREREG_5_4B): tertiles FIXED from observed dom_best; permute "
                   "OUTCOME labels within the top∪bottom pool (MIDDLE THIRD EXCLUDED); per-test "
                   "independent. add-one p=(1+#{|perm|>=|obs|})/(B+1).",
        "decision_rule": "ceiling-target (top5|fwd3_vorp) tertile lift p<0.05 AND directional in "
                         ">=2 of 3 non-R1 strata (R2,R3,R4-7), ALL-skill",
        "rule_met": bool(n_hit >= 2),
        "n_ceiling_strata_significant": int(n_hit),
        "strata_significant": strata_sig,
        "n_tests": len(marg),
        "n_significant_05": int(sum(v < 0.05 for v in vals)),
        "min_marginal_p": round(min(vals), 4),
        "median_marginal_p": round(float(np.median(vals)), 4),
        "marginal_p": marg,
        "seed": seed, "B": B,
    }


def _tertile_stat(dom, outcomes, top_mask, bot_mask):
    """|mean(outcome | top dom tertile) - mean(outcome | bottom tertile)|, vectorized over draws
    when top_mask/bot_mask are (B, n)."""
    with np.errstate(invalid="ignore", divide="ignore"):
        mt = (outcomes * top_mask).sum(-1) / top_mask.sum(-1)
        mb = (outcomes * bot_mask).sum(-1) / bot_mask.sum(-1)
    return np.abs(mt - mb)


def westfall_young_preg(df: pl.DataFrame, B: int = WY_B, seed: int | None = None) -> dict:
    """COHERENT multiplicity correction FOR the pre-registered test: Westfall-Young family-wise p
    computed UNDER perm_diff's OWN exchangeable set — tertiles FIXED, MIDDLE THIRD EXCLUDED, only
    the OUTCOME labels within top∪bottom are permuted — but coupled across the 24 tests by a SHARED
    within-stratum random key (so the 3 targets, which share the dom_best tertiles, and the ALL/WR
    slices are correlated). Each test's marginal is exactly its perm_diff null; the coupling adds
    the family structure. This is the family-wise p that actually corrects the pre-registered
    result, NOT the dom-shuffle null (which uses a different exchangeable set)."""
    seed = CONFIG["models"]["seed"] if seed is None else seed
    rng = np.random.default_rng(seed)
    perm_stat, obs_stat = {}, {}
    for rd, name in STRATA:
        s = df.filter(pl.col("draft_round") == rd) if rd else df.filter(pl.col("draft_round") >= 4)
        if s.height < WY_MIN_STRATUM_N:
            continue
        dom = s["dom_best"].to_numpy().astype(float)
        wr = s["position"].to_numpy() == "WR"
        outc = {t: s[t].cast(pl.Float64).to_numpy() for t in TARGETS}
        U = rng.random((B, len(dom)))                          # shared random key -> couples tests
        for wr_only in (False, True):
            slice_cols = np.where(wr)[0] if wr_only else np.arange(len(dom))
            if len(slice_cols) < WY_MIN_STRATUM_N:
                continue
            db = dom[slice_cols]
            top_t, bot_t = db >= np.quantile(db, 2 / 3), db <= np.quantile(db, 1 / 3)
            for t in TARGETS:
                o = outc[t][slice_cols]
                valid = ~np.isnan(o)
                top_i = slice_cols[top_t & valid]              # fixed real top tertile (complete-case)
                bot_i = slice_cols[bot_t & valid]              # fixed real bottom tertile
                k_top, k_bot = len(top_i), len(bot_i)
                if k_top < 3 or k_bot < 3:
                    continue
                pool = np.concatenate([top_i, bot_i])          # top∪bottom (MIDDLE EXCLUDED)
                o_pool = outc[t][pool]
                key = f"{'WR' if wr_only else 'ALL'}|{name}|{t}"
                obs_stat[key] = abs(outc[t][top_i].mean() - outc[t][bot_i].mean())
                keys = U[:, pool]                              # (B, m); shared across the 3 targets
                thr = np.sort(keys, axis=1)[:, k_top - 1][:, None]   # k_top smallest -> "top"
                tm = keys <= thr
                with np.errstate(invalid="ignore"):
                    mt = (o_pool * tm).sum(1) / tm.sum(1)
                    mb = (o_pool * ~tm).sum(1) / (~tm).sum(1)
                perm_stat[key] = np.abs(mt - mb)
    keys = sorted(perm_stat)
    marginal = {k: float((1 + np.sum(perm_stat[k] >= obs_stat[k])) / (B + 1)) for k in keys}
    obs_min = min(marginal.values())
    Q = np.empty((len(keys), B))
    for i, k in enumerate(keys):
        sa = np.sort(perm_stat[k])
        Q[i] = (1 + (B - np.searchsorted(sa, perm_stat[k], side="left"))) / (B + 1)
    fwe_p = float((1 + np.sum(Q.min(axis=0) <= obs_min)) / (B + 1))
    return {
        "_scheme": "COHERENT correction FOR the pre-registered test: perm_diff exchangeable set "
                   "(fixed tertiles, middle EXCLUDED, outcome-label permutation within top∪bottom) "
                   "COUPLED across the 24 tests by a shared within-stratum key. This is the "
                   "multiplicity correction for the pre-registered result.",
        "family_wise_p": round(fwe_p, 4),
        "min_marginal_p": round(obs_min, 4),
        "median_marginal_p": round(float(np.median(list(marginal.values()))), 4),
        "min_test": min(marginal, key=marginal.get),
        "n_tests": len(keys),
        "n_significant_05": int(sum(p < 0.05 for p in marginal.values())),
        "seed": seed, "B": B,
    }


def westfall_young(df: pl.DataFrame, B: int = WY_B, seed: int | None = None) -> dict:
    """POST-HOC joint null (AMENDMENT §A3). dom-shuffle over the whole stratum (middle third
    INCLUDED, tertiles re-derived), shared across the 24 tests -> Westfall-Young family-wise p of
    the family minimum, with per-test marginals. Deterministic given `seed`. NOTE: its marginals
    differ from the pre-registered perm_diff because the exchangeable set differs (middle-third
    inclusion), NOT because of the coupling."""
    seed = CONFIG["models"]["seed"] if seed is None else seed
    rng = np.random.default_rng(seed)
    perm_stat, obs_stat = {}, {}
    for rd, name in STRATA:                                    # fixed order => reproducible RNG use
        s = df.filter(pl.col("draft_round") == rd) if rd else df.filter(pl.col("draft_round") >= 4)
        if s.height < WY_MIN_STRATUM_N:
            continue
        dom = s["dom_best"].to_numpy().astype(float)
        wr = s["position"].to_numpy() == "WR"
        outc = {t: s[t].cast(pl.Float64).to_numpy() for t in TARGETS}
        P = rng.permuted(np.tile(dom, (B, 1)), axis=1)         # shared shuffle for this stratum
        for wr_only in (False, True):
            slice_cols = np.where(wr)[0] if wr_only else np.arange(len(dom))
            if len(slice_cols) < WY_MIN_STRATUM_N:
                continue
            for t in TARGETS:
                # complete-case per target (fwd3_vorp has nulls; hit/top5 do not) — matches
                # perm_diff, which strips NaN before testing. dom is permuted, so validity (an
                # outcome property) stays fixed per player under the shared shuffle.
                o_all = outc[t]
                cols = slice_cols[~np.isnan(o_all[slice_cols])]
                if len(cols) < WY_MIN_STRATUM_N:
                    continue
                d_sub, P_sub, o = dom[cols], P[:, cols], o_all[cols]
                oq1, oq2 = np.quantile(d_sub, 1 / 3), np.quantile(d_sub, 2 / 3)
                o_top, o_bot = d_sub >= oq2, d_sub <= oq1
                pq1 = np.quantile(P_sub, 1 / 3, axis=1)[:, None]
                pq2 = np.quantile(P_sub, 2 / 3, axis=1)[:, None]
                p_top, p_bot = P_sub >= pq2, P_sub <= pq1
                key = f"{'WR' if wr_only else 'ALL'}|{name}|{t}"
                obs_stat[key] = float(_tertile_stat(d_sub, o, o_top, o_bot))
                perm_stat[key] = _tertile_stat(d_sub, o[None, :], p_top, p_bot)
    keys = sorted(perm_stat)
    marginal = {k: float((1 + np.sum(perm_stat[k] >= obs_stat[k])) / (B + 1)) for k in keys}
    obs_min = min(marginal.values())
    # WY single-step minP: null distribution of the family minimum, correlation-aware.
    Q = np.empty((len(keys), B))
    for i, k in enumerate(keys):
        sa = np.sort(perm_stat[k])
        Q[i] = (1 + (B - np.searchsorted(sa, perm_stat[k], side="left"))) / (B + 1)
    min_q_null = Q.min(axis=0)
    fwe_p = float((1 + np.sum(min_q_null <= obs_min)) / (B + 1))
    return {
        "_scheme": "POST-HOC AMENDMENT (§A3): dom-shuffle over the whole stratum (MIDDLE THIRD "
                   "INCLUDED; tertiles RE-DERIVED), shared across the 24 tests. WY single-step "
                   "minP. Marginals differ from the pre-registered perm_diff by the exchangeable "
                   "set (middle-third inclusion), NOT by the coupling.",
        "n_tests": len(keys),
        "n_significant_05": int(sum(p < 0.05 for p in marginal.values())),
        "min_marginal_p": round(obs_min, 4),
        "median_marginal_p": round(float(np.median(list(marginal.values()))), 4),
        "min_test": min(marginal, key=marginal.get),
        "family_wise_p": round(fwe_p, 4),
        "marginal_p": {k: round(v, 4) for k, v in marginal.items()},
        "seed": seed, "B": B, "cohort_n": df.height,
    }


def write_perm_artifact(df: pl.DataFrame | None = None) -> dict:
    """Pin BOTH nulls to models/cfb_5_4b_perm.json (vintage-stamped, byte-reproducible): the
    PRE-REGISTERED test (+ its decision-rule outcome) as primary, and the POST-HOC Westfall-Young
    joint null as secondary. Brings 5.4B into the reproducibility + drift harness."""
    import json

    df = build_cohort() if df is None else df
    pre = pre_registered_marginals(df)
    wy_preg = westfall_young_preg(df)      # correction FOR the pre-registered test (same set)
    wy_dom = westfall_young(df)            # robustness under a DIFFERENT exchangeable set
    frozen = json.loads((CONFIG.path("data_raw") / "nflverse" / "FROZEN.json").read_text())
    art = {
        "_what": "5.4B college-production null — pinned. PRIMARY = pre-registered decision rule + "
                 "its coherent Westfall-Young family-wise correction (perm_diff exchangeable set). "
                 "SECONDARY = dom-shuffle joint null under a DIFFERENT exchangeable set (§A3) — a "
                 "robustness check, NOT the correction for the pre-registered test.",
        "vintage": frozen["vintage"],
        "nflverse_input_signature": frozen.get("input_signature_2013_2025"),
        "seed": CONFIG["models"]["seed"], "B": WY_B, "cohort_n": df.height,
        "pre_registered": pre,
        "westfall_young_pre_reg_set": wy_preg,
        "westfall_young_domshuffle_set": wy_dom,
    }
    out = CONFIG.path("models") / "cfb_5_4b_perm.json"
    out.write_text(json.dumps(art, indent=2, sort_keys=True))
    log.info("pinned 5.4B permutation artifact -> %s", out)
    return art


def run() -> None:
    df = build_cohort()
    log.info("5.4B cohort (college-matched): %d players", df.height)
    art = write_perm_artifact(df)
    pre = art["pre_registered"]
    wyp, wyd = art["westfall_young_pre_reg_set"], art["westfall_young_domshuffle_set"]

    print("=== 5.4B college-production lift — PRIMARY: pre-registered decision rule ===")
    print(f"college-matched cohort n={df.height}")
    print(f"  rule: {pre['decision_rule']}")
    print(f"  RESULT: {pre['n_ceiling_strata_significant']}/3 non-R1 strata significant "
          f"{pre['strata_significant']} -> rule_met={pre['rule_met']} "
          f"(need >=2) => draft capital is not improved on")
    print(f"  pre-reg marginals (perm_diff): {pre['n_significant_05']}/{pre['n_tests']} p<0.05, "
          f"min {pre['min_marginal_p']}, median {pre['median_marginal_p']}")
    print(f"  coherent Westfall-Young family-wise p FOR the pre-registered test "
          f"(same exchangeable set) = {wyp['family_wise_p']}  <-- the correction for the primary")

    print("\n=== SECONDARY: dom-shuffle joint null under a DIFFERENT exchangeable set (§A3) ===")
    print(f"  robustness only (NOT the correction for the pre-reg test): family-wise p "
          f"{wyd['family_wise_p']}, min marginal {wyd['min_marginal_p']} ({wyd['min_test']}), "
          f"median {wyd['median_marginal_p']}")
    print(f"  pinned -> models/cfb_5_4b_perm.json  (vintage {art['vintage']}, seed {art['seed']}, "
          f"B {art['B']})")


if __name__ == "__main__":
    run()
