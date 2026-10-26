# Addendum A — Dynasty Market Corpus (Phase 1G)

> Written for future sessions. Read this before touching corpus ingestion.

## Why this exists
The target league is a **brand-new, first-year startup dynasty league**. There is
**no league history**: Sleeper's `previous_league_id` chain returns nothing, and
there are zero prior transactions, drafts, or matchups to learn league-mate
tendencies from. Building league-specific priors against our own history is
impossible for year one.

**The fix:** learn from *other people's* dynasty history. Assemble a corpus of
publicly available dynasty drafts, ADP, and league behavior that stands in for the
15 years of history we don't have. This corpus is what powers draft-behavior
modeling, ADP calibration, and pick valuation until our own league accumulates
data.

## The four sub-sources (in order of load-bearing weight)

### 1G-a — MFL aggregate ADP/AAV  ★ load-bearing
Already produced by the Phase 1B sweep. The MFL `TYPE=adp` report is **aggregated
across thousands of real leagues** and goes back to **1999**. Two filters carry
the dynasty signal:
- `IS_KEEPER=1` → **dynasty / keeper / startup** ADP
- `IS_KEEPER=2` → **rookie-only** draft ADP
- `IS_KEEPER=0` → redraft (baseline / contrast)

This is *better* than any single league's history because it is already averaged
over league-level noise — it's a time series of **consensus opinion**, which is
exactly what answers "when did the market figure this guy out?" The sweep must
retain **all three formats**; do not silently collapse to redraft.
Sample size per cell = MFL's reported draft count for that (year, format, ppr,
size, period). Early years for rookie-only/dynasty will be thin — that thinness is
a reported result, not a bug.

### 1G-b — Scott Fish Bowl public datasets  (draft-behavior modeling)
Charity best-ball tournaments with **thousands of teams** and full draft results,
**publicly released for research** on GitHub under the `dynastyprocess` org
(`data.sfb14`, `data-sfb13`, and siblings). No scraping — just fetch the raw files.

> **CORRECTION (see Addendum B, Decision 4):** SFB is **best-ball redraft**, a
> different objective function from a dynasty startup. It is **demoted** to
> *supplementary draft-flow mechanics only* and **must not inform dynasty startup
> strategy/valuations**. All dynasty draft behavior (incl. the ADP-deviation noise
> model) comes from the **400-league snowball corpus (1G-c)**, not SFB.

### 1G-c — Sleeper public leagues  (scoped snowball)
Any `league_id` is fetchable without auth; chains backward via
`previous_league_id`. Snowball discovery:
```
league  →  /league/{id}/users  →  /user/{uid}/leagues/nfl/{season}
```
**Two hard limits, both enforced in config:**
1. Sleeper launched ~2017–18, so realistic depth is **~7 seasons**, not 15.
2. Sample a few **hundred** leagues, not tens of thousands. Marginal value of
   league #5000 is zero. `corpus.sleeper_snowball.max_leagues` caps it (400).
Rate-limit **well under 1000 req/min**, cache everything, send a real
User-Agent. Keep dynasty leagues (`settings.type == 2`).

### 1G-d — MFL per-league harvest  ✗ FORBIDDEN
Do **not** mass-harvest individual MFL leagues. MFL's own docs state most API
functionality is **current-year only**, and their acceptable-use terms **prohibit
collecting user information without permission**. Use MFL for the **aggregate
ADP/AAV reports only** — that is the intended public product and it works well.
Config guard: `corpus.mfl_per_league_harvest: forbidden`.

## GATE 1G reporting contract
Report, and flag skew:
- corpus size: # leagues, # seasons, # drafts, # transactions
- distribution of league settings (format, size, PPR, superflex, TE-premium)
- **format skew** will exist (redraft dominates MFL volume; SFB is TE-premium
  best-ball; Sleeper snowball over-represents recent seasons) and it biases
  everything downstream — call it out explicitly so calibration can correct for it.
