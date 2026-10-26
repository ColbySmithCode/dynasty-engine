# Archetypes — Phase 5.4 (design pre-registered in docs/PREREG_5_4_archetypes.md)

**KNOWN GAP: no college data → breakout_age / dominator absent (R3's top WR signal). Model leans on draft capital + combine + age; treat WR results as incomplete.**

## Supervised — P(top-12 in draft yrs 1-3). Out-of-sample (test = 2019-2022 classes)
- **Model (HistGB): AUC 0.901, Brier 0.043**
- Draft-capital-only (ln ovr): AUC 0.901, Brier 0.045
- Base-rate Brier: 0.057  (test base rate 6.1%)
- **Verdict: archetypes are INDISTINGUISHABLE from draft-capital-only** (ΔAUC -0.000; model beats capital in ~15% of REFIT-over-players resamples). The negative = 'archetypes add nothing BEYOND draft capital', NOT 'lost to capital'. Do NOT cite the point ΔAUC as a magnitude (ADDENDUM_B).
  - **AMENDMENT 2026-07-29 — point/CI pairing (two estimands, labelled).** The point (−0.00025) pairs with the **TEST-SET fixed-model** CI: DeLong paired SE **0.0153** (AUC corr 0.777, z −0.02), 95% CI **[−0.0303, +0.0298]** (5-seed test-only bootstrap sd 0.0154) — centred on the point; INDISTINGUISHABLE and equivalent within ~0.03 AUC. The **refit-over-players** CI **[−0.084, +0.018]** (sd 0.028) is a DIFFERENT estimand (refits both models per resample → training-instability-inflated ~1.8×), NOT the SE of the test-set claim; the point sat at ~82% of it — an artifact. The retracted "convergence with the 5.4B null" language is dropped. Source: `jobs.measure_sampling_variance.archetype_testonly`; see ADDENDUM_B.

Permutation importance (test AUC drop):
  - draft_ovr: +0.3793
  - wt: +0.0101
  - vertical: +0.0012
  - cone: +0.0011
  - ht_in: +0.0010
  - forty: +0.0009
  - pos_WR: +0.0004
  - bench: +0.0003

## Unsupervised archetypes (k=6 by silhouette=0.31; outcomes measured after)

| cluster | n | mean draft_ovr | mean age | mean forty | hit rate |
|--:|--:|--:|--:|--:|--:|
| 0 | 204 | 101 | 23.3 | 4.47 | 15.7% |
| 1 | 247 | 236 | 23.4 | 4.57 | 1.2% |
| 2 | 212 | 63 | 21.7 | 4.47 | 22.6% |
| 3 | 137 | 200 | 23.5 | 4.89 | 1.5% |
| 4 | 188 | 220 | 21.9 | 4.56 | 3.2% |
| 5 | 135 | 80 | 22.4 | 4.75 | 21.5% |

## Profile A — Late-round breakouts (round ≥4 who hit top-12)
n=25 of 648 late picks (3.9% hit).
vs late-round non-hits — mean ex-ante features:

| feature | breakouts | non-breakouts |
|---|--:|--:|
| draft_ovr | 138.32 | 166.22 |
| age_at_draft | 22.72 | 22.88 |
| forty | 4.59 | 4.60 |
| wt | 222.13 | 217.05 |
| vertical | 34.07 | 34.07 |

## Profile B — First-round busts (round 1, never top-12)
n=67 of 120 first-rounders (55.8% busted).
vs first-round hits — mean ex-ante features:

| feature | busts | hits |
|---|--:|--:|
| draft_ovr | 16.40 | 12.58 |
| age_at_draft | 22.16 | 22.11 |
| forty | 4.55 | 4.54 |
| wt | 211.76 | 223.66 |
| vertical | 34.81 | 35.18 |