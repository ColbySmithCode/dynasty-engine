# PHASE 8 — Chat-Assistant Exports (plan / pre-registration)

> Pre-registered **before any export code** (project convention). The bundle is the compact
> (<100KB) knowledge pack an LLM chat assistant reads to answer dynasty questions over the
> warehouse. The hard-won lesson of Phases 6.5–7 is that **the uncertainty and provenance ARE the
> product** — a bundle that ships point estimates without their CIs, freshness, and vintage would
> silently undo every correction those phases made. Gate 8 exists to prevent that.

## Goal
Produce `exports/assistant_bundle/` (or a single `assistant_bundle.json` + a human `.md`) that:
- carries the answerable facts (rankings, values, verdicts, hit rates) the assistant needs,
- with every claim wrapped in its **uncertainty, freshness, and data-vintage provenance**,
- under a **<100KB** budget,
- read-only over the warehouse, never re-deriving models.

## Gate-8 acceptance criteria (PRE-REGISTERED; a test must exist for each)

### G8.1 — Read-side scope + 2026 policy
- The plan **enumerates exactly which warehouse tables the bundle reads** (expected:
  `fact_player_season(_metrics)`, `fact_adp`, `fact_replacement`, `dim_player`, plus the export
  artifacts `trade_verdict.json`, `startup_strategy.md`, `hit_rates_by_slot.md`, `archetypes.md`,
  `projections.md`, `aging_curves.md`). No table is read that isn't listed.
- **Assertion (test-enforced):** every row that reaches the bundle either has `season <= 2025`
  **or** is explicitly labelled `2026 (in-progress)` via `jobs/read_policy.py`. `fact_adp` carries
  5,141 rows of season 2026 — this is **live, not hypothetical**. The test injects a bare 2026 row
  and fails if it reaches the bundle unlabelled (`assert_no_unlabeled_2026`).

### G8.2 — Freshness propagation
- Every claim in the bundle **carries the `fact_refresh_status` state of the tables it derives
  from** (fresh / stale + `last_successful_refresh`). Uses `jobs/read_policy.freshness_banner`.
- **Assertion (test-enforced):** with a table marked `stale=True` in `fact_refresh_status`, every
  claim derived from it renders a **visibly stale** marker; the test fails if any such claim is
  emitted without one (no silent staleness). A missing `fact_refresh_status` **hard-fails** the
  build (freshness is mandatory, not best-effort).

### G8.3 — Uncertainty preservation (the core criterion)
- A **named representation rule** for each of the following, and a **test that FAILS if any is
  collapsed to a bare point estimate**:
  1. **Dual-pool trade verdict** — MUST show **both pools with CIs** (corpus E[Δ]
     −76.1 [−82.8, −69.5] *and* consensus +8.6 [+3.3, +14.5], sign-consistent 200/200). Standing
     Constraint #4: never a single verdict. Test fails if only one pool, or any pool without its CI.
  2. **Archetype result** — represented as **"indistinguishable from draft capital"** with the
     sampling CI [−0.084, +0.018] (spans zero); test fails if it ships a bare ΔAUC or the phrase
     "beats/loses to capital".
  3. **College-production 5.4B null** — represented as **"0/24 strata significant (point p min
     0.103, median 0.753); no detectable lift, LOW POWER"**. The old min-perm-p CI [0.0, 0.091] is
     a **retracted min-selection artifact** and MUST NOT appear. Test fails if shipped as a bare
     "p=0.11" or with the retracted CI.
     _[AMENDED after approval — see AMENDMENTS §A1; the enforced representation is now the pinned
     Westfall-Young joint null. This criterion text is preserved as-approved and NOT edited.]_
  4. **6.5 no-strategy-recommended verdict** — the startup-strategy answer MUST carry "no strategy
     has a validated edge" + the opponent-model-dependence caveat; test fails if a single strategy
     is recommended.
  5. **Corpus-size-binds constraint** — any startup-strategy claim MUST carry the standing note
     that corpus size (**≤15 effective units in 2021**) binds it; test fails if absent.
