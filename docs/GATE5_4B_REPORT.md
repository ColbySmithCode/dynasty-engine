# GATE 5.4B — final college-production tests (report). Design: docs/PREREG_5_4B.md

College-matched cohort n=1280. Ran ONCE. All 3 pre-registered tests below.

## Test 3 — proper dominator (yards-share + TD-share) computed; variants: dom_best, dom_final, breakout_age_20/30.
## Test 2 — ceiling targets (top5, fwd3_VORP) alongside hit12.
## Test 1 — within-stratum tertile lift (perm p, 20k):

| stratum | n | hit12 | top5 | topTert VORP | botTert VORP | perm_p(VORP) | breakout_age hit-lift p |
|---|--:|--:|--:|--:|--:|--:|--:|
| R1 | 74 | 41% | 23% | +218 | +220 | 0.975 | 0.084 |
| R2 | 70 | 26% | 14% | +206 | +114 | 0.123 | 0.013 |
| R3 | 88 | 18% | 7% | +85 | +35 | 0.221 | 0.335 |
| R4-7 | 359 | 4% | 1% | +11 | -13 | 0.108 | 1.000 |

**VERDICT: no within-stratum lift significant on any ceiling target in any stratum I draft in.
Decision rule (p<0.05 in ≥2 non-R1 strata) NOT met → draft-capital-only is not improved on here
(a FAILURE TO IMPROVE, not a demonstrated bound — see ADDENDUM_B restatement).**
Directional hint only: top-tertile dominator → higher VORP in R2/R3/R4-7, underpowered.

> **Correction (Gate-8 acceptance review, 2026-07-29):** the earlier "all perm p ≥ 0.11" verdict
> phrasing was imprecise, and an interim independence benchmark (E[min]≈0.04) was wrong (the 24 tests
> are correlated). Both the pre-registered test and a post-hoc joint null are now **PINNED**
> (`models/cfb_5_4b_perm.json`; B=20000, seed=1729, vintage 2026-07-29; byte-reproducible ×5
> cross-process; in `tests/test_reproducibility.py` + the drift monitor).
> **PRIMARY — pre-registered decision rule** (perm_diff; fixed tertiles, outcome-shuffle within
> top∪bottom, middle EXCLUDED): ceiling-target lift p<0.05 & directional in ≥2 of 3 non-R1 strata →
> **0/3 → rule NOT met.** Pre-reg marginals: **0/24 p<0.05, min 0.1035, median 0.7431** — consistent
> with but not bit-identical to the report's original **0.103/0.753**, which predate the seed-pinning
> fix (the interim "0.098" was an RNG-stream wobble of the same scheme). The **coherent Westfall–Young
> family-wise correction FOR this test** (same exchangeable set, coupled across the 24 tests) =
> **0.645** — even the family minimum is what the null predicts.
> **SECONDARY — dom-shuffle joint null under a DIFFERENT exchangeable set** (§A3; whole stratum,
> middle INCLUDED, tertiles re-derived): **0/24, min marginal p 0.0543 (median 0.5765); family-wise p
> 0.4794** — a robustness check (also unremarkable), NOT the correction for the pre-registered test.
> The two nulls differ by the EXCHANGEABLE SET (middle excluded vs included), not the coupling; the
> threshold-fragile 0/24 count (min 0.0043 above 0.05) is not the headline. The `breakout_age` R2
> hit-lift p=0.013 above is a separate, non-pre-registered target — a lone flicker, not a result.