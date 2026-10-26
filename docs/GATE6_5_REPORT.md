# GATE 6.5 — Startup Draft Backtester (evidence & honest limits)

**Status: built, gated for review.** Deliverables: `docs/PREREG_6_5.md` (design + 3 review
rounds), `models/startup_data.py` (leak-free data layer), `models/startup_backtester.py`
(simulator), `exports/startup_strategy.md` (results). Config: `models.startup_backtest`.

The single most decision-relevant output of this phase is **not** a strategy ranking — it is
the **corpus-feasibility finding** that reshaped the whole gate. Read that first.

---

## 1. What was asked vs what the data allowed

**Asked (ADDENDUM_A §A4):** for each historical startup year 2011–2021, simulate a 12-team
full-PPR startup where opponents draft to ADP with noise and I draft strategy S from slot Y,
then score the roster on realized production Y..Y+5; ≥1000 sims/cell; dual-pool; superflex
split; corpus-only opponents; no lookahead; distributions; decayed-edge split.

**What the corpus actually supports (measured, §2):** the median-manager (CORPUS-AVG) pool and
the native-superflex board exist **only for startup years 2020–2021** (62 leagues), are
**97% TE-premium**, **65% drafted before the NFL draft**, and are **heavily manager-clustered**.
This forced the three-block stratification and a pre-registered **bias budget** under which
**most strategy comparisons are, by design, uninformative.** That honesty is the deliverable.

---

## 2. THE corpus-feasibility finding (leads the export)

the internal project notes' **55,309** picks = all-format/all-draft-type (mostly 4-round rookie drafts in
TE-premium leagues). Filtered to **startup drafts matching the target league** (superflex,
12-team, full-PPR, `rounds ≥ 15`), measured from the frozen raw corpus:

| set | leagues | picks | managers (multi-league) |
|---|--:|--:|--:|
| startups 2020–2025 | 100 | 34,551 | 595 (240) |
| **in-window 2020–2021** (full 5-yr realized window ≤2025) | **62** | **20,304** | **376 (158)** |
| strict no-TE-premium (exact league match) | **2** | ~700 | — |

- **97% of the 62 are TE-premium** (60/1/1) → known-sign bias against CORPUS-AVG, worst for TE.
- **60/62 drafted before Aug-15; 40/62 (65%) before the NFL draft** → rookies ranked with no
  landing spot/capital; also eliminated the ADP-as-of-date confound because Block-1 CONSENSUS
  is derived from the *same* 62 drafts (R3-1/R3-5).
- **Manager clustering:** mean 53.9 picks/manager, max 694 (one whale in ~23 leagues).
- **Survivorship frame:** SFB-seeded snowball, seasons ≥2020, reachable in the 2026 crawl →
  corpus median manager better than population → *shrinks* the reported spreads.

This is Decision-3's TE-premium skew and the Addendum-A format skew, quantified.

---

## 3. Method (as built; full detail in PREREG_6_5)

**Three blocks, never pooled (R2 §D):**
- **Block 1 — Superflex, 2020 & 2021, per draft-year, both pools & both opponent fields.** The
  only league-relevant evidence. Board = corpus-consensus native-SF ADP computed **strictly
  within draft-year** (R3-1). Scoring = SF lineup.
- **Block 2 — 1QB, 2011–2019, CONSENSUS-only.** Labeled **NON-TRANSFERRING** on every row
  (1QB framing, no validated SF translation). Decayed-edge split 2011–2016 vs 2017–2019.
- **Block 3 — pre-2020 sensitivity** exists only as a ranking-stability probe (not run as an
  estimate; the pre-2020 median-manager counterfactual does not exist).

**Two pools (R2 §A/B):** CONSENSUS = I draft the consensus-best available of my target position
(ex-ante; source named, no future info). CORPUS-AVG = an **empirical median-manager draw** at
(position × round) — never a parametric noise dial. The CONSENSUS−CORPUS gap is renamed the
**field-dispersion spread**; its **sign is uninformative** (guaranteed ≥0 by crowd-averaging),
only its magnitude is (R3-2).

**Opponent fields, swept (R3-5):** ADP-board best-available with a **reach window** (Fcons K=3
disciplined; Fcorp K=8 loose). A pure per-slot empirical draw was **tried and rejected** — it
let studs fall through independent draws and pinned optimal-me at a ~0.95 ceiling; documented.

