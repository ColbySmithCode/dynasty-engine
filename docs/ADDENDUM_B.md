# Addendum B — Design decisions forced by GATE 1 data findings

> Binding constraints for Phases 5 (models) and 6 (trade engine). Written after
> the ingest sweep revealed the real shape of the data. Do not silently violate.

## Provenance note
League settings used throughout (superflex, full-PPR, 12-team, **no** TE-premium)
come from a **live Sleeper league**, read through the API, not an assumption.
That league is a first-year startup with no previous seasons, so the
corpus (Addendum A) stands in for league history.

---

## Decision 1 — Rookie hit rates come from NFL draft capital, not rookie ADP
**Why:** MFL rookie-only ADP (`IS_KEEPER=R`) is unusable before ~2019 — measured
draft counts: 2011=3, 2013=14, 2016=1, 2017=0. It only reaches usable volume at
2021 (~3,525 drafts). Building `P(hit)` by *fantasy rookie pick slot* off that
would be fitting noise for 8 of the last 15 classes.

**Build instead:**
1. `P(hit)` / survival by **NFL draft capital** from `load_draft_picks` (full
   history, 1980+, dense every year). This is the load-bearing rookie prior.
2. Use **2021+ rookie ADP** to calibrate the mapping *fantasy rookie pick slot →
   NFL draft capital* (e.g., rookie 1.01 ≈ which NFL draft-capital bucket).
3. **Back-project** that mapping to pre-2021 classes to recover fantasy-slot hit
   rates where rookie ADP didn't exist.

**Must document:** the slot→capital mapping is itself uncertain (only ~5 recent
classes calibrate it, and rookie-draft behavior drifts). Carry that uncertainty
as an **explicit error term** in the trade engine's rookie-pick valuation — do not
report pick values as point estimates without it. Config:
`models.rookie_hitrate` (`source: draft_capital`, `calibration_min_season: 2021`).

## Decision 2 — ADP velocity is scoped to 2019+; two separate studies
**Why:** For 2011–2018, MFL retains essentially a single late-preseason snapshot —
historical K/R drafts land almost entirely in the **AUG15** period; JUNE/JULY/AUG1/
DRAFT ≈ 0. Multi-snapshot "when did the market move?" velocity simply does not
exist that far back.

**Build as two studies, never merged:**
- **Study A — 15-year single-snapshot calibration** (2011–present): one snapshot
  per season (AUG15 for legacy years, comparable final-preseason snapshot after).
  Answers "did the consensus turn out right?" across the full history.
- **Study B — 7-year multi-snapshot velocity** (2019+): the ~5-period time series
  (DRAFT→JUNE→JULY→AUG1→AUG15). Answers "when did the market figure it out?" and
  whether late risers/fallers outperform.

Any export or model that blends A and B must label which is which. Config:
`models.adp_studies` (`velocity_min_season: 2019`, `legacy_snapshot_period: AUG15`).

## Decision 3 — Superflex translation, corpus-validated, before any SF pricing
**Why:** MFL ADP has **no** superflex dimension, but the target league is
superflex. Backtesting a startup on 1QB ADP would badly misprice QBs (QBs are far
more valuable in SF; the whole draft reorders).

**Build a 1QB → Superflex translation:**
- Signal 1: **Sleeper corpus** — 55,309 real dynasty picks, 96% superflex. Gives
  actual SF draft position by player/position.
- Signal 2: **DynastyProcess** `value_1qb` vs `value_2qb` (2QB ≈ SF). The 1QB↔2QB
  spread by position is the market's own translation.

**Validation gate (before use anywhere):** compare the translated SF ranking to
**actual corpus draft position, position by position** (QB/RB/WR/TE). If translated
QB slots don't match where QBs actually go in the 96%-SF corpus, the translation is
wrong — fix before it touches the backtester or trade engine. Config:
`models.superflex_translation` (`corpus_validate: true`).

