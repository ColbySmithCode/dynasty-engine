# Pre-registration — Expanding-Window Ex-Ante Board Falsifier (LOCKED before any corpus growth)

> **⚠ PROVENANCE HEADER (2026-07-29, prepended; text below unchanged).** Every numeric threshold in
> this document — **Δ ≥ +0.03**, **half-width ≤ 0.03**, **≥40 units/season**, **≥60 pooled** — was
> **reviewer-supplied during the 2026-07-29 audit chain** and has **NO derivation, empirical basis,
> or pre-registration** behind it. They are **PROVISIONAL placeholders**. This document is **NOT
> BINDING** until each threshold is derived (power/decision analysis) or replaced. Do not treat
> these numbers as pre-registered.

Committed 2026-07-29, **before** the Phase-7 live pipeline ingests any new startup season, so the
trigger and the pass/fail rule are fixed before the data that would decide them exists. This
discharges STANDING CONSTRAINT #3 ("the expanding-window leak-free ex-ante board falsifier stays
QUEUED until the corpus grows") by fixing, in advance, exactly WHEN it fires and WHAT counts as a
pass. Run **ONCE** when both trigger conditions below are first met; report honestly; do not re-run
on the same data if it fails.

## What it tests
Whether a **production/model-derived ex-ante draft board** (value_based / anti_adp family, built
leak-free) **beats a capital-only board** at picking startup-draft value — the one question Gate 6.5
left UNRESOLVED (weak-board-vs-no-edge) because the 2020–2021 SF-startup corpus was too thin
(≤15 effective units in 2021) to separate "the board has no edge" from "the corpus can't see it."

## Trigger — BOTH conditions must hold before the falsifier runs
1. **Effective-n threshold (independent units, NOT sim-inflated eff n).**
   ≥ **40 effective independent SF-startup units in a single season**, OR ≥ **60 pooled** across
   the live-captured seasons, where an "effective independent unit" = a distinct *primary manager*
   in a league matching the target format (superflex, 12-team, full-PPR, rounds ≥ 15), counted
   **one-manager-one-vote per (season)** with multi-league managers deduplicated (the §C4 rule).
   This is the **league/manager count**, explicitly NOT the bootstrap-SE "eff n 60–270" (which is
   an iid-equivalent inflated by within-replicate sim averaging and does not count independent
   units). Rationale: 40 gives ~2.5× the 2021 unit count (15) — the minimum needed for a
   league-clustered CI on a strategy-vs-capital contrast to have a chance of excluding zero at a
   decision-relevant effect size (see the Gate-6.5 power note).
2. **Calendar condition.** Not before `ingest/sleeper_live.py` + the weekly refresh have captured
   **≥ 2 NEW SF-startup-draft seasons beyond 2021** as live end-of-season data — i.e., the 2026 and
   2027 startup drafts fully ingested. Earliest possible run: **after the 2027 NFL season completes
   (≈ Feb 2028)**, when 2026 and 2027 startup outcomes are both observed. (Startup drafts happen
   pre-season; their *outcomes* need the season played.)

Until BOTH hold, the falsifier stays QUEUED. Re-running it against the frozen 2020–2021 corpus is
explicitly forbidden — it would only re-litigate a null against the same thin data.

## Design (leak-free, pre-registered)
- **Boards compared, on the same held-out cells:** (a) `value_capital` — capital-only ex-ante board;
  (b) `value_board` — production/model ex-ante board. Both built with inputs filtered to `season < Y`
  and asserted by `assert_no_lookahead` (data-timestamp check; Phase-5 aging/projection artifacts
  remain import-banned — they leak).
- **Expanding window:** for each outcome season Y in the live-captured set, train the board on all
  seasons `< Y`, score on Y. No back-projection before 2020 (Decision 5).
