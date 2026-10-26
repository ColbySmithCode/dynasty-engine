"""GATE 1 / 1G reporting — reads the ingest ledger + staging parquets and prints
row counts per source per season, the ADP sweep sample-size matrix, and the
dynasty-corpus settings distribution (with format-skew flags).
"""
from __future__ import annotations

import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CONFIG
from ingest._common import read_ledger

pl.Config.set_tbl_rows(60)
pl.Config.set_tbl_cols(30)
STG = CONFIG.path("data_staging")


def nflverse_coverage() -> None:
    led = [r for r in read_ledger() if r["source"] == "nflverse"]
    if not led:
        print("no nflverse ledger rows"); return
    df = pl.DataFrame(led)
    # keep latest record per (dataset, season)
    df = (df.sort("ts").group_by(["dataset", "season"], maintain_order=True).last())
    print("\n===== 1A nflverse — rows per dataset per season =====")
    season_scoped = df.filter(pl.col("season") != "all")
    if season_scoped.height:
        piv = (season_scoped
               .with_columns(pl.col("season").cast(pl.Int64, strict=False))
               .pivot(values="rows", index="dataset", on="season", aggregate_function="first")
               .sort("dataset"))
        print(piv)
    print("\nseason-less datasets:")
    print(df.filter(pl.col("season") == "all").select("dataset", "rows", "status").sort("dataset"))
    fails = df.filter(pl.col("status") == "fail")
    if fails.height:
        print("\n⚠️  FAILURES (non-empty = investigate):")
        print(fails.select("dataset", "season", "note"))
    # anomaly flags: modern pbp season with < 40k rows, or 0 rows where data expected
    pbp = df.filter((pl.col("dataset") == "pbp"))
    print("\nanomaly flags:")
    for r in pbp.iter_rows(named=True):
        try:
            s = int(r["season"])
        except (TypeError, ValueError):
            continue
        if s <= 2024 and r["rows"] < 40000:
            print(f"  ⚠️ pbp {s}: only {r['rows']} rows (<40k) — check coverage")
        if s == 2025 and r["rows"] < 40000:
            print(f"  ⚠️ pbp 2025: {r['rows']} rows — likely mid/late-season partial")


LOW_CONF = 500   # cells under this many drafts quietly poison ADP calibration


def adp_matrix() -> None:
    p = STG / "mfl_adp_matrix.parquet"
    if not p.exists():
        print("\n(MFL sweep parquet not written yet)"); return
    df = pl.read_parquet(p)
    ren = {"N": "redraft(N)", "K": "dynasty/keeper(K)", "R": "rookie(R)"}
    # per-cell confidence tier
    df = df.with_columns(
        pl.when(pl.col("total_drafts") == 0).then(pl.lit("EMPTY"))
          .when(pl.col("total_drafts") < LOW_CONF).then(pl.lit("LOW"))
          .otherwise(pl.lit("OK")).alias("confidence"))
    print("\n===== 1B/1G-a MFL ADP sweep — draft counts PER CELL =====")
    print(f"cells fetched: {df.height} | seasons {df['season'].min()}-{df['season'].max()} "
          f"| formats {sorted(df['format'].unique().to_list())} "
          f"| ppr {sorted(df['ppr'].unique().to_list())} "
          f"| fcount {sorted(df['fcount'].unique().to_list())} "
          f"| periods {sorted(df['period'].unique().to_list())}")

    # full per-cell export — nothing hidden
    exp = CONFIG.path("exports") / "adp_sweep_cells.csv"
    df.sort(["season", "format", "ppr", "period"]).write_csv(exp)
    print(f"full per-cell matrix ({df.height} rows) -> {exp}")

    # confidence census
    cen = df.group_by("confidence").agg(pl.len().alias("cells")).sort("confidence")
    print("\nconfidence census (threshold <%d drafts = LOW):" % LOW_CONF)
    print(cen)

    # per-cell counts, dynasty & rookie (the load-bearing, thin ones): season x period @ppr-1
    for fmt in ("K", "R"):
        sub = df.filter((pl.col("format") == fmt) & (pl.col("ppr") == -1))
        piv = (sub.pivot(values="total_drafts", index="season", on="period",
                         aggregate_function="first").sort("season"))
        print(f"\n{ren[fmt]} draft counts per cell (ppr=-1, fcount=12), season x period:")
        print(piv)

    # season x format headline (max across ppr/period)
    m = (df.group_by(["season", "format"]).agg(pl.col("total_drafts").max().alias("drafts"))
           .pivot(values="drafts", index="season", on="format", aggregate_function="first")
           .sort("season").rename({k: v for k, v in ren.items()}))
    print("\nmax drafts per (season x format) [best-populated cell]:")
    print(m)

    # data-support summary
    print("\ndata-support per format (first season reaching each tier):")
    for fmt, label in ren.items():
        f_ok = df.filter((pl.col("format") == fmt) & (pl.col("total_drafts") >= LOW_CONF))
        first_ok = f_ok["season"].min() if f_ok.height else None
        peak = df.filter(pl.col("format") == fmt)["total_drafts"].max()
        print(f"  {label:20s} first season >= {LOW_CONF} drafts: {first_ok} | peak cell: {peak}")

    # explicit low-confidence cell list (0 < drafts < 500) — the ones to distrust
    low = (df.filter(pl.col("confidence") == "LOW")
             .select("season", "format", "ppr", "period", "total_drafts")
             .sort(["format", "season", "period"]))
    empty = df.filter(pl.col("confidence") == "EMPTY").height
    print(f"\n⚠️ LOW-confidence cells (1-{LOW_CONF-1} drafts): {low.height} "
          f"| EMPTY cells (0 drafts): {empty}")
    print("   → calibration/backtest must down-weight or exclude LOW/EMPTY cells.")
    print("   sample of LOW cells:")
    print(low.head(20))