**Residual caveat:** the corpus is ~95% TE-premium while the target league has
none (Addendum A skew). Translation must not import TE-premium value inflation —
reweight/exclude TE-premium leagues when fitting TE positional values.

---

## Decision 4 — SFB is best-ball redraft; demote it (corrects Addendum A)
**Why:** Scott Fish Bowl is **best-ball redraft**, whose objective function
(maximize summed weekly ceilings across a large roster, no in-season management,
no dynasty asset horizon) is fundamentally different from a **dynasty startup**.
Addendum A wrongly filed SFB under "draft-behavior modeling"; that is corrected
here.

**Binding:**
- All **dynasty draft behavior** — startup draft flow, positional runs, reach/
  value tendencies, and the **ADP-deviation noise model** — is built from the
  **400-league snowball corpus** (type 2 dynasty), not SFB.
- SFB is **supplementary only**: usable for generic **draft-flow mechanics**
  (pick timing, positional cadence in a large field). It **must not inform
  dynasty startup strategy, valuations, or the trade engine.**
- Config: `corpus.sfb` stays enabled for mechanics; any model consuming SFB for
  strategy is a bug.

## Decision 5 — Superflex backtest window: no pre-2020 back-projection
**Why:** the snowball corpus is **2020–2026 with nothing pre-2020**, so the
1QB→SF translation calibrates only on ~2020–2024. Superflex went mainstream across
2011–2019, so the 1QB↔SF relationship is **unstable** back there — projecting the
translation onto that era would fabricate precision.

**Run Phase 6.5 in two modes, never blended:**
- **Strategy-level** findings on the full **2011–2021 1QB** history (positional
  value curves, dead zones, hit rates) — 1QB framing only.
- **QB-specific SF calibration** on the narrow **2020–2022 superflex** window.

**Stability gate (before trusting the translation anywhere):** fit/apply the
mapping **separately for 2020, 2021, 2022, 2023, 2024** and **report whether it
drifts**. If QB SF-premium moves materially across those years, treat the
translation as a time-varying function, not a constant — and say so in the output.
Config: `models.superflex_translation` (`no_backproject_before: 2020`,
`stability_test_years: [2020,2021,2022,2023,2024]`).

---

## Decision 6 — Propagate per-position uncertainty; QB gets WIDER intervals
**Why:** the 5.1 aging deltas have the **widest CIs for QB** (high year-over-year
variance; QB is also the highest-value SF position). A point estimate that hides
that variance is dangerous precisely where the money is.

**Binding on Phase 6:** the trade engine must output QB valuations as **wider
credible intervals** than skill positions, not a point value. Carry the
per-position delta variance from 5.1/5.5 through the Monte Carlo so QB posteriors
are visibly wider. A trade whose verdict flips within the QB credible interval must
be surfaced as such.

