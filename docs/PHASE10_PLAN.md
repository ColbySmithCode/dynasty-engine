# PHASE 10 — Validation (plan / pre-registration)

> Pre-registered **before any Phase-10 code** (project convention). Phase 10 does **no new
> modeling** — it is the adversarial audit of everything Phases 3–9 asserted. Its charter:
> **leakage audit (headline), backtest vs the two named baselines (ADP + last-year PPG),
> calibration of the survival/projection posteriors against observed frequencies, and repro
> extending the 5× cross-process byte-check across the full pipeline** — plus the carried items
> the prior gates deferred with a live-source blind spot (win-rate ICC, `design_effect.json`,
> the youth-2020 SE mismatch, G9-OI-1) and the **Phase-5 backlog** of pre-registered results that
> were never printed.
>
> **APPEND-ONLY.** Once these criteria are reviewed and approved, their text is immutable. Every
> correction, scope change, or superseded value goes in a dated **AMENDMENTS** section at the
> bottom — never by editing an approved criterion in place (tests follow the amendment; the
> original stays as the record). Same convention as PHASE8_PLAN §A1/§A2 and PHASE9_PLAN.
>
> **REVISED 2026-07-29 (pre-approval review round 1).** Pre-approval edits (this plan is NOT yet
> approved, so criteria are edited in place, same as PHASE9_PLAN's pre-approval AMENDED note):
> G10.5/G10.6 resequenced + PROVISIONAL-PENDING (fix 1); G10.5 deff→LB table made explicit and its
> SE-derivation decoupled from the opt cell (fixes 2, 3); G10.2 test statistic + multiplicity family
> named (fix 4); the fixed replicate count B and the 30-cluster floor replaced by a convergence
> criterion and an ICC-interval estimability rule (fix 5); G10.9 contradiction-handling added (item 6).
>
> **REVISED 2026-07-29 (pre-approval review round 2).** (A) G10.5 LB table reconciled with explicit
> raw-scale arithmetic — **finding: youth-2020 Δ_bal is OVERTURNED under BOTH the arithmetic (1.12)
> and Kish (1.33) proxy weightings**, so the directional rule was rewritten to key on a break-even
> deff* ≈ 1.017 (ICC ≈ 0.0065 Kish), not on arith-vs-Kish; the recorded "+0.004" is corrected as an
> impossible widened LB. (B) 2020 roster ICC identified as a **doc-consistency-canon entry checked at
> 2 dp with no live wiring** — added to G10.6 pinning scope, not filed as rounding. (1) the Δ_bal
> percentile-CI verification is promoted to a G10.5 **prerequisite** alongside G10.6. (2) G10.2 margin
> constant deleted; one primary endpoint named; WY sub-families made homogeneous. (3) `conv_frac`/`
> icc_hw_max` anchoring disclosed. (4) the three "registry" objects given distinct names; the
> doc-consistency canon found to be **partly hand-maintained** (startup/trade blocks), weakening
> G9-OI-1. (5) Phase-7 dates confirmed and `z=−0.02` recorded as derived. **[The round-2 "point
> deff* ≈ 1.017 / not decision-relevant" claim is SUPERSEDED by round 3 below.]**
>
> **REVISED 2026-07-29 (pre-approval review round 3 — APPROVAL round).** (1) **deff\* is an INTERVAL,
> not a point.** Because the base LB (+0.001) sits at zero, deff\* = (p/(p−L₀))² is hyper-sensitive to
> endpoint noise; G10.7v now establishes Δ_bal endpoint precision by the SAME convergence criterion as
> `B`, and reference ±0.012 endpoint noise gives deff\* ∈ **[0.83, 1.27]**, which **STRADDLES 1.12**.
> **The round-2 "arith-vs-Kish not decision-relevant" claim is RETRACTED**: under favorable endpoint
> noise 1.12 lands NOT-OVERTURNED while 1.33 lands OVERTURNED, so the distinction can be live. G10.5's
> rule rewritten to key on the deff\* interval, with an explicit straddle outcome. (2) **One named
> UNESTIMABLE rule** (`UNESTIMABLE→CONSERVATIVE`) applied everywhere — 2021's anti-conservative
> `deff=1` changes to the upper-bound `deff≈1.28`; affected 2021 cells enumerated + re-marked. (3)
> **G10.2 CO-PRIMARY** — ADP and last-year-PPG both primary (two tests, no multiplicity control on the
> pair); SPLIT named as a non-BEATS outcome. (4) print-only: +0.004 AND −0.009 folded into one dated
> GATE6_5 amendment; 2020 ICC CI provenance, Δ_bal point-vs-midpoint, and RMSE status recorded.
>
> **Every G10.x below prints its own PASS/FAIL line, and the pre-registered pass condition, BEFORE
> any result exists** (a test enforces each). **Any numeric threshold with no derivation is labelled
> `author-supplied` and `PROVISIONAL`**, same convention as PREREG_FALSIFIER — it may gate a report
> line but it may NOT, on its own, close a gate or overturn a claim.

## Directional pre-registration — the standing rule for this phase

For **every** criterion, this plan states, before running it, **what result changes which existing
claim, including the outcomes that cost us something.** A criterion whose every branch leaves every
claim untouched is a vacuous criterion and is not accepted. The costly branches (a leak that forces
a refit; an ICC that keeps youth-2020 OVERTURNED; a backtest that fails to beat last-year PPG) are
written down here with the same weight as the clean ones. We do not get to discover the direction
after seeing the number.

## Anti-vacuity — the standing rule for this phase

Every criterion that "examines" something must **print the count and the identity of what it
examined, and an explicit list of what it could NOT reach.** A pass that examined zero rows, the
wrong rows, or a subset it silently narrowed to is **unreportable as a pass** — the test asserts the
examined-inventory equals (or is a superset of) the pre-registered inventory, and fails otherwise.
This is the direct lesson of the Gate-9 `registry_key` finding (a single-pin cross-check that
verified a copy step, not a value) and the pre-Phase-9 vacuity fix.

---

## PROVENANCE TRIPLE (stamped on every Phase-10 report + every artifact it pins)

Identical shape to G9.6a. Every Gate-10 report and every artifact Phase 10 writes carries:
- **raw-cache vintage** — nflverse FROZEN vintage **2026-07-29**, input signature
  **`d9c462197311a92e`** (+ the corpus FROZEN 2026-07-27); a signature bump invalidates the run.
- **warehouse build id** — `max(fact_refresh_status.last_successful_refresh)` / refresh-manifest id.
- **git commit** — HEAD short hash at run time; a vintage/commit mismatch is flagged, not hidden.

---

## Gate-10 acceptance criteria (PRE-REGISTERED; a test must exist for each)

### G10.1 — LEAKAGE AUDIT (headline; absorbs the G9.3 deferral)

**What it is.** Gate 9 (G9.3) verified the **write** side — `assert_no_2026_in_models` guards model
artifacts — but explicitly deferred whether **every model-CONSUMED input table is 2026-free**;
input-side exclusion was **never independently verified**. G10.1 is that independent verification,
generalized: no model consumes any value sourced from **inside its own outcome/holdout window** (not
just 2026 — any look-ahead into the label period).

**Pre-registered inventory (anti-vacuity — the audit MUST cover exactly this, and print it).**
Model-consumed tables, enumerated up front from `migrations/schema.sql` + each `models/*` reader:
`dim_player`, `dim_team`, `dim_season`, `dim_week`; `fact_player_week` (all 6 scoring profiles incl.
`your_league`), `fact_player_season`, `fact_player_season_metrics`, `fact_adp`, `fact_injury`,
`fact_dynasty_value`, `fact_replacement`, `fact_league_roster`, `fact_draft_pick`,
`fact_traded_pick`, `fact_transaction`; the frozen raw (`data/raw/nflverse/*`,
`data/raw/sleeper_corpus/*`, cfb) as read by ingest; and the per-model consumed **column** sets for
`aging_curves`, `survival`/`survival_cox`, `adp_calibration`, `adp_efficiency_retest`, `archetypes`,
`cfb_5_4b`, `projection`, `startup_backtester`/`startup_data`, `engine/trade_engine`.

**The audit MUST print:**
1. `tables_examined` (count + names) and `columns_examined` (count + fully-qualified names).
2. `model_consumed_but_unreachable` — an **explicit list** of anything model-consumed the audit could
   not resolve to a table+column+timestamp (empty list is the only clean value; a non-empty list is
   reported, never suppressed).
3. For each consumed column: the **max source timestamp** vs the model's **fit/outcome window**.

**Directional pre-registration (refit vs footnote — the numeric boundary):**
- **REFIT-FORCING:** ≥1 model-consumed column sources **≥1 row whose data timestamp falls inside that
  model's outcome/holdout window** (a genuine look-ahead into the label period). Consequence: refit
  the affected model on a corrected feature set, re-pin its artifact, and re-run every downstream
  gate that consumes it. This is the branch that costs us — it is written here so it cannot be
  reclassified as a footnote after the fact.
- **FOOTNOTE-ONLY:** a leakage-**adjacent** condition that does **not** enter the fitted feature set —
  e.g. a 2026 row present in a table but filtered by `season < Y` **before** fitting, or a
  frozen-vintage file mtime that postdates the window but whose contents are not consumed. Consequence:
  documented footnote, **no refit**.
- **Boundary, stated as a rule not a vibe:** refit iff `count(consumed columns sourcing ≥1
  label-window row) ≥ 1`; footnote iff that count is `0` and only non-consumed adjacency remains.

**Anti-vacuity pass condition (printed before results):** PASS **iff** `tables_examined ⊇`
pre-registered table inventory **AND** `columns_examined ⊇` the per-model consumed-column inventory
**AND** `model_consumed_but_unreachable == []` **AND** zero refit-forcing leaks found. A run that
examined a narrowed subset, or left any consumed input unreachable, is **FAIL — not PASS**, even if
it found no leak in what it did examine.

### G10.2 — BACKTEST vs the two named baselines (ADP + last-year PPG)

**Baselines (both required, reported separately — never a single "beats the market").**
(1) **ADP** (the market prior); (2) **last-year PPG** (naive persistence). CONVENTIONS §"report
beat-the-baseline honestly" names both as the bars.

**Target + metric + paired test (pre-registered, no "beat honestly"; the test MUST match the metric).**
- **PRIMARY — binary target.** Target = the project's existing **binary "hit"** label (the 2019–2022
  evaluation convention: n=704, **43 hits**). Because the target is binary and the metric is **AUC**,
  the paired test is **DeLong** — the **same** apparatus used for archetype-vs-capital (SE 0.0153,
  corr 0.777), so the estimand is comparable, not a fresh construction. DeLong is used **only** here,
  where the metric is AUC.
- **SECONDARY — continuous/ranking target.** Target = realized fantasy **rank** (or PPG). Metric =
  **Spearman rank-correlation** — **DeLong does NOT apply**; the paired test is a
  **league/manager-clustered paired bootstrap of the metric DIFFERENCE** (model − baseline), a
  **DIFFERENT estimand** from the binary-AUC gap (do not conflate; same discipline that keeps the
  refit CI [−0.084,+0.018] distinct from the test-set CI). **RMSE/MAE (print-only d): NOT dropped, and
  NOT a WY family.** Error is reported as a **descriptive diagnostic** (signed RMSE/MAE difference +
  its clustered-bootstrap CI) alongside Spearman; it is not folded into a family-wise correction
  because it answers a different question (calibration of magnitude, not rank discrimination). So
  "Family B = Spearman" is intentional; RMSE/MAE travels as a diagnostic column.

**CO-PRIMARY endpoints (TWO, pre-registered — round-3 fix 3).** The charter requires beating **ADP
AND last-year-PPG**, so BOTH are primary: the endpoint **{target = binary hit; metric = AUC; test =
DeLong; stratum = pooled}** is run **against each baseline** = **two tests**. **No multiplicity
control on the pair** (two pre-registered primaries, not a screen). Count note: promoting the second
pooled-AUC cell (PPG) from secondary to primary takes the secondary set from the round-2 **19** to
**18** — Family A (binary-AUC/DeLong) loses its two pooled cells (10 → 8 non-primary), Family B
(Spearman, 10) is unchanged; the secondary *structure* is otherwise "as written."

**Split-result verdict (named; NOT reportable as BEATS — round-3 fix 3).** Combining the two primary
three-way outcomes:
- **`CLEARS-BAR`** iff the model **BEATS both** ADP and last-year-PPG (each CI lower bound > 0).
- **`SPLIT`** iff it beats **exactly one** (BEATS one, INDISTINGUISHABLE/LOSES the other). This is its
  **own named outcome** and **must NOT be reported as BEATS** — the charter bar is unmet unless both
  fall. The report names which baseline was beaten and which was not.
- **`FAILS-BAR`** iff it beats **neither**. Each baseline still carries its own three-way
  BEATS/INDISTINGUISHABLE/LOSES label underneath.

**Multiplicity — homogeneous sub-families only (round-2 edit 2).** A Westfall–Young control assumes a
**shared exchangeable null**, which a mixed family (binary-target AUC/DeLong *and* continuous-target
Spearman) does **not** have — so there is **no single WY over the secondaries**. Within each
**homogeneous** sub-family the secondaries are WY-controlled separately — **Family A:** binary-AUC/
DeLong across the non-primary strata; **Family B:** Spearman across {2 baselines × 5 strata}
(clustered paired-rank null). Each uses the **same apparatus** as the 5.4B college null (WY p 0.645)
on its own null. RMSE/MAE is a diagnostic, in neither family.

**Directional pre-registration (margin-free three-way rule — round-2 edit 2 deleted the constant):**
The decision consumes **no `margin`**; the old 0.02–0.03 AUC constant is **removed** (it set no
boundary the three-way rule uses). Per test, using the paired CI (DeLong for binary-AUC, clustered
bootstrap for Spearman):
- **BEATS** iff CI **lower bound > 0**.
- **LOSES** iff CI **upper bound < 0**.
- **INDISTINGUISHABLE** iff the CI **spans 0**.
The two co-primaries are judged by the LB>0 / UB<0 / spans-0 rule alone (no WY); secondary rows
additionally require their sub-family WY p < 0.05 to be called a win.
- **Costly branch, written down:** a `SPLIT` or `FAILS-BAR` — in particular **failing to beat
  last-year-PPG** (naive persistence) — is a first-class Phase-10 finding, reported with equal
  prominence to any win vs ADP, never footnoted or upgraded to BEATS.

### G10.3 — CALIBRATION of the survival / projection posteriors vs observed frequencies

**What it is.** The 5.5 projection posteriors and the 5.2 survival (Clock A P(relevant in yr N),
Clock B KM persistence) assert intervals; G10.3 asks whether those intervals are **calibrated**
against realized outcomes on held-out seasons.

**Pre-registered procedure + inventory (anti-vacuity).** Print `n_predictions_scored`,
`n_by_position`, the season range scored, and any cohort **excluded** with the reason (exclusions
must be shown MNAR-safe — if an exclusion correlates with the outcome being calibrated, it is
reported as a threat, not dropped silently).
- **Reliability:** bin predicted probability into pre-registered deciles; plot/print observed
  frequency per bin; compute **calibration slope**, **intercept**, and **ECE**.
- **Interval coverage:** the nominal-90% posterior intervals should cover ≈90% of realized outcomes;
  print **empirical coverage** with a binomial CI at the scored `n`.

**Directional pre-registration (what forces action vs a footnote):**
- **Well-calibrated → footnote/PASS:** calibration slope 95% CI contains 1.0 **AND** empirical 90%
  coverage CI contains 0.90. `[slope∈[0.9,1.1], coverage∈[0.85,0.95]]` tolerances are
  **`author-supplied` and `PROVISIONAL`** (no derivation) — used only to LABEL, not to close.
- **Materially miscalibrated → recalibration note or refit:** slope CI excludes 1.0 in a direction
  that biases decisions (over-confident intervals: coverage CI wholly below nominal) forces a
  recalibration pass on that posterior and a re-pin; a slope offset with correct coverage is a
  documented footnote. State the number, not "looks off."
- **Small-n honesty:** where the scored event count does not support a decile reliability curve
  (event counts like the college strata), G10.3 reports the calibration as **UNINFORMATIVE**, not as
  a pass — the same discipline as the 5.4B "uninformative test, not a null" marking.

### G10.4 — REPRO: extend the 5× cross-process byte-check across the FULL pipeline

**What it is.** Phase 7 established 5-fresh-process byte-identity for the **9 model artifacts**
(`registry.jsonl` hashing) and a hermetic warehouse build. G10.4 extends the same 5× check **end to
end**: `ingest.* (frozen)` → `transform.warehouse` (`warehouse.db`) → `transform.metrics` →
`models.*` → `engine.trade_engine` → `jobs.build_bundle` (`assistant_bundle.{json,md}`) → the MCP
server payloads (already covered by G9.6b — re-asserted under the full-pipeline harness).

**Pre-registered inventory (anti-vacuity).** Print the **explicit list of pipeline stages checked**
and the artifact each emits; print any stage that is **NOT** byte-checkable and **why** (an explicit
named waiver, never a silent gap). The residual live call `nfl.load_teams` (32-row static lookup) is
pre-declared as the one known non-frozen read; it must be shown to not affect byte-identity or be
frozen.

**Directional pre-registration:**
- **PASS:** every listed stage is byte-identical across 5 fresh processes (excluding at most one
  explicitly-named `generated_at`-style field per artifact, stripped before compare).
- **FAIL → fix before close:** any stage that differs across processes is a defect (unordered
  DuckDB read feeding `.first()`/group-iteration, unsorted output) and must be fixed (ORDER BY /
  sorted) — Gate 10 does not close over a non-deterministic stage.
- **Costly branch:** a stage that **cannot** be made deterministic must be **named and waived
  explicitly** with its reason printed; silent truncation of the checked set to make the run go green
  is the failure mode this criterion exists to prevent.

### G10.5 — WIN-RATE ICC by manager-clustered, sims-OUTSIDE re-simulation (carried)

**What it is.** Every design effect in the project currently rests on a **roster-strength PROXY**
ICC (0.123 in 2020, −0.073 / unestimable in 2021). The outcome that actually matters — the
within-manager ICC of the per-cell strategy **WIN RATE** — has **never been measured**; it needs a
re-simulation with the sims **outside** the resampling loop (the sim-level clustered permutation from
Gate 6.5 round 2 was an artifact; this is the "option a" that GATE6_5 deferred in favor of the proxy).

**SEQUENCING (fix 1 + round-2 edit 1 — two prerequisites, not one).** G10.5's numeric threshold
table below is **doc-sourced** (from `docs/GATE6_5_REPORT.md`) and its **entire rule keys on the
Δ_bal lower bound**, so two things must be true *before* G10.5's numbers are binding:
**(a)** **G10.6** runs first (pins `design_effect.json` → the ICC/mbar/deff the widening consumes);
**(b)** the **G10.7 Δ_bal percentile-CI verification** runs first (confirms the CI endpoints are a
pure percentile CI so √deff widening is well-defined — this is a **PREREQUISITE**, not a cheap
add-on, because the LB is the whole rule). The table is marked **`PROVISIONAL-PENDING-G10.6+G10.7v`**
— it stays in the record (append-only) but is **non-binding** until a **dated AMENDMENTS entry
re-pre-registers the exact widened bounds against the pinned artifact**, written **after both (a) and
(b) run and before G10.5 runs**. No G10.5 result may be reported until that amendment exists.

**Pre-registered design (all fixed before running):**
- **Cluster variable:** `manager`.
- **Sims OUTSIDE the resampling loop** — the simulation draws are fixed once; the resampling
  (bootstrap/permutation over managers) happens over those fixed sims. Sims must not be re-drawn
  inside the loop (that is exactly the bias that inflated the earlier sim-averaged SE ~4× and the §1
  eff_n to 60–270).
- **Replicate count `B` — by CONVERGENCE, not a fixed number (fix 5).** There is **no standard `B`.**
  Run the clustered re-sim under **≥5 independent seeds**; require the **spread of each ICC/deff CI
  endpoint across seeds to be < `conv_frac` of that CI's half-width**. `B` is escalated (doubling from
  a small start) until met; the final `B` and the observed cross-seed spread are reported.
  **`conv_frac = 10%`** is **`author-supplied` and `PROVISIONAL`. Anchoring disclosed (round-2 edit
  3): this is set just ABOVE the observed archetype test-only bootstrap spread of 8.8% of the
  half-width — i.e. calibrated to a value already in hand, which is WEAKER than a derived threshold.**
  A run that does not meet `conv_frac` at the compute ceiling is reported as **not-converged**, never
  rounded to converged.
