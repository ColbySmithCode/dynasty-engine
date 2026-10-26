# Pre-registration v2 — Market calculator vs engine on rookie picks, engine leg scorable (LOCKED before any new data)

Written 2026-10-16, **before** any pre-2020 rookie ADP has been pulled, opened, or loaded, and before any
v2 number has been computed. Run under the rules below; deviations go in dated amendments at the bottom,
never by editing this text.

## Relation to v1 (append-only)
v1 = `exports/prereg_market_vs_engine.md` (+ amendments A1–A7) and its result
`exports/prereg_market_vs_engine_result.txt` (commit `50b80c6`). **v1 and its result stay on record
unchanged.** v2 does not supersede, re-score, or reinterpret v1. v1's engine leg was NOT ESTIMABLE because
the engine's rookie pool starts in 2020 and the leak rule leaves 0–14 comparables per pick cell; v2 exists
only to make that leg scorable by backfilling pre-2020 rookie classes.

## Carried from v1 unchanged
- **Hypothesis H1:** rookie picks underdeliver realized VORP relative to veterans of equal market value.
- **Data:** DynastyProcess `files/values.csv` at the same three commits, and only these:
  2021 `5faea36` (2021-07-30), 2022 `f8689a5` (2022-07-29), 2023 `eb9cb5c` (2023-07-28). No snapshots added.
- **Picks / matching / realization:** v1 rules + A1–A6 verbatim (D ∈ {S+1, S+2}, rounds 1–4, half-open
  ADP slot ranges, k = 5 nearest veterans in `value_2qb` within ±15%, ≥ 3 required, veteran = DP
  `draft_year < S`, `fp_id` identity join). **Ties broken by `player_uid` ascending (A7).**
- **Realized value:** `vorp_ppr_total`, missing season = 0, h = 6, δ = 0.82, both the extrapolated
  (0.85 canon decay past 2025) and observed-only reads. **No floor: negative VORP stays negative.**
  The floored read is NOT part of v2.
- **Uncertainty on realized Δ:** player-resampling bootstrap, 2000 resamples, seed 1729 (v1 method).
- **Pass/fail thresholds (v1, unchanged, author-supplied / PROVISIONAL as v1 states):** UNDERPOWERED iff
  CI half-width > 25 in either read (checked first); SUPPORTED iff Δ ≤ −25, CI upper < 0, both reads,
  Δ < 0 in every draft class with ≥ 10 rows; else NOT SUPPORTED.
- **Engine "predicts better"** iff MAE_engine < MAE_market with a paired-bootstrap 95% CI on
  (MAE_market − MAE_engine) excluding 0, in **both** pools.
- **Comparable requirement:** an engine cell with **n < 20** leak-free comparables is NOT ESTIMABLE.
  The threshold is not lowered for any reason.

## New in v2 — the backfill
- **Source:** MFL aggregate ADP, rookie-only format, identical request parameters to the existing
  `fact_adp` rookie rows (`ingest/mfl_adp.py::fetch_cell`: `TYPE=adp`, `IS_KEEPER=R`, `IS_PPR`,
  `FCOUNT=12`, `PERIOD`, `IS_MOCK=-1`, `CUTOFF=5`, `DETAILS=1`). ("IS_KEEPER=2" in the request is the
  legacy numeric code for rookie-only; the current API rejects numeric codes and the existing rows were
  pulled with `R`.) Target classes: every season before 2020 the API serves, 2012–2019 at minimum.
- **Write rule:** new `fact_adp` rows only. No existing row is modified or deleted. Raw responses go to a
  separate directory; existing cached cells are not overwritten.
- **Stop rule:** if MFL has no usable rookie ADP for those classes, v2 stops and says so. No other ADP
  source is substituted without Colby's approval.
- **Validation (before v2 runs):** re-pull one class already in the warehouse (2020 or 2021) with the
  same code; it must match the stored rows exactly. Differences are reported, not reconciled silently.

## New in v2 — engine leg, specified here because v1 left it open
- **Engine rookie pool:** the engine's own definition (`engine/trade_gw_kcc.pools()`: `fact_adp` R,
  ppr −1, period DRAFT, inner-joined to forward VORP) with its `season >= 2020` floor removed so the
  backfilled classes enter. Nothing else about the pool changes.
- **Leak rule (unchanged meaning):** a comparable row of season c is admissible for snapshot S iff all
  three of its forward seasons finished before the snapshot date: **c + 2 < S**.
- **Pick price:** `trade_gw_kcc.value()` on the leak-free rookie comparables in the pick's slot range
  (same half-open ranges as the realization side), start_year = D − S + 1, extra = 0.92^(D−S), jitter 15.
- **Veteran price:** slot = the veteran's MFL K-format ADP (ppr −1, f12, period **JULY** of season S, the
  last period before the late-July snapshot). Band = [floor(0.8·ADP), ceil(1.2·ADP)], restricted to his
  position (the ~±20% trade-script convention; **author-supplied / PROVISIONAL**). Comparables come from
  the pool under test with c + 2 < S, start_year = 1. A veteran with no JULY K-ADP row is unpriceable
  (no substitute read).
- **Pools:** consensus (`fact_adp` K AUG15, engine definition incl. its `season >= 2019` floor) and
  corpus (frozen startup corpus), reported separately, never blended. **v2 backfills only the rookie
  pool**, so the startup pools' leak-free sizes are what they are; prior run showed consensus 0 / 271 /
  527 and corpus 0 / 0 / 16524 rows before banding for S = 2021 / 2022 / 2023.
