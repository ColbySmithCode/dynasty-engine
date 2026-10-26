# Startup Draft Backtester — Phase 6.5  (v2, post 2nd-review)

> **⛔ TERMINAL STATUS (2026-07-31, Colby NOTE 0038 / G10.7v COND-A): youth-2020 Δ_bal = UNADJUDICATED-AND-CLOSED (corpus-limited).** Every 'youth-2020 edge' figure below (full-sample Δ_bal +0.152, percentile CI [+0.001, +0.281], clustered Δ_bal +0.116, permutation p<0.001) was computed under a SINGLE seed (1729). Recomputed league-clustered across 5 seeds, the Δ_bal lower bound L₀ straddles zero (B=160 mean −0.0146, all 5 seeds negative) — the edge was NEVER ESTABLISHED. Read the tables as the seed-1729 record, not a validated effect. Closure is corpus-limited; reopens only if the corpus grows. See GATE6_5_REPORT amendment 2026-07-31 + PHASE10_PLAN A20.

> Pre-registered in `docs/PREREG_6_5.md`. **v2 rebuild** after a second gate review fixed a `win_now` inversion bug and added: full strat×year×pool table with clustered CIs+effective n, a cross-family opponent sweep (empirical vs reach-window), a recomputed bias budget, a weekly-optimal spot-check, a year×cohort 2×2, a label-permutation null, and a capital-only falsifying test. Sim counts = estimator stability, not uncertainty; the only uncertainty is the manager/league-clustered bootstrap.

### ⚠️ Correction vs v1
v1 reported `win_now` with an inverted rookie penalty that made it draft *younger* than `youth` (mean roster age 21.8 vs 23.1). Fixed: `win_now` now averages age ~26.3 vs `youth` ~23.1 (rosters near-disjoint, Jaccard ~0.08 → they ARE opposite poles of one age axis). All `win_now` numbers below are the corrected strategy. The v1 'youth 2020 / win_now 2021 sign-flip' framing was **wrong** (different strategies, different years) and is retracted; see §1.

## 0. Operative corpus (the finding that reshaped the gate)
Filtered to startups matching the league (SF, 12-team, full-PPR, rounds≥15): **62 leagues / 20,304 picks / 376 managers (158 multi-league), 2020–2021**; strict no-TE-premium = **2** (unusable); **97% TE-premium**; **65% drafted pre-NFL-draft**; whale-clustered (max 694 picks/mgr); survivorship frame. Board-truncation ceiling: only the ~835 drafted players are reorderable. (55,309 was all-format/all-draft-type.)

## §1  Full strategy × year table (item 1) — mid slot 6, clustered CIs + effective n
`opt` = CONSENSUS pool / disciplined field (reach K3). `field` = CORPUS-AVG pool / loose field (reach K8). CI = league-clustered 95%; eff n = p(1−p)/SE² from that bootstrap. Δ = strategy − balanced under `opt`; **budget** is the recomputed bias budget (§3).

### 2020 (SF)
| strategy | opt win (95% CI, eff n) | field win (95% CI, eff n) | Δopt vs bal | budget | verdict |
|---|---|---|--:|--:|---|
| balanced_adp | 0.568 [0.497,0.662] n≈103 | 0.336 [0.304,0.398] n≈320 | +0.000 | 0.10 | baseline |
| win_now | 0.520 [0.459,0.567] n≈250 | 0.352 [0.279,0.410] n≈167 | -0.048 | 0.13 | within budget (-0.048) |
| youth | 0.715 [0.595,0.806] n≈51 | 0.323 [0.254,0.361] n≈166 | +0.147 | 0.16 | within budget (+0.147) |
| zero_rb | 0.550 [0.451,0.648] n≈77 | 0.381 [0.349,0.421] n≈424 | -0.018 | 0.20 | within budget (-0.018) |
| hero_rb | 0.637 [0.571,0.702] n≈150 | 0.367 [0.330,0.439] n≈231 | +0.069 | 0.17 | within budget (+0.069) |
| early_qb | 0.557 [0.421,0.657] n≈53 | 0.318 [0.259,0.397] n≈147 | -0.011 | 0.17 | within budget (-0.011) |
| anti_adp | 0.000 [0.000,0.002] n≈— | 0.423 [0.097,0.444] n≈14 | -0.568 | 0.19 | model-strat — see §7 (null vs weak-board unresolved) |
| value_based | 0.463 [0.397,0.565] n≈109 | 0.229 [0.174,0.258] n≈310 | -0.105 | 0.12 | model-strat — see §7 (null vs weak-board unresolved) |

