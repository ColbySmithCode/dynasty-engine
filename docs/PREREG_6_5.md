# PRE-REGISTRATION — Phase 6.5 Startup Draft Backtester

> **A second review round (9 items) forced material design changes — see the
> `## AMENDMENTS` section at the bottom, which OVERRIDES the body where they conflict.**
> Most consequential: Block-1 CONSENSUS is now the corpus-derived native-SF consensus
> board (not MFL 1QB/Aug-15), because 60/62 corpus startups drafted before Aug 15 and MFL
> ADP has no superflex dimension. Read AMENDMENTS with the body.

> Locked **before** writing the simulator (project convention: pre-register designs
> before seeing results). Resolves the four constraints the user raised (A–D) plus the
> extra documentation items. Nothing in the simulator may deviate from this without an
> amendment recorded here and surfaced to the user.

**Core question.** If I had drafted with strategy *S* from slot *Y* in a historical
12-team full-PPR startup, how would that roster have actually performed over the
following 5 seasons (Y..Y+4) under my scoring and starter requirements?

**Gate discipline.** This whole gate exists to *measure* pick-outcome uncertainty, not
to let the analyst tune it. Every knob that could turn an empirical estimate into a dial
is either (a) an empirical draw from data, or (b) an explicitly-labeled sensitivity sweep
whose only output is "does the strategy *ranking* survive the sweep." No fitted noise
parameter is ever the primary estimate.

---

## 0. THE FINDING THAT RESHAPES THE GATE — operative corpus n (resolves C)

the internal project notes' "55,309 picks" is **all** corpus draft picks across **all** formats and
**all** draft types (mostly 4-round *rookie* drafts in TE-premium leagues). It is **not**
the operative n for a startup backtest. Measured directly from
`data/raw/sleeper_corpus/leagues/*/{league,drafts,draft_picks}.json` (frozen 2026-07-27),
filtering to matching league settings:

Startup draft = a draft with `settings.rounds ≥ 15` (clean gap in the rounds histogram:
rookie drafts cluster at 2–6 rounds — 331 drafts; startups at 16–60 — the next cluster;
6 drafts at rounds=10 are ambiguous and **excluded**, logged).

| filter (successive) | # league-season drafts |
|---|--:|
| all corpus drafts | 453 |
| superflex | 436 |
| + 12-team | 388 |
| + full PPR (rec == 1.0) | 384 |
| + startup (rounds ≥ 15) | **100** |
| + **no TE-premium** (bonus_rec_te ∈ {none,0}) | **2** |

Operative counts (SF, 12-team, full-PPR, startup; **TE-prem included** — see §2 caveat):

| set | n_leagues | n_picks | n_unique_managers | managers in >1 startup |
|---|--:|--:|--:|--:|
| all startup years 2020–2025 | 100 | 34,551 | 595 | 240 |
| **in-window 2020–2021** (full 5-yr realized window) | **62** (47+15) | **20,304** | **376** | **158** |
| strict no-TE-prem (exact league match) | 2 | ~700 | — | — |

**Consequences (binding):**
1. The median-manager (CORPUS-AVG) pool is only supportable for **startup years 2020 &
   2021** (62 drafts). Startup years 2022–2025 lack a full 5-yr realized window
   (Y+4 > 2025; 2026 excluded, no data), so they are **out of scope** for the primary
   metric regardless of corpus availability.
2. **Strict no-TE-premium matching is infeasible (n=2).** The operative corpus is
   TE-premium-inclusive. This is exactly the Decision-3 skew; handled in §2, not hidden.
3. Every CORPUS-AVG cell reports its own draw-level n; thin (position × slot) cells widen
   the slot window and are flagged. No silent fill.

---

## A. CORPUS-AVG POOL = EMPIRICAL DRAW, NEVER PARAMETRIC NOISE (binding)

CORPUS-AVG is an **empirical resolution of a pick to a realized outcome**, taken from what
managers *actually did* in the 62 matching startup drafts. It is the **primary estimate**
wherever it exists (2020–2021), not a check on a noise size.

**Construct (primary).** For my pick at overall slot *p* where my strategy selects
position *X*: draw uniformly from the empirical set

  `O(X, p) = { realized 5-yr scoring stream of every position-X player actually drafted
               within a slot window of p across the 62 startup drafts }`

and assign that drawn player's **realized** production (seasons Y..Y+4) to my roster slot.
Slot window: start at ±0 (exact `pick_no`); widen symmetrically (±3, ±6, ±12) until
`|O| ≥ 20`; record the window used and `|O|` per draw. If `|O| < 20` at ±12, the cell is
reported as **corpus-thin** and excluded from that cell's CORPUS-AVG estimate (logged, not
imputed).

- Strategy still expresses itself through **which position it drafts at which slot**
  (Zero-RB draws median-manager *WR/QB* outcomes early and median-manager *RB* outcomes
  late). The pool degrades outcome *quality* to median-manager level; the strategy chooses
  *what to spend picks on*.
- **Property to report, not hide:** under CORPUS-AVG the strategies compress toward each
  other (drafting like the field erases most edges). That compression, contrasted with the
  CONSENSUS spread, *is* the headline result.
