# Dynasty Assistant Bundle

> INSTRUCTION TO THE ASSISTANT (read first). Every numeric in this bundle carries a {point, ci_lo, ci_hi, uncertainty_status} schema and every claim carries a `must_carry` list of caveats. OMITTING AN ATTACHED CI OR CAVEAT IS AN ERROR, NOT A SUMMARIZATION CHOICE. Specifically: (1) trade questions MUST report BOTH pools (consensus AND corpus) with their CIs — never a single verdict; (2) 'unmeasured' means the sampling variance was never computed — say so, do not present it as certain; (3) startup-strategy questions MUST carry no-strategy-recommended AND the corpus-size bind; (4) archetype/college questions MUST carry 'indistinguishable from capital' / 'uninformative test at these event counts (not a null)', never a yes/no. If the bundle does not support a question, cite the matching `cannot_answer` entry instead of improvising. CAVEAT-RETENTION WAS VERIFIED AGAINST ONE MODEL FAMILY ONLY (Claude Opus 4.8) and self-graded by the authoring session; a different consumer model at draft time is UNTESTED — do not assume another model will retain these caveats.

## Provenance
- nflverse vintage: 2026-07-29 (frozen offseason snapshot) [sig d9c462197311a92e]
- corpus freeze: 2026-07-27 (offseason freeze)
- artifact baseline commit: efe5170

## Freshness
data fresh | 🔒 frozen-by-design (cannot update until its gating condition changes, NOT a failure): _startup_strategy

## trade_verdict
SIGN-REVERSING across pools: consensus E[Δ] +10.3 [+4.9,+16.1] (package wins) vs corpus E[Δ] -77.9 [-84.5,-71.4] (1.11 wins), sign-consistent 200/200 — but these are MC PRECISION BANDS (200-seed simulator precision only; they do NOT propagate aging/survival posteriors, pool choice, or the 0.92× rookie discount). That input-posterior uncertainty is UNPROPAGATED — magnitude UNKNOWN and UNQUEUED. The answer depends decisively on how well you draft; report both pools, never one.
- MUST carry: BOTH pools (consensus AND corpus) with their CIs; the pick-outcome pool is the highest-leverage assumption; the spread IS the verdict; the CIs are MC PRECISION BANDS (simulator precision only) — they do NOT propagate aging/survival posteriors, pool choice, or the 0.92× rookie discount
- consensus (you draft the best-available at every slot (optimal drafter)): E[Δ] 10.337131397806298 [4.865953577847554, 16.07215611866746] VORP → package wins
- corpus (you draft like the median manager (busts included)): E[Δ] -77.87029531550294 [-84.48047796921138, -71.39707944930845] VORP → 1.11 wins

## archetypes
Archetype clusters are statistically INDISTINGUISHABLE from draft-capital-only on the 2019-2022 test set (704 players, 43 hits): gap −0.00025, DeLong paired SE 0.0153 (corr 0.777, z=−0.02), 95% CI [−0.0303, +0.0298] — which EXCLUDES any true gap larger than ~0.03 AUC in magnitude. The refit-over-players CI [−0.084, +0.018] is a different estimand (training-instability-inflated), not this SE. Whether a gap below ~0.03 matters for a board depends on a decision-relevant AUC threshold; the 0.02–0.03 figure floated in review is an UNSOURCED reviewer-supplied constant pending derivation, so no such claim is made.
- verdict: INDISTINGUISHABLE from draft-capital-only (equivalent within ~0.03 AUC)
- MUST carry: indistinguishable from draft capital (NOT 'beats'/'loses to'); the CI that pairs with the point is the test-set DeLong CI, which EXCLUDES |gap| > ~0.03 AUC; the refit-over-players CI [−0.084,+0.018] is a different estimand
- gap AUC: -0.00025 [-0.0303, 0.0298]