- **Row scorability:** a pick row is engine-scorable in a pool iff its pick cell has n ≥ 20 AND every
  matched veteran is priceable with a band n ≥ 20 in that pool. MAE comparisons use scorable rows only,
  with the market MAE computed on the same rows. Per-snapshot scorable counts are reported. A pool with
  zero scorable rows is NOT ESTIMABLE.
- **Engine prediction per row:** Δ_eng = E[pick price] − mean over matched veterans of E[veteran price],
  each E[·] the mean over the 200-seed run (seeds 1–200), with the 200-seed MC precision band reported
  per standing format.

## Reproducibility
v2 runs three times; the outputs must be byte-identical (hash printed). If not, stop and report.

## Decision authority (STILL-COLBY)
The builder does **not** make the PASS/FAIL call or the engine-vs-market call. The output prints what
each locked rule evaluates to, marked **AWAITING COLBY**, and stops.

## AMENDMENTS

### 2026-10-16 — B1, backfill STOP RULE triggered; v2 not run
Live pull with `ingest/mfl_rookie_backfill.py` (same request as `fetch_cell`; raw under
`data/raw/mfl_rookie_backfill/2026-10-16/`), `IS_KEEPER=R`, `IS_PPR=-1`, `FCOUNT=12`, `CUTOFF=5`,
all five sweep periods, classes 2005–2021. Players / total drafts per cell:

    class             DRAFT              JUNE              JULY              AUG1             AUG15
     2005-2010   0p/    0d in every period
     2011     0p/    0d      0p/    0d      0p/    0d      0p/    0d      0p/    3d
     2012     0p/    0d      0p/    0d      0p/    0d      0p/    0d      0p/    4d
     2013     0p/    0d      0p/    0d      0p/    0d      0p/    0d     85p/   14d
     2014     0p/    0d      0p/    0d      0p/    0d      0p/    0d     74p/   11d
     2015     0p/    0d      0p/    0d      0p/    0d      0p/    0d      0p/    3d
     2016     0p/    0d      0p/    0d      0p/    0d      0p/    0d      0p/    1d
     2017     0p/    0d      0p/    0d      0p/    0d      0p/    0d      0p/    0d
     2018     0p/    0d      0p/    0d      0p/    0d      0p/    0d      0p/    0d
     2019    65p/   10d      0p/    2d      0p/    0d      0p/    0d      0p/    0d
     2020   124p/ 1990d    123p/  695d    124p/  442d    131p/  280d    133p/  192d
     2021   129p/ 2002d    124p/  743d    125p/  453d    125p/  247d    126p/  155d

Identical to the original sweep cache (2026-07-27). Numeric `IS_KEEPER=2` returns
"Invalid value for IS_KEEPER". The engine pool's period (DRAFT) is empty for every class before 2019;
2019 has 10 drafts. **MFL has no usable pre-2020 rookie-only ADP → stop rule.** No `fact_adp` row was
added, so validation (step 3) and the v2 run (step 4) were not performed. No alternative ADP source was
pulled; that choice is Colby's. v1 and its result are unchanged.

### 2026-10-16T14:58:21Z — B2, CLOSED: NOT ESTIMABLE — result label **UNINFORMATIVE** (STILL-COLBY authorization)
**Status: CLOSED. Result: UNINFORMATIVE.** This label travels with every citation of the market-vs-engine
test (v1 and v2). The test neither supports nor refutes H1 as an engine-vs-market comparison, and the v1
realized-Δ figures must not be cited as evidence that the market or the engine predicts rookie-pick value
better. Closed on Colby's explicit authorization (2026-10-16); the builder made no PASS/FAIL call.
- **Why NOT ESTIMABLE.** MFL has no usable pre-2020 rookie-only ADP (B1: the DRAFT period is empty for
  every class 2005–2018; 2019 has 10 drafts). The engine's rookie pool therefore starts in 2020, and
  under the leak rule (c + 2 < S) no locked snapshot reaches n ≥ 20 in any pick cell.
- **A complete rookie backfill would not have rescued it.** The leak-free startup pools are 0 for
  S = 2021 (consensus 0, corpus 0) and the corpus pool is 0 for S = 2022, so the veteran side of those
  snapshots is NOT ESTIMABLE independent of any rookie data.
- **Data-limited by the engine's 2020 start.** Revisit once enough 2020+ seasons have finished. Because
  the leak rule is relative to each snapshot, the three locked snapshots (2021–2023) can never become
  estimable; a revisit means **later snapshots under a new pre-registration**. Projection at current
  per-class rates (engine rookie pool 2020–2025, not a computed result): whole-round cells reach n ≥ 20
  after 2–3 classes; the thinnest third-of-round cells (Early 1st 2.83/class, Mid 2nd 2.67/class) need
  ~8 classes (2020–2027), i.e. snapshots S ≥ 2030.
- **IS_KEEPER code.** `IS_KEEPER=2` is a legacy numeric code that the live MFL API rejects
  ("Invalid value for IS_KEEPER"). The existing `fact_adp` rookie rows were pulled with `IS_KEEPER=R`.
- **No other ADP source was pulled** (per Colby). Thresholds, matching, and the no-floor rule unchanged.
