# Key results

> The headline findings, with their uncertainty. Every number here is a pinned registry entry:
> `jobs/check_doc_consistency.py` fails the build if any of them drifts from the computed artifacts.

## Results

Every number here is a pinned registry entry (the doc-consistency
guard fails the build if any drifts); scope limits of the guard are stated in PHASE8_PLAN §A4.
- **Archetype vs draft-capital (2019-2022 test, n=704, 43 hits):** gap **−0.00025** (model 0.901,
  capital 0.901). The SE that pairs with the point is the **test-set fixed-model** one — DeLong
  paired **SE 0.0153** (AUC correlation 0.777), fixed-model 95% CI **[−0.0303, +0.0298]**;
  INDISTINGUISHABLE and equivalent within ~0.03 AUC. The refit-over-players CI **[−0.084, +0.018]**
  is a *different estimand* (training-instability-inflated), NOT the SE of this claim.
- **College 5.4B:** pre-registered rule **NOT met (0/3 non-R1 strata)**; coherent Westfall-Young
  family-wise p **0.645** (same exchangeable set); dom-shuffle robustness **0.4794**, min **0.1035**.
- **Trade dual-pool (RE-PINNED 2026-07-31, producer-backed — the old hand-typed figures had NO
  producer, superseded; originals in PHASE10_PLAN A16 + registry `_superseded`):** corpus E[Δ] **−77.9 [−84.5, −71.4]** vs consensus **+10.3
  [+4.9, +16.1]**, sign-consistent 200/200 — report BOTH, always. Now live-wired to
  `models/trade_mc200.json` (`jobs/g104_trade200.py`). The brackets are **MC PRECISION BANDS**
  (per-seed simulator precision only; do NOT propagate aging/survival posteriors, pool choice, or the
  rookie discount). They ALSO never captured build-rebuild nondeterminism (a historical source that
  shifted the mean by a small amount pre-fix; eliminated now that the build is deterministic, G10.4
  A15). The two pools are **common-mode** (both join the same forward-VORP streams the fix changed),
  NOT independent confirmations.
- **Startup 6.5:** no validated edge; **youth-2020 Δ_bal status: UNADJUDICATED-AND-CLOSED
  (corpus-limited)** — TERMINAL(G10.7v COND-A). The apparent "marginal edge" was a
  **SINGLE-SEED (1729) ARTIFACT**: the lower bound that excluded 0 was seed-specific; across 5 seeds
  the Δ_bal lower bound straddles 0 (B=160 mean −0.0146, all 5 seeds negative) — **the edge was NEVER
  ESTABLISHED**. Closure is corpus-limited (only a larger corpus moves it; NOT more compute on the
  frozen sample); reopens ONLY if the SF-startup corpus grows. Historical single-seed values +
  four-round status history are preserved in the GATE6_5 amendment (2026-07-31). Corpus: **62**
  leagues (2020 **47** / 2021 **15**), **377** distinct managers (291 /
  128), **159** multi-league, max **25** leagues/manager. **"≤15 effective units" is the 2021
  per-season league figure, NOT pooled** (pooled = 62 leagues). **37** more SF-startup leagues
  (founded 2022-2025) sit UNUSED in the frozen corpus.
- **THREE "registries" — use these DISTINCT names (do not say "the registry"):**
  **(1) hash-ledger** = `models/_versions/registry.jsonl` — append-only *artifact file-hashes* only
  (Phase-7 drift/repro); holds NO claim values, so −77.9 / 0.00025 etc. never appear there.
  **(2) doc-consistency canon** = pinned claim values in `jobs/check_doc_consistency.py` + baseline
  store `jobs/drift_baseline.json`, cross-checked against the prose docs.
  **(3) bundle key-map** = the Phase-8 bundle `registry_key` copy-step (G9-OI-1).
- **doc-consistency canon (2):** only the SIGNED estimates are sign-checked (trade E[Δ]±CI,
  archetype gap); the rest are magnitude/string presence — NOT every entry. (The youth-2020 Δ±CI /
  Δ_bal canonicals were RETIRED 2026-07-31 — single-seed artifact, NOT established; the guard now pins
  the CLOSED status string instead.) (Live
  entry/sign counts print from `jobs.check_doc_consistency`; not hardcoded here, as they drift.)
  **MIXED PROVENANCE (2026-07-29 audit):** college/archetype canonicals are artifact-derived + live-
  wired (drift-checked 1e-6); the `startup_6_5`/`trade_verdict` blocks are read from
  `drift_baseline.json` with NO live wiring and no writer job → **hand-maintained copies**. The 2020
  roster ICC (re-pinned 2026-07-31, producer-backed, A19) was previously checked doc-vs-registry → load-
  bearing-but-unverified (feeds deff → the youth-2020 LB); the design-effect pin in the validation
  phase closes this. The archetype DeLong `z` is **derived** from gap/SE, not independently pinned.