- **Estimability — by the ICC INTERVAL, not a cluster count (fix 5).** The ICC is **`UNESTIMABLE`**
  iff its bootstrap CI **spans zero** **OR** its **half-width > `icc_hw_max`**. **`icc_hw_max = 0.20`**
  is **`author-supplied` and `PROVISIONAL`. Anchoring disclosed: 0.20 is permissive — it admits (as
  ESTIMABLE) an ICC whose CI half-width is ~1.6× its own point estimate (0.20 / 0.123 ≈ 1.63).** The
  **multi-league-manager count is a reported DIAGNOSTIC, not the gate.**
  - **THE UNESTIMABLE RULE — `UNESTIMABLE→CONSERVATIVE` (named once here; cited by G10.5, the 2021
    handling, and G10.6; round-3 fix 2).** An `UNESTIMABLE` ICC is **never floored to zero / deff 1**;
    it routes to the **least-favorable-to-the-claim endpoint of its own CI.** Operationally: use the
    **upper ICC-CI bound** to form the design effect (widest CI, most widening), for **every** deff in
    the project, in **both** directions — a claim that would be *validated* by a small CI and a claim
    that would be *reduced-in-power* by a wide CI both get the widest CI. Flooring to zero is
    forbidden because it manufactures precision an unestimable quantity does not have.
  - **SCOPE SWEEP (round-3 fix 2, done 2026-07-29).** Grepped `models/`, `jobs/`, `transform/`,
    `engine/`, `config.yaml` for estimated parameters defaulted to a null value (ICC→0, deff→1,
    correlation→0, shrinkage→0/1). **Only hit: 2021 `deff=1`** (`drift_baseline.json.startup_6_5` +
    docs). No model code floors ICC/correlation/shrinkage; `np.corrcoef` (`startup_backtester.py:1148`)
    is computed-not-defaulted, and `shrinkage_k_games=10` (`config.yaml:263`) is a genuine tunable
    pseudo-count (estimable, not a null default). So the rule has exactly ONE site to fix: 2021 deff.
  - **Classification under the rule:** 2020 (ICC point 0.123, CI **[0.04, 0.19]**, half-width ≈ 0.075
    < 0.20, CI **excludes 0**) → **ESTIMABLE**; 2021 (CI [−0.41, +0.26], spans 0 and half-width 0.335
    > 0.20) → **UNESTIMABLE** → upper-bound deff (see the 2021 re-marking below, NOT deff 1).
  - **2020 ICC CI provenance (print-only b).** The 2020 ICC CI **[0.04, 0.19]** and its half-width
    **0.075** come from an **unpersisted session table**, NOT a reviewer-supplied figure and NOT a
    pinned artifact — which is itself why G10.6 must persist them. The CI **excludes zero**, so the
    2020 *proxy* deff > 1; but this criterion keys on the **OUTCOME** win-rate ICC, so 2020's proxy
    being estimable-and-positive does not settle the outcome deff.

**Directional pre-registration (numeric — deff → widened Δ_bal lower bound → status).**
**Inputs (from `drift_baseline.json.startup_6_5` + `GATE6_5_REPORT.md`):** point estimate
**Δ_bal(clustered) = +0.116**; unwidened percentile CI **[+0.001, +0.281]** (asymmetric — lower
distance `p − L₀ = 0.115`, upper distance `0.165`); symmetric half-width **0.140**; midpoint
**0.141**. **Scale = RAW.** Δ_bal is a *difference* of win rates ∈ [−1, 1], which has no logit; the
report uses logit ONLY for win-rate *levels* (GATE6_5:256, 260), never for this delta. So the
widening is raw-scale. **Formula (primary, point-anchored):** `LB(deff) = p − √deff · (p − L₀)`.
(Midpoint-anchored variant `mid − √deff·HW` shown for reconciliation.) Widened LBs are
**`PROVISIONAL-PENDING-G10.6+G10.7v`**; the re-sim produces the binding bounds (GATE6_5:239).

| pooled deff | source | √deff | LB point-anchored `0.116−√deff·0.115` | LB midpoint-anchored `0.141−√deff·0.140` | status |
|---|---|---|---|---|---|
| **1.00** | base CI (no widening) | 1.00000 | 0.116−0.11500 = **+0.00100** | 0.141−0.14000 = **+0.00100** | **NOT OVERTURNED**, but half-width 0.14 fails the falsifier's own ≤0.03 rule → *underpowered*, not a clean exclusion |
| **1.12** | arith mbar 1.94, proxy ICC 0.123 | 1.05830 | 0.116−0.12170 = **−0.00570** | 0.141−0.14816 = **−0.00716** | **OVERTURNED** (LB < 0) |
| **1.33** | Kish mbar 3.68, proxy ICC 0.123 | 1.15326 | 0.116−0.13263 = **−0.01663** | 0.141−0.16146 = **−0.02046** | **OVERTURNED** (LB < 0) |
| **break-even deff\*** | solve LB = 0 (see interval below) | — | **deff\* = (0.116/0.115)² = 1.01747** at the pinned LB | 1.01434 at the pinned midpoint | LB = 0 knife-edge — but deff\* is an INTERVAL, not this point |
| **UNESTIMABLE** | ICC CI spans 0 or HW > 0.20 → `UNESTIMABLE→CONSERVATIVE` | upper ICC-CI bound | **< 0** | **< 0** | **OVERTURNED** (conservative; never floored to deff 1) |

**deff\* IS AN INTERVAL, not a point (round-3 fix 1).** deff\* = (p/(p−L₀))² depends on the lower
endpoint L₀ = +0.001, which sits *at zero*, so deff\* is hyper-sensitive to endpoint noise. **G10.7v
must first establish L₀'s cross-seed spread** (see G10.7v); deff\* is then reported at
`L₀`, `L₀−spread`, `L₀+spread`. **Reference (±0.012 endpoint noise, illustrative — real spread comes
from G10.7v):**

| L₀ | deff\* = (0.116/(0.116−L₀))² |
|---|---|
| −0.011 (L₀−spread) | (0.116/0.127)² = **0.834** (degenerate: base CI already crosses 0) |
| +0.001 (pinned LB) | (0.116/0.115)² = **1.017** |
| +0.013 (L₀+spread) | (0.116/0.103)² = **1.268** |

→ deff\* ∈ **[0.83, 1.27]**, which **STRADDLES 1.12** and reaches above it (sup 1.27 > 1.12).

**FINDING (round-3, supersedes round-2's "not decision-relevant").** At the *pinned* endpoints,
deff 1.12 and 1.33 both give a negative LB (−0.0057 / −0.0072 at 1.12). **But deff\* is an interval
[0.83, 1.27] that straddles 1.12** (above), so the sign at 1.12 is **NOT robust to Δ_bal endpoint
noise**: under favorable noise (L₀ up to +0.013 → deff\* 1.27) an outcome deff of 1.12 lands
**NOT-OVERTURNED** while 1.33 stays **OVERTURNED**, which **restores** the arith-vs-Kish distinction.
So the round-2 claim "arith-vs-Kish not decision-relevant" is **RETRACTED**; whether it matters is
itself contingent on G10.7v's measured endpoint precision. The live status is unchanged (OVERTURNED
at the pinned point), but it is **not** established as robust.

**Reconciling the recorded deff-widened LB values (print-only a — ONE dated GATE6_5 amendment):**
- **−0.0072** (raw-scale √1.12 of [+0.001,+0.281] about the midpoint, `0.141 − 0.1482`): reviewer's
  value, **arithmetically correct**; point-anchored gives −0.0057. Both negative. **Correct family.**
- **"+0.004"** (GATE6_5:272, deff 1.12): **impossible as a widened LB** — widening moves the LB DOWN,
  yet +0.004 > the base +0.001 (`+0.004 ≤ +0.001` is False). It is the **item-1 SD/eff_n normal-approx
  path**, the same SD-vs-percentile error flagged for the `opt` cell.
- **"−0.009"** (GATE6_5:270, deff 1.33): **does not reproduce** — raw-scale √1.33 gives **−0.017
  point / −0.020 midpoint**. It is a **fourth non-reproducing value** for this quantity (with +0.004,
  ~+0.00, −0.009), so flagging is no longer enough.
- **"≈ +0.00"** (this table, round 1): hand-wave paraphrase; **superseded.**
- **REQUIRED AMENDMENT:** a **single dated `GATE6_5_REPORT.md` amendment** corrects **both** the deff-
  1.12 "+0.004" **and** the deff-1.33 "−0.009" to their reproducing values (−0.0057/−0.0072 and
  −0.017/−0.020). The OVERTURNED *status* at the pinned point stands; only the justifying numbers were
  wrong. (Originals preserved; append-only.)

**Point-vs-midpoint (print-only c).** The Δ_bal **point estimate is +0.116** everywhere. The
**0.141 midpoint of the CI is NOT the point estimate** (the percentile CI is asymmetric); it appears
only as the anchor of the midpoint-variant column. Point-anchored `LB = p − √deff·(p−L₀)` is primary.