## college_production_5_4b
No college-production signal beyond draft capital was DEMONSTRATED, and the pre-registered test COULD NOT have demonstrated one at these event counts — an UNINFORMATIVE test, not a null. Raw top5 (ceiling-target) events per stratum (top-tertile/bottom-tertile): R1 6/6, R2 6/4, R3 2/1, R4-7 3/2 (middle-tertile 5/0/3/0). The pre-registered rule needs a directional tertile lift with perm p<0.05 in ≥2 of 3 non-R1 strata; at ≤6 events/tertile that p<0.05 is unreachable, so 0/3 strata are informative — the 0/3 result means the test could not satisfy its own rule, not that the effect is absent. The pre-registered Westfall-Young family-wise p = 0.645 shows only that the minimum of the 24 marginal p's is unremarkable given their correlation; it does NOT establish no-effect or equivalence (same underpowered counts). Draft-capital-only was not improved on here because the test lacked the events to improve on it. (A non-pre-registered dom-shuffle variant gives family-wise p 0.4794 — reported for transparency, not the pre-registered test.)
- verdict: no signal demonstrated; the pre-registered test was UNINFORMATIVE at these event counts (not a null)
- MUST carry: the pre-registered test is UNINFORMATIVE (could not satisfy its own rule at these event counts), NOT a demonstrated null; report only the pre-registered Westfall-Young p; the dom-shuffle p is a non-pre-registered variant; the WY family-wise p establishes neither no-effect nor equivalence
- PRIMARY (pre-registered rule): need ≥2 of 3 non-R1 strata (R2,R3,R4-7); got 0 → rule NOT met → draft capital is not improved on. PRE-REGISTERED (PREREG_5_4B) — the primary test.
- PRIMARY correction FOR that test (same exchangeable set): Westfall-Young family-wise p = 0.645 (uncertainty not measured) — THE multiplicity correction FOR the pre-registered test: WY family-wise p computed under perm_diff's OWN exchangeable set (fixed tertiles, middle EXCLUDED), coupled across the 24 tests. Unremarkable ⇒ even the family minimum is what the null predicts. B=20000, seed 1729, vintage 2026-07-29 (offseason). No CI.
- SECONDARY — DIFFERENT exchangeable set (dom-shuffle: whole stratum, middle INCLUDED, tertiles re-derived). This is a robustness check, NOT the multiplicity correction for the pre-registered test. Do NOT read it as confirming the primary — they are different nulls.
  dom-shuffle family-wise p 0.4794 (uncertainty not measured); 0/24 significant, min marginal p 0.0543 (uncertainty not measured) — dom-shuffle min (ALL|R4-7|fwd3_vorp). THRESHOLD-FRAGILE: only 0.0043 above 0.05; the exchangeable-set change alone moved it 0.1035→0.0543, so the count is not a headline.
- provenance: PRIMARY = the pre-registered perm_diff test (fixed tertiles, outcome-shuffle within top∪bottom, middle EXCLUDED) + its coherent family-wise correction on the SAME set. The dom-shuffle joint null (middle INCLUDED) is a POST-HOC amendment (PHASE8_PLAN §A3) under a DIFFERENT exchangeable set. The two family-wise p's are NOT two views of one test.
- An earlier min-selection-artifact interval [retracted] and an independence-based expected-minimum benchmark [withdrawn] MUST NOT be reported.

## startup_strategy  🔒 FROZEN BY DESIGN — corpus-gated (Gate 6.5): regenerates ONLY on a corpus-signature change; inputs frozen 2026-07-27 (offseason). This is NOT a refresh failure — the backtester cannot update until the SF-startup corpus grows (≤15 effective units in 2021; Phase-7 live pipeline). The no-strategy-edge verdict is therefore a STANDING conclusion, not a pending one.
NO startup strategy has a validated edge. The one APPARENT in-sample effect (youth-2020) was a single-seed (1729) artifact — UNADJUDICATED-AND-CLOSED, never established (its lower bound straddles 0 across seeds). Corpus size — not model quality — is the binding constraint.
- verdict: NO startup strategy has a validated edge — none recommended.
- MUST carry: no strategy has a validated edge (do NOT recommend one); results are opponent-model-dependent (ranking unstable across opponent families); corpus size binds every claim (≤15 effective units in 2021); this is a STANDING conclusion, not pending — it cannot update until the SF-startup corpus grows (Phase-7 live pipeline); the youth-2020 'edge' was a SINGLE-SEED (1729) artifact — UNADJUDICATED-AND-CLOSED, NEVER established; do NOT present it as a real or marginal effect
- operative corpus: 62 leagues / 20304 picks; effective units 2021: 15
- opponent dependence: Strategy RANKING is NOT stable across opponent families (reach-window vs empirical draw) — the answer is opponent-model-dependent, a first-order caveat.
- standing conclusion: The no-edge verdict is a STANDING conclusion, not a pending one: the backtester is corpus-gated and cannot change until the SF-startup corpus grows beyond the ≤15 effective units of 2021 (Phase-7 live pipeline). Corpus size, not model quality, is the binding constraint.

## hit_rates_clock_a
- MUST carry: every rate WITH its Wilson 95% CI + n — never the bare rate
- QB·R1 y1 relevance: 0.66 [0.52, 0.78] (n=50)
- QB·R3 y1 relevance: 0.19 [0.08, 0.4] (n=21)
- QB·R4-7 y1 relevance: 0.04 [0.02, 0.1] (n=95)
- QB·UDFA y1 relevance: 0.0 [0.0, 0.04] (n=86)
- RB·R1 y1 relevance: 0.83 [0.64, 0.93] (n=24)
- RB·R2 y1 relevance: 0.45 [0.31, 0.6] (n=42)

## projections_established
- MUST carry: every projection is a distribution (90% CI), never a point; projection loses to last-year-PPG under matched information sets (dAUC -0.0224, CI [-0.0365, -0.0085])
- Christian McCaffrey (RB): yr1 17.1 [15.0, 19.0], yr3 14.0 [10.0, 18.0]
- Puka Nacua (WR): yr1 18.0 [16.0, 20.0], yr3 17.3 [15.0, 19.0]
- Josh Allen (QB): yr1 19.8 [17.0, 22.0], yr3 20.5 [16.0, 25.0]
- Bijan Robinson (RB): yr1 16.4 [14.0, 18.0], yr3 15.8 [14.0, 18.0]
- Jahmyr Gibbs (RB): yr1 16.2 [14.0, 18.0], yr3 15.6 [14.0, 18.0]
- Jonathan Taylor (RB): yr1 15.2 [13.0, 17.0], yr3 14.4 [12.0, 17.0]
- Matthew Stafford (QB): yr1 17.9 [16.0, 20.0], yr3 16.3 [14.0, 18.0]
- Jaxon Smith-Njigba (WR): yr1 16.4 [15.0, 18.0], yr3 16.1 [14.0, 18.0]