### 2021 (SF)
| strategy | opt win (95% CI, eff n) | field win (95% CI, eff n) | Δopt vs bal | budget | verdict |
|---|---|---|--:|--:|---|
| balanced_adp | 0.546 [0.491,0.635] n≈130 | 0.364 [0.290,0.406] n≈228 | +0.000 | 0.10 | baseline |
| win_now | 0.556 [0.477,0.645] n≈113 | 0.353 [0.323,0.426] n≈253 | +0.009 | 0.13 | within budget (+0.009) |
| youth | 0.508 [0.374,0.618] n≈57 | 0.343 [0.328,0.438] n≈220 | -0.038 | 0.16 | within budget (-0.038) |
| zero_rb | 0.590 [0.464,0.697] n≈58 | 0.356 [0.286,0.431] n≈138 | +0.043 | 0.20 | within budget (+0.043) |
| hero_rb | 0.612 [0.520,0.713] n≈82 | 0.392 [0.315,0.450] n≈169 | +0.065 | 0.17 | within budget (+0.065) |
| early_qb | 0.468 [0.352,0.564] n≈61 | 0.339 [0.260,0.391] n≈157 | -0.079 | 0.17 | within budget (-0.079) |
| anti_adp | 0.000 [0.000,0.000] n≈— | 0.191 [0.140,0.332] n≈63 | -0.546 | 0.19 | model-strat — see §7 (null vs weak-board unresolved) |
| value_based | 0.025 [0.013,0.082] n≈99 | 0.354 [0.292,0.415] n≈190 | -0.522 | 0.12 | model-strat — see §7 (null vs weak-board unresolved) |

### §1b  Age axis: are `youth` and `win_now` anti-poles? (item 1)
| year | mean age youth | mean age win_now | roster Jaccard | Δyouth | Δwin_now | youth−winnow |
|---|--:|--:|--:|--:|--:|--:|
| 2020 | 23.2 | 26.7 | 0.04 | +0.147 | -0.048 | +0.195 |
| 2021 | 23.2 | 26.0 | 0.04 | -0.038 | +0.009 | -0.048 |

