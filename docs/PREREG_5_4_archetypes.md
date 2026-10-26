# Pre-registration — Phase 5.4 Archetypes (LOCKED before any results seen)

Committed 2026-07-27, before fitting. Changing anything here after seeing test
performance is post-hoc overfitting and is forbidden.

## Target
`hit` = player achieved a top-12 positional PPR season in ANY of draft years 1–3
(from `fact_player_season.pos_finish_ppr <= 12`). Cohort: NFL draft classes with
≥3 observed seasons.

## Temporal split (STRICT — no random split, no leakage)
- Train: draft classes **2010–2018**.
- Test:  draft classes **2019–2022** (each has ≥3 seasons observed by 2025).
- Excluded: 2023+ classes (insufficient observed years) and 2026 (no data).
- No feature may postdate a player's draft date (audited programmatically).

## Features (draft-time only; ex-ante)
draft_ovr (overall pick, UDFA→260), draft_round, age_at_draft, position (one-hot),
combine: forty, vertical, bench, broad_jump, cone, shuttle, weight, height.
Missing combine handled natively by the model (no imputation-as-signal).
**KNOWN GAP:** no college data ingested → breakout_age / dominator (R3's best WR
signal) are ABSENT. Flag in results; do not claim WR completeness.

## AMENDMENT (2026-07-27, still before any refit result seen)
Adding college-production features from cfbfastR (bulk parquet, 2014+):
`peak_dominator` (max college yards-share: receiving for WR/TE, scrimmage for RB)
and `breakout_age` (age at first season with dominator ≥ 0.20 WR / 0.15 RB·TE,
min 200 receiving or 400 scrimmage yards). Coverage caveat: cfbfastR starts 2014,
so breakout_age is right-censored / missing for players whose college career began
pre-2014 (mostly ≤2016 draft classes) — handled as missing (HistGB native), and the
beat-the-baseline test is ALSO reported on the college-covered subset (2017+ classes)
to avoid a coverage-confounded verdict. College→NFL match by normalized name (+school
tiebreak); match rate reported. Same locked hyperparameters; same strict temporal split.

## Supervised model (hyperparameters LOCKED)
`HistGradientBoostingClassifier` (native missing handling):
`max_iter=200, learning_rate=0.05, max_depth=3, l2_regularization=1.0,
min_samples_leaf=20, early_stopping=True, validation_fraction=0.15,
random_state=1729`.
Interpretability: permutation importance + SHAP on the held-out test set.

## Baselines it MUST beat to be worth anything (per R3 — draft capital is king)
1. **Draft-capital-only** logistic regression on `ln(draft_ovr)`.
2. Positional base rate.
Report out-of-sample AUC + Brier + calibration for model vs both baselines.
If the model does not beat draft-capital-only out-of-sample, SAY SO plainly.

## Unsupervised (archetypes)
K-means on standardized [draft_ovr, age_at_draft, athletic_composite] within the
rookie cohort; k chosen by silhouette over k∈{3..8}. Name clusters from their
centroids; report realized `hit` rate per cluster (outcomes measured AFTER, never
used in clustering).

## Two profile documents (ex-ante signals only)
- **Late-round breakouts**: drafted round ≥4 yet hit — what did they share pre-draft?
- **First-round busts**: round 1, never hit — what did the market over-weight?