- **Opponent families:** run under BOTH `reach-window` (consensus/corpus K3/K8) AND `empirical`
  draw (STANDING CONSTRAINT #2). Report both; lead with both.
- **Inference:** league- and manager-clustered bootstrap 95% CI on Δ = win(value_board) −
  win(value_capital), per the Gate-6.5 clustered method. Seed 1729. Sim counts are estimator
  stability, not uncertainty.

## Pass / fail (LOCKED)
- **PASS — the model board has a real edge** iff, on **≥ 2 independent live seasons**, Δ ≥ **+0.03**
  win rate with a **league/manager-clustered 95% CI excluding 0**, under **BOTH** opponent families.
- **FAIL — capital-only is not improved on** iff, in either family, the clustered CI includes 0, OR
  Δ < +0.03, OR it does not replicate across ≥ 2 seasons. → capital-only stays the board; the
  falsifier is retired as "tested at adequate power, no edge" (not "queued").
- **UNDERPOWERED — do not conclude** iff the trigger fired but the achieved clustered CI half-width
  is still > 0.03 at the observed unit count (i.e., the test could not have detected the pre-set
  effect). Report as under-powered and re-queue with a higher n threshold; do NOT read a wide null
  as a pass or a fail.

## Bias budget (carried from Gate 6.5)
Survivorship, clustering, reach-window, slot-coverage, TE-premium, thin-cell, truncation, pre/post
NFL-draft, season-scoring — all apply. Δ must clear the relevant lines, reported alongside the CI.

## Provenance
Pre-registration only — NO code written or run here. Implementation is deferred to the trigger.
`models/startup_backtester.py` already contains `value_based`/`anti_adp`/`value_capital` strategies
and `assert_no_lookahead`; the falsifier reuses them with the expanding-window driver added at run
time. Any deviation from this text at run time must be recorded as a dated amendment below.

## AMENDMENTS

### 2026-07-29 — three fixes (original pre-registration text above is INTACT)
- **(a) Order of evaluation — Underpowered is checked BEFORE Fail.** Evaluate power first: if the
  achieved league/manager-clustered 95% CI **half-width on Δ exceeds 0.03 win-rate**, the result is
  **UNDERPOWERED → re-queue**, regardless of the value of Δ (a near-zero Δ with a wide CI is NOT a
  pass and NOT an adequately-powered null). Only if the half-width ≤ 0.03 do we then read PASS
  (Δ ≥ +0.03, CI excludes 0, both families, ≥2 seasons) vs FAIL (adequately-powered null → retire).
- **(b) Units.** Δ and the CI/half-width are in **win-rate units** (fraction of head-to-head league
  finishes won, ∈ [0,1]) — the same units as the Gate-6.5 `opt win`/`field win` columns. The
  half-width clause in (a) uses these same units. "+0.03 win" = a 3-percentage-point win-rate edge.
- **(c) The count threshold does NOT bind — replaced.** Recompute (2026-07-29,
  `load_corpus_startups()`): the frozen corpus already has **2020 = 47 leagues, pooled 2020-21 = 62**,
  so the original "≥40 in one season / ≥60 pooled" is **already satisfied** and never bound.
  Worse, the corpus **already contains 37 SF-startup leagues founded 2022-2025** (2022=11, 2023=4,
  2024=17, 2025=5), **excluded from Gate 6.5 only by config `block1_years=[2020,2021]`** — they are
  genuinely **out-of-sample** for the youth-2020 hypothesis. **Revised trigger:** the falsifier is
  **runnable NOW** on the held-out **2022-2025** SF-startups via an expanding-window (train seasons
  < Y, test Y ∈ {2022,2023,2024,2025}); the calendar clause (wait for live 2026-2027) is **NOT the
  sole trigger and NOT required** — the 19-month wait was predicated on the false assumption that
  2022-2025 could not be obtained. The **binding** condition is now **out-of-sample validity +
  adequate power**: run on 2022-2025; if the whale-deduped clustered CI half-width > 0.03, report
  UNDERPOWERED and re-queue for additional live seasons; do NOT re-use 2020-2021 (hypothesis-gen).
  Caveat carried: the corpus is ~97% TE-premium (target is no-TE-prem) — report format sensitivity.
- **Provenance:** amendment only; no run. Implementation still deferred, but the gate is now "run on
  the existing 2022-2025 held-out set," not "wait for 2026-2027."

### 2026-07-29 (second amendment) — REINSTATE the calendar clause; the prior amendment was wrong
The first 2026-07-29 amendment removed the calendar clause on the belief that 2022-2025 SF-startups
were immediately usable. That was **wrong** — the reason for Gate-6.5's `block1_years=[2020,2021]`
is documented in `PREREG_6_5.md:52` as **"in-window 2020-2021 (full 5-yr realized window)"** with
`window_years=5` — i.e. **OUTCOME HORIZON, not availability.** The 37 leagues founded 2022-2025 exist
in the corpus, but their evaluation windows are TRUNCATED (completed seasons through 2025):

| founding year | leagues | completed seasons | full 5-yr window? |
|--:|--:|--:|---|
| 2022 | 11 | 4 (2022-25) | no (needs 2026) |
| 2023 | 4 | 3 | no |
| 2024 | 17 | 2 | no |
| 2025 | 5 | 1 | no |

- **Calendar clause REINSTATED.** With the pre-registered **5-yr** window, ≥2 foundings with a full
  window require waiting: 2022's completes after the 2026 season; **≥2 (2022 AND 2023) after the 2027
  season (~Feb 2028)** — which is what the ORIGINAL pre-registration said. The removal is retracted.
- **Near-term alternative (pre-committed, optional):** a **3-yr** window (config
  `window_sensitivity` includes 3) makes **2022 (2022-24)** and **2023 (2023-25)** complete NOW and
  out-of-sample → the falsifier COULD run on those 2 cohorts today. If used, this is a locked
  deviation (shorter dynasty horizon) and must be reported as such; it does not replace the 5-yr run.
- **SE BLOCKER (item 4) — must resolve before either run.** The amended pass rules ("clustered CI
  half-width > 0.03", "CI excludes 0") consume the Gate-6.5 clustered-bootstrap SE, which is (i)
  **league-clustered, not manager-clustered** (159 managers span up to 25 leagues → cross-league
  dependence uncaptured) and (ii) computed with the **40-sim average INSIDE each resample**, which
  narrows the SE and inflates eff_n (60-270) above the league ceiling (47/15). Both make the SE
  **too small → both rules biased toward PASS**, by roughly **sqrt(eff_n/ceiling) ≈ up to ~4×**. The
  falsifier MUST use a manager-clustered SE with sims OUTSIDE the resampling (or a cluster-level
  statistic) before its pass/fail can be trusted. **Do not run until this is fixed.**

### 2026-07-29 (third amendment) — trigger unit named to match STANDING CONSTRAINT #1
Condition-1's "distinct primary manager, one-manager-one-vote" is SUPERSEDED as the unit. The
independent-unit ceiling for this league-level comparison is the **manager-deduped independent
league-component count** (leagues collapsed when they share a manager): recompute gives **2 (2020),
2 (2021), 2 (pooled)** — whales (max 25 leagues/mgr, 159 multi-league) link nearly all leagues into
~2 components. So the trigger MUST cite **manager-deduped independent league-components** (same
named quantity as STANDING CONSTRAINT #1 (iii)), NOT the distinct-manager count (291/128, which is a
count of people and is trivially ≥40). Under the component ceiling (~2), the existing corpus cannot
support ANY league-level strategy CI — reinforcing that the falsifier needs genuinely NEW,
low-manager-overlap seasons (calendar clause, 2nd amendment), not more of the same whale-clustered
corpus. Threshold restated: **≥ ~20 manager-deduped independent league-components** in the
out-of-sample test set (vs the current 2) — a target the frozen corpus does not meet.