- **No tunable parameter.** The only free choice is the slot-window widening rule above,
  which is a data-sufficiency rule (reported), not a value dial.

**Robustness variant (secondary, reported separately):** strategy-agnostic slot draw —
resolve each pick purely by overall slot *p* regardless of the position my strategy wanted
(`O(p)` = any player taken at *p*). This is the literal "player the median manager took at
that slot." Shown as a second CORPUS-AVG row to bound how much of the strategy signal is
positional-targeting vs pick-cost.

TE-premium caveat applied per §2.

---

## B. CONSENSUS POOL = CONTEMPORANEOUS EX-ANTE CONSENSUS (binding)

**CONSENSUS is ex-ante, not ex-post.** Selection uses only information available on or
before the draft; realized outcomes enter **only** scoring, never selection.

- **Source & as-of date:** MyFantasyLeague aggregate **dynasty-startup ADP**, `format='K'`,
  `ppr=1` (full PPR), `league_size=12`, `period='AUG15'` — the final-preseason consensus
  snapshot **as of ~Aug 15 of the draft year Y**. This is the market's own contemporaneous
  ranking, averaged over thousands of leagues.
- **CONSENSUS pick resolution:** at each of my picks I take the **best-available player by
  that year's AUG15 ADP** consistent with my strategy's positional logic; the roster slot
  gets **that specific player's** realized Y..Y+4 production.
- **Interpretation of the CONSENSUS − CORPUS spread (naming discipline):** neither arm uses
  future information in selection, so the spread is **NOT hindsight/perfect-foresight** and
  will **never be labeled "draft skill" or "foresight."** It is the
  **ADP-discipline / execution spread**: the value of drafting the consensus-best available
  player with discipline versus ending up with what the realized median manager got.
  Perfect-foresight (ranking players by realized outcome) is **explicitly not built**; if it
  ever is, it will be a clearly-labeled *ceiling* row, never the CONSENSUS arm.
- **Model strategies (anti-ADP, value-based)** replace the ADP ranking with the **ex-ante
  model board** of §6 (still no future info); the drawn slot gets that specific player's
  realized production.

---

## C. Post-filter corpus counts — see §0 (delivered).

The operative n is **62 startup leagues / 20,304 picks / 376 managers (158 multi-league)**
for 2020–2021, TE-prem-inclusive; **2 leagues** at strict no-TE-prem. Reported at the top
of `exports/startup_strategy.md`, not buried.

---

## D. STRATIFICATION — NO POOLED HEADLINE (binding)

Results are structured in three blocks; **there is no cross-block pooled number anywhere.**

**Block 1 — 2020 & 2021 (both pools, real corpus).**
- Reported **per draft-year** (2020 separately from 2021); no 2020+2021 pooled headline.
- Superflex framing (native SF corpus board + SF lineup, §8).
- Both CONSENSUS and CORPUS-AVG, with the spread shown per (strategy × slot).
- This is the block that actually resembles the target league.

**Block 2 — 2011–2019 (CONSENSUS arm only).**
- **No median-manager counterfactual exists** (no pre-2020 corpus; Decision 5 forbids
  back-projecting it). Reported as an **explicit optimistic upper bound**, labeled as such
  on every table.
- **1QB framing** (2011–2019 ADP is 1QB; Decision 5). 1QB lineup for scoring. Used for
  **strategy-structure findings only** (positional value curves, dead zones, decay), NOT as
  win-rate estimates for the superflex target league.
- Internal era split for the decayed-edge requirement: **2011–2016 vs 2017–2019**.

**Block 3 — pre-2020 sensitivity sweep (secondary, ranking-stability only).**
- The only pre-2020 median-manager analog possible is a **degradation applied to my own
  picks** (I draft like a noisy manager). The degradation scale is **swept across a
  plausible range, NOT fitted** (e.g., σ ∈ {0.5, 1.0, 1.5, 2.0} pick-slots of Gaussian
  mis-ranking, plus a "draw a worse-ranked available player with prob q ∈ {0.2,0.4}").
- **Only output:** does the **strategy ranking** (order of strategies by win rate at each
  slot) stay stable across the sweep? If it flips, **that flip is the finding**; the
  absolute numbers from this block are never reported as estimates.
- The sweep magnitude is **validated** against the measured 2020–2021 corpus deviation so
  the plausible range is data-anchored, but no single value is promoted to an estimate.

---

## §6. EX-ANTE DRAFT BOARD — composition & leak-free guarantee (binding)

Two boards, both **strictly ex-ante**; every input column is asserted `season < Y`.

