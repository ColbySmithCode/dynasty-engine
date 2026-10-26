# Pre-registration — Market calculator vs engine on rookie picks (LOCKED before any data pull)

Written 2026-10-16, **before** any historical DynastyProcess value has been downloaded, opened, or
matched, and before any realized-VORP comparison has been computed. Run **once** on the data defined
below; any deviation is recorded as a dated amendment at the bottom, never by editing this text.

## Hypothesis
**H1: Rookie picks underdeliver realized VORP relative to veterans of equal market value.**
H0: at equal DynastyProcess superflex value, picks and veterans deliver the same realized VORP.

Companion question (the reason for the test): does the **market calculator** or the **engine**
better predict realized value for rookie picks? Under the market, equal value ⇒ predicted
pick − veteran difference = 0. Under the engine, the predicted difference is the engine's
comparable-slot price of the pick minus that of the matched veterans.

## Data (fixed in advance)
- **Market values:** DynastyProcess `values-players.csv` + `values-picks.csv`, column `value_2qb`
  (superflex), as archived — first source: the git history of `dynastyprocess/data` (`files/`),
  which is what `ingest/dynastyprocess.py` pulls from. No other source (KTC, FantasyCalc, ADP-as-value)
  may be substituted. **If no archived 2021–2023 version containing both files with `value_2qb`
  exists, the test STOPS and is reported as not runnable.**
- **Snapshots:** one per season S ∈ {2021, 2022, 2023}: the archived version nearest to **Aug 1 of S**
  (pre-season, after that year's NFL draft — so the picks file holds only future-year picks).
  Nearest = latest commit on or before Aug 1; if none within 30 days before, earliest within 30 days after.
- **Picks:** every row of `values-picks.csv` for draft years D ∈ {S+1, S+2}. (D=S+3 excluded: realized
  seasons would be ≤1 even for S=2021.) Generic labels map to rookie-ADP slot ranges:
  `1st`/`2nd`/`3rd`/`4th` unknown → 1-12 / 13-24 / 25-36 / 37-48; `Early`/`Mid`/`Late` → thirds of the round;
  explicit `Pick r.pp` → overall slot 12(r−1)+pp.
- **Pick realization:** the realized value of a pick = mean realized value of the players at that
  slot range in year D by rookie ADP (`fact_adp` format R, ppr −1, period DRAFT) — the engine's own
  rookie-pool convention.
- **Veterans:** every player in `values-players.csv` at that snapshot with NFL `draft_year < S`
  (excludes rookies of year S, which are realized picks). All positions; DP's `value_2qb` already
  prices QBs for superflex.
- **Matching (equal market value):** each pick row is matched to the **k = 5** veterans nearest in
  `value_2qb` at the same snapshot, restricted to ±15% of the pick's value; pick rows with < 3 vets
  inside ±15% are dropped and counted. Veterans may be reused across picks (counted in the cluster bootstrap).

## Realized value (same h/δ conventions as the trade engine)
- Per-season realized value = `fact_player_season_metrics.vorp_ppr_total`; a season with no row = 0
  (out of the league = replacement, engine convention).
- Discounted from the snapshot season: value = Σ_{t=0}^{h−1} δ^t · VORP(S+t), **h = 6, δ = 0.82**.
  A pick for draft D contributes from t = D−S (it produces nothing before it is used). No 0.92 pick
  tick on the realized side (that tick is a pricing uncertainty discount, not an outcome).
- **Truncation:** last complete season is 2025. Seasons after 2025 are filled with the engine canon
  (yr+1 = 0.85 × last observed season, compounding), applied identically to picks and veterans.
  **Known bias direction:** truncation + decay favors veterans (front-loaded value) over picks
  (back-loaded), i.e. it biases TOWARD H1. Therefore the observed-seasons-only read (no extrapolation)
  is reported alongside as a required sensitivity, and H1 must hold on both (see Pass/Fail).

## Comparison method
- **Primary statistic:** Δ = mean over matched pick rows of [realized(pick) − mean realized(matched vets)],
  in discounted VORP. Also reported per snapshot S, per draft class D, and per round.
- **Market vs engine:** for each pick row, prediction error of the market (pred Δ = 0) vs the engine
  (pred Δ_eng = engine price(pick) − mean engine price(matched vets)). Score = mean absolute error vs
  realized Δ, both legs on the same rows. Engine price uses `trade_gw_kcc.value()` exactly
  (pick: rookie pool, 0.92^drafts_out tick, jitter 15; veterans: startup slot pool at their
  snapshot-year ADP). **Both pools** (consensus K-ADP, corpus) reported, never blended.
- **Leak rule for the engine leg:** comparables limited to rows whose full forward window
  (season + 2) is < S. If any engine cell has n < 20 comparables, that cell is reported
  **NOT ESTIMABLE** — no leaky in-sample substitute is run.
- **Uncertainty (standing format):** 95% CI by bootstrap, 2000 resamples, seed 1729, resampling
  **realized players** (rookies within each draft class, and veterans) so reuse across rows is respected.
  Point + CI on every headline; no single verdict without its CI.

## Pass / fail (LOCKED)
Threshold provenance: **author-set decision threshold, not power-derived.** −25 discounted VORP is
about a quarter of the engine's unknown-slot 2027 1st (+91, from a one-off pick-valuation run, h=6, δ=0.82) — a
judgement call for "large enough to change a pick-for-veteran trade call." Not to be quoted as empirical.

- **SUPPORTED (H1)** iff Δ ≤ **−25** with the 95% CI upper bound **< 0**, in **both** the
  extrapolated and observed-only reads, **and** Δ < 0 in every draft class D with ≥ 10 matched rows.
- **UNDERPOWERED — no conclusion** iff the CI half-width exceeds 25 in either read (checked FIRST).
  A wide null is not a pass or a fail.
- **NOT SUPPORTED** iff not UNDERPOWERED and not SUPPORTED (CI includes 0, or Δ > −25, or the sign
  flips across draft classes, or H1 holds in only one of the two reads).
- **Market vs engine:** the engine "predicts better" iff its MAE is lower than the market's with a
  paired-bootstrap 95% CI on (MAE_market − MAE_engine) excluding 0, in **both** pools. If the engine
  leg is NOT ESTIMABLE, this question is reported unanswered.

## AMENDMENTS

### 2026-10-16 — data-shape fixes, written BEFORE any matching or realized-VORP computation
Only file headers, row counts and pick labels of the archive had been inspected when these were written.
- **A1 (source file).** Archived `values-picks.csv` has **no `value_2qb`** (only `ecr_*` ranks). The
  same commits carry `files/values.csv` — DynastyProcess's combined file (players + `pos == "PICK"`
  rows) with `value_2qb` for both. Both picks and veterans are taken from `values.csv` at the snapshot
  commit. Same publisher, same commit, same column — not a substitute source.