**Leakage controls (hard, code-level):**
- `assert_no_lookahead(Y)` raises if any board/selection input has `season ≥ Y` or any scoring
  input has `season < Y`. Runs per simulated year.
- **Phase-5 `aging_curves`/`projection` artifacts are NOT used** (they were fit on outcome
  seasons → leak). The ex-ante model board uses only seasons `< Y` + fixed, hand-set age/capital
  priors (not fitted on any outcome season). Verified: 2020 ex-ante top = CMC/Zeke/Thomas/Kamara
  with **Todd Gurley still high** (no knowledge of his 2020 collapse) — leak-free.
- Corpus draws are **without replacement within a sim**; **one-manager-one-vote per cell**
  (whale cap).

**Metric:** all-play win rate (relative → replacement level cancels, deliberately unused) +
championship rate + cumulative-points distribution. **Diff vs trade-engine VORP:** the trade
engine sums per-player `vorp_ppr_total` (roster-agnostic); the backtester scores **fielded
lineup** (roster-construction-dependent) — the correct target for a draft question. The two are
**non-commensurable and never combined** (R3-8).

**Scoring policy (documented deviation, R2-8b):** the grid uses **season-level** optimal
lineup (fast, unbiased for a *relative* metric); weekly-optimal is the bounded spot-check.
**The v2 weekly spot-check (all 8 strategies × both years) confirms every season-vs-weekly
shift is < ½ its bias budget → season-level is a valid grid primary** (item 4 resolved).

**Second-review additions (v2, this build).** A second gate review (8 items) fixed a `win_now`
inversion bug (it had been drafting *younger* than `youth`) and added: (1) the full strategy ×
year × pool table with league-clustered CIs + effective n; (2) a **cross-family opponent sweep**
(reach-window vs empirical per-slot draw) — restoring the empirical draw as a reported family
and naming its ~0.94 optimal-me ceiling, with the finding that **strategy ranking is not stable
across opponent families**; (3) a **recomputed bias budget** with three added lines (season
scoring, reach-window dial, slot coverage); (4) the weekly spot-check above; (5) a year ×
pre/post-NFL-draft 2×2 showing the year contrast is confounded with cohort mix; (6) a
**label-permutation null** over the 16 strategy-year cells (p≈0.000 for youth-2020, but within
budget and non-replicating); (7) a **capital-only falsifying test** for the model strategies
(reclassified from "artifact" to "weak-board-vs-no-edge unresolved"); (8) slot 12 added.

**Uncertainty:** manager/league-clustered **bootstrap** only (resample leagues w/ replacement,
rebuild board+pools, re-sim). Sim-loop Monte-Carlo intervals are **not** reported (they
understate; the sim count is for estimator stability). (R3-8)

---

## 4. Pre-registered bias budget (R3-9) — the governing rule

Per-strategy summed same-signed budget (win-rate pp/100): survivorship 0.02 + clustering 0.03,
plus TE-premium 0.04 & thin-cell 0.03 (deviant strategies), truncation 0.02 (model strategies),
pre/post 0.03 (rookie-exposed). **Rule, locked before results:** if a strategy-vs-baseline gap
is inside its budget (and the clustered CI includes it), the comparison is **UNINFORMATIVE and
no recommendation issues from Block 1 alone.** Stated up front: this marks **most** Block-1
comparisons uninformative — the intended, honest outcome of this sample.

---

## 5. Headline results (v2 production run: 400 sims/cell, boot 20×40, slots {1,6,11,12})

> **v2 supersedes v1.** A second gate review caught a `win_now` inversion bug (it drafted
> *younger* than `youth`) and forced seven methodological additions (below). v1's "youth/win_now
> sign-flip" narrative was wrong (two different strategies) and is **retracted**.

- **`win_now` bug fixed** (now age ~26 vs youth ~23; near-disjoint rosters, Jaccard ~0.06 →
  genuine opposite poles of one age axis).
- **youth-2020: point estimate excludes zero only at the boundary, and not actionable** (v2.1,
  §C1–C6). Headline clustered estimate **Δ_bal(clustered)=+0.116, CI [+0.001, +0.281]** (the full-
  corpus +0.152 is a second estimator, descriptive). The league/manager clustered permutation
  (p<0.001) shuffles **within** replicate → it is **conditional on league composition and is NOT
  evidence of generalization** (§C4); the bootstrap CI governs. The edge appears **only at its
  most-favorable slot** (§C6b), **flips sign under the empirical opponent family** (§C6c: −0.087),
  and **2021 is underpowered** — its CI contains the 2020 estimate (§C1): *under-tested*, **not**
  "non-replication."