**(a) Market board** (ADP strategies + CONSENSUS): the AUG15 year-Y dynasty-startup ADP of
§B. For 2011–2019 this is the `format='K'` 1QB board (rookie-ADP unusability pre-2020 is
**irrelevant here** — a startup drafts from the *combined veteran+rookie startup board*,
which the K report covers densely from 2011; rookie-only `format='R'` ADP is a *different
asset class* used by the trade engine's rookie-pick valuation, not by this draft board).
For 2020–2021 the market board is the **native superflex** empirical draft order from the
62 corpus startups (real SF startup ADP), so **no 1QB→SF translation is applied** (§8).

**(b) Ex-ante model board** (anti-ADP, value-based; and youth/win-now tiebreaks): built for
each player from, and **only** from:
  1. that player's **own realized production in seasons strictly < Y** (recency-weighted
     VORP/PPG) — this is past information a real drafter had, and is *outside* the scored
     window Y..Y+4;
  2. a **fixed, hand-specified age multiplier** per position (peak ages QB 28 / RB 25 /
     WR 26 / TE 27; linear pre-peak ramp and post-peak decline) — a structural domain prior
     with **no coefficients fitted on any season's outcomes**;
  3. a **fixed, coarse, monotone draft-capital prior** (R1 > R2 > R3 > Day-3 > UDFA) for
     rookies (draft_year == Y with no prior NFL season) — a structural prior, **not fitted
     on any season's outcomes**.

**No component of either board derives from a model fit on outcome seasons inside or after
the backtest window.** The project's `aging_curves`/`projection` artifacts were fit on the
full 2010–2025 panel and would leak future outcomes into selection; they are therefore
**NOT used** by the backtester. This is a deliberate, documented departure from reusing
Phase-5 artifacts, made to guarantee no lookahead. (The tradeoff: the ex-ante board is
weaker than Phase-5 projections — that weakness is honest and is the price of zero leakage.)

**Enforcement:** `assert_no_lookahead(Y)` verifies `max(season)` over every board/selection
input `< Y` and `min(season)` over every scoring input `≥ Y`, and raises otherwise. It runs
inside the per-year build, not as an afterthought.

---

## §7. MISSING DRAFT CAPITAL — impute UDFA, never drop (binding)

Measured: of fantasy-position players with a draft_year, only ~50% carry a draft_round
(RB 822/1653 have round; 1621 have year). Handling:
- **Missing draft_round → imputed as UDFA** (lowest capital tier). **Dropping is
  prohibited** because it induces **survivorship bias**: undocumented players skew toward
  washed-out/undrafted busts, so dropping them keeps a rosier, better-documented pool and
  **inflates hit rates**.
- Direction of the imputation's residual bias is **conservative**: a genuine mid-round pick
  mis-filed as UDFA gets a *lower* model value, so the model *under-rates* some rookies
  rather than over-rating them. Reported with the affected count.
- Missing **draft_year** (~2% of skill players): if the player has prior-season production
  they are treated as a veteran (board (b).1); otherwise they are dropped from the *rookie*
  pool only (n is tiny; logged). They still appear on the market board if they have an ADP.

---

## §8. SUPERFLEX RECONCILIATION & RENAMING (binding)

The task's "SF QB calibration (2020–2022)" is **renamed** and reconciled:

- The backtester's superflex work is the **Block-1 Superflex arm (startup years 2020 &
  2021)** — the only SF startup years with both a full 5-yr realized window and corpus
  support. It is **not** a 2020–2022 window: 2022 has no full realized window (2022+4=2026,
  no data).
- It uses **native superflex data** (real SF corpus draft boards 2020–2021 + SF lineup
  scoring), so it **does not consume the 1QB→SF translation at all**. The standing
  "superflex translation calibrated on 2020–2024" (config
  `superflex_translation.stability_test_years`) is a **separate upstream artifact**
  (per-season cross-sectional market-efficiency residuals, Decision 8) that the backtester
  **does not refit and does not need**, because native SF startup drafts exist for the
  operative years. No conflict: nothing here narrows the translation window; the backtester
  simply sidesteps translation by using native SF data.
- **Decision 7 (78.3% SF QB fill)** is applied where it belongs — in **valuation/reporting**
  of the SUPERFLEX slot (QB2/QB3 optionality, replacement framing). For **scoring**, the
  weekly/seasonal SUPERFLEX slot is filled **optimally by realized points** (a real manager
  starts their best eligible player); the 78.3% is reported as the empirical fill the
  optimal policy reproduces, not imposed as a cap.

---

## §9. STRATEGIES (8; TE-premium variants skipped — league has none)

Each is a selection policy over the board respecting roster minimums (QB≥1[SF:≥2], RB≥2,
WR≥3, TE≥1) and caps (QB≤3, RB≤6, WR≤7, TE≤3); unmet minimums are force-filled in the final
rounds.

1. **win-now** — maximize projected year-Y production; discount rookies (×0.6) and youth
   uncertainty; prefer proven prime veterans.
2. **youth / rebuild** — hard age cap: only draft age ≤ 25 (rookies preferred) until roster
   minimums force relaxation in late rounds; among eligible, best board value.
3. **balanced ADP + age tiebreak** — best available by market board; ties/near-ties broken
   toward the younger player. (This is the **baseline** other strategies are compared to.)
4. **Zero-RB** — no RB in rounds 1–5; load WR/QB/TE; take RB value from round 6+.
5. **Hero-RB** — exactly one RB in round 1, then Zero-RB behavior.
6. **early-QB** — prioritize QB early (SF: two QBs within first ~5 rounds), then best
   available.