## replacement_levels_sf
- QB: replacement rank 21, season-mean replacement PPG 10.97 (uncertainty not measured)
- RB: replacement rank 34, season-mean replacement PPG 7.17 (uncertainty not measured)
- WR: replacement rank 48, season-mean replacement PPG 7.12 (uncertainty not measured)
- TE: replacement rank 16, season-mean replacement PPG 7.72 (uncertainty not measured)

## adp_head
- season: 2026 (in-progress)
  - Bijan Robinson — ADP 1.3 (uncertainty not measured) [2026 (in-progress)]
  - Bijan Robinson — ADP 1.3 (uncertainty not measured) [2026 (in-progress)]
  - Bijan Robinson — ADP 1.3 (uncertainty not measured) [2026 (in-progress)]
  - Bijan Robinson — ADP 1.3 (uncertainty not measured) [2026 (in-progress)]
  - Bijan Robinson — ADP 1.3 (uncertainty not measured) [2026 (in-progress)]
  - Bijan Robinson — ADP 1.3 (uncertainty not measured) [2026 (in-progress)]
  - Jahmyr Gibbs — ADP 1.8 (uncertainty not measured) [2026 (in-progress)]
  - Jahmyr Gibbs — ADP 1.8 (uncertainty not measured) [2026 (in-progress)]
  - Jahmyr Gibbs — ADP 1.8 (uncertainty not measured) [2026 (in-progress)]
  - Jahmyr Gibbs — ADP 1.8 (uncertainty not measured) [2026 (in-progress)]
  - Jahmyr Gibbs — ADP 1.8 (uncertainty not measured) [2026 (in-progress)]
  - Jahmyr Gibbs — ADP 1.8 (uncertainty not measured) [2026 (in-progress)]
  - Ja'Marr Chase — ADP 3.0 (uncertainty not measured) [2026 (in-progress)]
  - Ja'Marr Chase — ADP 3.3 (uncertainty not measured) [2026 (in-progress)]
  - Ja'Marr Chase — ADP 3.3 (uncertainty not measured) [2026 (in-progress)]
  - Ja'Marr Chase — ADP 3.3 (uncertainty not measured) [2026 (in-progress)]
  - Ja'Marr Chase — ADP 3.3 (uncertainty not measured) [2026 (in-progress)]
  - Ja'Marr Chase — ADP 3.3 (uncertainty not measured) [2026 (in-progress)]
  - Jeremiyah Love — ADP 4.1 (uncertainty not measured) [2026 (in-progress)]
  - Jeremiyah Love — ADP 4.2 (uncertainty not measured) [2026 (in-progress)]
  - Jeremiyah Love — ADP 4.4 (uncertainty not measured) [2026 (in-progress)]
  - Jeremiyah Love — ADP 4.4 (uncertainty not measured) [2026 (in-progress)]
  - Christian McCaffrey — ADP 5.0 (uncertainty not measured) [2026 (in-progress)]
  - Jeremiyah Love — ADP 5.1 (uncertainty not measured) [2026 (in-progress)]

## Cannot answer (cite these instead of improvising)
- **What is player X's single, context-free dynasty trade value / value ranking?** — Not built. The engine outputs trade DELTAS (E[Δ] VORP) under two pick-outcome pools, not a context-free per-player value. A ranking that hides the pool assumption would violate Standing Constraint #4.
- **What is the optimal startup-draft strategy / who do I pick at slot X?** — No strategy has a validated edge (Gate 6.5); the corpus (≤15 effective SF-startup units in 2021) cannot support a recommendation. Report the null + the opponent-model dependence, not a pick.
- **In-season lineup / waiver / start-sit / weekly projection advice?** — Out of scope. This is a dynasty-startup valuation engine; no in-season weekly projection model is shipped.
- **Completed 2026 (offseason) season results, standings, or stats?** — 2026 is offseason / in-progress and is EXCLUDED from all models (latest complete season = 2025). Only ADP is live, and it is labeled '2026 (in-progress)'.
- **Do college production or archetype clusters predict hits (yes/no)?** — Cannot be answered yes/no. Archetypes are INDISTINGUISHABLE from draft capital (test-set DeLong CI excludes |gap|>~0.03 AUC); the college test was UNINFORMATIVE at these event counts (not a null). Neither is a usable predictive feature.
- **Guaranteed / point-estimate future player points?** — Projections are distributions with wide credible intervals (esp. QB), not point forecasts. A bare point would drop the mandatory interval.
- **Trade/value for kickers, DST, IDP, or players absent from dim_player?** — Out of scope — the engine covers QB/RB/WR/TE skill players in dim_player only.