- **The bias budget does NOT govern this.** `balanced` is a grid strategy, so `Δ_bal` is a
  strategy-vs-strategy contrast, and the vs-field budget doesn't apply (§C3); the "fails by 0.008"
  framing is **retracted**. Inference rests on the clustered CI + slot/family dependence + 2021
  underpower. Effective independent units are **below the league count (47 / 15)** — 158
  multi-league managers, one in ~23 leagues — so **≤15 effective units in 2021 is the binding
  constraint on the phase**.
- **Weekly-optimal spot-check (all 8 strategies × both years):** every season-vs-weekly shift is
  **< ½ budget** → season-level scoring is an acceptable grid primary (the v1 concern was
  small-sim noise; confirmed here at 400 sims).
- **Opponent family changes the ranking** (reach-window vs empirical draw) — non-model top-3
  differ across families → the answer is **opponent-model-dependent** (a first-order caveat). The
  empirical family's optimal-me **ceiling ≈ 0.94** is reported as a named result (dispersed
  startups let studs fall to a disciplined drafter).
- **Model strategies (value/anti-ADP): weak-board vs no-edge is UNRESOLVED** (not "artifact").
  Capital-only falsifying test is mixed (production ex-ante +0.088 in 2020, −0.225 in 2021 vs
  capital-only) → production board does not reliably beat capital; given 5.4/5.4B, the **null (no
  model edge) is better-supported**. Falsifier queued (expanding-window leak-free board).
- **Year × cohort 2×2:** cohort mix differs by year (2020 29/18, 2021 11/4 pre/post) → the year
  contrast is **confounded with landing-spot knowledge**; within-cohort the youth Δ does not
  persist (post-2021 is n=4).
- **Block 2 (1QB, non-transferring):** `value_based` +0.23 / `youth` +0.07 strengthen into the
  modern era, others flat/decay — informational only.

**One-line verdict (v2.1):** *draft discipline (consensus adherence) dominates strategy choice*;
the one real in-sample effect (youth-2020) is **marginal, slot- and opponent-family-dependent,
and cannot be validated on the 15-league 2021 sample** — measured once, not confirmed. **No
strategy is recommended.** The binding constraint is corpus size (15 SF startups in 2021), which
no modeling change relieves.

## 8. Second-review resolution & next step

A second gate review (6 items) was resolved in **v2.1** (`exports/startup_strategy.md §C1–C6`):
(1) 2021 reclassified **underpowered, not non-replication** (CIs contain the 2020 estimates);
(2) the three centerings (+0.152 Δ_bal / +0.181 Δ_pole / 0.128 dev_mean) **reconciled and
renamed**; (3) the bias budget applies to **strategy-vs-balanced only**, not to contrasts;
(4) the sim-level permutation **replaced** by league- and manager-clustered permutations, and
effective n reconciled to the ≤62-league ceiling; (5) each new budget line tagged
**measured** (season_scoring, from the weekly check) or **judgment** (reach_window, slot_coverage),
with the verdict shown to *not* rest on the 0.008 margin; (6) completions — season-vs-weekly
shift is monotone in concentration (corr +0.82, a real small depth bias), the verdict is
slot-checked at all four slots and per opponent family, and the bug is localized to `win_now`'s
own definition.

**Follow-ups (deferred, per reviewer):** the expanding-window leak-free ex-ante board falsifier
is **held** — the binding constraint is 15 leagues in 2021, and a stronger board only re-litigates
a null against the same thin corpus; its value arrives when Phase 7's live pipeline grows the
corpus. **Next: Phase 7** (weekly refresh).

---

## 6. Honest limitations (what this gate is NOT)

1. **Two SF draft-years (2020, 2021), 62 heavily-clustered, 97%-TE-premium, survivorship-
   selected leagues.** Not enough for a confident single strategy verdict, and the export says
   so in those words.
2. **Board-truncation ceiling:** strategies can only reorder the ~835 players the field drafted;
   no truly-ignored gem is discoverable.
3. **Ex-ante model board is intentionally weak** (leakage-safe) → model strategies handicapped.
4. **Opponent-model dependence:** strategy ranking is **not stable across opponent families**
   (reach-window vs empirical draw) — any strategy claim is conditional on the opponent model.