**Rewritten directional rule (round-3 — keys on the deff\* INTERVAL, not a point):** let the measured
outcome win-rate deff be `d_out` and the deff\* interval from G10.7v be `[deff*_lo, deff*_hi]`.
- **`d_out > deff*_hi`** → widened Δ_bal LB < 0 for the whole interval → **STAYS OVERTURNED**
  (unambiguous). This is the likely branch (the proxy Kish deff 1.33 sits here if endpoint noise is
  small).
- **`d_out < deff*_lo`** → widened LB > 0 for the whole interval → **LEAVES OVERTURNED** (→ at most
  `AT_RISK`/`ESTIMATED`). Requires an essentially-zero/negative outcome ICC.
- **`d_out ∈ [deff*_lo, deff*_hi]`** (straddle) → the endpoint noise dominates the verdict →
  **INDETERMINATE**: report `UNRESOLVED-ENDPOINT-NOISE`, do NOT declare a status, and either tighten
  G10.7v (more seeds, larger `B`) until deff\* no longer straddles `d_out`, or record that Δ_bal
  cannot adjudicate youth-2020 at the achievable precision.
- **Arith-vs-Kish is decision-relevant iff `deff*_hi > 1.12`** (reference: 1.27 > 1.12, so at
  reference precision it IS): then outcome deff 1.12 vs 1.33 can yield different verdicts, and both
  must be reported, not collapsed.
