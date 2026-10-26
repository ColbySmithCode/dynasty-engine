# OPEN ITEMS — single live list (guard-covered)

The one authoritative open-items list. Coverage-scanned by `jobs/check_doc_consistency.py` (with
the internal project notes' STANDING CONSTRAINTS / SESSION HANDOFF / NEXT SESSION), so it cannot silently drift.
Numeric detail lives in `docs/PHASE10_PLAN.md` amendments (referenced by letter, e.g. A14); this
file carries STATUS in words. Update the status word when an item moves; delete when truly closed.

## GATE BLOCKERS (Gate 10 cannot close while any of these is open)
- **identity.py determinism + G10.4 re-run** — **RESOLVED 2026-07-31, PASS** (was BLOCKING). Root
  cause was BROADER than `dim_player`: several nondeterminism classes (dim_player tiebreak;
  ordinal-rank ties; float aggregation-order; replacement-band — sites enumerated in PHASE10_PLAN
  A15), all fixed via the pre-registered ORDER BY remedy (determinism-only, no logic change).
  `jobs/g104_repro.fullrun(5)` = PASS, all stages byte-identical across five fresh processes
  (PHASE10_PLAN A15). Fix is in the UNCOMMITTED working tree (three source files); committing is
  Colby's. **Follow-on OPEN:** the trade E[Δ] canon re-pin from the fix's vorp change (Colby
  DECISIONS 2–3, review channel) — the re-pin uses the deterministic 200-seed mean, verdicts preserved.
- **G9-OI-1 — copy-step vs independent pin** — **OPEN, gate blocker** (G10.8). The `registry_key`
  cross-checks verify a bundle copy step, and the doc-consistency canon is partly hand-maintained
  (`startup_6_5`/`trade` read from `drift_baseline.json`, no writer job). Repoint at an
  independently-COMPUTED second pin, or relabel copy-step.
- **Gate 6.5 REOPENED** — youth-2020 Δ_bal now **TERMINAL: UNADJUDICATED-AND-CLOSED (corpus-limited)**
  (Colby NOTE 0038, G10.7v COND-A) — the "marginal edge" was a single-seed (1729) artifact, L₀ straddles
  0 across 5 seeds (B=160 mean −0.0146). The G10.6 pin is done; G10.5 (win-rate ICC) still owed as the
  design-effect validation, but its Δ_bal GATING role is moot. G10.7opt (opt SE) is MOOT (see below).

## CARRIED VALIDATION ITEMS
- **design_effect.json pinning** — **✅ RESOLVED** (G10.6, PHASE10_PLAN A19). `models/design_effect.py`
  → `design_effect.json` is the byte-checked (×5) producer, live-wired into the doc-consistency guard.
  Both seasons UNESTIMABLE → conservative Kish deffs (2020 1.62 / 2021 1.73 / pooled 1.66); pooled ICC
  0.214 ESTIMABLE.
- **youth-2020 opt SE mismatch** — **✅ MOOT** (G10.7v, NOTE 0038, A20). youth-2020 is
  UNADJUDICATED-AND-CLOSED because L₀ is a single-seed artifact (straddles 0 across seeds regardless of
  SE definition); the SD-vs-percentile SE reconciliation cannot revive the edge.
- **win-rate ICC unmeasured** — **OPEN** (G10.5). Every project design effect rests on a
  roster-strength PROXY; needs a manager-clustered, sims-OUTSIDE re-simulation. Still owed as the
  design-effect VALIDATION (compare d_out to the pooled proxy ICC 0.214); no longer gates youth-2020.
- **FROZEN.json teams vintage mismatch** — **OPEN, recorded not absorbed** (A13). The teams lookup
  was fetched one day after the raw vintage (`FROZEN.json.teams_lookup`); static data, later
  provenance stamped explicitly.

## PHASE-5 BACKLOG (G10.9 — Gate 10 must not close with these unprinted)
- **5.4B remaining pre-registered results** — **QUEUED**.
- **era-decay check on market-efficiency residuals** (Decision 8) — **QUEUED**.
- **full superflex translation table + Decision-5 stability test** — **QUEUED**.
- **G10.10 multi-year backtest** (target Y..Y+2, obs years through Decision window) — **QUEUED, NOT
  RUN**; pre-registered counts reinstated in A8; the one-year FAILS-BAR (A3/A4) stands as primary.

## OUTSIDE PHASE 10 (tracked, not Gate-10 blockers)
- **Three Gate-7 keyboard items** — **NOT YET OBSERVED**. Criteria three/four/nine target
  Wed 2026-09-02; criterion eight is a wake-test on the first sleep-through-Wednesday after launchd
  install; the in-season completeness criterion needs the first Wednesday after Week-1 MNF,
  ~2026-09-16. See PHASE7_PLAN amendment.
- **ingest/sleeper_live.py** — **DOES NOT EXIST**. Live target-league state ingester; needed to wire
  the in-season FAST path once the startup draft date is known.