5. **Season-level scoring** (not weekly) for the grid — but the v2 weekly spot-check confirms it
   does not mislead here (all shifts < ½ budget).
6. **CORPUS-AVG coarsening:** (position × round) understates slot-appropriateness at early picks;
   (position × exact) and (slot-only) variants are reported to expose the cost.
7. **Model strategies handicapped OR genuinely edgeless** — unresolved (§7); the leak-free ex-ante
   board is intentionally weak, and the capital-only test does not cleanly separate the two.

---

## 7. What remains (out of this gate's scope)

- Weekly-optimal full-grid scoring (spot-check only here).
- A stronger *leak-free* ex-ante board (expanding-window refit) to give model strategies a fair
  test without using Phase-5 artifacts.
- Live-league application: the target league's actual startup will be a single draw from exactly
  the high-variance, field-dispersion-dominated distribution this gate characterizes — the
  practical takeaway is *draft discipline (consensus adherence) matters far more than strategy
  label*, with the caveats above.

---

## AMENDMENT 2026-07-29 — GATE 6.5 REOPENED (original report above is INTACT)
Prior status: **CLOSED**. Reopened because the pre-Phase-9 audit (items 1-2) **overturns one
conclusion inside this gate** and materially sharpens the binding constraint.

- **OVERTURNED — "youth-2020 is the one real in-sample effect" / "Δ_bal CI [+0.001,+0.281] excludes
  zero at the boundary."** The §1/§C1 CIs were computed with a league-clustered bootstrap whose
  40-sim average sits INSIDE the resampling loop, inflating eff_n to 60-270 (vs a league count of
  47/15). Under the correct ceiling — **manager-deduped independent league-components = 2** (whales
  link ~all leagues) — every §1 win-rate CI widens to ~[0,1] and the youth-2020 Δ_bal exclusion of
  zero **does not survive**. Even at the gentler league-count ceiling (47), the design-effect
  rescale pushes the Δ_bal lower bound below 0. And by the falsifier's OWN half-width≤0.03 rule, the
  Δ_bal CI (half-width 0.14) is **underpowered**, not a valid exclusion. → youth-2020 is downgraded
  from "one real in-sample effect" to **not distinguishable from zero at the honest ceiling**.
- **STRENGTHENED (not overturned) — "no startup strategy has a validated edge."** With the ceiling
  at ~2 components, NO §1 cell is distinguishable from any other; the no-edge verdict holds a
  fortiori. The binding constraint is corrected from "≤15 units (2021)" (a league-count upper bound)
  to **manager-deduped independent league-components ≈ 2** — far more severe.
- **CAVEAT — re-SE method.** The re-SE above is an **analytic design-effect rescale** to the
  manager-deduped ceiling, NOT a full manager-clustered sims-outside re-simulation (the sims ARE the
  draft process; moving them out requires bootstrap surgery, flagged as required). The DIRECTION is
  unambiguous under any ceiling < ~15; the exact widened bounds await the re-sim.
- **Verdict:** headline (no validated edge) INTACT and strengthened; the youth-2020 "real effect"
  sub-claim RETRACTED. Gate 6.5 status → **REOPENED / code-and-verdict stable on the headline,
  one sub-claim retracted**. The two negative-result VERDICT paragraphs are NOT edited here
  (rewrites pending approval, audit item 7).

### CORRECTION (2026-07-29, same day) — the reopen above over-relied on the saturated component count
The bullets above used the manager-deduped **component count = 2** as the ceiling and concluded
youth-2020 "OVERTURNED" with "every §1 CI ~[0,1]." That component count SATURATES (single-linkage
"shares ≥1 manager") and is **not a design effect**. The **MEASURED** design effect (ICC of manager
roster-strength across leagues = 0.123 in 2020, ≈0 in 2021; mbar 1.94/1.41; deff = 1+(mbar−1)·ICC ≈
**1.12 (2020) / ≈1 (2021)**) gives **effective leagues ≈ 42 / 15 / 57** — essentially the league
count, mildly reduced. So the corrected re-marking:

> **[AMENDMENT 2026-07-31 — DESIGN EFFECT RE-PINNED (producer-backed).** The 0.123/≈0 figures above
> were HAND-TYPED with no producer. The byte-checked producer `models/design_effect.py` (ex-post 3-yr
> MEAN roster-strength VORP, manager-clustered) finds BOTH seasons UNESTIMABLE (2020 CI spans 0; 2021
> half-width > 0.20) and pooled ESTIMABLE (ICC 0.214). Under UNESTIMABLE→CONSERVATIVE the deffs rise to
> Kish ≈ 1.62 (2020) / 1.73 (2021) / 1.66 (pooled) and effective leagues fall to ≈ 29 / 8.7 / 37 — MORE
> conservative than above (youth-2020 more overturned; the corpus binds harder). Originals preserved
> here + in the registry `_superseded`. See PHASE10_PLAN A19.]**