- **A2 (snapshots resolved by the locked rule).** 2021: `5faea36` (2021-07-30); 2022: `f8689a5`
  (2022-07-29); 2023: `eb9cb5c` (2023-07-28).
- **A3 (factual correction, rule unchanged).** The late-July files also list current-year slot picks
  (`S Pick 1.01`…). The text above assumed they would not. The locked rule already restricts to
  D ∈ {S+1, S+2}, so current-year picks are excluded.
- **A4 (5th round).** Files include `5th` / `Early|Mid|Late 5th`. The locked mapping covers 1st–4th
  only, so 5th-round rows are excluded.
- **A5 (slot ranges on continuous ADP).** Rookie ADP is continuous, so ranges are half-open on
  ADP: round r = [12(r−1)+0.5, 12r+0.5); Early/Mid/Late = the three 4-slot thirds of that interval.
- **A6 (identity).** DP rows join to `dim_player` on `fp_id = fantasypros_id`. Unmatched veterans are
  dropped before matching and counted; veteran = DP `draft_year < S`.

### 2026-10-16 — A7, implementation determinism fix, written AFTER results were seen
- **A7 (tie-break).** The locked "k = 5 nearest in `value_2qb`" rule did not say how to break ties,
  and ~50 veterans per snapshot share a `value_2qb` with another veteran. The first implementation
  broke ties by non-deterministic row order (polars join order + unstable argsort), so two executions
  of the same code gave different results: overall extrapolated Δ +29.1 [+5.0, +53.4] vs
  +33.2 [+9.3, +57.3]; observed-only +16.9 [−2.6, +36.2] vs +20.4 [+1.2, +39.5]. Both executions
  gave NOT SUPPORTED. Fix: ties are broken by `player_uid` ascending (stable sort). This rule was
  chosen because it is neutral to outcome, not by comparing results; it is disclosed here because it
  was written after both nondeterministic results had been seen.

### 2026-10-16T14:58:21Z — A8, pointer: test CLOSED — result label **UNINFORMATIVE**
The market-vs-engine test (this v1 and `exports/prereg_market_vs_engine_v2.md`) is CLOSED as NOT ESTIMABLE,
result **UNINFORMATIVE**, on Colby's authorization; see v2 amendment B2. The v1 result above stays on
record unchanged; cite it only with the UNINFORMATIVE label.