> **⚠️ Phase-7 FINDING — a documented headline number moved on a silent upstream data change.**
> The archetype (model − draft-capital-only) AUC gap is **refit-deterministic (sd 0.000 across 20
> cross-process refits)** — but that measures the PIPELINE (determinism), **NOT** the effect's
> robustness. Across nflverse **data vintages** the gap ranges **−0.014 (Phase-5 doc, 0.887/0.901)
> → −0.018 (2026-07 live-build) → −0.00025 (2026-07-29 frozen-raw, 0.900785/0.901031)** — a
> data-vintage range (~0.018) that **EXCEEDS the effect size**, driven by nflverse revising
> 2013–2025 draft/production data (survival also gained a TE·R3 group). The archetype module code
> is unchanged (0 commits since HEAD), so this is purely the data.
> **Non-degeneracy verified (2nd review):** on the frozen vintage the two AUCs are 0.900785 vs
> 0.901031 (the "0.000" was 3-decimal rounding — true gap −0.00025); the archetype features are
> intact (draft_ovr 2346/2346·238-distinct, age 2312, combine metrics 764–1219 non-null·17–110
> distinct), and the two models' predictions **differ** (max|Δp| 0.63, corr 0.74) — the model has
> NOT collapsed to the capital columns.
> **Mechanism (confirmed):** `combine/all.parquet` and `ff_playerids/all.parquet` were re-pulled
> 2026-07-29 (revised) while `pbp`/`player_stats` stayed 2026-07-27. Capital-only (draft_ovr) held
> at 0.901 → **draft data is stable**; the model arm moved 0.887 → 0.900785 because the revised
> **combine features** (wt/ht/forty/…) shifted. Nothing else feeds the model-vs-capital delta.
> **SAMPLING VARIANCE (now measured — bootstrap over players, fold fixed, B=300):** the gap is
> **−0.029 mean, sd 0.028, 95% CI [−0.084, +0.018]** — it **SPANS ZERO**, and the model **beats
> capital in ~15%** of player-resamples. So the point estimate (−0.014 or −0.00025) was **never
> statistically distinguishable from zero**; the 704-player 2019–22 test set is simply too small.
>
> **AMENDMENT 2026-07-29 — point/CI pairing repaired (two DISTINCT estimands; text above intact).**
> The refit-over-players bootstrap above (CI **[−0.084, +0.018]**, sd 0.028) **refits both models on
> each resample**, so it conflates test-set sampling variance with the **training instability** of
> the flexible HistGB on ~63%-unique resamples — its model-AUC mean falls to **0.874** (vs the
> full-sample 0.901) while capital-only holds at ~0.903. It is a **different estimand** and does NOT
> pair with the fixed-model point (−0.00025), which sat at ~82% of that interval — an artifact, not a
> finding. **The estimand that pairs with the point** (models fit ONCE on train≤2018, resample only
> the 704 test players / DeLong): gap **−0.00025**, **DeLong paired SE 0.0153** (AUC correlation
> **0.777**, z −0.02, p≈0.99), fixed-model 95% CI **[−0.0303, +0.0298]**; 5-seed test-only bootstrap
> sd 0.0154, endpoint spread ≤0.0028. This CI is **centered on the point** (~49% of resamples above
> zero) and is the correct SE for "archetype AUC is indistinguishable from capital-only on this test
> set." Recompute: `jobs.measure_sampling_variance.archetype_testonly` (seeds 1729,2,3,4,5, B=2000).
> **College 5.4B null — PRIMARY (pre-registered) + SECONDARY (post-hoc joint null), both pinned
> (`models/cfb_5_4b_perm.json`, B=20000, seed=1729, vintage 2026-07-29, byte-reproducible ×5
> cross-process).**
>
> **PRIMARY — the pre-registered test (PREREG_5_4B).** Scheme: tertiles FIXED from observed
> `dom_best`; permute the OUTCOME labels WITHIN the top∪bottom pool (MIDDLE THIRD EXCLUDED); per-test
> independent (`perm_diff`). The pre-registered **decision rule** — ceiling-target (top5|fwd3_vorp)
> tertile lift p<0.05 AND directional in **≥2 of 3 non-R1 strata (R2,R3,R4-7)** — is **NOT met: 0/3
> strata** (R2/R3/R4-7 all False) → **draft capital is not improved on.** Pre-registered marginals:
> **0/24 p<0.05, min 0.1035, median 0.7431** — **consistent with but not bit-identical to the
> originally-documented 0.103/0.753, which predate the seed-pinning fix.** Under the now-fixed seeded
> generator the pinned canonical values are **0.1035/0.7431** (the interim "0.098" was an RNG-stream
> wobble of the *same* scheme). The **coherent multiplicity correction FOR the pre-registered test**
> — a Westfall–Young family-wise p under perm_diff's OWN exchangeable set (fixed tertiles, middle
> EXCLUDED), coupled across the 24 tests — is **0.645**: even the family minimum is what the null
> predicts.
>
> **SECONDARY — dom-shuffle joint null under a DIFFERENT exchangeable set (§A3), robustness ONLY.**
> NOT the correction for the pre-registered test. Shuffle `dom_best` over the WHOLE stratum and
> re-derive tertiles each draw (MIDDLE THIRD INCLUDED). Result: **0/24 significant, min marginal p
> 0.0543 (median 0.5765); family-wise p 0.4794** — also unremarkable, so the null-holds conclusion is
> robust across BOTH exchangeable sets; but do NOT read this as confirming the primary — they are
> different nulls.
>
> **Why the marginals differ (0.1035 → 0.0543):** the **EXCHANGEABLE SET** changed (top∪bottom pool
> with the middle third EXCLUDED and tertiles FIXED → the whole stratum with the middle third
> INCLUDED and tertiles RE-DERIVED). The observed statistic and the stratification are UNCHANGED, and
> the cross-test **coupling is NOT the cause** — coupling leaves every per-test marginal null
> unchanged by construction. It is a different null, not re-derivation noise. The threshold-fragile
> 0/24 count (min only 0.0043 above 0.05) is therefore SECONDARY; the pre-registered rule and the
> family-wise p are the headline. The independence benchmark E[min]≈0.04 is **WITHDRAWN** (tests
> correlated); the "min-perm-p CI [0.0, 0.091]" was a min-selection artifact, retracted.
> **Provenance — the 24-test frame + dom-shuffle joint null are POST-HOC.** The individual per-(slice
> × stratum × target) permutation tests, and the decision rule, are pre-registered in `PREREG_5_4B.md`.
> The *aggregate multiplicity summary* ("0/24 significant / min-p") and the dom-shuffle joint null
> were introduced post-registration (§A3), and are NOT the pre-registered decision rule (which was:
> tertile lift p<0.05 in ≥2 of 3 non-R1 strata on a ceiling target — reported PRIMARY above as NOT
> met). Do not cite "0/24" as the original pre-registered test. **The college null HOLDS** (no
> detectable lift); report the PRIMARY pre-registered rule outcome (NOT met) and the Westfall–Young
> family-wise p — never the retracted min-selection interval and never the withdrawn independence
> benchmark.
>
> **RESTATEMENT (binding) — the honest project-level conclusion.** **No feature set tested
> (archetype clusters, college production) BEAT draft-capital-only, and none was shown to be
> DISTINGUISHABLE from it.** The archetype gap CI spans zero (indistinguishable, not "lost to");
> the college strata show no lift but with low power (wide per-stratum CIs). So the "draft capital
> is the ceiling" claim is a **FAILURE TO IMPROVE — NOT a demonstrated bound.** Draft-capital-only
> remains the best tested predictor because nothing beat it, not because it was proven optimal.
> This is NOT "convergence of two nulls" (mutual support between a weakened result and a
> low-power one is not convergence). Do NOT cite −0.014/−0.018/−0.00025 as a directional magnitude,
> and do NOT phrase either result as "lost to" / "king" / "closed". Build is hermetic against a
> versioned frozen raw; Phase-5 vintage preserved in `models/_versions/phase5_2026-07-28/`.
>
> **Trade dual-pool verdict — MC PRECISION BANDS (Phase-7 200-seed MC sweep over the sorted
> pool):** consensus E[Δ] mean **+8.6** (sd 2.9, 95% CI [+3.3, +14.5], **package wins 200/200**);
> corpus E[Δ] mean **−76.1** (sd 3.6, 95% CI [−82.8, −69.5], **1.11 wins 200/200**). Cite this
> distribution, NOT a single seeded draw; the verdict is **sign-consistent across all 200 seeds**.
> **[SUPERSEDED 2026-07-31 — RE-PINNED: the +8.6 / −76.1 above were UNREPRODUCIBLE HAND-TYPED figures
> with NO producer; the canonical producer-backed 200-seed mean (`jobs/g104_trade200.py` →
> `models/trade_mc200.json`) is consensus **+10.3 [+4.9, +16.1]** / corpus **−77.9 [−84.5, −71.4]**.
> Cite THESE; the originals are preserved above as the historical record. See PHASE10_PLAN A16.]**
> **⚠ These brackets are MC PRECISION BANDS — seed-to-seed simulator precision ONLY (±~3 VORP). They
> do NOT propagate the aging/survival posterior parameter uncertainty, the pick-outcome pool choice,
> or the 0.92× rookie discount.** That **input-posterior uncertainty is UNPROPAGATED; its magnitude
> is UNKNOWN and UNQUEUED.** (The per-draw VORP band in `trade_verdict.md` is the predictive spread of
> ONE simulated outcome — not input-posterior uncertainty — so it is NOT cited here as a proxy for
> it.) So "non-overlapping / sign-consistent 200/200" is a statement about **simulator precision**,
> not about how confident the trade verdict is once input uncertainty is propagated (which is
> **unknown/unqueued** beyond the per-draw band). **The canonical baseline is VINTAGE-SCOPED: a
> `data/raw/nflverse/FROZEN.json` bump invalidates it and requires re-baselining.**