def corpus_distribution() -> None:
    print("\n===== 1G-b/c Dynasty Market Corpus =====")
    sfb_p = STG / "sfb_sleeper_leagues.parquet"
    if sfb_p.exists():
        sfb = pl.read_parquet(sfb_p)
        print(f"\n1G-b SFB Sleeper: {sfb.height} leagues, {int(sfb['n_picks'].sum())} draft picks "
              f"(~{int(sfb['n_picks'].sum()/22) if sfb['n_picks'].sum() else 0} team-drafts)")
        print("  by repo:")
        print(sfb.group_by("repo").agg(pl.len().alias("leagues"),
              pl.col("n_picks").sum().alias("picks")).sort("repo"))
        print("  league type distribution (0=redraft/best-ball, 2=dynasty):")
        print(sfb.group_by("type").agg(pl.len().alias("n")).sort("type"))
    else:
        print("\n1G-b SFB parquet not written yet")

    sc_p = STG / "sleeper_corpus_leagues.parquet"
    if sc_p.exists():
        sc = pl.read_parquet(sc_p)
        print(f"\n1G-c Sleeper snowball: {sc.height} dynasty leagues")
        print(f"  seasons covered: {sorted(sc['season'].unique().to_list())}")
        print(f"  total draft picks: {int(sc['n_draft_picks'].sum())} | "
              f"traded picks: {int(sc['n_traded_picks'].sum())}")
        txt = sc.filter(pl.col('n_transactions').is_not_null())
        if txt.height:
            print(f"  transactions (sampled {txt.height} leagues): {int(txt['n_transactions'].sum())}")
        print("\n  SETTINGS DISTRIBUTION (format skew — biases downstream):")
        print("   superflex:"); print(sc.group_by("superflex").agg(pl.len().alias("n")).sort("superflex"))
        print("   league size:"); print(sc.group_by("size").agg(pl.len().alias("n")).sort("size"))
        print("   ppr (rec pts):"); print(sc.group_by("ppr").agg(pl.len().alias("n")).sort("ppr"))
        print("   te premium (bonus_rec_te):")
        print(sc.group_by("te_prem").agg(pl.len().alias("n")).sort("te_prem"))
        # skew verdict vs YOUR league (superflex, full-PPR, size 12, NO te premium)
        n = sc.height
        sf = sc.filter(pl.col("superflex")).height
        ppr1 = sc.filter(pl.col("ppr") == 1.0).height
        sz12 = sc.filter(pl.col("size") == 12).height
        te = sc.filter(pl.col("te_prem").fill_null(0.0) > 0).height
        print("\n  ⚠️ SKEW vs YOUR league (superflex / full-PPR / 12-team / NO TE-prem):")
        print(f"     superflex : {sf}/{n} ({100*sf//n}%)  -> MATCHES your league; 1QB thin ({n-sf})")
        print(f"     full PPR  : {ppr1}/{n} ({100*ppr1//n}%)  -> MATCHES your league")
        print(f"     12-team   : {sz12}/{n} ({100*sz12//n}%)  -> MATCHES your league")
        print(f"     TE premium: {te}/{n} ({100*te//n}%)  -> MISMATCH (yours has none): "
              f"corpus over-values TEs; down-weight/reweight before applying to your league")
    else:
        print("\n1G-c snowball parquet not written yet")


if __name__ == "__main__":
    nflverse_coverage()
    adp_matrix()
    corpus_distribution()