**Read:** `youth`/`win_now` are opposite poles (Jaccard≈0.08, ~3-yr age gap). The age-axis contrast (youth−winnow) is **large-positive in 2020 (youth favored) but small/near-zero in 2021** → the youth edge is a **2020 phenomenon, not a stable axis**. No robust age signal across the two SF years — the corrected, honest read (v1's 'sign flip' is retracted).

## §2  Opponent FAMILY sweep (item 2) — reach-window vs empirical draw
v1 rejected the empirical per-slot draw for the reach window (a parametric dial). Restored here as a reported family. `reachF` = reach-window loose field (K8); `empir` = empirical slot draw. Both under the CONSENSUS pool, mid slot, 2020. **The empirical family's optimal-me ceiling is a NAMED result:** independent per-slot draws let studs fall through, so a consensus drafter hoards value → win rate near the top of the range. Question: does the strategy RANKING agree across families?

| strategy | reach Fcons (K3) | reach Fcorp (K8) | empirical draw |
|---|--:|--:|--:|
| balanced_adp | 0.568 | 0.633 | 0.946 |
| win_now | 0.520 | 0.596 | 0.908 |
| youth | 0.715 | 0.632 | 0.863 |
| zero_rb | 0.550 | 0.617 | 0.948 |
| hero_rb | 0.637 | 0.615 | 0.951 |
| early_qb | 0.557 | 0.657 | 0.953 |
| anti_adp | 0.000 | 0.000 | 0.000 |
| value_based | 0.463 | 0.530 | 0.902 |

*Non-model ranking — reachFcons: ['youth', 'hero_rb', 'balanced_adp'] | reachFcorp: ['early_qb', 'balanced_adp', 'youth'] | empirical: ['early_qb', 'hero_rb', 'zero_rb'] → RANKING NOT STABLE across opponent families (a headline: the answer depends on the opponent model).*

*Empirical-family optimal-me ceiling (balanced): 0.946 — the named hoarding result; the dispersed pre/post-draft startups let studs fall to a disciplined drafter.*

## §3  Recomputed bias budget (item 3)
Pre-registered lines + three added for post-registration engine choices:

| bias line | magnitude | applies to |
|---|--:|---|
| survivorship | 0.02 | all |
| clustering | 0.03 | all |
| reach_window (opponent dial, NEW) | 0.03 | all |
| slot_coverage (NEW) | 0.02 | all |
| te_premium | 0.04 | deviant strategies |
| thin_cell | 0.03 | deviant strategies |
| truncation | 0.02 | model strategies |
| pre_post | 0.03 | rookie-exposed (youth/win_now) |
| season_scoring (depth penalty, NEW; bounded by §4) | 0.03 | depth strategies (zero_rb/youth) |

Per-strategy summed budget: balanced_adp=0.10, win_now=0.13, youth=0.16, zero_rb=0.20, hero_rb=0.17, early_qb=0.17, anti_adp=0.19, value_based=0.12

**Re-applied:** with the enlarged engine-wide budget (≥0.10 for every comparison), and clustered CIs of width ≈0.10–0.19, **no non-model strategy clears budget in BOTH years**; the only single-year clearer is `youth` in 2020 (see §1). The pre-committed rule stands: **no strategy recommended from Block 1.**

## §4  Weekly-optimal spot-check (item 4) — does season-level scoring mislead?
Season-level scoring removes bye/injury-week replacement (favours top-heavy over depth). Re-scored with WEEKLY-optimal on the flagged cells + most/least concentrated strategies. If Δ(gap) > ½·budget, season-level cannot be primary.

| year | strategy | season Δvs bal | weekly Δvs bal | shift | > ½ budget? |
|---|---|--:|--:|--:|---|
| 2020 | win_now | -0.048 | -0.042 | +0.006 | no |
| 2020 | youth | +0.147 | +0.148 | +0.001 | no |
| 2020 | zero_rb | -0.018 | +0.006 | +0.024 | no |
| 2020 | hero_rb | +0.069 | +0.053 | -0.015 | no |
| 2020 | early_qb | -0.011 | +0.038 | +0.049 | no |
| 2021 | win_now | +0.009 | +0.009 | -0.000 | no |
| 2021 | youth | -0.038 | -0.050 | -0.012 | no |
| 2021 | zero_rb | +0.043 | +0.082 | +0.038 | no |
| 2021 | hero_rb | +0.065 | +0.057 | -0.008 | no |
| 2021 | early_qb | -0.079 | -0.069 | +0.010 | no |

*Weekly-optimal moves no flagged gap beyond half budget; season-level is acceptable.*

## §5  Year × pre/post-NFL-draft 2×2 (item 5) — is the year effect confounded with landing-spot knowledge?

| | pre-NFL-draft | post-NFL-draft |
|---|--:|--:|
| 2020 | 29 | 18 |
| 2021 | 11 | 4 |

Cohort mix differs by year (2020 29/18 pre/post; 2021 11/4) → the 2020-vs-2021 contrast is **confounded with landing-spot knowledge**. Within-cohort year contrast (youth Δ, corpA/Fcorp):

| cohort | youth Δ 2020 | youth Δ 2021 |
|---|--:|--:|
| pre | -0.008 | +0.016 |
| post | +0.015 | +0.019 |

*Within cohort, the youth Δ does not persist as a clean 2020>2021 pattern → the apparent year effect is entangled with cohort mix and thin post-2021 (n=4). Not a clean year effect.*

## §6  Label-permutation null (item 6) — 16 comparisons need a multiplicity-aware null
Observed max |strategy − year-mean| across the 16 (strategy×year) `opt` cells (non-model): **0.124**. Null (shuffle strategy labels across sims within each year, 1000 perms): 95th pct = 0.027, max = 0.041. **Empirical p = 0.000**.

*The largest deviation exceeds the permutation null (p<0.05) — a real but single-cell effect (see §1); still inside the bias budget in the other year.*

## §7  Model strategies: weak board vs no edge? capital-only falsifying test (item 7)
Near-zero `value_based`/`anti_adp` is **equally consistent with a weak ex-ante board and with the models having no ex-ante edge** — and given 5.4 (archetypes) and 5.4B (college) both lost to draft capital, **the null (no model edge) is the better-supported prior**. We therefore DO NOT call it an artifact. Falsifying test: does the production-based ex-ante board beat a **capital-only** board on the same cells?

| year | value_based (production ex-ante) | value_capital (capital-only) | Δ |
|---|--:|--:|--:|
| 2020 | 0.453 | 0.362 | +0.091 |
| 2021 | 0.028 | 0.285 | -0.257 |

*If production ex-ante ≈ capital-only, the ex-ante board adds nothing beyond capital → consistent with 'no model edge'. Both explanations (weak board / no edge) remain LIVE; language changed from 'artifact' to 'unresolved'. Falsifier for the follow-up list: build an expanding-window leak-free board and test whether it beats capital-only here.*

## §8  Slot coverage (item 8)
Slots run: **[1, 6, 11, 12]** (incl. slot 12, the extreme late-turn). **No cross-slot aggregation is performed** — every headline is reported at a fixed slot (6) and each slot is shown separately, so no slot-weighting approximates the 12-slot mean (avoiding that assumption). Balanced win rate by slot (opt, 2020): s1=0.490, s6=0.570, s11=0.478, s12=0.535

## Block 2 — 1QB startup (2011–2019), CONSENSUS-only  ⚠️ DOES NOT TRANSFER
**⚠️ 1QB framing, no validated 1QB→SF translation — does NOT carry to the superflex league; decayed-edge / structure only.** No pre-2020 median-manager counterfactual (optimistic bound).

| strategy | 2011–2016 | 2017–2019 | Δ (decay) |
|---|--:|--:|--:|
| balanced_adp | 0.492 | 0.479 | -0.013 |
| win_now | 0.540 | 0.542 | +0.002 |
| youth | 0.604 | 0.674 | +0.071 |
| zero_rb | 0.559 | 0.544 | -0.015 |
| hero_rb | 0.553 | 0.519 | -0.034 |
| early_qb | 0.411 | 0.365 | -0.046 |
| anti_adp | 0.067 | 0.059 | -0.008 |
| value_based | 0.265 | 0.458 | +0.193 |

*1QB only — informational, non-transferring.*

## Leakage controls (what `assert_no_lookahead` asserts)
`assert_no_lookahead(Y, board_seasons, score_seasons)` asserts **on data timestamps**: it raises if any board/selection input row has `season ≥ Y`, or any scoring input has `season < Y`. It is **not** a table-level import ban; the import-level control is manual and documented — the Phase-5 `aging_curves`/`projection` artifacts are **never imported** by this module (they were fit across all seasons → would leak). The Block-1 consensus board is computed **strictly within draft-year** (`market_board` filters corpus picks to `season == Y`; confirmed). Ex-ante board inputs are filtered to `season < Y` and asserted.

## Bottom line (corrected — read WITH §C1–C6, which govern)
- **`win_now` bug fixed** (its own definition, §C6d); v1's 'sign flip' retracted.
- **youth-2020: the clustered point estimate excludes zero only at the boundary** (Δ_bal(clustered)=+0.116, CI [+0.001,+0.281], §C1). The clustered permutation (p<0.001) is **conditional on league composition, NOT evidence of generalization** (§C4). It is **not actionable**: largest at slot 6 / ~0 at slot 1 (§C6b), **flips sign under the empirical opponent family** (§C6c), and **2021 is underpowered** (≤15 effective units; 2021 CI contains the 2020 estimate → *under-tested*, NOT non-replication, §C1).
- **The vs-field budget does NOT govern Δ_bal** (§C3: balanced is a grid strategy → strategy-vs-strategy contrast); the '0.008 margin' framing is retracted. Inference = clustered CI + slot/family dependence + 2021 underpower. **No strategy recommended from Block 1.**
- **Opponent family changes the ranking** (item 2) — the answer is opponent-model-dependent, a first-order caveat, and the empirical family's ~ceiling for optimal-me is a named result.
- **Model strategies: weak-board vs no-edge is unresolved** (§7), null better-supported; not called an artifact. Falsifier queued.
- **Field-dispersion (draft discipline) dominates strategy choice**; a startup is one high-variance draw. **Block 2 is 1QB and does NOT transfer.**

*v2 run: 400 sims/cell, boot 20×40, slots [1, 6, 11, 12]. Reproduce: `uv run python -m models.startup_backtester`.*