7. **anti-ADP (my model's board)** — draft by the ex-ante model board (§6b), taking the
   largest positive (model-rank − ADP-rank) edges; ignore market ordering.
8. **value-based (max projected VORP)** — each pick take the max ex-ante model value
   available subject to caps/minimums.

---

## §10. OPPONENT MODEL (corpus-only where it exists; Decision 4)

Opponents are the 11 non-me teams; they draft to consensus with realistic deviation.
- **2020–2021:** opponents' picks are **sampled from the empirical corpus draft behavior**
  of the 62 startup leagues (real median-manager pick-vs-slot deviations). This is the
  Decision-4 corpus opponent model, applied directly.
- **2011–2019:** no corpus exists. Opponents draft to the AUG15 ADP with deviation drawn
  from the **MFL-reported `min_pick`/`max_pick` spread** of each player (a *contemporaneous*
  market source, not SFB — SFB is forbidden for dynasty behavior, Decision 4). Modeled as a
  **triangular(min_pick, adp, max_pick)** draw per player, re-ranked to form the noisy board.
- **Validation hook:** the MFL-spread opponent model's deviation magnitude is compared to
  the measured 2020–2021 corpus deviation; if materially different, the discrepancy is
  reported (it does not get silently tuned to match).

The opponent model is the *availability* process (who gets taken before my pick). It is
**distinct** from the CORPUS-AVG *pool* (§A), which resolves *my own* pick's realized
outcome. The A-constraint (no parametric pool noise) governs the pool, not opponent
availability; opponent availability legitimately uses the contemporaneous ADP spread.

---

## §11. METRICS, DISTRIBUTIONS, ERA SPLIT, CIs

Per (year × slot × strategy × pool), ≥1000 draft sims (opponent-noise realizations):
- **All-play win rate** — per window-season, rank the 12 rosters by seasonal starting
  points (optimal lineup, §8); my contribution = (# of the 11 opponents I outscore)/11,
  averaged over the 5 window-seasons and all sims. Avoids schedule luck.
- **Championship rate** — P(my cumulative 5-yr starting points is #1 of 12).
- **Full distribution** of cumulative 5-yr starting points: mean, sd, **P5 / P25 / P50 /
  P75 / P95**. Fat-left-tail flag when (P50 − P5) is large relative to the field — a good
  mean with a fat left tail is a *different asset* than a reliable one (a 5-yr position).
- **Sample size** (n sims) and **Wilson 95% CI** on every win-rate / championship-rate.
- **Era / decay (constraint 6):** each strategy's edge vs the balanced baseline reported for
  **2011–2016**, **2017–2019** (both CONSENSUS/1QB), and **2020–2021** (both pools/SF).
  Strategies whose edge shrinks toward zero across eras are **flagged as decayed** — trading
  a dead edge is worse than no model.

---

## §12. NO-LOOKAHEAD ENFORCEMENT (code-level, not intent)

`assert_no_lookahead(Y, board_inputs, score_inputs)`:
- raises if any `board_inputs` row has `season ≥ Y`;
- raises if any `score_inputs` row has `season < Y`;
- runs once per simulated startup year, before any pick is made;
- fixed structural priors (age multiplier, capital tiers) carry no season and are exempt by
  construction (documented that they are not fitted on data).

---

## §13. RUNTIME / SIM PLAN

`config.yaml → models.startup_backtest`: `sims_per_cell: 1000`, `window_years: 5`,
`horizon_last_complete_season: 2025`, `draft_rounds: {oneqb: 15, sf: 15}`,
`board_size: 260`, `startup_years_consensus: [2011..2019]`,
`startup_years_both_pools: [2020, 2021]`, `slot_window_widen: [0,3,6,12]`,
`corpus_thin_min: 20`, `startup_rounds_min: 15`, `sensitivity_sweep: {...}`.
Benchmark a small run first; if the full grid can't hit ≥1000/cell within a sane wall-clock,
**reduce breadth (fewer slots reported), never silently cap sims** — and `log()` any cell
run at < 1000 with the reason.

---

## §14. DOCUMENTED DEVIATIONS (surfaced, not silent)

1. **Operative corpus is 62 leagues / 20,304 picks (2020–2021), not 55,309.** The larger
   figure is all-format/all-draft-type. (§0/C)
2. **Strict no-TE-premium corpus matching is infeasible (n=2);** CORPUS-AVG runs on the
   TE-prem-inclusive startup set with an explicit TE caveat. (§2)
3. **Phase-5 `aging_curves`/`projection` artifacts are NOT used** by the ex-ante board
   (they leak future outcomes); a weaker, fixed, leak-free ex-ante board is used instead.
   (§6)
4. **"SF QB calibration (2020–2022)" is renamed** to the *Superflex arm (2020–2021 startup
   cohorts, native SF)* and uses native SF corpus data instead of the 1QB→SF translation;
   the 2020–2024 translation artifact is untouched. (§8)
5. **Both-pools reporting is only possible for 2020–2021.** 2011–2019 is CONSENSUS-only,
   labeled an optimistic bound; the pre-2020 median-manager view exists only as a
   ranking-stability sweep (Block 3), never as an estimate. (§D)

---

# AMENDMENTS (post-review round 2 — locked before the data layer)

All nine review items were investigated **empirically against the frozen corpus and the
warehouse**, not argued. Numbers below are measured. Where an amendment conflicts with the
body above, **the amendment governs.**

## Item 1 — CONSENSUS board QB format (RESOLVED; changes Block 1)
Measured: `fact_adp` has formats **only {N, K, R}** and **no superflex/2QB column**. MFL
dynasty-startup ADP is **1QB-only** (confirms Decision 3). Therefore:
- **Block 1 (2020–2021, SF) CONSENSUS board = the corpus-derived native-SF consensus ADP**
  = mean draft position per player across the 62 matching SF startups (835 players have a
  corpus draft position). It is genuinely superflex and needs no 1QB→SF translation.
- **MFL K/ppr=1/AUG15 1QB ADP is used ONLY in Block 2** (2011–2019, explicitly 1QB and
  non-transferring). The §B claim that MFL ADP is "the" CONSENSUS source is **amended**: it
  holds for Block 2 only.
- This also **resolves Item 5** for Block 1 (below): both Block-1 arms derive from the same
  62 SF drafts, so there is **no ADP-as-of-date information advantage** between them.

## Item 2 — outcome window (literal lists + sensitivity)
Window is **draft-year-inclusive** (players play the NFL season of the draft year):
- **2020 draft → outcome seasons [2020, 2021, 2022, 2023, 2024]**
- **2021 draft → outcome seasons [2021, 2022, 2023, 2024, 2025]**
Both fit within last-complete-season 2025. **Window length is run as a sensitivity, not a
constant:** report each cell at **W3 / W4 / W5** (2020: [..2022]/[..2023]/[..2024];
2021: [..2023]/[..2024]/[..2025]) and report whether the **strategy ranking is stable**
across window length. Explicitly flagged: any finite window **clips the back end of
rookie-heavy strategies** (a 2020 rookie peaks 2023–2025); a symmetric 6-yr view is
impossible (2021 would need 2026, excluded). If the ranking flips across W3→W5, **that flip
is the result**, reported as such.

## Item 3 — slot-window widening is a strategy-correlated bias (FIXED by re-keying)
Measured support for the primary (position × **exact pick_no**) key across the 62 startups:
median cell n=**12**, p10=**2**, **78%** of cells n<20, **21%** n<5; rounds 1–2 median n=16
but **59%** still <20; **TE rounds 1–3 median n=5, p10=2**. Exact-pick keying would force
widening on most cells, the widening would be **worst for the deviant (interesting)
strategies**, and early picks can **only widen toward later, worse players** (nothing exists
before 1.01). This is a strategy-dependent bias, not a free parameter.
- **FIX:** CORPUS-AVG is re-keyed to **(position × round)** (round = ⌈pick_no/12⌉), pooling
  all corpus picks of that position in that round across the 62 leagues → far denser, no
  one-sided widening. Report **n per (position, round)** in the output; any (position,
  round) with n < `corpus_thin_min` (20) is flagged **corpus-thin** and that draw is
  excluded (logged, never imputed). The old ±slot widening rule is **removed.**
- Still reported (as the justification for re-keying): the exact-pick support distribution
  above, and the count of rounds-1–2 draws that would have required one-sided widening.

## Item 4 — TE-premium composition (KNOWN-SIGN BIAS, not a caveat)
Measured composition of the 62 in-window startups: **premium 60, non-premium 1, unknown 1**
(**97% premium**). Outcomes are scored under the target league's **no-TE-premium** rules, so
a TE a premium-league manager correctly took early scores as a *bad* pick here. **Binding
consequences:**
- CORPUS-AVG carries a **known-sign negative bias** (it drafts TEs earlier than a
  no-premium league would), **largest in the TE-heavy strategy row** and in any early-TE draw.
- A strict non-premium restriction is **infeasible (n=1)** and is reported as such.
- **Mitigation:** report a CORPUS-AVG variant **excluding the TE position** (QB/RB/WR-only
  outcome draws), so the median-manager read is trustworthy for the positions TE-premium does
  not distort. The full-roster CORPUS-AVG is reported **with the TE-premium bias flag on
  every table**; it is treated as a **lower bound** on the field for TE-forward strategies.

## Item 5 — draft-date / relative-information leakage (RESOLVED for Block 1)
Measured draft dates of the 62: **60/62 (97%) drafted BEFORE Aug 15**; the mass is
**Jan–Jun** (many *pre-NFL-draft* startups). A fixed Aug-15 MFL board would hand CONSENSUS
months of information (NFL draft, FA, camp, preseason injuries) the corpus managers lacked —
inflating the headline spread. **Resolution:** because Item 1 moves Block-1 CONSENSUS to the
**corpus-consensus board built from those same 62 drafts**, both Block-1 arms share the
managers' actual draft timing → **the timing advantage is eliminated by construction**, not
patched. Documented residual: these early/pre-draft startups valued rookies with less info
than a modern August startup; this affects **both arms equally** (same picks), so it is a
"these are unusual cohorts" note, not a spread confound. (Block 2 has no corpus counterfactual,
so no spread to inflate.)

## Item 6 — manager clustering + sampling frame (CLUSTER + SURVIVORSHIP)
Measured: **376 managers**, mean **53.9 picks/manager**, **max 694** (one whale in ~23
leagues), **235 managers with ≥30 picks**. Picks are **not independent**.
- **Binding:** all interval estimates are **clustered at the manager level** (manager-block
  bootstrap for CIs), and **per-manager influence is capped** in the CORPUS-AVG draw pool
  (a manager contributes at most a fixed weight so the 694-pick whale cannot dominate);
  report the **effective n** (design-effect-adjusted) alongside the raw 62/20,304.
- **Sampling frame (from `ingest/sleeper_corpus.py`):** BFS snowball **seeded from SFB
  Sleeper leagues**, `max_seasons_back=7` → seasons ≥ 2020, `max_leagues=400`. A startup is
  only observable if its **inaugural year is in-window (≥2020)** and at least one manager is
  **still discoverable in the 2026-07-27 crawl**. This is a **survivorship frame**: leagues
  whose managers stayed active are over-represented, so the **corpus median manager is better
  than the population median** → this **shrinks the CONSENSUS−CORPUS spread** (CORPUS-AVG
  optimistic). Logged as a named bias with sign. The 2020 startup spike (47 of 62) reflects
  both a genuine COVID-era surge and the window's back edge (pre-2020 startups are invisible;
  their in-window drafts are rookie drafts). **The 100 matched startups are drawn from the
  bounded 400-league corpus** (not the 150-league transaction cap, which only governs
  transaction pulls).

## Item 7 — Block 2 non-transfer label (BINDING)
Block 2 (2011–2019, nine draft-years, 1QB) has far more data than Block 1 (two years, SF) and
will read as "the substantial result." Every Block-2 table carries, **in the table header**,
the label: *"1QB framing, NO validated 1QB→SF translation applied — does NOT transfer to the
superflex target league; strategy-structure/decay evidence only."* Block 2 is **never** placed
adjacent to Block 1 without that label. The export leads with Block 1 (SF, the league-relevant
block), then Block 2 as clearly-fenced 1QB structural evidence.

## Item 8 — scoring definition, lineup policy, sims/seed/replacement (SPECIFIED)
**(a) Scoring metric + diff vs trade-engine VORP.** Scoring uses **realized `fp_ppr`**
(full-PPR skill points; NOT `fp_your_league`, which folds in IDP/DST scored in separate roster
slots outside this skill-draft question). A roster's seasonal score = **sum over weeks of its
optimal starting-lineup points** (lineup below). The reported metric is the **all-play win
rate** — a *relative* rank among the 12 simulated rosters — so **replacement level cancels and
is deliberately not used.** Line-by-line diff vs `engine/trade_engine.py` (which sums
`vorp_ppr_total`):
  - *Trade engine:* per-player **VORP** = season-sum of weekly `(fp_ppr − replacement_points)`,
    `replacement_points` = mean fp over the 3-player band `[N, N+2]` at **SF-adjusted ranks**
    (QB21/RB34/WR48/TE16 via `_replacement_ranks`, using `sf_qb_fill_rate=0.783`).
    Roster-construction-**agnostic** (values a stud even if you can't start him / duplicates).
  - *Backtester:* **fielded-lineup output** given the whole roster — roster-construction
    **dependent** (rewards positional balance and depth in injury/bye weeks; penalizes
    unstartable surplus). SF starter slots applied directly; the 78.3% QB-fill **emerges** from
    optimal fill rather than being imposed as a replacement rank.
  - *Difference flagged:* these can disagree — a VORP-max roster with positional surplus scores
    lower on fielded lineup. For the draft question, **fielded lineup is the correct target**;
    a secondary roster-VORP column (sum of `vorp_ppr_total`) is reported for continuity, noting
    it double-counts unstartable surplus.
**(b) Lineup constraints.** SF lineup **binds** in Block 1: QB1/RB2/WR3/TE1/FLEX2(RB/WR/TE)/
SUPERFLEX1(QB/RB/WR/TE). Block 2 uses the **1QB** lineup (no SUPERFLEX). Fill is
**weekly-optimal** (perfect start/sit each week from realized points), applied **identically to
all 12 teams** → unbiased for the *relative* win rate; documented as a scoring-side
hindsight-optimal lineup (it does **not** touch selection, so it is not a draft-time leak). A
season-level-optimal variant is spot-checked to bound the weekly-vs-season gap.
**(c) Sims / seed / replacement.** `sims_per_cell = 1000` per **(draft-year × slot × strategy
× pool)**, reported **per draft-year** (no pooling). RNG seeded from `models.seed=1729` with a
deterministic per-cell stream offset for independence + reproducibility. **Corpus draws are
without replacement within a sim** (a drawn player already on my roster is rejected and
redrawn) so **no roster can contain a duplicate player**; CONSENSUS availability is unique by
construction.

## Item 9 — draft_round missingness is genuine UDFA (VALIDATED, not asserted)
Cross-checked missing-`draft_round` players (draft_year present, actually played) against the
**independent** nflverse `load_draft_picks` table. All-2010 sample (n=40): **0 join failures**
— all textbook UDFAs (Victor Cruz, Chris Ivory, Joique Bell, …). Year-stratified 2012–2023
(n=36): **34/36 confirmed absent** from the draft table; the 2 apparent hits (James Wilder Jr.
2014, Duke Williams 2018) are **name collisions with earlier drafted players**, themselves
UDFA. Mechanism: dim_player `draft_year` = **entry/rookie year** (populated for everyone incl.
UDFA); `draft_round` is null **iff undrafted**. Conclusion: **≥94% of missing-round players are
true UDFA**; imputing UDFA is accurate, residual contamination is small and its sign is
**conservative** (a mis-imputed real draftee is *under*-valued, never over-valued). §7's
"conservative, shown not asserted" is now **shown**. Dropping remains prohibited (survivorship).

## Answers to the two standing questions
- **(position × round) is primary** (paired counterfactual to my strategy's positional choice)
  **AND slot-only is reported in every table** as the field-roster baseline (strategy-agnostic
  "what the median manager took at that slot"). Both, always — they answer different questions.
- **TE-premium-inclusive CORPUS-AVG is accepted** *only* with (Item 4) the known-sign bias flag
  on every table + the **TE-excluded QB/RB/WR variant** as the trustworthy median-manager read.
  Strict non-premium is infeasible (n=1).

## Net effect on the gate's honest scope
Block 1 (the only SF, league-relevant evidence) rests on **62 heavily-clustered, 97%-TE-premium,
survivorship-selected startups across two draft-years**. That is enough to report **per-year,
manager-clustered, bias-flagged** results with the CONSENSUS−CORPUS spread — but **not** enough
for a confident single verdict, and the write-up will say so in those words. The **corpus
filtering result itself (55,309 → 20,304 → strict-match n=2; 97% TE-premium; 97% pre-Aug-15) is
the most decision-relevant finding of the phase** and leads the export.

---

# AMENDMENTS (post-review round 3 — locked before the data layer)

Eight further items. Empirical where checkable; the rest are binding design/rule statements.
**Governs over both the body and round-2 amendments where they conflict.**

## R3-1 — corpus-consensus ADP is computed STRICTLY PER DRAFT-YEAR (leakage guard)
The Block-1 CONSENSUS board (round-2 R1) is the mean draft position **within a single draft
year**: the **2020** board uses **only 2020** startup drafts, the **2021** board uses **only
2021**. Pooling 2020+2021 would let post-2020-season rankings bleed into the 2020 board —
outcome leakage. Enforced by `assert_no_lookahead` (the consensus board for year Y is built
from picks whose draft `season == Y`, never Y±1). Confirmed binding.

## R3-2 — RENAMED "field-dispersion spread"; its SIGN is uninformative (binding)
Both Block-1 arms are summary statistics of the **same 62 drafts**: CONSENSUS = central
tendency (best-available by mean draft position), CORPUS-AVG = a single empirical draw.
Crowd-averaging reduces idiosyncratic error **by construction**, so **CONSENSUS ≥ CORPUS-AVG
is guaranteed and is NOT evidence of anything.** Therefore:
- The quantity is renamed the **field-dispersion spread** (was "ADP-discipline / execution
  spread"). **Only its magnitude is interpretable** — how much realized-outcome variance a
  single manager absorbs relative to the consensus. Any framing that treats the **sign** as a
  finding is removed from the prereg and forbidden in the export.
- It is **not** a claim that "discipline beats the field"; that interpretation is retired.

## R3-3 — pre/post NFL-draft split (EMPIRICAL; may be the Block-1 result)
Measured against each year's NFL-draft day-1 (2020-04-23, 2021-04-29):
**pre-draft startups = 40, post-draft = 22** (2020: 29 pre / 18 post; 2021: **11 pre / 4
post**). **65% of the operative corpus drafted rookies with no landing spot or draft capital.**
Binding:
- Compute the CONSENSUS board and CORPUS-AVG draws **separately for the pre- and post-draft
  cohorts**, per year, and **report whether the strategy ranking is stable across them.** If it
  flips (especially for rookie-heavy vs win-now — the headline contrast), **that flip is the
  Block-1 result**, reported as such.
- **post-2021 is n=4** — too thin for a per-year post-draft consensus; flagged and reported as
  a coverage gap, not smoothed over.

## R3-4 — thin-cell exclusion is MNAR and strategy-correlated (per-strategy accounting)
CORPUS-AVG is keyed (position × round) (round-2 R3). Exclusion of corpus-thin (position,round)
cells is **MNAR with the same strategy-correlated sign** as the widening rule it replaced.
Binding reporting:
- Per strategy, per block, report **the share of that strategy's picks that land in excluded
  cells** and the **fallback** taken (fallback = the **strategy-agnostic slot-only draw** for
  that pick, itself flagged). Any strategy with a **materially higher exclusion share** is
  **flagged in-table as not comparable** to the others.
- Report CORPUS-AVG under **both** the **(position × round)** key **and** the **(position ×
  exact pick_no)** key, plus the **within-round outcome spread** (sd of realized streams inside
  each round), so the cost of coarsening picks 1.01–1.12 into one cell is **visible**, not
  assumed away.

## R3-5 — opponent field is specified and swept (metric is undefined without it)
All-play win rate is defined only relative to the other 11 rosters; with replacement level
dropped, the **opponent field fully determines the metric**. Binding:
- Run every cell under **≥2 opponent fields**: **(F-CONS)** all 11 opponents draft
  best-available by the (year-specific) corpus-consensus board; **(F-CORP)** all 11 opponents
  are empirical corpus draws (median managers). Opponent field is a **separate axis** from my
  pool.
- Report whether the **strategy ranking is stable across F-CONS and F-CORP.** Instability is a
  reported result, not averaged away.
- Draft mechanics: 12-team snake, me at slot Y, opponents fill all other picks by their field
  policy; availability shared (a player taken is gone); no duplicate players (round-2 Item 8c).

## R3-6 — board-truncation ceiling (structural limit on discoverable edge)
The Block-1 board universe is the **835 players drafted in ≥1 of the 62 startups**. **No
strategy can express a preference for a player the field uniformly ignored** — the anti-ADP and
value-based strategies are **capped**: they can only re-order players the field already
considered, never surface a truly-ignored gem. Stated in the export **next to the corpus-
filtering result** as a structural ceiling on any measurable edge (Block 2's board is the MFL
1QB ADP list, subject to the analogous ceiling).

## R3-7 — UDFA re-verified against a NON-nflverse source (VALIDATED)
`dim_player` draft fields come from nflverse `ff_playerids` (+ DynastyProcess fill), which
shares upstream with `load_draft_picks` — so round-2 Item 9 could self-confirm. Re-checked a
year-spread sample of **12** missing-`draft_round` players (2010, 2012, 2015, 2016, 2017×2,
2019, 2020, 2021, 2022, 2023×2) against **independent web sources** (ESPN, Wikipedia, CBS, SI,
247Sports, team sites): **12/12 confirmed undrafted (UDFA), 0 contradictions.** Combined with
the 76 nflverse-confirmed, the UDFA imputation is validated against a genuinely independent
source. §7 / round-2 Item 9 stand.

## R3-8 — interval & metric hygiene (binding)
- **CIs are manager-clustered bootstrap ONLY.** The 1000-sim loop is for **estimator
  stability**, not uncertainty; **no Monte-Carlo interval from the sim loop is reported
  anywhere.** The export states this in words.
- **Non-commensurability:** the backtester's **all-play win rate** and the trade engine's
  **VORP** are on different scales and **must never be combined in a joint statement or
  arithmetic.** A one-line guard to this effect goes in the export.

## R3-9 — PRE-REGISTERED BLOCK-1 BIAS BUDGET + UNINFORMATIVE-COMPARISON RULE (written before any results)
Estimates below are **pre-data, order-of-magnitude**, in **all-play win-rate percentage points
(pp)**. They are deliberately conservative (erring large). Signs are stated relative to the
strategy comparison they distort.

| # | bias | expected sign on a strategy-vs-baseline comparison | est. magnitude (pp) | applies to |
|--:|---|---|--:|---|
| 1 | **TE-premium 97%** | penalizes strategies with higher early-TE exposure under no-TE scoring | **±4** | any comparison where early-TE exposure differs; ~0 if equal |
| 2 | **survivorship frame** | shrinks field dispersion → compresses all CORPUS-AVG spreads toward 0 | **2** | all CORPUS-AVG comparisons |
| 3 | **manager clustering** | not a point bias; widens true CI (precision loss) → raises required spread | **3** | all (as CI widening) |
| 4 | **thin-cell exclusion (MNAR)** | pulls high-exclusion (deviant) strategies toward the slot-only fallback → toward baseline | **3** | anti-ADP, early-QB, Zero/Hero-RB early rounds |
| 5 | **board truncation (835)** | caps model-strategy edge → biases \|edge\| downward | **2** | anti-ADP, value-based |
| 6 | **pre/post NFL-draft blend (65% pre)** | mis-prices pre-draft rookies → noise/bias on rookie-heavy vs win-now | **3** | youth/rebuild, win-now, and rookie-exposed strategies |

**Pre-committed rule (locked before seeing results):**
> For any pairwise strategy comparison in Block 1, sum the magnitudes of the biases above that
> **apply to that comparison and share sign**. If the **observed |field-dispersion / win-rate
> spread| is smaller than that summed magnitude**, the comparison is **reported as
> UNINFORMATIVE regardless of its point estimate**, and **no strategy recommendation may be
> issued from Block 1 alone.** A recommendation may only be made where the spread **exceeds**
> the summed same-signed bias budget **and** the manager-clustered CI excludes zero.

**Expected consequence, stated up front:** because inter-strategy win-rate spreads in a
12-team all-play are typically only a few pp, this budget will likely classify **most Block-1
pairwise comparisons as UNINFORMATIVE.** That is the **intended, honest outcome** of a
62-league, 97%-TE-premium, survivorship-selected, 65%-pre-draft sample — not a failure of the
simulator. Block 1 is built to find out *whether any edge survives the bias budget*, and the
prior is that few will.