| conclusion | corrected status |
|---|---|
| youth-2020 "one real in-sample effect" / Δ_bal boundary exclusion | **AT-RISK** (not OVERTURNED): under the measured deff the paired league-clustered CI [+0.001,+0.281] widens by only √deff≈1.06 (LB ~+0.00), and the unpaired bound crosses 0; it also fails the falsifier's own half-width≤0.03 standard and flips sign under the empirical opponent field. Survives the design-effect widening at the boundary but is not admissible as a validated effect. |
| individual §1 strategy edges (e.g. "youth beats balanced") | **UNINFORMATIVE**: at eff-leagues 42/15 the logit-scale CIs are ~±0.14 (2020) / ±0.23 (2021) — they admit essentially every decision-relevant win-rate difference, so they neither confirm nor exclude a small edge. |
| "no startup strategy has a **validated** edge" (headline) | **DIRECTION-SAFE as a non-validation statement** — but the underlying data are UNINFORMATIVE about whether small edges exist (can't confirm or deny). Do not read the headline as "no edge exists." |

**Normal-approx clipping fixed:** the earlier rescaled CIs clipped at 0/1 (invalid, same failure as
the R4-7 MDE). Re-done on the **logit scale** (no clipping); the degenerate `anti_adp` cells (winrate
0) have no logit and need an exact interval — flagged, not forced.
**Method used:** design-effect via measured ICC (option b) — chosen over a full manager-clustered
sims-outside re-run (option a) because ICC is responsive and needs no simulation surgery; the
component count is retained in docs as a **topological descriptor only**, explicitly not a design effect.

### FINAL STATUS (2026-07-29, item-2 recompute) — youth-2020 = OVERTURNED
The same-day correction above marked youth-2020 AT-RISK using the ARITHMETIC-mean design effect
(deff 1.12). The correct weighting for whale-skewed cluster sizes (max 25 leagues/mgr) is the
**cluster-size-weighted (Kish) mbar = 3.68 (2020)** → **deff = 1.33**. Under that, the youth-2020
Δ_bal league-clustered CI [+0.001,+0.281] widens by √1.33 ≈ 1.15 → lower bound ≈ **−0.009 < 0** →
the boundary exclusion of zero **does NOT hold** → **OVERTURNED** (arith weighting barely held it at
+0.004; both rest on the ROSTER-STRENGTH PROXY ICC — the true win-rate ICC needs the sim re-run and
is unmeasured). Net: the "one real in-sample effect" sub-claim is **OVERTURNED**; the "no VALIDATED
edge" headline is unchanged (individual edges UNINFORMATIVE). No §1 win rate CHANGED (item 1: the
88-vs-118 eff_n gap was a SE-input difference — bootstrap SD vs CI-half-width — at the same p=0.720).

### BACKLOG NOTES (2026-07-29, no recomputation) — read before trusting the OVERTURNED marking
- **CURRENT STATUS POINTER:** youth-2020 Δ_bal is **OVERTURNED as of commit 02e7f88** — the live
  status among the three dated 2026-07-29 amendments above (REOPENED → same-day AT-RISK correction →
  item-2 OVERTURNED). Read the last one.
- **2021 deff=1 is the ANTI-CONSERVATIVE end of an unestimable interval.** The 2021 within-manager
  ICC is unestimable: point −0.073, CI [−0.41, +0.26], only 28 multi-league managers. deff=1 uses the
  bottom of that CI. Upper bound: at ICC 0.26 and Kish mbar 2.06, deff ≈ 1.28 → ~12 effective leagues
  (not 15). So any 2021 CI computed at deff=1 is narrow by up to ~1.13× (√1.28). Backlog: pin a
  defensible 2021 deff once more corpus exists.