## Decision 10 — Archetype clusters are DESCRIPTIVE ONLY (never an engine factor)
The k=6 archetypes (silhouette 0.30) are mostly **draft capital re-expressed**
(centroids draft_ovr 62/77/101/197–236 with monotonic hit rate). Using archetype as
a trade-engine factor *independent of* draft capital would double-count capital — the
same error as the age/capital confound (Decision 6/Cox). Rule: archetypes are for
human-readable profiling only; the engine's rookie prior is the Cox joint (capital +
residual age) + survival, NOT cluster membership.

## Decision 8 — Market efficiency: use SF-draft-position residuals; edges decay
Regressing SF-scored VORP on 1QB MFL ADP is TAUTOLOGICAL (QB must show a positive
residual). The valid test is against **actual corpus superflex draft position**
(55k picks). Results the trade engine/draft assistant must use:
- **QB only +11.9 residual (not +86)** and **shrinking (+13.8→+8.3 pre-2022→2022+)**
  — the SF QB premium is largely priced and being arbitraged. Do NOT overweight QBs
  on the pooled tautological number.
- **RB +22.9 and GROWING (+17→+26)** — most underpriced; the "sell RBs" narrative
  overcorrects. **TE −54.8 and persistent (−56→−52)** — TE premium is a durable trap.
