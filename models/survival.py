"""Phase 5.2 — Career survival, two clocks (rebuilt after gate review).

CLOCK A — time since DRAFT: P(relevant in year N | drafted at slot). This is the
  pick-valuation quantity — the buyer owns the whole future stream from draft, so a
  slow-developing TE relevant in years 3-7 must be credited in those years, not
  scored as an early exit. Per-year empirical rate, censoring-correct (year-N
  denominator only includes players with N observed seasons), Wilson 95% CI.
CLOCK B — time since FIRST RELEVANT: KM career persistence conditional on breaking
  out (median/P25/P75, Greenwood CI). This is the decline-shape view, conditioning-
  matched to the 5.1 aging curve (both conditional on being an established player).

Relevance = played >= min_games at >= that season's positional REPLACEMENT PPG.
Active-in-latest players right-censored. Cohort: NFL draft classes 2010+.
Stratified by position, NFL draft round, AND age-at-entry. Era split: 2010-2016 vs 2017+.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import duckdb
import polars as pl
from lifelines import KaplanMeierFitter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CONFIG
from ingest._common import get_logger

log = get_logger("survival")
MIN_GAMES = CONFIG["models"]["relevance"]["min_games"]
EXPORTS = CONFIG.path("exports")


def _wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    if n == 0:
        return (float("nan"),) * 3
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, c - h), min(1.0, c + h)


def _panel():
    con = duckdb.connect(str(CONFIG.path("warehouse")), read_only=True)
    repl = con.execute("""SELECT season, position, avg(replacement_points) repl_ppg
                          FROM fact_replacement WHERE profile='ppr' GROUP BY season, position""").pl()
    s = con.execute("""SELECT s.player_uid, s.season, s.position, s.games, s.ppg_ppr,
                              d.draft_year, d.draft_round, d.birthdate
                       FROM fact_player_season s JOIN dim_player d USING(player_uid)
                       WHERE s.position IN ('QB','RB','WR','TE')""").pl()
    con.close()
    latest = int(s["season"].max())
    df = s.join(repl, on=["season", "position"], how="left").with_columns(
        pl.col("draft_year").cast(pl.Int32, strict=False),
        pl.col("draft_round").fill_null("UDFA"))
    df = df.filter(pl.col("draft_year") >= 2010).with_columns([
        ((pl.col("games") >= MIN_GAMES) & (pl.col("ppg_ppr") >= pl.col("repl_ppg"))).alias("relevant"),
        (pl.col("season") - pl.col("draft_year") + 1).alias("yr_since_draft"),
        (pl.col("draft_year") - pl.col("birthdate").str.slice(0, 4).cast(pl.Int32)).alias("age_entry")])
    df = df.with_columns([
        pl.when(pl.col("draft_round") == "1").then(pl.lit("R1"))
          .when(pl.col("draft_round") == "2").then(pl.lit("R2"))
          .when(pl.col("draft_round") == "3").then(pl.lit("R3"))
          .when(pl.col("draft_round").is_in(["4", "5", "6", "7"])).then(pl.lit("R4-7"))
          .otherwise(pl.lit("UDFA")).alias("round_grp"),
        pl.when(pl.col("age_entry") <= 21).then(pl.lit("≤21"))
          .when(pl.col("age_entry") == 22).then(pl.lit("22"))
          .when(pl.col("age_entry") == 23).then(pl.lit("23"))
          .otherwise(pl.lit("≥24")).alias("age_grp"),
        pl.when(pl.col("draft_year") <= 2016).then(pl.lit("2010-16")).otherwise(pl.lit("2017+")).alias("era")])
    return df, latest


# ---- CLOCK A: per-year P(relevant in year N since draft) --------------------
def clock_a(df: pl.DataFrame, latest: int, group_cols: list[str], maxN=8) -> list[dict]:
    # one row per player with entry + which yr_since_draft they were relevant in
    players = df.group_by(["player_uid"] + group_cols).agg(
        pl.col("draft_year").min().alias("entry"),
        pl.col("yr_since_draft").filter(pl.col("relevant")).alias("rel_years"))
    out = []
    for key, sub in players.group_by(group_cols):
        keyd = dict(zip(group_cols, key if isinstance(key, tuple) else (key,)))
        for N in range(1, maxN + 1):
            elig = sub.filter(pl.col("entry") <= latest - N + 1)   # observed N years
            n = elig.height
            if n < 15:
                continue
            k = elig.filter(pl.col("rel_years").list.contains(N)).height
            p, lo, hi = _wilson(k, n)
            out.append({**keyd, "N": N, "n": n, "k": k,
                        "p_relevant": round(p, 3), "ci_lo": round(lo, 3), "ci_hi": round(hi, 3)})
    return out


# ---- CLOCK B: KM career persistence since first relevant --------------------
def clock_b(df: pl.DataFrame, latest: int, group_cols: list[str]) -> list[dict]:
    rel = df.filter(pl.col("relevant")).group_by(["player_uid"] + group_cols).agg(
        pl.col("season").min().alias("first_rel"), pl.col("season").max().alias("last_rel"))
    rel = rel.with_columns([
        (pl.col("last_rel") - pl.col("first_rel") + 1).alias("dur"),
        (pl.col("last_rel") < latest).cast(pl.Int8).alias("event")])   # censored if relevant in latest
    kmf = KaplanMeierFitter()
    out = []
    for key, sub in rel.group_by(group_cols):
        keyd = dict(zip(group_cols, key if isinstance(key, tuple) else (key,)))
        if sub.height < 15:
            continue
        kmf.fit(sub["dur"].to_numpy(), sub["event"].to_numpy())
        med = kmf.median_survival_time_
        from lifelines.utils import median_survival_times
        ci = median_survival_times(kmf.confidence_interval_)
        row = {**keyd, "n": sub.height, "events": int(sub["event"].sum()),
               "median": None if med != med else float(med),
               "median_ci": [round(float(ci.iloc[0, 0]), 1), round(float(ci.iloc[0, 1]), 1)]}
        for N in (3, 5):
            row[f"S{N}"] = round(float(kmf.survival_function_at_times([N]).iloc[0]), 3)
            cifs = kmf.confidence_interval_survival_function_
            idx = cifs.index[cifs.index <= N]
            if len(idx):
                r = cifs.loc[idx[-1]]
                row[f"S{N}_ci"] = [round(float(r.iloc[0]), 3), round(float(r.iloc[1]), 3)]
        out.append(row)
    return out


def build() -> None:
    df, latest = _panel()
    log.info("panel: %d player-seasons, latest completed=%d", df.height, latest)

    a_round = clock_a(df, latest, ["position", "round_grp"])
    a_age = clock_a(df, latest, ["position", "age_grp"])
    b_round = clock_b(df, latest, ["position", "round_grp"])
    # era stability on clock A (RB·R1 focus) and clock B
    a_era = clock_a(df.filter(pl.col("position") == "RB"), latest, ["round_grp", "era"])
    b_era = clock_b(df, latest, ["position", "round_grp", "era"])

    # determinism: clock_a/clock_b append rows in nondeterministic group-iteration order — sort by
    # key before writing so the parquet bytes are reproducible (values were already deterministic).
    a_round = sorted(a_round, key=lambda r: (r["position"], r["round_grp"], r["N"]))
    b_round = sorted(b_round, key=lambda r: (r["position"], r["round_grp"]))
    pl.DataFrame(a_round).write_parquet(CONFIG.path("models") / "survival_clockA.parquet")
    pl.DataFrame(b_round).write_parquet(CONFIG.path("models") / "survival_clockB.parquet")
    _write_md(a_round, a_age, b_round, a_era, b_era, latest)
    log.info("survival curves -> %s", EXPORTS / "hit_rates_by_slot.md")


def _fmt_a(rows, keyfn) -> list[str]:
    d = {}
    for r in rows:
        d.setdefault(keyfn(r), {})[r["N"]] = r
    lines = []
    for k in sorted(d):
        cells = []
        for N in range(1, 9):
            r = d[k].get(N)
            cells.append(f"{r['p_relevant']:.2f}[{r['ci_lo']:.2f},{r['ci_hi']:.2f}](n{r['n']})" if r else "—")
        lines.append(f"| {k} | " + " | ".join(cells) + " |")
    return lines


def _write_md(a_round, a_age, b_round, a_era, b_era, latest) -> None:
    L = [f"# Career Survival — Phase 5.2 (two clocks). Latest completed season {latest}.", "",
         "Relevance = ≥%d games at ≥ season replacement PPG. Cohort: NFL drafts 2010+." % MIN_GAMES,
         "",
         "## CLOCK A — P(relevant in year N SINCE DRAFT)  ← use this for pick valuation",
         "Per-year rate (Wilson 95% CI, n = players with N observed years). Credits slow "
         "developers in the years they produce. Format: p[lo,hi](n).", "",
         "| position·round | y1 | y2 | y3 | y4 | y5 | y6 | y7 | y8 |",
         "|---|" + "---|" * 8]
    L += _fmt_a(a_round, lambda r: f"{r['position']}·{r['round_grp']}")
    L += ["", "### Clock A by AGE-AT-ENTRY (per-year relevance)", "",
          "| position·age@entry | y1 | y2 | y3 | y4 | y5 | y6 | y7 | y8 |", "|---|" + "---|" * 8]
    L += _fmt_a(a_age, lambda r: f"{r['position']}·{r['age_grp']}")

    L += ["", "## CLOCK B — career persistence SINCE FIRST RELEVANT (KM, conditioning-matched to 5.1 aging)",
          "median/P25-P75 in relevant years once established; Greenwood CI.", "",
          "| position·round | n | events | median [95% CI] | S3 [CI] | S5 [CI] |", "|---|--:|--:|--:|--:|--:|"]
    for r in sorted(b_round, key=lambda x: (x["position"], x["round_grp"])):
        med = f"{r['median']:.1f} {r['median_ci']}" if r["median"] is not None else "—"
        L.append(f"| {r['position']}·{r['round_grp']} | {r['n']} | {r['events']} | {med} | "
                 f"{r.get('S3','—')} {r.get('S3_ci','')} | {r.get('S5','—')} {r.get('S5_ci','')} |")

    L += ["", "## ERA STABILITY (2010-16 vs 2017+)", "",
          "### RB by round — Clock A per-year relevance", "",
          "| round·era | y1 | y2 | y3 | y4 | y5 | y6 | y7 | y8 |", "|---|" + "---|" * 8]
    L += _fmt_a(a_era, lambda r: f"{r['round_grp']}·{r['era']}")
    L += ["", "### Clock B career persistence by era (key strata)", "",
          "| position·round·era | n | events | median [CI] | S3 [CI] |", "|---|--:|--:|--:|--:|"]
    for r in sorted(b_era, key=lambda x: (x["position"], x["round_grp"], x["era"])):
        if r["position"] in ("RB", "WR") and r["round_grp"] in ("R1", "R2"):
            med = f"{r['median']:.1f} {r['median_ci']}" if r["median"] is not None else "—"
            L.append(f"| {r['position']}·{r['round_grp']}·{r['era']} | {r['n']} | {r['events']} | "
                     f"{med} | {r.get('S3','—')} {r.get('S3_ci','')} |")
    EXPORTS.mkdir(parents=True, exist_ok=True)
    (EXPORTS / "hit_rates_by_slot.md").write_text("\n".join(L))


if __name__ == "__main__":
    build()