- Numeric fields use a **{point, ci_lo, ci_hi, uncertainty_status}** schema. `uncertainty_status`
  ∈ **{measured, unmeasured, exact}** on EVERY numeric:
  - **exact** — allowed **only** for a pre-registered allowlist: **counts, dates, IDs, league
    settings, and other exact non-estimated values**. `point_only` is permitted ONLY here.
  - **measured** — a CI is present (e.g. trade E[Δ], hit_rates_by_slot Wilson CIs, archetype gap).
  - **unmeasured** — no CI exists because the sampling variance was never computed; **must** be used
    there, and **must render as visible text** ("uncertainty not measured") in the human-readable
    output, not merely a JSON field.
  - **No estimate, rate, AUC, p-value, win rate, or model output may use `exact`/`point_only`.**
    The test fails if any such field ships without measured-CI or an explicit `unmeasured` flag.

### G8.4 — Vintage stamping (provenance)
- The bundle records, in a top-level `provenance` block: **`FROZEN.json` nflverse vintage**
  (2026-07-29 + input signature), **corpus freeze date** (2026-07-27), and the **artifact baseline
  commit** (git HEAD short hash at build time). So any answer traces to the exact data state that
  produced it.
- **Assertion (test-enforced):** the provenance block is present and non-empty; a vintage/commit
  mismatch between the bundle and the live repo state is flagged.

### G8.5 — Size + completeness (what is dropped first)
- The bundle is **< 100KB** (hard). If it binds, the **drop order** is pre-registered:
  first deep bench / low-ADP tail rows → then per-week detail → then prose exposition. 
- **Non-negotiable rule (test-enforced):** **caveats, CIs, freshness, and provenance are NEVER
  dropped to save space** — they are structural, not optional. The test builds a deliberately
  oversized input and asserts the size-reduction path removes *data rows*, and that every retained
  claim still carries its CI + freshness + the standing caveats.