- Rule: value picks/players against SF-draft-position residuals split by era; prefer
  the **2022+** slice (SF-adoption-mature) and widen intervals where an edge is decaying.

## Decision 9 — Consolidation must be STARTUP-aware (Phase 6)
In an ESTABLISHED league, roster spots are scarce → a consolidation penalty favors
the single stud (1.11) over 3rd+4th+future-2nd. **This league is a first-year
STARTUP**, so the extra picks displace **end-of-draft picks that 5.3 prices as
NEGATIVE VORP** (startup rounds 10+ RB/WR go below replacement). Marginal roster
cost of the extra picks is therefore **near zero** — the in-season consolidation
penalty must NOT be imported. Model the startup case explicitly: value = Σ(asset
VORP) with the consolidation penalty scaled by the *realized* marginal roster slot
value (near 0 when the displaced pick is negative-VORP), not a fixed in-season penalty.

## Decision 7 — SF QB fill is CHOICE (78%), and RB decline is USAGE
Two empirical results (5.1 follow-ups) that constrain valuation:
- **SF QB fill 78.3% is 99.3% choice, not roster constraint.** The starter
  replacement uses 78% (correct). But teams roster 3–4 QBs and situationally
  flex-start skill players → **QB2/QB3 optionality is a distinct streaming asset**
  and must be priced separately, NOT by inflating QB starter replacement to 100%.
- **The RB age cliff is usage-driven, not ability.** Per-opportunity production is
  ~flat at 28–31 while per-game falls (fewer touches). Projection (5.5) must age RB
  **opportunity/volume**, not per-touch efficiency; the sell trigger is role
  erosion, not age alone. WR is mixed (real efficiency decline too) — treat
  separately. Continuous `age×target_share = −3.13` supersedes the binary RB split.