- **SE-derivation note (fix 3 — decoupling from the opt cell).** The Δ_bal CI this table keys on is
  the **clustered percentile CI (half-width 0.14)**. The SD-vs-percentile mismatch of G10.7 is on a
  **DIFFERENT cell** — the youth-2020 **opt** cell (bootstrap SD **0.0479** vs percentile-HW **0.081**,
  not Δ_bal's 0.14). Same clustered-bootstrap *procedure*, **different output cells**. **Correcting the
  record:** `GATE6_5_REPORT.md:286` says the opt SE mismatch "blocks moving youth-2020 off OVERTURNED"
  — but OVERTURNED is a **Δ_bal** marking and the mismatch is on **opt**; prior rounds conflated the
  two cells (the same conflation that produced the impossible "+0.004"). Per round-2 edit 1, the Δ_bal
  percentile-CI verification is a **G10.7 PREREQUISITE** run before G10.5 (not a residual add-on).
- **2021 re-marking under `UNESTIMABLE→CONSERVATIVE` (round-3 fix 2 — the SAME rule, applied here).**
  2021's proxy ICC is `UNESTIMABLE` (CI [−0.41,+0.26] spans 0). The project currently sets 2021
  **`deff = 1`** (ICC=0) — the **anti-conservative** end, the exact flooring the named rule forbids.
  Applying `UNESTIMABLE→CONSERVATIVE` (upper ICC-CI bound 0.26, Kish mbar 2021 = 2.06):
  **2021 deff → ≈ 1.28** (GATE6_5:283). This is a **direction change**, not a wording change; the
  affected 2021 cells are re-marked (originals preserved, append-only):
  - **2021 effective leagues:** 15 → **≈ 12** (15 / 1.28; GATE6_5:283 "~12").
  - **Every 2021 §1 win-rate CI:** widens by **√1.28 ≈ 1.13×** (they were narrow by up to that factor
    at deff=1).
  - **`design_effect.json` (G10.6):** must persist **`deff_2021 = 1.28` (upper-bound)**, not 1; the
    `_design_effect_note` "unestimable ~0 (2021)" is superseded by "unestimable → conservative
    upper-bound 1.28."
  - **the internal project notes STANDING CONSTRAINT 1** ("effective leagues ≈ 35 / 15 / 49"): the 2021 figure moves
    15 → ~12 via a dated amendment.
  - **Unchanged in direction:** "2021 (≤15 units) cannot confirm youth-2020" — a wider 2021 CI only
    reinforces underpowered; pooled (its own Kish mbar) is computed independently and does not move
    from this 2021-only change.
- **Why conservative wins both places (answering the round-3 challenge directly):** the rule is
  symmetric — for youth-2020 (G10.5) "least-favorable" means the **widest** widening (upper ICC bound
  → LB most negative → OVERTURNED held); for 2021 it *also* means the **widest** CI (upper ICC bound
  → deff 1.28 → CIs wider). Both use the upper bound; neither floors to zero. The prior repo state was
  inconsistent only because 2021 was floored while G10.5 was not — this fix removes that asymmetry.
- **Project-wide consequence, stated up front:** if the **outcome** win-rate ICC differs *materially*
  from the roster-strength proxy (0.123 / −0.073), **every deff in the project is restated** — the
  effective-league counts (2020 ≈35 Kish / pooled ≈49 Kish; arithmetic 42/57), the 2021 deff (now
  1.28, above), the falsifier's design-effect trigger, and any downstream "effective n" all move
  together. A higher outcome ICC widens every startup-strategy interval (more claims to
  `INDISTINGUISHABLE`/`OVERTURNED`); a lower one narrows them but does **not** by itself validate any
  strategy (corpus size still binds, STANDING CONSTRAINT 1).

### G10.6 — PIN `models/design_effect.json` (carried backlog #1)

**RUNS BEFORE G10.5 (fix 1).** G10.6 is sequenced ahead of G10.5: the deff→LB table in G10.5 is
doc-sourced and non-binding until this artifact exists and a dated amendment re-pre-registers those
bounds against it.

**What it is.** The item-1/2 re-SE table + the ICC/deff values that **drive the youth-2020
OVERTURNED marking have NO live-computing artifact** (verified 2026-07-29: `models/design_effect.json`
does not exist; no job writes these numbers). They currently live as a **hand-maintained baseline
block** `startup_6_5` inside `jobs/drift_baseline.json`, read by the doc-consistency canon.

**B FINDING (round-2 — do NOT file as rounding).** The 2020 roster ICC **is** a doc-consistency-canon
entry: `_num("roster ICC 2020", su["roster_icc_2020"], 2, 5e-4)` where `su =
drift_baseline.json["startup_6_5"]`. Its **pinned value is 0.123** (full precision in the baseline);
the internal project notes' "0.12" is a *correct 2-dp display* of that 0.123, so there is **no drift** — BUT the guard
**could not catch one if there were**, for two structural reasons: (1) the canonical is checked at
**2 dp** (`places=2` → magnitude string "0.12"), and "0.12" is a substring of "0.123", so any value in
[0.115, 0.125) passes the presence check; (2) the entry carries **no `live=` argument**, so the
sub-rounding **drift check (tol 5e-4) is never exercised** on it (guard runs it only `if c["live"] is
not None`). The declared 5e-4 tolerance is therefore **dormant**. This is a **load-bearing blind
spot**: roster ICC 0.123 → deff → the G10.5 Δ_bal LB. The same applies to every `startup_6_5`
design-effect entry (`mbar_2020/2021`, `deff_2020`, `deff_2020_kish`, `eff_leagues_*`) — all
present-checked at low precision with no live wiring — and to the **2020 ICC CI half-width (≈0.075)**,
which is **not stored at all**.

**Pre-registered requirements:**
- Persist `models/design_effect.json` at **full precision**, produced by a **re-runnable job** (not
  hand-entered): proxy ICC (2020 0.123 **+ its CI [0.04,0.19] / half-width 0.075**, 2021 −0.073 + CI
  [−0.41,+0.26], n_multi_league 2020/2021), Kish & arithmetic mbar, deff (Kish 1.33/1.28, arith 1.12),
  effective-league counts, AND the **G10.5 outcome win-rate ICC/deff** once measured.
- **2021 deff, pinned as a CONSERVATIVE BOUND, not an estimate (round-3 fix 3).** Record
  **`deff_2021 = 1.28`** with an explicit field marking it **derived from the upper CI limit of an
  UNESTIMABLE ICC** (ICC 0.26, Kish mbar 2.06) per `UNESTIMABLE→CONSERVATIVE`, NOT a point estimate;
  the prior `deff=1` (ICC=0 floor) is superseded. Pin **`eff_leagues_2021 = 15 / deff_2021` at full
  precision (≈ 11.7)** — do **not** let "~12" circulate; the artifact carries the exact quotient and
  the guard checks it at ≥3 dp.
- Wire the roster-ICC / mbar / deff / eff-league canonicals to **`live`-source this artifact** (add
  the `live=` argument), check them at **≥3 dp** (not 2 dp) at **tol 1e-6**, and **add the file to the
  5× cross-process byte-check** (G10.4). This closes the dormant-tolerance blind spot above.

**Directional:** PASS iff the artifact exists (job-produced), the guard reads it live at ≥3 dp / tol
1e-6, and the byte-check covers it. Until then the youth-2020 cell's provenance is `OPEN` and **cannot
be cited as artifact-backed** — and the G10.5 table stays `PROVISIONAL-PENDING`.

### G10.7 — youth-2020 OPT-cell SE mismatch (carried backlog #2)

**What it is (scoped to the OPT cell — see G10.5's fix-3 correction).** On the youth-2020 **opt**
cell, the widening applies an **SD-derived eff_n** to a **percentile-derived interval**: bootstrap SD
**0.0479** (eff_n 88) vs percentile-CI half-width **0.081** (implied SE **0.0413**); the p sits at
~73% of [0.602,0.764] (p=0.720). Two SE definitions for one quantity — the standing "same quantity
carrying two values" watch-item. **This mismatch is on `opt`, not on `Δ_bal`** (whose CI half-width is
0.14, a different cell); `GATE6_5_REPORT.md:286` conflated them by asserting the opt mismatch blocks
the Δ_bal OVERTURNED status.

**Pre-registered requirement + directional (two parts, ordered):**
- **G10.7v — Δ_bal percentile-CI verification + ENDPOINT PRECISION (a G10.5 PREREQUISITE; round-2
  edit 1 + round-3 fix 1).** Because G10.5's *entire rule keys on the Δ_bal lower bound* — and deff\*
  = (p/(p−L₀))² is hyper-sensitive to L₀ because L₀ sits at zero — this is not a cheap add-on; it
  **runs before G10.5, alongside G10.6.** Two sub-checks:
  - **(v1) Construction.** Verify Δ_bal's endpoints [+0.001, +0.281] are a **pure percentile bootstrap
    CI** (not an SD-derived normal-approx, and not the SD↔percentile hybrid that produced the
    impossible "+0.004"). FAIL → Δ_bal inherits an opt-style SE-reconciliation prerequisite and G10.5
    is blocked.
  - **(v2) Endpoint precision — SAME convergence criterion as `B`.** Recompute the Δ_bal percentile CI
    under **≥5 independent seeds** (sims outside the loop, per G10.5). Report, for **BOTH** endpoints
    (L₀ and the upper endpoint), the **cross-seed spread in absolute terms AND as a fraction of the
    half-width 0.140**, and require it **< `conv_frac` (10%, i.e. < 0.014 absolute)** before G10.5 may
    run; otherwise `not-converged`, escalate `B`. Then compute **deff\* as an INTERVAL** — deff\*
    evaluated at `L₀`, `L₀ − spread`, `L₀ + spread` — and hand `[deff*_lo, deff*_hi]` to G10.5's
    directional rule. **Reference:** ±0.012 endpoint noise → deff\* ∈ **[0.83, 1.27]**, which
    straddles 1.12; so even a converged run can leave the youth-2020 verdict endpoint-noise-dominated
    (G10.5's `UNRESOLVED-ENDPOINT-NOISE` branch), and the arith-vs-Kish distinction can be live
    (`deff*_hi > 1.12`).
- **G10.7opt — opt-cell SE reconciliation.** Resolve the **opt** cell to **ONE** SE definition
  (SD-based throughout, or percentile-half-width throughout) — pre-registered here, not re-picked
  after seeing which keeps a result alive. Until reconciled, the **opt** cell's status stays `OPEN`.
- **Composite note:** the youth-2020 *bundle* leaving OVERTURNED needs BOTH the Δ_bal verdict (G10.5,
  which may itself be `UNRESOLVED-ENDPOINT-NOISE` per the deff\* interval) and the opt cell
  reconciled+admissible (G10.7opt); the two are tracked as **separate cells**, not merged.

### G10.8 — G9-OI-1: bundle `registry_key` cross-checks (carried)

**Naming (round-2 edit 4).** Uses the disambiguated names from the registry glossary (the internal project notes
SESSION HANDOFF): the **bundle key-map** (`registry_key`), distinct from the **hash-ledger**
(`models/_versions/registry.jsonl`) and the **doc-consistency canon** (`jobs/check_doc_consistency.py`
+ its baseline store `jobs/drift_baseline.json`).

**What it is.** The three single-pin bundle-key-map cross-checks (trade ×2, youth-2020) verify the
bundle **COPY STEP**, not the value — a single pin compared against itself.

**HAND-MAINTAINED-CANON FINDING (round-2 edit 4 — weakens "second independent pin").** The
doc-consistency canon is **mixed provenance**: the college/archetype canonicals are **artifact-derived
and live-wired** (`cfb_5_4b_perm.json`, `archetype_gap.json`, drift-checked at tol 1e-6), but the
**`startup_6_5` and `trade_verdict` blocks are read from `drift_baseline.json` with NO `live=`
wiring** and **no job writes them** (grep finds no producer) → they are **hand-maintained copies.**
Therefore a trade/youth-2020 "second independent pin" sourced from `drift_baseline.json` would be
**a second HAND-TYPED copy, not an independently-computed one** — it catches transcription drift, not
value error. The open item must say so.

**Pre-registered requirement + directional:** either **(a)** repoint each cross-check at a **second,
independently-COMPUTED pin** (a job-produced artifact — e.g. `design_effect.json` for youth-2020 per
G10.6, and a trade-engine-emitted artifact for the trade cells — NOT a second hand-typed baseline), or
**(b)** **relabel** it `copy_step` and stop counting it as value verification. PASS iff every bundle
key-map cross-check is either backed by an independently-computed second pin **or** explicitly
labelled `copy_step` — and the open item records that a hand-typed baseline does **not** satisfy (a).
This is a **gate blocker** (see CLOSURE DEPENDENCY), not backlog.

### G10.9 — PHASE-5 BACKLOG GATE (pre-registered results never printed)

Gate 10 must not close with pre-registered Phase-5 results still unprinted. Three sub-items, each
with its own printed PASS/FAIL and anti-vacuity inventory:

- **G10.9a — 5.4B remaining pre-registered results.** Diff `docs/PREREG_5_4B.md`'s pre-registered
  output list against what was actually emitted; **print the delta** (which pre-registered results
  were never printed) and then produce them. The perm artifact is pinned
  (`models/cfb_5_4b_perm.json`, B=20000, seed=1729); any result it implies but never surfaced is in
  scope. PASS iff the printed delta is empty.
- **G10.9b — era-decay check on market-efficiency residuals (Decision 8).** The SF-draft-position
  residual edges (QB **+12 shrinking**, RB **+23 growing**, TE **−55 persistent**, prefer the 2022+
  slice) assert **decay directions that were never formally tested**. Pre-register the era slices
  (e.g. ≤2021 vs 2022+) and a **residual×era interaction slope** with its CI; PASS reports the slope
  + CI per position (the "shrinking/growing/persistent" language must be backed by a signed slope CI,
  not asserted). Any significance threshold is `author-supplied`/`PROVISIONAL`.
- **G10.9c — full superflex translation table + Decision-5 stability test.** Decision 3's 1QB→SF
  translation exists **only** as market-efficiency residuals; the **full translation table** is
  unbuilt. Build it (corpus + DynastyProcess `value_2qb`, TE-premium leagues excluded when fitting
  TE), calibrated **2020–2022 only**, and run the **Decision-5 stability test across 2020–2024** (no
  pre-2020 back-projection). PASS iff the table is emitted AND the stability test prints per-season
  drift with a pre-registered stability tolerance (`author-supplied`/`PROVISIONAL`).

**IF A REMAINING RESULT CONTRADICTS A CURRENT HEADLINE (item 6 — pre-registered before running).**
A backlog result is not exempt from overturning a live claim, and the mechanism is fixed in advance:
- **Which claim yields, per sub-item.** G10.9a contradiction → the **5.4B college negative** ("no
  detectable lift / draft capital is not improved on; 0/3 rule; WY p 0.645") is the claim that yields.
  G10.9b contradiction → the **Decision-8 residual-edge directions** ("QB shrinking / RB growing / TE
  persistent") yield to the signed slope CI. G10.9c contradiction → the **Decision-3/5 "translation
  built only as residuals, calibrated 2020–2022, no back-projection"** claim yields to the built
  table + stability result.
- **Via what amendment (append-only, never in-place).** The contradicted claim's text is **not
  edited.** A **dated AMENDMENTS entry** is added here AND in the owning pre-registration
  (`PREREG_5_4B.md` for 9a; `ADDENDUM_B.md`/the Decision-8 record for 9b; the Decision-3/5 record for
  9c), with the original text preserved and a **live-status pointer** flipped (e.g. college negative →
  `CONTESTED`/`OVERTURNED as of <commit>`). The doc-consistency guard's "as-of-<commit> is an ancestor
  of HEAD" check applies to the new pointer.
- **Preconditions before any overturn (anti-vacuity + anti-fishing).** The contradicting result MUST
  (1) be **pinned** in a seeded, hashed artifact (`cfb_5_4b_perm.json` for 9a; a new pinned artifact
  for 9b/9c) and pass the 5× byte-check, and (2) **survive the same multiplicity control** as the
  claim it overturns — for 9a it joins the Westfall–Young family (a lone marginal that does not
  survive family-wise correction is a **flicker, not an overturn**, exactly as the R2 breakout-age
  p=0.013 is currently marked). A contradiction failing either precondition is recorded as
  `INFORMATIVE-BUT-NOT-DECISIVE`, not an overturn.

---

## CLOSURE DEPENDENCY (blockers on the gate, NOT backlog)

**Gate 10 CANNOT be marked CLOSED while either of these holds:**
1. **Gate 6.5 is REOPENED.** It is reopened as of 2026-07-29 (youth-2020 OVERTURNED). Its closure
   requires, on the youth-2020 **bundle**: **G10.6** first (pin `design_effect.json`) → **G10.5** (the
   outcome-ICC deff yields a widened **Δ_bal** LB > 0, re-pre-registered against the pinned artifact)
   → **G10.7** (the **opt** cell reconciled to one SE definition and admissible). Δ_bal (G10.5) and opt
   (G10.7) are separate cells; the bundle needs both. Until Gate 6.5 re-closes, Gate 10 stays open.
2. **G9-OI-1 is OPEN.** Its closure is **G10.8**.

These are listed here as **gate blockers**, deliberately not in the open-items backlog — a green run
on G10.1–G10.4 does not close Gate 10 while (1) or (2) stands. A test asserts the close routine
refuses to stamp CLOSED while `gate_6_5_state == REOPENED` or `g9_oi_1_state == OPEN`.

---

## Non-goals / constraints

- **No new science; no model logic changed to make a result come out clean.** Phase 10 audits Phases
  3–9. Where an audit forces a refit (G10.1) or recalibration (G10.3), that is a corrective re-pin of
  an existing model, pre-registered here as a branch — never a redefinition to survive a check.
- **Corpus size still binds (STANDING CONSTRAINT 1).** No Phase-10 result validates a startup
  strategy; the ICC work can only widen or narrow intervals, not manufacture units.
- **Frozen inputs.** All runs use the frozen nflverse (vintage 2026-07-29, sig `d9c462197311a92e`)
  and frozen corpus (2026-07-27); a signature bump invalidates the run and forces re-baseline.
- **Append-only.** Corrections to any approved criterion go in AMENDMENTS below, dated.

## Build order (after criteria are approved)

1. `jobs/leakage_audit.py` (G10.1) — inventory-driven, prints examined/unreachable counts.
2. `models/backtest_baselines.py` (G10.2) — binary-AUC/DeLong + ranking/clustered-bootstrap vs ADP
   and vs last-year PPG, with the Westfall–Young family-wise correction.
3. `models/calibration_check.py` (G10.3) — reliability + interval coverage on held-out seasons.
4. `jobs/repro_check.py` extension (G10.4) — full-pipeline 5× byte harness.
5. **Two G10.5 PREREQUISITES first, in either order:** (i) `models/design_effect.json` pin
   (**G10.6**, job-produced) and (ii) the **Δ_bal percentile-CI verification** (**G10.7v**). → THEN
   the dated amendment re-pre-registering G10.5's bounds against the pinned artifact → THEN
   `models/winrate_icc.py` (**G10.5**, convergence-`B` + ICC-interval estimability) → THEN the
   `opt`-cell SE reconciliation (**G10.7opt**).
6. `jobs/check_doc_consistency.py` bundle-key-map repointing + `startup_6_5`/`trade` live-wiring
   (G10.8, and the G10.6 live-source wiring).
7. `models/cfb_5_4b.py` / `models/adp_efficiency_retest.py` / a new SF-translation module (G10.9).
8. `tests/test_gate10.py` — one test per G10.1–G10.9 (incl. the anti-vacuity inventory assertions,
   the directional-branch assertions, the **G10.6+G10.7v-before-G10.5** sequencing guard, and the
   closure-dependency refusal).

**Do not write Phase-10 code until these criteria are reviewed and approved.**

## OPEN ITEMS (carried into / tracked by Phase 10)

- **Win-rate ICC unmeasured** → G10.5 (every project deff rests on the roster-strength proxy).
- **`design_effect.json` unpinned + 2020 roster ICC canon is 2-dp / no-live-wiring (B finding)** →
  G10.6 (hand-maintained baseline behind the OVERTURNED marking; dormant 5e-4 tolerance).
- **youth-2020 opt SE mismatch** → G10.7opt; **Δ_bal percentile-CI verification** → G10.7v (a G10.5
  prerequisite). Note the round-2 finding: **Δ_bal is OVERTURNED under both proxy weightings.**
- **G9-OI-1** → G10.8 (single-pin cross-checks verify copy, not value; and the trade/youth-2020
  canon is a **hand-maintained** baseline, so a same-source second pin is still hand-typed) — **gate
  blocker**.
- **Gate 6.5 REOPENED** — **gate blocker**, re-closes only via G10.6+G10.7v → G10.5 → G10.7opt.
- **G9.3 input-side exclusion deferral** → absorbed by G10.1.
- **Phase-5 pre-registered-but-unprinted results** → G10.9 (5.4B remainder, era-decay, SF table).
- **Verification items closed (round-2 edit 5):** (a) Phase-7 target dates **CONFIRMED** against
  `docs/PHASE7_PLAN.md:332–336` — criteria 3/4/9 target **Wed 2026-09-02**; criterion 8 installs
  2026-09-02 with the wake-test on the first sleep-through-Wednesday; in-season-5 on the **first
  in-season Wednesday after Week-1 MNF, ~2026-09-16**. (b) `z = −0.02` (archetype DeLong) is
  **DERIVED** (gap/SE = −0.00025/0.0153 = −0.016 ≈ −0.02), **not independently pinned** — recorded as
  derived, not added to the canon.
- **Outside Phase 10 (tracked, not gated here):** the three Gate-7 keyboard/observation items and
  `ingest/sleeper_live.py` (once the target-league draft date is known); MCP freshness is only as
  good as `jobs/refresh.py` actually running under launchd.

## AMENDMENTS

### A1 — 2026-07-29 · G10.1 first execution: leak found, audit design defect, refit applied

**(1) G10.1 audit DESIGN DEFECT, found on first execution (per-table → per-path).** The first run
tallied coverage per TABLE and printed "tables NOT examined = []" while the `fact_league_roster`
join in `adp_efficiency_retest._corpus_sf_adp` was never empirically tested — a per-table tally
cannot see an untested consumption PATH. **Fix:** coverage is now enumerated per CONSUMPTION PATH
(table × module.function × predicate); an empty unreachable list is reportable ONLY if every path is
tested (empirical assert-guarded execution, by-source fact check, or verified guard token); pure
dimensions (`dim_player.draft_year=2026`) are excluded from the disqualifier BY STATED RULE (they
leak only via a join to a 2026 FACT, which is the checked vector). First run: 9 tables / 116 columns,
1 leak + 1 unreachable, verdict masked-adjacent. Rewritten run: **15 paths (14 tested + 1 live-exempt),
0 untested, 0 leaks → PASS.**

**(2) Repo-wide unbounded-season sweep (`season >= N` with no upper cap).** Found (file:line → table
→ disposition): `adp_calibration.py:59/85/120/142` (fact_adp) — capped `<= last_complete_season` +
asserted; `:85` (rookie_slot_to_capital) was the live leak; `adp_efficiency_retest.py:74/99` (fact_adp)
and `:37` (fact_league_roster subquery) — capped + asserted; `projection.py:41/123` (fact_replacement)
— capped (defense-in-depth; table already ≤2025); `engine/trade_engine.py:45/50` (fact_adp) —
**INTENTIONAL-LIVE, not capped** (a live tool must price current-season market state; calibration
still inner-joins to forward-VORP ≤ last_complete_season). `startup_data.py`/`aging_curves.py` already
guarded (`assert_no_lookahead`/`exclude_seasons`). Pattern confirmed: `startup_calibration` had been
clean only because an inner join incidentally dropped 2026 — now made explicit via `assert
frame.season.max() <= last_complete_season` (derived, not hardcoded 2025).

**(3) The leak — REFIT-FORCING, reclassification DECLINED.** Per the pre-registered rule
(≥1 consumed column sourcing ≥1 label-window row → REFIT), `adp_calibration.rookie_slot_to_capital`
consumed 2026 rookie ADP (`fact_adp ⨝ dim_player`, `season>=2020`, no upper cap, no outcome join).
Recorded as REFIT-FORCING; reclassification to footnote is explicitly declined. **Accurate nuance:**
draft capital is not a future fantasy *outcome*, so this is not outcome leakage — BUT 2026 rookie ADP
is a **market price formed AFTER the 2025 season closed**, so fitting the slot→capital map on it
embeds **post-label market information**. "Practical bias likely small" is a **conjecture, not a
measurement** (so labeled). The fix caps the read at `last_complete_season`.

**(4) Refit quantification (full precision; item 5).** Raw join carried **124** rows > 2025; the
FITTED frame (after `rookie_round≤4` ∧ `nfl_round` not null) drops **59** rows (rr1:11, rr2:14, rr3:19,
rr4:15), n 414→355. Slot→capital map OLD (incl. 2026) → NEW (≤2025):

| rookie_rd | mean NFL rd OLD→NEW | %R1 OLD→NEW | %UDFA OLD→NEW | P25–P75 |
|--:|---|---|---|---|
| 1 | 1.3333 → 1.3714 | 0.7160 → 0.6857 | 0.0000 → 0.0000 | 1–2 → 1–2 (unchanged) |
| 2 | 2.1364 → 2.0811 | 0.3295 → 0.3378 | 0.0000 → 0.0000 | 1–3 → 1–3 (unchanged) |
| 3 | 2.8039 → 2.7349 | 0.1961 → 0.2169 | 0.0392 → 0.0241 | 2–3 → 2–3 (unchanged) |
| 4 | 3.5734 → 3.6094 | 0.1608 → 0.1608 | 0.1678 → 0.1797 | 2–5 → 2–5 (unchanged) |

Movement: mean NFL round shifts ≤ 0.069; %R1 / %UDFA shift ≤ ~3pp. **The load-bearing P25–P75 band
(the "uncertainty that propagates into every rookie-pick valuation," `adp_calibration.py:9`) is
UNCHANGED for all four rounds.** Downstream: because the propagated quantity (the P25–P75 slot→capital
distribution) is identical, the rookie-pick valuation inputs to the trade dual-pool are unchanged; the
sub-0.07-round mean shifts sit far inside that ~2-round spread. **Therefore no trade/startup claim
moves materially** — this is an INFERENCE from the P25–P75 invariance (a measurement), not a re-run of
the full trade MC; flagged as such. Nothing else in the project consumes the point means.
**Coefficient full precision (the point coefficients DO move even though the bands do not):** rr1
meanNFLrd 1.3333333333333333→1.3714285714285714, %R1 0.7160493827160493→0.6857142857142857; rr2
%R1-2 0.6931818181818182→0.7027027027027027; rr3 %R1 0.19607843137254902→0.21686746987951808, %R1-2
0.39215686274509803→0.42168674698795183, %UDFA 0.0392156862745098→0.024096385542168676; rr4 meanNFLrd
3.5734265734265733→3.609375, %UDFA 0.16783216783216784→0.1796875.

### A2 — 2026-07-30 · G10.2 target changed to Option B (returning-player forward backtest)

**NO G10.2 CODE WAS WRITTEN AND NO G10.2 RESULT EXISTED WHEN THIS TARGET WAS CHANGED.** The change is
forced by a **definitional impossibility**, not by an observed outcome: the original G10.2 pinned the
**rookie-hit** label (n=704, 43 hits) as the target while naming **last-year-PPG** (naive persistence)
as a co-primary baseline — and last-year-PPG is **undefined for rookies** (no prior NFL season). The
two co-primaries would run on disjoint populations. Original G10.2 text above is **intact** (append-
only); this amendment supersedes only its **target and population**. The 704/43 pin remains the
label for the **archetype-vs-capital** criterion (unchanged there); it no longer applies to G10.2.

**New G10.2 target/population (Option B).** Returning-player forward backtest: for player-season
`(p, Y)`, predict the season-`Y` outcome from information available before `Y`, on the population of
players that have a prior NFL season (last-year-PPG defined) and a season-`Y` preseason price.
Predictors: **engine projection** (5.5) vs **ADP** (season-`Y` AUG15 K) vs **last-year-PPG**
(`ppg_ppr(Y-1)`). Both named baselines are now defined on the same population.

**Readiness findings printed BEFORE criteria (reviewer items 1–3, this session):**
- **(1) ADP dependence — NONE.** `models/projection.py` imports only config/duckdb/numpy/polars;
  reads `fact_player_season_metrics`, `dim_player`, `fact_replacement`, `fact_injury`,
  `aging_deltas.parquet`. No `fact_adp`, no `models.adp_calibration`, no ADP feature/prior/shrinkage-
  target/blend (shrinkage target = positional-mean PPG, `projection.con_free`). So "engine vs ADP"
  is NOT a model-vs-its-own-input; BEATS is meaningful.
- **(2) Model-level lookahead — NO per-vintage refit natively.** `projection.py` has no `as_of`/
  vintage/refit parameter; it reads `aging_deltas.parquet` (fit by `aging_curves.run` over 2010–2025)
  and projects forward from `latest=max(season)`. `assert_no_lookahead` covers only
  `startup_data`/backtester, **not** projection. **Pre-registered choice: (a) PER-FOLD REFIT.** For
  each test season `Y`, refit the aging deltas + the projection's deterministic core on data through
  `Y-1` only and score `Y`. The MC interval layer is not needed for an AUC/ranking backtest (score
  ORDER only), so the tested predictor is the projection's deterministic point score refit per fold.
  Single-fit option (b) is rejected: it is in-sample at the fitting level and cannot support BEATS.
  This requires a per-vintage refit harness the engine does not currently have (a G10.2 build task).
- **(3) Population/events (printed before criteria so thresholds are not set at unsatisfiable counts).**
  Per season `Y ∈ 2019..2025`: player-seasons 201–217, events 39–49, base rate 0.19–0.24. **No fold
  has <5 events (min 39).** Total: **1457 player-seasons, 501 distinct players, 304 events, base rate
  0.2086.**

**Pre-registered method decisions (reviewer items 4–5; the pass/fail CRITERIA themselves are held
until items 1–3 are reviewed):**
- **(5) Primary target = forward per-position top-12 PPR finish (ONE, not "or").** `target(p,Y)=1`
  iff `pos_finish_ppr(p,Y) ≤ 12`, where `pos_finish_ppr` is the player's full-PPR fantasy-point rank
  **within position** for season `Y` — **per-position, NOT overall, NOT superflex-adjusted**
  (superflex changes QB VALUE, not per-position finish rank), scoring = the `ppr` profile. Chosen over
  forward-VORP-hit because it matches the existing project convention (`archetypes.py:64` uses
  `pos_finish_ppr ≤ 12`) and is scoring-transparent.
- **(4) Clustering = player (`player_uid`) for ALL interval estimation.** The same player recurs
  across ~2.9 seasons, so DeLong's independence assumption is violated and **closed-form DeLong is NOT
  used**. Paired clustered alternative: **player-clustered paired bootstrap of ΔAUC** (resample
  PLAYERS with replacement, carrying all their player-seasons together; recompute the paired AUC gap;
  percentile CI). Bootstrap sits OUTSIDE any inner loop (no sim-average inside), replicate count set
  by the same convergence criterion as G10.5's `B` (cross-seed CI-endpoint spread < `conv_frac`).
  This supersedes the plan's "DeLong" for the binary co-primary; the three-way BEATS/LOSES/
  INDISTINGUISHABLE rule and CLEARS-BAR/SPLIT/FAILS-BAR structure carry over unchanged.

### A3 — 2026-07-30 · G10.2 RESULT: FAILS-BAR (engine projection loses to both bars)

Harness `models/backtest_baselines.py` (per-fold refit on ≤Y-1; prints the pre-registered PASS
condition before the result). **Pooled 1454 player-seasons / 499 players / 301 events (base 0.2070)**
— 3 fewer than the pre-registered 1457/304 (the harness restricts `position IN (QB,RB,WR,TE)` on the
last-year metrics join and needs a parsed birthdate; disclosed, immaterial, no fold < 5 events).
Pooled AUC: **model 0.7179, ADP 0.7756, last-year-PPG 0.7402.** Player-clustered paired bootstrap
of ΔAUC (5 seeds, both converged):
- vs **ADP**: ΔAUC **−0.0577**, 95% CI **[−0.0874, −0.0277]** → **LOSES** (spread 4.0% of HW).
- vs **last-year-PPG**: ΔAUC **−0.0224**, 95% CI **[−0.0365, −0.0085]** → **LOSES** (spread 5.8% of HW).
→ **COMBINED = FAILS-BAR** → G10.2 does not clear → **STOP** (per the pre-registered gate rule).

**Fidelity disclosure (result NOT rescued/degraded to taste):** the first run keyed aging deltas by
position only (a shortcut, not projection.py's `(pos,age)`); fixing it to faithful per-(pos,age)
deltas moved the model AUC 0.7248→0.7179 (WORSE), i.e. against the model — so FAILS-BAR is not an
artifact of the shortcut. The pre-registered model score (E[VORP]) was NOT switched to a
better-looking one (e.g. proj_ppg) after seeing the result.

**Scope of the negative (honest framing).** This is a real converged negative: the projection's
deterministic core does NOT beat the market (ADP) or naive persistence (last-year-PPG) at ranking
**next-year per-position top-12 finish**. Two caveats travel with it: (a) the tested predictor is a
faithful DETERMINISTIC-CORE RECONSTRUCTION refit per fold, not `projection.py` itself (which is not
per-vintage-refittable); (b) the engine is a MULTI-YEAR dynasty E[VORP] tool, and this target is a
1-YEAR per-position classification — a specific, arguably unfavorable framing that rewards raw
production persistence and market wisdom. The result condemns the projection as a 1-year top-12
ranker vs these bars; it does not by itself adjudicate its multi-year dynasty purpose (a different
target, not tested here). Carried caveat from A2 item-2 also stands (hand-set constants asserted
pre-registered, not independently proven untuned).

### A4 — 2026-07-30 · G10.2 verdict refinements (post-FAIL; A3 stands, this appends)

**(item 1) Reconstruction fidelity MEASURED and ESTABLISHED — the negative is about the ENGINE.**
`jobs/g102_fidelity.py` scores `projection.py`'s actual `project_player()` and the reconstruction on
the SAME 571 players, SAME target (2025 outcome / 2024 base), MATCHED full-window fit: **AUC
projection.py 0.8868 vs reconstruction 0.8831 (ΔAUC −0.0036); Spearman rank-corr 0.9808; mean
|Δ| 7.41, max |Δ| 42.86 VORP; per-position top-12 classification differs for 10/571 (1.8%).**
Fidelity ESTABLISHED (Spearman ≥ 0.95 AND top-12 disagreement ≤ 5%). → the FAILS-BAR is a property
of the engine's projection, **not** a reconstruction artifact; the A3 caveat (a) is downgraded from
"weakens the claim" to "does not: the reconstruction tracks projection.py at Spearman 0.98."

**(item 3) HEADLINE = the matched-information-set last-year-PPG comparison.** Information-set
asymmetry: the model is restricted to ≤Y-1 by design, while **ADP is a market price formed at the
start of Y that embeds offseason information** (free agency, draft, camp) the model is DENIED — so the
−0.0577 ADP gap partly measures **denied information, not modeling skill**. The **last-year-PPG
comparison has MATCHED information sets** (both ≤Y-1), and there the model **LOSES by ΔAUC −0.0224,
95% CI [−0.0365, −0.0085] entirely below zero.** **THIS IS THE HEADLINE G10.2 FINDING:** with equal
information, the engine's projection does not beat naive persistence at ranking next-year
per-position top-12 — it is beaten. The ADP comparison is secondary and information-asymmetric.

**(item 4) The negative is CONSERVATIVE, not fragile.** The carried-over hand-set constants (k=10,
availability base rates, `availability_age_slope`, `wide_delta_se`, `recency_halflife`) are
untuned-but-unproven (A2 item-2); any residual tuning in them would have been chosen to help the
model, so it **favors the model**. The model loses anyway → the negative is conservative (a truly
untuned model would do no better, plausibly worse).

**(item 6) The 3-row population discrepancy (1457/304 → 1454/301) resolved — NOT fold-concentrated.**
The 3 dropped rows are player M15283 (position `XX`, unresolved) in folds 2022 & 2023, and M12752
(position `S`, safety) in 2019 — i.e. **concentrated in NON-SKILL positions** (exactly the intended
`QB/RB/WR/TE` filter), spread across 3 different folds (one each), not one fold. All 3 carry
`target=1` (a `pos_finish_ppr` artifact on non-skill positions). Their exclusion is correct;
immaterial (base 0.2070 vs 0.2086).

### A5 — 2026-07-30 · G10.2 downstream propagation + a PRE-REGISTRATION GAP

**Verbatim, what the G10.2 directional pre-registration says a FAILS-BAR implies for other claims:**
> "a `SPLIT` or `FAILS-BAR` — in particular failing to beat last-year-PPG (naive persistence) — is a
> first-class Phase-10 finding, reported with equal prominence to any win vs ADP, never footnoted or
> upgraded to BEATS."

That is the ENTIRETY of its downstream language: it governs **how the result is reported**, and is
**SILENT on propagation to other claims/outputs.** **Recorded as a PRE-REGISTRATION GAP** — the
implication is NOT backfilled here. Enumeration of every output that consumes projection values:

| Consumer | AFFECTED? | reason |
|---|---|---|
| Trade engine E[Δ] (both pools) | **UNAFFECTED** | uses `_forward_vorp()` (REALIZED forward VORP) + pick calibration, not the projection model (`trade_engine.py:42`); no `project_player`/`projections.md` reference |
| Startup backtester opponent models | **UNAFFECTED** | explicitly **never imports** the projection/aging artifacts — a documented leak control (`startup_backtester.py:864`) |
| Chat-assistant bundle | **AFFECTED** | ships `projections_established` PPG posteriors parsed from `projections.md` (`build_bundle.py:521`); the 1-year top-12 negative is decision-relevant to how these are presented — but the shipped claim is a MULTI-YEAR distribution with wide CIs, which the 1-year test does not directly falsify. What caveat (if any) the bundle must carry is the PRE-REG GAP above, to be closed by a future dated amendment, not decided now. |
| `jobs/refresh.py` | N/A (producer) | calls `projection.run()` to BUILD `projections.md`; it produces, not consumes |

### A6 — 2026-07-30 · G10.10 (NEW criterion) — multi-year forward-VORP backtest

**ADDED AFTER A FAIL ON THE PRE-REGISTERED 1-YEAR TARGET.** This is a NEW criterion, not an
amendment to G10.2. **The G10.2 1-year FAILS-BAR (A3/A4) STANDS AS THE PRIMARY RESULT regardless of
G10.10's outcome** — G10.10 tests a different, engine-favorable target (the projection's actual
multi-year dynasty purpose) and cannot overturn or dilute the 1-year finding.

**Counts printed BEFORE the pass criteria (same discipline as G10.2).** Target: forward-3yr
cumulative VORP (`sum vorp_ppr_total` over Y..Y+2) ranked **top-12 within position** per fold.
Population = the SAME returning-priced players (last-year-PPG + season-Y AUG15 K ADP), folds
**Y ∈ 2019..2023** (Y+2 ≤ last_complete_season 2025). Per fold: n 202–216, **events 48 each**, base
0.2222–0.2376. **Total: 1049 player-seasons / 412 distinct players / 240 events / base 0.2288. No
fold < 5 events.**

**Pre-registered pass criteria (mirror G10.2; NOT YET RUN).** Predictors refit per fold on ≤Y-1:
model = the projection's **cumulative forward E[VORP] over the window** (the engine's actual dynasty
output), vs ADP (−adp), vs last-year-PPG. Co-primary (2 tests, no pair multiplicity): ΔAUC via
player-clustered paired bootstrap (≥5 seeds, converged iff cross-seed endpoint spread < 10% HW).
BEATS iff CI-LB>0; LOSES iff CI-UB<0; INDISTINGUISHABLE iff spans 0. CLEARS-BAR / SPLIT / FAILS-BAR
as in G10.2; the 7-folds-not-independent note applies (412 players over 1049 seasons). Same
information-set asymmetry caveat: the ADP comparison is information-asymmetric; the last-year-PPG
comparison is the matched-information headline. **DO NOT RUN until these counts + criteria are
reviewed.** *(Counts in this A6 block are RETRACTED by A7 item 2 below — see the corrected 835/361/192.)*

### A7 — 2026-07-30 · Review follow-ups (trade-engine resolution, G10.10 retraction, bundle wired, fidelity scope)

**(item 1) TRADE ENGINE — contradiction RESOLVED; UNAFFECTED confirmed on a FULL READ.** Every input
`engine/trade_engine.py` consumes, with realized-vs-model marking:

| input | line | realized or model-derived? |
|---|---|---|
| `_forward_vorp()` streams `v0,v1,v2` | 24, 42 | **REALIZED** per-season VORP (`fact_player_season_metrics.vorp_ppr_total`) — NOT the projection model |
| `kadp` (K/AUG15 ADP) | 48–49 | **REALIZED** market price |
| `corpus` (draft positions) | 50–52 | **REALIZED** corpus draft slots |
| `radp` (rookie ADP) | 53–54 | **REALIZED** market price |
| `qbshare` | 164–167 | **REALIZED** corpus QB draft rate |
| `UNKNOWN_TICK=0.92`, δ∈{.70,.82,.90}, `jitter=15`, yr4 `×0.85` | 31, 128, 102, 92 | **HAND-SET assumptions** (not model-fit) |

**What the MC draws over (lines 77–94):** `_value_draws` bootstraps — each of the 10,000 draws samples
a RANDOM row from the EMPIRICAL pool of REALIZED `(v0,v1,v2)` streams of players who historically
occupied that ADP slot, then discounts. It draws over the **empirical realized-outcome distribution**,
NOT model posteriors. **Prospective mode:** there is NONE that consumes the projection — even for a
trade offered today, a pick/slot is priced by the empirical distribution of REALIZED historical
streams at that slot; `project_player`/`aging_deltas`/survival posteriors are never invoked.
**Resolving the standing-constraint #2 contradiction:** #2 says aging/survival posteriors, pool
choice, and the 0.92× are *unpropagated* — compatible with, and explained by, the engine **REPLACING
forward projection with realized streams** (aging/survival posteriors never consumed → uncertainty
unpropagated by OMISSION; pool choice and 0.92× ARE consumed as fixed inputs, shown as a 2-pool spread
/ single constant, uncertainty not propagated). **No path consumes projections/aging/survival → the
A5 `UNAFFECTED` marking STANDS** (now on a full read, not a grep).

**(item 2) G10.10 FOLD RANGE — RETRACTED and corrected (not silently replaced).** The A6 figures
**1049 player-seasons / 412 players / 240 events / base 0.2288 over folds 2019–2023 are RETRACTED**:
they used a target window `Y..Y+2` that (a) misaligns with the projection's strictly-future output
(`project_player` projects Y+1..Y+H) and (b) under the reviewer-correct `Y+1..Y+3` reading the 2023
fold requires 2026 (NOT_STARTED). **Corrected G10.10:** observation year Y ∈ **2019–2022**, target =
realized cumulative VORP over **Y+1..Y+3** (strictly future) top-12 within position; predictors known
through Y (last-year-PPG = ppg(Y), ADP(Y+1)), model = projection cumulative E[VORP] over Y+1..Y+3 refit
on ≤Y. **Corrected counts: 835 player-seasons / 361 distinct players / 192 events / base 0.2299**; per
fold n 202–216, **48 events each — BY CONSTRUCTION** (each fold has 4 positions each ≥12 players: QB
30–34, TE 28–34, RB 66–71, WR 75–81 → 12×4=48, not coincidental; the base rate is mechanically fixed
per fold). Pass criteria otherwise as A6. **STILL NOT RUN.**

**(item 3) BUNDLE CAVEAT CLOSED NOW (not deferred).** The G10.2 finding is persisted to the pinned
artifact `models/backtest_g102.json` (written by `models.backtest_baselines`) and READ live into the
`projections_established` claim's `must_carry` via `build_bundle._projection_must_carry()` (G9.4:
read, never restate) — so any response carrying projection values also carries "projection loses to
last-year-PPG under matched information sets (dAUC −0.0224, CI [−0.0365, −0.0085])". Test added:
`tests/test_bundle_gate8.py::g10_2` asserts the claim carries it AND is live-sourced (mutating the
artifact changes the bundle). The A5 pre-reg gap on the AFFECTED bundle consumer is thereby CLOSED.

**(item 4) FIDELITY SCOPE + MARGIN.** (a) A4 fidelity was measured under a **full-window fit on 2025
only**; per-fold-refit fidelity is now ALSO measured: **truncated fit ≤2021, score 2022 → Spearman
0.9724, top-12 disagreement 14/607 (2.3%) → per-fold-refit fidelity HOLDS.** (b) The `Spearman ≥ 0.95
/ ≤ 5%` bar was **set at MEASUREMENT time, not pre-registered** (labelled as such). (c) The
reconstruction runs **−0.0036 AUC BELOW** projection.py, so the real engine's matched-info PPG margin
would be ≈ **−0.0224 + 0.0036 = −0.0188**, still entirely below zero — the fidelity gap does NOT flip
the finding, and **the reconstruction is the CONSERVATIVE object.**

**(item 5) IN-SAMPLE vs OUT-OF-SAMPLE (own line).** Full-window 2025 AUC **0.8868** vs per-fold pooled
OOS **0.7179** ≈ a 0.17 gap — but that is almost entirely **POPULATION**, not optimism: on the SAME
1454 backtest population, full-window in-sample AUC is **0.7266** vs OOS 0.7179 → **optimism = +0.0087
only**. The 0.8868 is high because the 571-player fidelity population has a much lower base rate (0.079
vs 0.207 — more easy-to-classify low-end players). The model is NOT materially overfit.

### A8 — 2026-07-30 · CORRECTION: the A7-item-2 G10.10 retraction was REVIEWER-INDUCED, not a count defect

**Both the A7 retraction and this correction are preserved (neither deleted).** The A7 item-2
retraction of the **1049 player-seasons / 412 distinct players / 240 events / base 0.2288** figures was
caused by a **reviewer's incorrect impossibility claim** — the assertion that a `Y..Y+2` target's 2023
fold "requires 2026." It does not: `Y..Y+2` for Y=2023 is seasons **2023/2024/2025, all complete**.
The 1049/412/240/0.2288 counts (5 folds, 2019–2023) were **VALID**; nothing was impossible. The error
was the reviewer's, not a defect in the counts.

**Target window decided on SUBSTANCE (not on the error) — pre-registering `Y..Y+2`.** Reasoning:
- **Aligns with the engine's actual forward output.** From base season Y−1, `project_player` t=1..3
  projects seasons **Y, Y+1, Y+2** (t=1 is Y, not Y+1) — so the projection's cumulative forward
  E[VORP] over the horizon IS the `Y..Y+2` window. The earlier "the projection is strictly-future
  Y+1..Y+3" reasoning (A6/A7) was also wrong on the same off-by-one.
- **It is the dynasty question:** value from the ACQUISITION point — you own the player for season Y
  onward. `Y+1..Y+3` answers a different question ("value starting a year from now") and costs a fold.
- **Leakage-safe:** with the ≤Y−1 fit window, `Y..Y+2` is strictly post-fit (all three seasons > Y−1).
- **More data:** 5 folds / 1049 player-seasons / 240 events vs 4 folds / 835 / 192.

**Therefore G10.10 REVERTS to `Y..Y+2`, and the original counts are REINSTATED BY REFERENCE to this
correction: 1049 player-seasons / 412 distinct players / 240 events / base 0.2288, folds 2019–2023,
48 events/fold by construction.** (The A7-item-2 corrected block `835/361/192`, folds 2019–2022, is
the `Y+1..Y+3` alternative and is NOT the pre-registered target.) **G10.10 STILL NOT RUN.**

### A9 — 2026-07-30 · G10.3 RESULTS (both components; width printed before the verdict stands)

`models/calibration_check.py`. Prints the pre-registered PASS condition before each result.

**Component 1 — survival Clock-A P(relevant) OUT-OF-SAMPLE reliability: PASS-BUT-UNINFORMATIVE**
(corrected down from an initially-overstated "PASS" once the WIDTH was printed). n=14,574 obs / 2,353
players / 1,661 events, cohorts 2010–2025, player-clustered (5×1000); 91% of predictions from full
stratum×N cells (earlier cohorts only — not the in-sample Beta tautology). **Slope 1.0348, 95% CI
[0.9342, 1.1332]** (half-width 0.0995); **intercept +0.0045, CI [−0.0050, +0.0141]**; **ECE 0.0114**
vs the perfect-calibration null 95% band **[0.0027, 0.0078]**, P(null≥obs)=0.000. Verdict logic
(archetype standard): a **decision-relevant** miscalibration is a slope outside **[0.90, 1.10]** or
ECE > **0.03** (author-supplied, set-at-measurement). The slope CI's upper 1.133 **spills past 1.10**
→ underpowered to exclude a decision-relevant slope miscalibration. **ECE IS A DETECTED DEVIATION, NOT
AN ABSENCE:** ECE 0.0114 vs permutation null [0.0027, 0.0078], p=0.000 — **miscalibration IS DETECTED,
at ~1 percentage point**; its *decision-relevance* is assessed against a band (slope [0.90,1.10], ECE
≤ 0.03) **set at measurement time and labeled unsourced/author-supplied**. "Sub-decision-relevant"
means the detected ~1pp deviation is below that unsourced band — it does **NOT** mean "no
miscalibration found." Net: **not a FAIL** (magnitude below the unsourced band), but a real deviation
IS present AND the CI admits decision-relevant values → **UNINFORMATIVE, not a clean PASS.**

**Component 2 — projection PPG 90%-interval COVERAGE (option (a) clarified): PASS-CONSERVATIVE.**
**Option (a) = (a)(i):** an MC-interval layer on the existing per-fold RECONSTRUCTION (projection.py
is NOT per-vintage-refittable, which is why the reconstruction exists); the coverage result therefore
**inherits the reconstruction's fidelity scope** (Spearman 0.9724 / top-12 2.3% at ≤2021→2022).
Pre-registered before running: nominal 90%, PASS band = player-clustered coverage 95% CI CONTAINS
0.90; ABOVE 0.90 (too wide) = CONSERVATIVE footnote, BELOW (too narrow/overconfident) = ANTI-
CONSERVATIVE FAIL. Result: n=3,294 / 1,064 players / effective_n≈770; per-fold coverage 0.874–0.937;
**pooled 0.9132, player-clustered 95% CI [0.9019, 0.9240]**.
**FINDING (stated alongside the marking, NOT as a footnote to it): the intervals are OVER-COVERING.**
The coverage CI [0.9019, 0.9240] **EXCLUDES the nominal 0.90** — so the projection's nominal 90%
intervals are **~91.3% in practice, SYSTEMATICALLY wider than stated**: stated uncertainty does NOT
match realized uncertainty. The direction is **conservative (safe — not overconfident)**, so it is a
**PASS-CONSERVATIVE, not a FAIL** — but "well-calibrated" would be wrong; the honest read is
**mis-stated-but-safe**. (Population note: coverage ran on all 3,294 returning player-seasons, not the
1,454 ADP-priced G10.2 population — coverage needs no ADP.)

**(item 3) DIAGNOSTICS PINNED (no longer session-only).** Persisted to `models/calibration_g103.json`
(written by `models.calibration_check.regenerate()`, verified byte-identical across runs) with the
survival slope/CI/intercept/ECE/null and the coverage/CI/effective_n/design_effect/per-fold. **Design-
effect correction:** the reviewer's "≈1.9 against 1454" assumed the G10.2 population; coverage ran on
**n=3,294** returning player-seasons (coverage needs no ADP) with **effective_n≈769.5 → design effect
≈ 4.28** (consistent with variable ~3.1 seasons/player + whale players). Added to the **5× cross-
process byte-check** (`tests/test_reproducibility.py`, `G103_ART`). Live doc-consistency-canon wiring
(the `live=` + ≥3 dp presence checks) is bundled with the **G10.6** canon-wiring mechanism (which
builds the same for `design_effect.json`); PHASE10_PLAN is not in the guard's `DOCS` set, so
half-wiring a presence check now would break the guard — the byte-check + pinned artifact already take
these out of "session-only," and G10.6 completes the canon wiring.

**G10.3 status: no FAIL. Component 1 UNINFORMATIVE, component 2 conservative-PASS (over-covering).**

**(item 4, backlog print-only) TRADE ENGINE is PROSPECTIVE-CAPABLE VIA COMPARABLES.** Recorded in
`engine/trade_engine.py` docstring and the internal project notes standing-constraint #4: a trade's valuation draws on
the realized VORP distribution of COMPARABLE players (same ADP slot), NOT the realized future of the
specific traded players — so the engine can value a trade offered today, and the corpus E[Δ] is a
PROSPECTIVE valuation, not a hindsight evaluation of a historical trade.

### A10 — 2026-07-30 · G10.4 first run (model + calibration stage byte-identical; full-pipeline extension named)

Pre-registered PASS condition printed before the result. **`tests/test_reproducibility.py` (5 fresh
cross-process refits): PASS — all 10 artifacts byte-identical**, i.e. the 9 model artifacts (aging×2,
survival clockA/B/curves, cox×2, cfb_5_4b_perm, archetype_gap) **+ the newly-added
`calibration_g103.json`** (G10.3 diagnostics now under the 5× check). The model+calibration STAGE is
byte-reproducible.

**Anti-vacuity — this is NOT the full G10.4 PASS; the remaining stages are NAMED, not silently
passed.** Stages still to be unified into ONE end-to-end harness (each prior-verified separately, not
re-run under this harness): `transform.warehouse` (`warehouse.db`) + `transform.metrics` (Phase-7
hermetic, 5× byte-verified); `engine.trade_engine` (`trade_verdict.json`, G6); `jobs.build_bundle`
(`assistant_bundle.{json,md}`, G8, with a `generated_at` strip); MCP payloads (G9.6b, 5× byte-
identical). Waiver: the residual live `nfl.load_teams` (32-row static). **G10.4 status: model+
calibration stage PASS; end-to-end unification is the remaining build — no FAIL.**

### A11 — 2026-07-30 · Two G10.4 pre-checks before the unification

**(item 1) COVERAGE deff 4.28 was the KISH CEILING, not the design effect — but over-coverage STANDS
(right axis).** ICC of the binary coverage indicator by clustering axis: **player +0.1173 (1064
clusters) DOMINATES**; season +0.0048 (7); position +0.0596 (4). Player is the largest, so the
committed **player-clustered** CI is on the CORRECT axis — over-coverage is NOT a wrong-axis artifact:
under the dominant player axis the coverage CI **[0.9013, 0.9236] still EXCLUDES 0.90** (coverage
0.9126). **Design-effect corrected:** the reported "4.28" is the **Kish ICC=1 CEILING**
(`effective_n_kish` / n); the **MEASURED** design effect from ICC 0.1173 and mbar 3.1 is
**1 + (3.1−1)×0.1173 ≈ 1.25** (consistent with Gate 6.5's manager-clustering 1.1–1.3, as the reviewer
suspected). Both are now in `calibration_g103.json` (`design_effect_measured` 1.25 vs
`design_effect_kish_max` 4.28). **Over-coverage finding STANDS; the alarming 4.28 does not.**

**(item 2) WAIVER PROVENANCE — `nfl.load_teams` is a NETWORK call RIGHT NOW (cache MISSING), a real
scope limit.** Reason: the 32-row static team lookup (abbr/name/conf/division) for `dim_team`
(`transform/warehouse.py:321–329`). Set by: the Phase-7 hermetic-build work (PHASE7_PLAN §item, the
"cache once so the build is network-free after" comment). **Network/hermetic status: NON-HERMETIC in
the current repo state** — the cache file `data/raw/nflverse/teams/all.parquet` **does NOT exist**, so
the next warehouse build calls `nfl.load_teams()` **live over the network**. What it exempts: the
byte-identity of **`dim_team`** and therefore **`warehouse.db`** across fresh processes. **Recorded as
a SCOPE LIMIT / FAIL precondition on G10.4's warehouse stage, NOT a silent waiver:** the warehouse
stage cannot be byte-checked hermetically until the teams cache is frozen (call once + commit, or
add to `data/raw/nflverse/FROZEN`).

### A12 — 2026-07-30 · G10.4 unification RUN → FAIL (warehouse stage non-hermetic), stopped

`jobs/g104_repro.py` — the full-pipeline unification harness. Printed the pre-registered PASS
condition + the full 7-stage inventory (ingest→warehouse→metrics→models→engine→bundle→mcp) BEFORE the
result, then **fail-fast on the hermeticity precondition**: **teams cache MISSING → the
`transform.warehouse` stage is NON-HERMETIC** (`nfl.load_teams()` live network at `warehouse.py:326`)
→ `dim_team`/`warehouse.db` are not byte-checkable across 5 fresh processes. Per the pre-registered
directional rule ("Gate 10 does not close over a non-deterministic stage; a stage that cannot be made
deterministic must be named + fixed, not silently passed"), **G10.4 = FAIL, STOP.** The 5× rebuild
was deliberately NOT run (it would consume a live network call, not prove byte-identity). Verified
this phase: the **models + `calibration_g103` stage is 5× byte-identical** (A10). **FIX before
G10.4 can pass:** freeze the teams cache (`nfl.load_teams()` once → commit `data/raw/nflverse/teams/
all.parquet`, add to the FROZEN manifest), then re-run the harness + the downstream engine/bundle/mcp
5× byte-check. Not fixed here (freezing consumes a network call — surfaced as the FAIL, per the
stop-at-FAIL rule, rather than silently patched).

### A13 — 2026-07-30 · G10.4 FIX: teams cache frozen, build-time assertion added, hermeticity claims corrected

**(item 1) Teams cache FROZEN with full provenance.** `nfl.load_teams()` run ONCE; wrote
`data/raw/nflverse/teams/all.parquet`. Provenance (in `FROZEN.json.teams_lookup`): **nflreadpy
0.1.5**, **fetched 2026-07-30T19:28:31Z**, **rows 36** (NOT the "32" the prior waiver stated — incl.
historical/relocated abbrevs), **sha256 `1d1d105ff0b0fca8806bfa047c96ef001d150c0bcbba481db5babbafa1f36636`**,
12,024 bytes. **VINTAGE MISMATCH MADE VISIBLE:** fetched **2026-07-30 = one day LATER** than the
2013-2025 raw vintage **2026-07-29**; teams data is static so content is near-certainly identical to a
2026-07-29 fetch, but the later provenance is recorded explicitly, NOT absorbed into the 2026-07-29
vintage.

**(item 2) Manifest-existence assertion is now part of the BUILD.** `transform.warehouse.
assert_frozen_files_exist()` runs at the top of `run()`: it reads `FROZEN.json` and raises if any
named file is absent. **The failure was never the network call — it was that a documented
"network-free after caching" claim went UNVERIFIED for phases 3-9 because nothing checked the cache
existed.** This check is in the build, not in G10.4.

**(item 3) Hermeticity claims audited (grep, file:line, true/false).** ONLY `load_teams` was false;
every other claim rests on a cache that EXISTS:
- `transform/warehouse.py:345` "cache load_teams once → network-free after" — **FALSE** (cache never
  persisted → live call every build, phases 3-9). CORRECTED in place (dated) + `log.info "fully
  hermetic"` → `log.warning "was MISSING → LIVE call"`.
- `transform/warehouse.py:75` bulk loads via `_cached_nflverse` — **TRUE** (pbp 16, rosters_weekly
  16, snap_counts 14, schedules 1, all present).
- `transform/identity.py:275` player_stats — **TRUE** (reads `data/raw/nflverse/player_stats/*.parquet`,
  16 files present, `.exists()`-guarded; Defect-2 fix landed).
- `docs/PHASE7_PLAN.md:192-193,277` — TRUE for the historical inputs it verified; :277 already LISTED
  `load_teams:298` as a defect but the fix (cache-once) was left incomplete (never persisted).
- the internal project notes / `docs/ADDENDUM_B.md:206` "build hermetic" — TRUE for historical inputs but
  OVERBROAD as a blanket claim (the teams path was live). `FROZEN.json._what` corrected to
  "hermetic ONLY IF every named file exists (asserted at build start)."
- **No OTHER claim rests on a missing file** — teams was the sole gap.

**(item 5, print-only) BOTH design effects recorded with meanings distinguished.**
`calibration_g103.json`: **`design_effect_measured` = 1.25** (from ICC 0.117, mbar 3.1 — the real
design effect) vs **`design_effect_kish_max` = 4.28** (the Kish ICC=1 CEILING, an upper bound assuming
perfect within-player correlation). **4.28 was briefly recorded (A9/A10 commit) as `design_effect` as
if measured — that was wrong and is corrected here.** **Confirmed: NO interval anywhere consumed
4.28** — the coverage CI [0.9013, 0.9236] is a player-clustered BOOTSTRAP (resampling players
directly, `calibration_check.py:313`), never a deff-scaled interval; grep finds no consumer of the
calibration deff.

### A14 — 2026-07-30 · G10.4 end-to-end RE-RUN → FAIL (dim_player build is non-deterministic)

`jobs/g104_repro.py fullrun(5)` — with the teams cache frozen, the hermeticity precondition PASSES
and the harness ran the 5× full-pipeline byte-check (warehouse→metrics→models→engine, 5 fresh
processes). Pass condition + 7-stage inventory printed before the result. **RESULT: FAIL.** The
**warehouse CONTENT differs across all 5 processes** (5 distinct hashes), and every model built on top
inherits it (`aging_curves.parquet` alone matched — it doesn't depend on the affected columns).

**Localized (per-table, 2 fresh rebuilds):** `dim_team` is now **DETERMINISTIC** (`142a7ca23194`
both — the teams-cache freeze WORKED, items 1-3 validated). The non-deterministic tables are
**`dim_player`** (12,685 rows, same count, different content hash) and everything keyed off it:
`fact_player_season`, `fact_player_season_metrics`, `fact_player_week`, `fact_player_week_metrics`,
`fact_injury`, `fact_replacement`. Deterministic: dim_season/week, fact_adp, fact_dynasty_value,
fact_league_*. **ROOT CAUSE: `transform/identity.py` resolves `dim_player` non-deterministically**
across processes (a non-deterministic tie-break / unordered read / dict-iteration when choosing the
representative attribute per player — the same CLASS as the Phase-7 unordered-read defects, but on the
IDENTITY build, which was never itself byte-checked).

**META-FINDING (why this survived to Phase 10):** the Phase-7 "5× byte-match verified" claim covered
the **model artifacts built on a FIXED `warehouse.db`** — the warehouse/identity **REBUILD** was
never byte-checked across fresh processes. G10.4's full-pipeline extension is exactly what exposed it.
So the downstream model artifacts are deterministic GIVEN a fixed warehouse, but the pipeline is NOT
reproducible from scratch.

**G10.4 = FAIL, STOP** (Gate 10 does not close over a non-deterministic stage). **FIX (not applied —
surfaced per stop-at-FAIL):** make `transform/identity.py`'s `build_dim_player` deterministic (sort
source rows + deterministic tie-break before the per-player representative pick / uid assignment),
then re-run `g104_repro.fullrun(5)` — expect dim_player + all player-keyed facts + models to collapse
to one hash each. The `dim_team` freeze (A13) stands as verified.

### A15 — 2026-07-31 · G10.4 FIX APPLIED → full-pipeline byte-check PASS (byte criterion MET)

Per Colby DECISION 1 (`docs/review/NOTES.md` NOTE 0012). **A14's "`dim_player`-only" root cause was
INCOMPLETE** — a two-session adversarial review (`docs/review/NOTES.md` 0002–0011) found **three
independent nondeterminism classes across ≥4 sites**, each fixed by the pre-registered *ORDER BY /
sorted* remedy (determinism-only, NO model logic changed, NO single-thread pin — sorted input proven
byte-invariant under 1 AND 8 threads):
- **`dim_player` representative/base tiebreak** (`identity.py:180` `_canonicalize` base, `:196-198`
  representative pick): total-order `mfl_id` tiebreak + null/unique asserts (S1/S2, NOTE 0004).
- **C1 — ordinal-rank ties** (`warehouse.py:156` `pos_finish_ppr`; `metrics.py:140` `wk_pos_rank`):
  pre-sort by the window key + `player_uid` so `rank("ordinal")` breaks ties deterministically.
- **C2 — float aggregation-order (non-associative sums)** (`warehouse.py:149` fp sums;
  `metrics.py:184` season aggregates): deterministic sort of the INPUT before each `group_by`, with a
  per-site key-uniqueness assert. Root cause was unordered `select *` feeding an order-sensitive float
  reduction — the pre-registered class verbatim; single-thread does NOT fix it, ORDER BY does.
- **C3 — replacement-band membership** (`metrics.py:148`): follows from C1; band sorted before the mean.

**RESULT: `jobs/g104_repro.fullrun(5)` = PASS — all 8 stages byte-identical across 5 fresh processes**
(WAREHOUSE content, aging_curves, survival_clockA, cox_age_capital, cfb_5_4b_perm, archetype_gap,
calibration_g103, trade_verdict). The pre-registered G10.4 PASS condition is MET end-to-end.

**SCOPE (stated per DECISION 1):** cross-process byte-reproducibility of the FULL pipeline
(warehouse/identity build → metrics → models → engine) — the FIRST time the warehouse/identity REBUILD
is covered. The Phase-7-through-9 "5× byte-match verified" claim covered MODEL ARTIFACTS on a FIXED
`warehouse.db` only (the A14 META-FINDING). Bundle+MCP carry named `generated_at` timestamps (G8/G9.6b,
not re-hashed here). The `nfl.load_teams` waiver is closed (A13 teams-cache freeze).

**Verification:** per-site column sweep (`jobs/g104_colsweep.py`, 5 processes byte-identical, RANK-ONLY
completeness verdict → `_nflverse_leaders` S4 confirmed report-only/non-leaking) + flip enumeration
(NOTE 0010): **0 skill-position top-12 flips**, archetype gap byte-identical
(−0.0002462794215951636), both trade verdicts preserved.

**The fix is in the WORKING TREE (3 source files: `transform/identity.py`, `transform/warehouse.py`,
`transform/metrics.py`), UNCOMMITTED — the PASS is contingent on these; committing is Colby's.** The
A14 FAIL text above is preserved (append-only). **Consequence for downstream published values → see
the trade-canon re-pin (Colby DECISIONS 2–3, in progress in the review channel): the determinism fix
canonicalizes vorp_ppr_total (previously build-nondeterministic), which propagates to the trade E[Δ]
canon.**

### A16 — 2026-07-31 · Trade E[Δ] canon RE-PINNED (Colby DECISIONS 2–3, reconfirmed NOTE 0016)

Per Colby (review-channel NOTES 0012/0016) after the G10.4 fix (A15) canonicalized `vorp_ppr_total`.
Originals PRESERVED (append-only); `drift_baseline.json._superseded_2026_07_31` + this block.

**NEW DEFINITION (not a correction — the old figures had NO producer).** −76.1/+8.6 were
UNREPRODUCIBLE HAND-TYPED figures: grep of the repo AND its full history found no producer for the
200-seed mean. The canonical 200-seed distribution is hereby DEFINED by **`jobs/g104_trade200.py`**
(seed protocol `numpy.random.default_rng(s) for s in range(200)`, δ=0.82, deterministic warehouse) →
persisted to **`models/trade_mc200.json`**:
- **corpus: mean −77.87029531550294, sd 3.5215, CI [−84.48047796921138, −71.39707944930845],
  sign 200/200 → 1.11 wins.**
- **consensus: mean +10.337131397806298, sd 2.8729, CI [4.865953577847554, 16.07215611866746],
  sign 200/200 → package wins.**
Registry re-pinned to these (displayed 1 dp: corpus −77.9 [−84.5,−71.4]; consensus +10.3 [+4.9,+16.1]);
the doc-consistency guard is now **LIVE-WIRED** to `trade_mc200.json` (trade block no longer copy_step;
registry == artifact, drift 0). **The reviewer's earlier "−80.0 / 3.9 / 59%-of-band" was WRONG** — it
compared the 200-seed MEAN (−76.1) to a single-seed `run()` POINT (−80.0, itself an RNG-consumption-
order artifact: a FRESH seed-1729 corpus = −76.9321). cc flagged it (NOTE 0013); the reviewer owned it
(0014).

**COND 1 — full distribution byte-checked across 5 fresh processes** (`g104_trade200.bytecheck`): the
ENTIRE artifact (mean + sd + CI endpoints + all 200 seed values) is byte-identical, ARThash
`34f0d82b518a4057` on all 5. Not just the mean — the CI endpoints are byte-stable too.

**COND 2 — seed protocol recorded (above); this is a NEW DEFINITION, not a recovery.**

**DECISION 3 — MC-band caveat.** Build-rebuild nondeterminism was a REAL, UNMODELED source the
per-seed "MC precision band" (sd ≈3.5) never captured. Its magnitude: the RANGE of the 200-seed MEAN
over **3 pre-fix builds** was **≈1.45** (corpus −77.8703 / −77.4793 / −76.4167; consensus
+10.3371 / +11.5039 / +11.8387 → 1.5016), i.e. **~22% of the band half-width 6.65**. It is a rough n=3
magnitude and it is **HISTORICAL: eliminated going forward** (the build is now deterministic). Every
trade verdict published pre-fix understated its own uncertainty by ≈1.45.

**COND 2b — COMMON-MODE (not independent pools).** corpus moved +1.77, consensus +1.74 — near-identical
because both pools join the **same** `_forward_vorp()` streams (`fact_player_season_metrics.vorp_ppr_total`,
the quantity the fix changed) in `trade_engine._pools()`. ONE upstream change → two outputs. The two
pools are NOT independent confirmations of each other; the amendment says so.

**TASK-1 EXPOSURE.** −76.1/+8.6 first pinned into `drift_baseline.json` at **83d58c0 (2026-07-29
15:28:10)**, live canon through HEAD **01a8a85 (2026-07-30 15:51:35)** — ~24 commits. Shipped in
`exports/assistant_bundle.{json,md}`, the internal project notes, `docs/PHASE8_PLAN.md`, `docs/GATE9_REPORT.md`,
`docs/ADDENDUM_B.md`. The committed `exports/trade_verdict.json` over that window stored −78.4 (a
single-seed point, different statistic). **Original derivation of −76.1/+8.6 is NOT RECOVERABLE** (no
producer ever existed).

**TASK-4 NON-OVERLAP (re-pinned).** corpus CI-hi −71.3971 < consensus CI-lo +4.8660; separation
**76.2631** (OLD 72.8), sign-consistent 200/200 each. The re-pin does NOT move the verdict — it widens
the separation.

**GUARD GENERALIZATION (DECISION-2 wiring).** `trade_verdict` is now live-wired (above). `startup_6_5`
and the archetype test-set SE/CI/corr + gap-CI remain **explicitly `copy_step`** (labeled in the
registry): startup HAS a producer (`startup_backtester.py`→`startup_strategy.md`, values agree,
frozen_by_design) but its artifact is markdown, not a clean value store; the archetype SE/CI HAVE a
producer (`measure_sampling_variance.archetype_testonly`) but it is not persisted to any artifact
(`archetype_gap.json` holds only the gap/AUCs). Wiring those cleanly (emit JSON from each producer) is a
tracked follow-up; until then the registry records that their checks verify the COPY STEP, not the VALUE.

### A17 — 2026-07-31 · EXPOSURE BOUND for the superseded trade E[Δ] −76.1/+8.6 (Colby's open hole)

Complete accounting of the superseded hand-typed canon, per Colby's standing request.

**First PUBLISHED (any surface):** commit **`8d54206` (2026-07-29 11:28:52 −0400)** — −76.1 entered
the internal project notes prose (the "Phase 6.5 backtester + Phase 7 refresh" commit).
**First pinned as REGISTRY CANON:** commit **`83d58c0` (2026-07-29 15:28:10 −0400)** — added to
`jobs/drift_baseline.json.trade_verdict.corpus_e_delta` (the doc-consistency registry).
**Last LIVE-CANON commit:** **`01a8a85` (2026-07-30 15:51:35 −0400)** — the commit immediately before
the re-pin (`cadac2e`, 2026-07-31).
**Live-canon span:** the value was unchanged in the registry from `83d58c0` to `01a8a85` = **24 commits**
(`git rev-list --count 83d58c0~1..01a8a85`), ~**24.4 hours** as formal canon (~28.4 h published counting
the internal project notes prose from `8d54206`). Verified it was NEVER modified in that span: `git log -S'corpus_e_delta'
-- jobs/drift_baseline.json` returns only `83d58c0` (introduce) and `cadac2e` (re-pin).

**Every artifact/export that SHIPPED it (git-verified at `01a8a85`):**
- `jobs/drift_baseline.json` — the registry canon.
- `exports/assistant_bundle.{json,md}` — the shipped chat-assistant bundle; structured block AND flat
  list (`trade_corpus_e_delta: -76.1`, git-confirmed).
- **MCP payloads** — `jobs/mcp_server.py trade_delta()` serves `_fact("trade_corpus_e_delta")` from the
  bundle, so every MCP client received −76.1.
- the internal project notes, `docs/ADDENDUM_B.md`, `docs/GATE9_REPORT.md`, `docs/PHASE8_PLAN.md` — prose / gate records.
- **NOT** `exports/trade_verdict.json`: it stored `e_delta_082` (a single-seed point, −78.4), a
  DIFFERENT statistic — never the −76.1 mean.

**How −76.1/+8.6 were originally arrived at: NOT RECOVERABLE.** No producer for the 200-seed mean exists
in the repo OR its full history: `git log -S'range(200)' --all -- '*.py'` is EMPTY; the only
`sign_consistency` commit (`bd0dcee`) added the guard FIELD, not a computation. The value was hand-typed
into the internal project notes (`8d54206`) and the registry (`83d58c0`). **The first reproducible producer is
`jobs/g104_trade200.py`, created 2026-07-31 (this round)** — so the re-pinned −77.87029531550294 is a NEW
DEFINITION (A16), not a recovery. The exposure hole is now bounded and closed; it can never recur for the
trade block because the canon is producer-backed and live-wired.

### A18 — 2026-07-31 · G10.5 decision rule: PR-1 CI-vs-interval + terminal case + pre-run blast radius

Colby-authorized (review-channel NOTE 0024) BEFORE any G10.5/G10.6 producer runs. The ORIGINAL G10.5
directional rule (lines 363–373 above) and G10.5's numeric table are PRESERVED (append-only); this
amendment supersedes only the branching and adds two pre-registered pre-run conditions.

**PART 1 — PR-1: branch on `d_out`'s CI, not its point (reviewer NOTE 0022, cc 0023).** The original
rule keyed a SCALAR `d_out` against the deff\* INTERVAL, but `d_out` is a manager-clustered
bootstrap estimate with its own sampling CI (endpoints already tracked by the convergence rule). In
deff units that CI is not negligible: with Kish mbar 3.68, an outcome-ICC half-width up to the
`icc_hw_max=0.20` gate maps to a deff half-width ≈ (3.68−1)×0.20 ≈ 0.54 — comparable to the reference
deff\* interval [0.83,1.27] (half-width 0.22). So a STAYS/LEAVES could be declared on a point whose CI
overlaps deff\*. **Superseding rule:** let `[d_lo, d_hi]` be `d_out`'s manager-clustered bootstrap CI
and `[deff*_lo, deff*_hi]` the G10.7v interval.
- **`d_lo > deff*_hi`** → **STAYS OVERTURNED** (d_out's CI clears the interval above).
- **`d_hi < deff*_lo`** → **LEAVES OVERTURNED** (→ at most `AT_RISK`/`ESTIMATED`; d_out's CI clears below).
- **the two CIs OVERLAP** → **INDETERMINATE**: report `UNRESOLVED-ENDPOINT-NOISE` **or**
  `UNRESOLVED-SAMPLING-NOISE` (name which CI drives the overlap; if both, say so), declare NO status.
Status is declared ONLY when `d_out`'s CI clears deff\* entirely — no verdict on precision the data lack.

**PART 2 — COND-A: TERMINAL CASE for INDETERMINATE (pre-registered NOW).** On this thin, FROZEN corpus
INDETERMINATE may be the TRUE FINAL answer, not a waiting room. Youth-2020 is recorded
**`UNADJUDICATED-AND-CLOSED` (permanent, not re-queued)** — NOT pending — iff ALL THREE hold:
1. `d_out`'s manager-clustered bootstrap CI has **CONVERGED** — replicate escalation to the compute
   ceiling (per the convergence rule) no longer narrows its width; i.e. the width is at the
   **corpus-limited floor** set by the fixed 62-league / 377-manager / 159-multi-league sample (the
   between/within-manager variance is estimated from a fixed number of clusters and cannot tighten
   without more clusters), AND
2. G10.7v's deff\* interval has CONVERGED (seed escalation to the ceiling no longer narrows it), AND
3. the two converged CIs STILL overlap.
When all three hold, tightening either CI requires **more CORPUS**, which is **FROZEN** (STANDING
CONSTRAINT 1: only the Phase-7 live pipeline relieves it, and `FROZEN.json` refuses re-pull). So the
status is recorded as `UNADJUDICATED-AND-CLOSED (corpus-limited)`, removed from the open-items queue,
and re-opened ONLY if the corpus grows (a `FROZEN` bump / Phase-7 live data) — never by more compute on
the frozen sample. If (1) or (2) is NOT met (a CI is still compute-limited, not corpus-limited), the
status stays `PENDING` and G10.7v/the bootstrap is escalated. **Exit is thus pre-registered before any
number exists:** compute-limited overlap → keep tightening; corpus-limited overlap → closed.

**PART 3 — COND-B: DEFF BLAST RADIUS, DIRECTION-LABELED, PRE-RUN (was PO-2; moved to PRE-RUN so the
restatement cannot be shaped by the result).** Every quantity/interval/conclusion that consumes a deff
derived from the roster-strength proxy `roster_icc_2020 = 0.123` / `deff_2020_kish = 1.33`, with the
direction each moves under an ICC INCREASE vs DECREASE and whether that is CONSERVATIVE or
ANTI-CONSERVATIVE for the claim it supports. `deff = 1 + (mbar − 1)·ICC`, so ICC↑ ⇒ deff↑ ⇒
eff-leagues↓ ⇒ every startup interval WIDER. The operative claim is **"youth-2020 has NO validated
edge (OVERTURNED / underpowered)"**; CONSERVATIVE = reinforces no-edge, ANTI-CONSERVATIVE = weakens it.

| consumer (current proxy value) | ICC ↑ ⇒ | ICC ↓ ⇒ | conservative direction |
|---|---|---|---|
| `deff_2020_kish` (1.33), `deff_2020` (1.12) | deff ↑ | deff ↓ | — (input) |
| `eff_leagues_2020_kish` (35), `_2020` (42) | fewer eff leagues ↓ | more ↑ | ICC↑ conservative (fewer independent units) |
| `deff_pooled_kish` (1.28), `eff_leagues_pooled_kish` (49) | deff ↑ / eff ↓ | deff ↓ / eff ↑ | ICC↑ conservative |
| **youth-2020 Δ_bal widened LB** = p − √deff·(p−L₀) (G10.5 GATING) | √deff ↑ ⇒ LB more negative ⇒ **MORE OVERTURNED** | √deff ↓ ⇒ LB → base +0.001 ⇒ **LESS overturned** (→ underpowered, never a validated edge — corpus still binds) | **ICC↑ = CONSERVATIVE** (reinforces no-edge); **ICC↓ = ANTI-CONSERVATIVE** (weakens the overturn) |
| STANDING CONSTRAINT #1 "eff leagues ≈ 35/15/49" | tighter (fewer units) | looser | ICC↑ conservative |
| PREREG_FALSIFIER design-effect trigger | trigger threshold shifts with deff | inverse | ICC↑ conservative (higher bar to claim an effect) |
| 2021 `deff = 1.28` (upper-bound, UNESTIMABLE→CONSERVATIVE) | **NOT driven by 2020's ICC** — 2021 has its OWN unestimable ICC (CI [−0.41,+0.26]); listed for completeness, moves with the 2021 upper bound (0.26), same direction map | — | ICC↑ conservative |
| G10.3 coverage deff (1.25 / Kish-max 4.28) | **NOT a consumer** — derived from the player-clustered COVERAGE-indicator ICC (0.117), a DIFFERENT quantity; unaffected by the roster-strength ICC | — | n/a |

**Net direction (pre-registered before the number exists):** an ICC INCREASE is CONSERVATIVE for every
startup claim (more OVERTURNED, fewer effective units, wider intervals); an ICC DECREASE is
ANTI-CONSERVATIVE (weakens the overturn) but — by STANDING CONSTRAINT 1 — still cannot MANUFACTURE a
validated edge, because at deff→1 the base Δ_bal LB is +0.001 with half-width 0.14 (underpowered, not a
clean exclusion). Whatever direction G10.6's producer-defined ICC (and G10.5's outcome ICC) lands, the
restatement is the SAME table, applied to ALL rows together — never selectively.

**SEQUENCE (unchanged):** this amendment → G10.6 (build the ICC/deff producer) → G10.7v → the dated
bounds-amendment (widened bounds pinned before G10.5 runs) → G10.5. Reviewer reviews THIS amendment
before G10.5 executes.

### A19 — 2026-07-31 · G10.6 producer + DESIGN-EFFECT RE-PIN (conservative; new-gate cascade)

Done under Colby's narrowed authorization gate (review-channel NOTE: proceed without parking when both
instances agree + the change is conservative/direction-neutral + history preserved via dated amendment).
The hand-typed design-effect ICCs (`roster_icc_2020=0.123` estimable / `2021=−0.073` unestimable) had NO
producer and NO written metric (the −76.1 pattern, one layer up). Originals PRESERVED
(`drift_baseline._designeffect_superseded_2026_07_31`); this is a NEW DEFINITION, not a correction.

**Producer** `models/design_effect.py` → `models/design_effect.json` (byte-identical ×5): PRIMARY metric
= ex-post MEAN 3-yr forward VORP per (manager,league) roster, manager-clustered, 0-fill; sensitivities
ex-ante/SUM/v0. Reuses `calibration_check._icc` + the deff formula. The byte-check CAUGHT the producer's
own `group_by` float-order ULP drift (fixed by a deterministic sort) — the discipline applied to itself.

**FINDING — both seasons UNESTIMABLE (both estimability clauses enforced; reviewer NOTE 0031 corrected a
cc gap that had missed the width clause on 2021):**
| | ICC (point) | CI | UNESTIMABLE via | conservative deff (Kish) | eff-leagues |
|---|---|---|---|---|---|
| 2020 | 0.113795 | [−0.0259, 0.2326] | spans-zero | 1.62 (ub 0.2326) | 29 (was 35) |
| 2021 | +0.464084 | [0.1778, 0.6889] | **half-width 0.2556 > 0.20** | 1.73 (ub 0.6889) | 8.7 (was ~12) |
| pooled | 0.214402 | [0.0868, 0.3418] | — (ESTIMABLE, HW 0.127) | 1.66 (point) | 37 (was 49) |
Only 2020's estimability flips (estimable→unestimable); 2021 stays unestimable (only the POINT sign-flips
−0.073→+0.464); pooled (62 leagues) is estimable. **ALL restatements CONSERVATIVE** (deffs up 1.33→1.62 /
1.28→1.66; eff-leagues 35/15/49 → 29/8.7/37; arith 1.12→1.22, 42/57→39/51) → youth-2020 MORE overturned
(now under BOTH the arith and Kish widenings), matching COND-B/A18. Structure validated (mbar_arith
1.938≈1.94, Kish 3.681≈3.68).

**Convergence (5 seeds, B=2000):** the deff-driving upper bounds are converged — 2020 0.2326 spread 8.3%,
2021 0.6889 spread 9.3% (< conv_frac 10%); 2020's lower bound spread is 12.8% (not converged) but
unanimously negative → the spans-zero classification is robust (value can be B-escalated if a pinned
lower bound is wanted).

**Re-pinned surfaces:** `drift_baseline.startup_6_5` design-effect block + the internal project notes STANDING CONSTRAINT
1 (+ the guard now green at the new values). REMAINING propagation (tracked, not Colby-pending — all
conservative): wire the guard LIVE to `design_effect.json` (full-precision), regenerate
`assistant_bundle`, dated GATE6_5_REPORT amendment, verify the exports. Reviewer flag: the pooled-
ESTIMABLE result is new (2020/2021 were reviewed in NOTE 0031; pooled uses the same agreed method).

### A20 — 2026-07-31 · G10.7v TERMINAL: youth-2020 Δ_bal = UNADJUDICATED-AND-CLOSED (COND-A)

**Authority:** Colby review-channel NOTE 0038 (adopts the A18 COND-A terminal case). Append-only.

**Finding (G10.7v).** The published youth-2020 Δ_bal interval `[+0.001, +0.281]` — whose lower bound
`+0.001` was the *entire* basis for calling the effect a "marginal edge" — was computed under a single
seed (1729). Recomputed league-clustered across 5 independent seeds, the lower bound L₀ **straddles
zero**: B=40 mean −0.007; B=160 solidifier (`jobs/g107v2_b160_solidifier.py`) mean **−0.0146, all 5
seeds negative**. The edge was **never established**.

**Decision.** youth-2020 Δ_bal → **UNADJUDICATED-AND-CLOSED (corpus-limited)**, terminal. Closure is
corpus-limited on the VALUE (converged L₀ includes 0; only more corpus moves it), not compute-limited
(the seed spread is B-reducible: 36.4%→16.0% of the half-width from B=40→B=160). This makes the G10.5
deff\* interval un-pinnable on this sample (it straddles: B=160 deff\* [0.575, 1.151]) — a downstream
consequence of the same corpus limit. **REOPEN only if the SF-startup corpus grows** (Phase-7 live
and/or the 37 out-of-sample 2022–2025 leagues maturing); never by more compute on the frozen sample.

**Surfaces swept (PO-4).** `drift_baseline.startup_6_5` (status + B=160 L₀ + terminal note; youth
canonicals retired), `jobs/check_doc_consistency.py` (4 youth numeric canonicals → 1 CLOSED-status
string canonical), the internal project notes (SESSION HANDOFF + status bullet + G6.5 GATE STATUS + OPEN-ITEMS backlog),
`docs/GATE6_5_REPORT.md` (dated amendment, single-seed values preserved), `docs/OPEN_ITEMS.md`,
`exports/startup_strategy.md`, `exports/assistant_bundle.{json,md}`, `jobs/mcp_server.py`.

**Then → G10.5** proceeds as the design-effect VALIDATION (measure `d_out` = the outcome win-rate ICC
the roster-strength proxy stood in for; compare to the pooled proxy ICC 0.214). Its Δ_bal GATING role
is moot, but the outcome-ICC measurement is still owed (Phase-8 backlog + A18).