### G8.6 — Consumer-side retention + refusal manifest (does the assistant KEEP the caveats?)
Every other criterion tests the bundle; G8.6 tests what a consumer does with it.
- **(a) Round-trip retention test.** The bundle + a fixed question set is given to a model; each
  response is checked for **retention of the corresponding caveat**. Minimum questions:
  - *"should I trade X for Y"* → response MUST surface **both pools + CIs** (Standing Constraint #4);
  - *"what startup strategy should I use"* → MUST surface **no-strategy-recommended** AND the
    **≤15-effective-units bind**;
  - *"do archetypes predict hits"* → MUST surface **indistinguishability** (not "yes/no").
  The test fails if a response drops the attached caveat.
- **(b) `cannot_answer` block.** A top-level list of questions the bundle does NOT support, each
  with its reason, so a consumer cites a refusal instead of improvising (e.g. "single-player
  dynasty value ranking — not built; the engine outputs trade *deltas* under two pools, not a
  context-free value").
- **(c) Instruction preamble.** The bundle leads with a preamble stating that **omitting an
  attached CI or caveat is an ERROR, not a summarization choice** — the assistant must carry them.

### Uncertainty status of the source exports (pre-checked)
- `hit_rates_by_slot.md` — **measured**: every rate carries a Wilson 95% CI + n; small-n slots
  (n≈15) show appropriately wide CIs (e.g. `QB·R3 y5 0.07[0.01,0.30]`). Ship WITH the CIs; a
  draft-day consumer must never see the bare rate.
- `trade_verdict.json` — measured (dual-pool CIs). `archetypes.md` — measured (gap CI, spans zero).
- `startup_strategy.md` — the win rates are measured (clustered CIs) but the headline is the
  no-strategy-recommended verdict + the corpus-size bind (both mandatory).
- `projections.md` — verify per-projection intervals exist; if any point projection lacks one, flag
  **unmeasured** before shipping (to be checked at build time).

## Non-goals / constraints
- **Read-only.** The bundle never refits a model or rebuilds the warehouse; it reads artifacts +
  fact tables. If an artifact is missing/stale, that propagates as staleness, not a silent gap.
- **No new science.** Phase 8 packages Phases 3–7 outputs; it does not compute new verdicts.
- Deterministic + reproducible (same warehouse + artifacts → same bundle bytes).

## Build order (after criteria are approved)
1. `jobs/build_bundle.py` reading the enumerated tables/artifacts through `read_policy`.
2. The {point, ci_lo, ci_hi} claim schema + the five uncertainty rules.
3. Freshness + provenance wrappers.
4. Size budget + drop-order.
5. `tests/test_bundle_gate8.py` — one test per G8.1–G8.5.

**Do not write export code until these criteria are reviewed and approved.**

---

## AMENDMENTS (append-only — pre-registered criteria are NEVER edited after approval)

> **STANDING RULE (project-wide, adopted 2026-07-29):** once a pre-registration or gate criterion
> is approved, its text is **immutable**. Corrections, scope changes, and superseded values are
> recorded here as dated amendments — never by editing the approved criterion in place. The tests
> and the shipped bundle follow the amendment; the original criterion text remains as the record of
> what was approved. (Mirrors the append-only discipline already used for `models/_versions/`,
> `drift_baseline.json`, and the frozen-raw vintage.)

### §A1 — G8.3.3 college-null representation: independence benchmark → Westfall–Young joint null
- **Date:** 2026-07-29.
- **Cause:** Gate-8 acceptance review, item 2. The approved G8.3.3 (and an interim edit that had
  added an `E[min p] ≈ 1/25 = 0.04` "expected-min-under-null" note) **assumed independence** of the
  24 within-stratum tests. But the same analysis states the tests are **positively correlated**
  (shared players across the 3 targets and the ALL/WR slices), so 0.04 is the **wrong benchmark**
  and "conservative relative to the null" was **unsupported**.
- **Superseded values (retired):** `min p 0.103, median 0.753`; the `E[min]≈0.04` independence
  benchmark; and the interim `min 0.098` independent-shuffle figure. (History of the point min:
  0.11 → 0.118 → 0.103 → 0.098 were older-design / independent-shuffle / cross-vintage figures, none
  seeded-pinned.)
- **Replacement (now enforced by `tests/test_bundle_gate8.py` and shipped in the bundle):** the
  bundle leads with the PRIMARY, coherent quantities from the pinned artifact
  (`models/cfb_5_4b_perm.json`): the **pre-registered decision-rule outcome** (NOT met, 0/3 non-R1
  strata; marginals min 0.1035, median 0.7431) and its **coherent Westfall–Young family-wise p =
  0.645**, computed under perm_diff's OWN exchangeable set (see §A3). The dom-shuffle family-wise p
  0.4794 is a DIFFERENT-set robustness check, shown as secondary and labeled NOT the correction for
  the pre-registered test. Pre-reg marginals are **consistent with but not bit-identical to the
  originally-documented 0.103/0.753, which predate seed pinning**; the interim "0.098" was an
  RNG-stream wobble. The retracted min-selection CI [0.0, 0.091] still MUST NOT appear.
- **Correction to this amendment (superseded within §A1):** an earlier version of §A1 wrongly
  reported `min 0.098`/`min 0.0543` as THE marginal min, called 0.103 "superseded," and used the
  dom-shuffle family-wise p (0.4794) as the primary. All mistaken — 0.103≈0.1035 is the pre-registered
  min (correct), 0.0543 is the dom-shuffle (different-set) min, and the correction FOR the
  pre-registered test is the same-set coherent family-wise p 0.645 (§A3).

### §A2 — G8.1 read scope: add the pinned 5.4B model artifact
- **Date:** 2026-07-29. **Cause:** §A1 — the bundle now sources the college null from the
  drift-guarded pinned artifact rather than hardcoding it.
- **Change:** the enumerated read scope gains **`models/cfb_5_4b_perm.json`** (a pinned, hashed,
  drift-monitored model artifact). No warehouse table is added.

### §A3 — 5.4B: the dom-shuffle joint null is a POST-HOC methodological amendment (not the pre-reg test)
- **Date:** 2026-07-29. **Cause:** Gate-8 acceptance review, item 1 — precise attribution of the
  marginal-p shift.
- **What changed, exactly:** the **EXCHANGEABLE SET**, nothing else. The **pre-registered** test
  (`perm_diff`, PREREG_5_4B) FIXES tertiles from observed `dom_best` and permutes OUTCOME labels
  WITHIN the top∪bottom pool — the **middle third is EXCLUDED**. The **post-hoc** Westfall–Young null
  permutes `dom_best` over the WHOLE stratum and RE-DERIVES tertiles each draw — the **middle third
  PARTICIPATES**. The observed statistic (|mean_top − mean_bot|) and the stratification are
  **unchanged**. The cross-test **coupling is NOT the cause** of the marginal shift (0.1035→0.0543):
  coupling leaves every per-test marginal null unchanged by construction.
- **Status:** the pre-registered `perm_diff` scheme is PRIMARY (decision rule + marginals). Its
  **coherent** multiplicity correction is a Westfall–Young family-wise p computed on the SAME
  exchangeable set, coupled across the 24 tests = **0.645** — this is the family-wise p that actually
  corrects the pre-registered result. The dom-shuffle joint null (family-wise p **0.4794**) uses a
  DIFFERENT exchangeable set and is SECONDARY/robustness ONLY — explicitly NOT the correction for the
  pre-registered test, so the two must not be read as mutually confirming. Both agree the null holds.
  This is a **different null**, not re-derivation noise.

### §A4 — doc-consistency guard: registry breakdown + tolerance-vacuity rule (2026-07-29)
- **Cause:** Phase-8 audit items 1–2. Clarify what the guard does and does not check.
- **Registry is 39 entries (30 numeric + 9 string). NOT all 39 are sign-checked** — only the **12
  signed numeric estimates** are (trade corpus/consensus E[Δ] + their CIs, archetype gap point +
  CI-lo, youth-2020 Δ + CI, Δ_bal). The remaining 18 numeric are magnitude+drift only and the 9
  string canonicals are presence-only. Any prior phrasing implying "39 entries, sign-checked" is
  corrected here: **12 of 39 are sign-checked.** The archetype gap CI *hi* (+0.018) is guarded as a
  signed INTERVAL string (it collides in magnitude with the vintage gap −0.018), not a lone bound.
- **Tolerance-vacuity rule (now test-enforced):** no registry entry may carry a comparison tolerance
  `>= 0.1*|value|` (a tolerance that can't discriminate the value — and, for a signed sub-|value|
  tolerance, could swallow a sign flip). Sub-milli quantities (archetype gap point, both AUCs, all
  six college p-values, youth-2020 CI-lo) use tol 1e-6; a DOC-GUARD test asserts sub-milli tol
  < 3e-4 (the `.sort()` drift scale) AND that no entry is vacuous.
- **Known scope limits (unchanged, do not overread):** the 22/22 coverage assertion is over
  the internal project notes' STANDING CONSTRAINTS section ONLY (not the whole registry, not headline findings
  elsewhere); the live-vs-baseline drift check fires only where a live artifact is read (college) —
  the archetype AUCs have no live source in this guard, so `jobs/drift_monitor.py` remains their
  drift guard.

### §A5 — pre-Phase-9 audit recomputes (2026-07-29; originals intact)
- **Archetype gap SE corrected estimand.** The refit-over-players bootstrap CI [−0.084,+0.018]
  (sd 0.028) refits both models per resample and is inflated ~1.8× by HistGB training instability
  (bootstrap model-AUC 0.874 vs full-sample 0.901). The estimand that pairs with the point
  (−0.00025) is the TEST-SET fixed-model one: DeLong paired SE **0.0153** (AUC corr 0.777, z −0.02),
  fixed-model 95% CI **[−0.0303,+0.0298]**; 5-seed test-only bootstrap sd 0.0154. Pinned in
  drift_baseline `archetype_auc._estimands`; both estimands now guarded. Verdict language unchanged
  pending approval of the "equivalent within ~0.03 vs underpowered" wording (audit item 2).
- **Corpus counts recomputed** (`load_corpus_startups()`): 2020=47lg/291mgr, 2021=15lg/128mgr,
  pooled 62lg/**377**mgr, **159** multi-league (was 158), max **25** leagues/mgr (was ~23). The
  frozen corpus ALSO holds **37** SF-startup leagues founded 2022-2025 (out-of-sample; excluded by
  Gate-6.5 config) — see PREREG_FALSIFIER §amendment + STANDING CONSTRAINT #1 note.
- **Guard bug fixed:** `_signed_hits` read a bare (unsigned) number as negative (`"" in "-−"` is
  True in Python) — false sign-flip; now compares the sign explicitly. Sub-milli tol floor made
  value-based (|value|<3e-3), and coverage now scans STANDING CONSTRAINTS + SESSION HANDOFF.