- **GATE 10 (validation) — IN PROGRESS; live open items in `docs/OPEN_ITEMS.md`.** G10.1 leakage
  audit **PASS**. G10.2 backtest **FAILS-BAR** — the engine projection LOSES to last-year-PPG under
  MATCHED information sets (headline; it also loses to ADP, but that comparison is
  information-asymmetric since ADP embeds offseason info the model is denied). G10.3 calibration
  **no-FAIL**: survival Clock-A **PASS-BUT-UNINFORMATIVE** (well-calibrated in magnitude but
  underpowered, with a detected sub-decision-relevant deviation), projection interval coverage
  **PASS-CONSERVATIVE** (intervals OVER-cover — safe direction, but stated ≠ realized uncertainty).
  G10.4 full-pipeline repro **PASS (byte criterion MET, 2026-07-31)** — `fullrun(5)` byte-identical
  across five fresh processes after the determinism fix (three source files, UNCOMMITTED working tree).
  A14's "dim_player-only" cause was INCOMPLETE: several nondeterminism classes (dim_player tiebreak,
  ordinal-rank ties, float aggregation-order, replacement-band), all fixed via the pre-registered ORDER
  BY remedy — determinism-only, no logic change, no thread pin (PHASE10_PLAN A15). **A downstream
  consequence — the trade E[Δ] canon re-pin from the fix's vorp change — is IN PROGRESS in the review
  channel (Colby DECISIONS 2–3); the re-pin uses the deterministic 200-seed mean, verdicts preserved.**
  G10.5-G10.9 **NOT STARTED**; G10.10 **QUEUED** (target Y..Y+2, not run). Details in
  `docs/PHASE10_PLAN.md` amendments.
- **youth-2020 Δ_bal live status: UNADJUDICATED-AND-CLOSED (corpus-limited) — TERMINAL** (Colby NOTE
  0038, G10.7v COND-A). The lower bound that made the edge look "marginal" was a single-seed (1729)
  artifact; across 5 seeds L₀ straddles 0 (B=160 mean −0.0146, all 5 negative) → edge NEVER established.
  Reopens ONLY if the corpus grows; never on more compute. (Supersedes the earlier OVERTURNED/PENDING/
  deff\*-straddle readings — all were chasing seed noise.)
- **TWO SCOPE CORRECTIONS (2026-07-30).** (a) the "network-free after caching" hermeticity claim was
  **FALSE** — the teams cache never existed, so every warehouse build made a LIVE `nfl.load_teams`
  call; now frozen with provenance (`FROZEN.json.teams_lookup`) + a build-time existence assertion
  (`transform.warehouse.assert_frozen_files_exist`). (b) the earlier "byte-match verified across
  cross-process runs" claim covered MODELS built on a FIXED `warehouse.db` only; the
  warehouse/identity REBUILD was never byte-checked — G10.4 caught it.

---

## Corpus notes

- **Startup corpus:** the operative corpus is **62 leagues / 20,304 picks** (2020–2021 superflex
  startups), not the 55,309 picks first collected. The 62 are 97% TE-premium, 65% pre-NFL-draft,
  whale-clustered, and survivorship-selected.
- **Design effect:** both seasons are UNESTIMABLE on their own, so conservative upper-bound design
  effects are used (2020 1.62 / 2021 1.73 / pooled 1.66 Kish); pooled ICC 0.214 ESTIMABLE.

## How the pipeline fits together

`ingest/*` → raw (`data/raw/`) → `transform/identity.py` (dim_player) →
`transform/warehouse.py` (builds `data/warehouse.db` from staging) →
`transform/metrics.py` (derived metrics) → `models/*` (5.1–5.5) → `engine/trade_engine.py`.
Rebuild order if starting cold: `ingest.nflverse`, `ingest.mfl_adp`, `ingest.dynastyprocess`,
`ingest.sfb`, `ingest.sleeper_corpus`, `ingest.corpus_backfill`, `ingest.cfb`, then
`transform.warehouse`, `transform.metrics`, then each `models.*`, then `engine.trade_engine`.
**The corpus is FROZEN** (`data/raw/sleeper_corpus/FROZEN.json`, 2026-07-27) — ingest
refuses to re-pull it (set `VIGIL_UNFREEZE=1` to override) so Phase-10 rebuilds reproduce.
The nflverse historical raw is likewise frozen (`data/raw/nflverse/FROZEN.json`, vintage 2026-07-29,
input signature `d9c462197311a92e`); a signature bump invalidates `drift_baseline.json` (re-baseline).

---
