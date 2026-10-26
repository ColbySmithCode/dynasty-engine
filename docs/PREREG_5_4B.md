# Pre-registration 5.4B — final college-production attempt (LOCKED before results)

Committed 2026-07-27 before running. Run ONCE, report honestly. If it loses,
"draft capital is the ceiling" is the FINAL answer and we never revisit.

## 1. Proper dominator (recomputed from cfbfastR play-level, incl. TDs)
- **dominator = mean(receiving_yards_share, receiving_TD_share)** for WR/TE;
  scrimmage version (rush+rec yards & TD share) for RB.
- receiving_TD = play where reception_player == touchdown_player; team_rec_TD =
  team receiving TDs. Shares computed per (player, team, season).
- Variants (all pre-registered):
  - `dom_best`  = max dominator over the player's college seasons (pre-draft).
  - `dom_final` = dominator in the player's FINAL pre-draft college season.
  - `breakout_age_20` = age at first season with dominator ≥ 0.20 (min 200 rec /
    400 scrim yds).
  - `breakout_age_30` = same at ≥ 0.30 threshold.
- Match: normalized name, college seasons strictly before draft_year, within 6-yr
  window. Report match rate; test set (2019-22) coverage was 90% previously.

## 2. Targets (ceiling, not just hit)
Run the SAME analysis against three targets:
- `hit12`  = top-12 positional PPR season in draft yrs 1-3 (existing).
- `top5`   = top-5 positional PPR season in draft yrs 1-3 (CEILING).
- `fwd3_vorp` = summed VORP over draft yrs 1-3 (continuous CEILING).

## 3. Within-stratum residual test (the decision-relevant question)
Within EACH draft-capital stratum separately — **R1, R2, R3, R4-7** — test whether
college production separates outcomes. Report the LIFT within stratum, not pooled AUC:
- For each stratum × college metric: mean metric for hits vs busts (+ permutation
  p, 20k), AND outcome rate / mean VORP for TOP-tertile vs BOTTOM-tertile of the
  metric within that stratum.
- Also WR-only within stratum (R3's signal is a WR claim).
- Within-stratum n is small, so this is an ASSOCIATION test (flag: not a per-stratum
  OOS split). Report n every row.

## Hyperparameters / decision rule (LOCKED)
- Cohort: college-matched drafted skill players, classes 2010-2022.
- Strata by draft_round: R1(=1), R2(=2), R3(=3), R4-7(4-7).
- Tertiles within stratum by `dom_best`.
- Permutation test: 20,000 shuffles, two-sided, seed 1729.
- **DECISION:** college production "adds decision-relevant signal" iff, within a
  stratum I actually draft in (R2/R3/R4-7), the top-vs-bottom-tertile difference on a
  CEILING target (top5 or fwd3_vorp) is significant (perm p < 0.05) and directionally
  correct, in **≥2 of the 3 non-R1 strata**. Otherwise: draft capital is the ceiling,
  FINAL.