- **OPEN ITEM (do NOT fix now; blocks moving youth-2020 off OVERTURNED):** the youth-2020 opt cell
  has an internal SE inconsistency — bootstrap SD 0.0479 (eff_n 88) vs percentile-CI half-width 0.081
  (implied SE 0.0413); the point 0.720 sits at 73% of [0.602,0.764]; 1.96×0.0479 would imply a
  half-width 0.094, not the observed 0.081. The 1.45×/1.58× widening applies an **SD-derived eff_n to
  a percentile-derived interval** — a category mismatch. This MUST be resolved (one consistent SE
  definition) before the cell's status can move off OVERTURNED.
- **BACKLOG (blind spot):** the item-1/2 re-SE table + ICC/deff values currently drive the OVERTURNED
  marking with **no live-source artifact** (same gap the archetype gap had before wiring). Persist
  them to `models/design_effect.json` (full precision), wire the registry `live` source, and add to
  the 5× cross-process byte check. Until then this marking is doc-vs-registry only.

---

## AMENDMENT 2026-07-31 — youth-2020 Δ_bal TERMINAL: UNADJUDICATED-AND-CLOSED (corpus-limited)

**Authority:** Colby, review-channel NOTE 0038 (adopting the G10.7v COND-A terminal case; cc + reviewer
both recommended). This amendment is APPEND-ONLY and supersedes the "FINAL STATUS … OVERTURNED" and
"BACKLOG NOTES … OVERTURNED" markings above **without editing them** — they remain as the record of the
status history. The single-seed values are PRESERVED here.

**Decision.** youth-2020 Δ_bal = **UNADJUDICATED-AND-CLOSED (corpus-limited)** — terminal.

1. **The +0.001 Δ_bal lower bound — the ENTIRE basis for the "marginal edge" — was a SINGLE-SEED (1729)
   ARTIFACT.** The published interval `[+0.001, +0.281]` was computed under one seed (1729). Under the
   G10.7v recompute (`startup_backtester._joint_boot`, league-clustered, 5 independent seeds) the Δ_bal
   lower bound L₀ **straddles zero**: B=40 5-seed mean **−0.007**; the B=160 solidifier
   (`jobs/g107v2_b160_solidifier.py`) 5-seed mean **−0.0146 with ALL 5 seeds negative**
   [−0.0052, −0.0196, −0.0276, −0.0111, −0.0093]. **The edge was NEVER ESTABLISHED.**

2. **The whole status history was driven by that artifact at every step:**
   OVERTURNED → AT-RISK → OVERTURNED → PENDING(-G10.5) → **UNADJUDICATED-AND-CLOSED**. Each
   re-litigation was chasing seed noise, not signal.

3. **Closure is CORPUS-limited, NOT compute-limited.** The seed SPREAD is compute-reducible (it narrowed
   36.4%→16.0% of the half-width from B=40 to B=160), but the converged L₀ ≈ −0.015 **includes 0**; only
   more corpus moves it. The deff\* interval (G10.5) is therefore not pinnable on this sample — it
   straddles (B=160 deff\* interval [0.575, 1.151]), which is a downstream consequence of the same
   corpus limit, not an independent finding.

4. **REOPEN condition (closed ≠ unreopenable):** youth-2020 reopens ONLY if the operative SF-startup
   corpus GROWS — Phase-7 live-pipeline data and/or the 37 out-of-sample 2022–2025 leagues maturing past
   the current ~47 (2020) / 62 (pooled) sample — enough that the league-clustered Δ_bal L₀ becomes
   seed-stable AND separates from 0. **NEVER reopened by more compute on the FROZEN sample.**

**PRESERVED single-seed (1729) historical values** (no longer live canonicals; retired from
`jobs/check_doc_consistency.py` 2026-07-31 so the guard stops serving the superseded marginal edge):
full-sample Δ_bal(full) **+0.152**; single-seed percentile CI **[+0.001, +0.281]**; Δ_bal(clustered)
bootstrap mean **+0.116**; single-seed clustered permutation **p<0.001**. All seed-1729-specific.

**Two prior BACKLOG items are now closed by this decision:** (a) the "youth-2020 opt SE mismatch"
(SD-derived eff_n vs percentile half-width) is **MOOT** — L₀ straddles 0 regardless of the SE
definition, so the SE reconciliation cannot revive the edge; (b) the "no live-source artifact for the
design-effect / ICC" blind spot is **RESOLVED** independently by G10.6
(`models/design_effect.py`, byte-checked ×5, live-wired; PHASE10_PLAN A19). The "2021 deff=1" note is
**SUPERSEDED** by G10.6 (2021 UNESTIMABLE, conservative Kish deff 1.73, never floored to 1).
