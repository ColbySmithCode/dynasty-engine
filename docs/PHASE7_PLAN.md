# PHASE 7 — Weekly Refresh + Cron (plan / pre-registration)

> Gate 6.5 closed. Phase 7 makes the pipeline *stay current* on a schedule. Pre-registered here
> before building, per project convention.

## Goal
Keep the warehouse + exports current without manual re-runs, on two cadences:
- **FAST** — Tue **00:15 ET**: pull the week's fresh numbers (current-season nflverse weekly stats
  + DynastyProcess values), rebuild the warehouse + metrics. Cheap (~minutes). No model refits.
- **FULL** — Tue **06:00 ET**: everything FAST does, plus refresh MFL ADP (current season), refit
  the models, and regenerate every export/verdict. Heavier (~tens of minutes).

Both run `jobs/refresh.py`; the mode selects the stage set.

## Binding constraints (carry-over)
1. **The corpus is FROZEN** (`data/raw/sleeper_corpus/FROZEN.json`). Neither mode re-pulls it —
   `ingest.sleeper_corpus.run()` refuses unless `VIGIL_UNFREEZE=1`. Phase-10 reproducibility
   depends on this. The refresh must never unfreeze.
2. **Idempotent + cached.** Every ingest module caches to `data/raw/`; re-running is safe. The
   current-season nflverse pull uses `force=True` (new games each week); everything else is cached
   (`force=False`), so a full run that finds nothing new is a fast no-op.
3. **2026 excluded from models** (offseason, no data). The current-season resolver
   (`resolve_current_season()` via Sleeper `/state/nfl`) drives which season is "current"; models
   still exclude the incomplete season.
4. **Fail-soft, logged.** Each stage is wrapped: a failure logs + records into the run manifest and
   does NOT abort later independent stages (a flaky source shouldn't block the rebuild). The
   manifest (`logs/refresh_<mode>_<ts>.json`) records per-stage status + duration.

## Stage sets
**FAST:** `nflverse(current, force)` → `dynastyprocess(snapshot)` → `warehouse` → `metrics`.
**FULL:** `nflverse(all, cached)` → `mfl_adp(current)` → `dynastyprocess` → `sleeper_corpus(frozen
no-op)` → `cfb(cached)` → `warehouse` → `metrics` → models `aging_curves` / `survival` /
`survival_cox` / `adp_calibration` / `projection` / `archetypes` → `engine.trade_engine` →
`models.startup_backtester` → (all exports regenerated as a side effect of the above).

## Scheduling — MEASUREMENTS (2nd-review items 2 & 3) then corrected schedule

**Item 2 — cron mechanism, measured on this machine (macOS 26.2):**
- `man 5 crontab` has **no `CRON_TZ`** entry → BSD cron here **does NOT honor `CRON_TZ`**; the
  DST-pin line is a **silent no-op**. Cron evaluates schedules in the machine's **local** time.
  This machine is on **America/New_York (EDT, −0400)**, so ET times *happen* to be honored — but
  only by coincidence of the machine TZ; if the TZ changes, the schedule follows the machine.
- **Missed-run-on-sleep:** BSD cron "wakes every minute" but a suspended machine runs nothing;
  cron does **NOT** catch up a job that was due while asleep — it is **skipped silently** (no
  anacron behavior). This is the dangerous failure mode for a laptop.
- **Remedy (adopted): `launchd`** (`jobs/launchd/com.dynasty-engine.refresh-{fast,full}.plist`,
  `plutil -lint` OK). `StartCalendarInterval` **runs a missed job on the next wake** if the
  machine was asleep at the scheduled time. launchd also uses local time (no TZ pin), so the
  plists are written for the machine's local (=ET here) time.
- **On a missed run:** cron → skipped silently; launchd `StartCalendarInterval` → **caught up once
  on wake.** Cron is retained only as a documented fallback (`jobs/crontab.txt`) with these caveats.

**Item 3 — nflverse publish latency (partial; see limitation):**
- Verified the source **lag ordering** via nflverse-data GitHub asset timestamps: `pbp` publishes
  first, `snap_counts` and `depth_charts` lag (separate scrapes). Precise per-week 2025 latency is
  **not reconstructable in the offseason** (GitHub exposes only current `updated_at`, which for
  2025 is the offseason final rebuild) — flagged as needing an in-season empirical probe (the
  manifest's `sources_as_of` will log the real lag once live).
- **Structural finding (the actionable one):** a **Tue 00:15 ET** run executes **before the
  post-Monday-Night-Football nflverse publish** (MNF ends ~23:45 ET Mon; pbp/snap_counts for it
  land Tue AM–midday ET). It would capture Sun+Thu but **systematically miss MNF every week**,
  biasing weekly metrics against the same (MNF) teams — a fixed repeating bias.
- **Corrected schedule: Wednesday AM ET** (safely past the Tue MNF publish, and after the full
  Thu→Mon slate is processed): **FAST Wed 06:00 ET, FULL Wed 07:00 ET.** Encoded in the launchd
  plists (`Weekday 3`). To be re-confirmed in-season from the manifest's measured `sources_as_of`.

**Install (launchd, recommended):**
```
cp jobs/launchd/*.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.dynasty-engine.refresh-fast.plist
launchctl load ~/Library/LaunchAgents/com.dynasty-engine.refresh-full.plist
```

## Hardening for unattended runs (2nd-review items 4–7)
- **Atomic FULL/FAST DB build (item 7).** warehouse+metrics build into a **temp db**
  (`warehouse.build.db`), are **validated** (`_validate_db`: key tables present + non-empty), then
  **atomic-renamed** into place; the prior db is **snapshotted** to `data/snapshots/` (retain last
  5). A crash/validation-failure mid-build leaves the **live warehouse untouched**. Rollback:
  `uv run python -m jobs.refresh --rollback` (restores the latest snapshot).
- **Staleness first-class (item 4).** The orchestrator writes `data/refresh_status.json` **and** a
  `fact_refresh_status` table (`table_name, last_successful_refresh, stale, updated`). Fail-soft
  **MARKS the fed tables `stale=True`**, not just logs. **Contract:** Phase 8/9 consumers MUST read
  `fact_refresh_status` and surface freshness with any output (the per-run JSON manifest in
  `logs/refresh_*.json` is for humans; the *table* is the machine-readable signal — if nothing
  reads it, fail-soft is silent corruption, hence the contract).
- **2026 exclusion guard (item 6).** `assert_no_2026_in_models()` **fails the run** if any 2026 row
  reaches a model artifact (`models/*.parquet`, cols season/year/s0). **Where 2026 is allowed:**
  `data/raw/nflverse/2026/*`, `fact_player_week`, `fact_adp` (offseason startup ADP). **Where it is
  blocked:** every model fit + derived metric (aging deltas, survival, projections) — config
  `exclude_seasons:[2026]` + `last_complete_season 2025`. The manifest records **mixed vintage**:
  fresh nflverse/ADP (today) vs **corpus frozen 2026-07-27** (`sources_as_of`).
- **Model versioning + drift (item 5).** FULL hashes every model artifact into an **append-only**
  registry (`models/_versions/registry.jsonl`; never overwritten) and runs `jobs/drift_monitor.py`
  on the three established results: **archetype AUC vs capital-only** (alert if the Decision-10
  negative result flips or AUC moves > **0.02**), **college 5.4B perm-p** (alert if any < **0.05**;
  not refit by FULL → status-reported), **trade dual-pool verdict** (alert if either pool's winner
  flips). Baselines in `jobs/drift_baseline.json`. Checks are hash-gated + fail-safe (an
  unparseable result is an info note, never a false DRIFT alert).

## CLI
`uv run python -m jobs.refresh --mode {fast|full} [--dry-run] [--only stage,stage] [--force]`.
`--dry-run` prints the stage plan without executing. Exit code non-zero if any stage failed.

## Out of scope for the FAST/FULL split (Phase 7 sub-items, tracked)
- **Live-league state ingest** (Sleeper `/league/{id}` rosters/matchups/transactions for the TARGET
  league, once the startup draft happens). No such module exists yet — the corpus ingest is the
  snowball, not the live league. Add `ingest/sleeper_live.py` when the league drafts; wire into FAST.
- **Delta reporting** ("what changed since last refresh") — nice-to-have, deferred.

## Gate 7 acceptance criteria (pre-registered; expanded for the 2nd-review hardening)
1. `--dry-run` lists the correct stages **and phases** for each mode. *(met)*
2. A FAST run completes, updates `fact_player_week`/metrics for the current season, writes a
   manifest, and leaves the corpus untouched (freeze intact). *(pending live run)*
3. A FULL run regenerates the exports; manifest shows all stages ok (or documents any down source
   in `sources_as_of` + marks fed tables stale). *(pending live run)*
4. **Atomic (item 7):** a deliberately-failed build leaves the live warehouse unchanged; `--rollback`
   restores the latest snapshot. *(mechanism built + unit-tested; live fault-injection pending)*
5. **Staleness (item 4):** `fact_refresh_status` + `refresh_status.json` written every run; a failed
   stage marks its tables `stale=True`. Phase 8/9 read-contract documented. *(built)*
6. **2026 guard (item 6):** `assert_no_2026_in_models()` passes on the current artifacts and would
   FAIL if a 2026 row reached a model artifact. *(built + verified: passes)*
7. **Versioning/drift (item 5):** artifacts hashed to the append-only registry; drift monitor runs
   on the 3 established results with no false positives. *(built + verified)*
8. **Schedule:** launchd plists installed at the item-3 corrected time (Wed AM ET); missed-run-on-
   wake behavior confirmed. *(plists built + lint-OK; install + wake-test are user/live steps)*
9. Idempotent: running twice back-to-back is a safe no-op (except the forced current-season pull).

**Live FAST validation (2026-07-29): PASS.** Wall-clock **33.8s** (nflverse_current 4.7s,
dynastyprocess 2.9s, warehouse 20.6s, metrics 4.7s), 0 failed. Atomic swap succeeded (snapshot
`warehouse_1785332051.db` retained; temp cleaned). `sources_as_of` recorded the **mixed vintage**
(nflverse/mfl/dynastyprocess 2026-07-29 vs corpus frozen 2026-07-27). Completeness: offseason →
"nothing due" (correct; per-table lag will populate in-season). `fact_refresh_status` written, all
7 tables fresh. **2026 landed exactly per policy:** `fact_adp` 5,141 rows (allowed), `fact_player_week`
0, derived metrics 0 (no leak) — confirming the read-side filter (§ item 3) is load-bearing since
`fact_adp` carries 2026.

**FULL wall-clock: not yet measured** (est. ~20–30 min: adds MFL sweep + 5 model refits + engine +
the ~13-min backtester). FAST (34s) ≪ the Wed→Thu day gap, and different-day scheduling + the lock
mean no contention regardless.

**Status:** items 1,2,4,5,6,7 + FAST live-validated. Remaining before full close: the live FULL
run (criterion 3) and launchd install + a real missed-run-on-wake observation (criterion 8).

### ⚠️ Three FAST greens are offseason-VACUOUS (not passes) — 2nd-review honesty
- **Criterion 5 (completeness):** returned `offseason/no-games — nothing due`; it has **never
  evaluated a week with games** (passed by returning early). **Requires re-verification on the
  first in-season Wednesday.**
- **Criterion 7 (drift) under FAST:** FAST does **no model refits**, so there were no fresh
  artifacts to compare — "no false positive on an empty comparison is not evidence." Exercised
  properly only by FULL.
- **Criterion 4 (atomic):** graded "mechanism proven" but `--rollback` restoring a live warehouse
  and a killed-mid-build have **never executed** — **pending the fault-injection test below.**
- The **33.8s FAST wall-clock is an offseason number** with **no in-season implication** (the
  Wed/Thu split was justified partly on in-season runtime, still unmeasured).

## FULL validation — criteria PRE-REGISTERED before launch (2nd review)
The corpus is **frozen 2026-07-27**, **2026 is blocked** from model fits, and FAST re-pulls only
the current season → refitting on **2013–2025 must reproduce the existing artifacts EXACTLY**.
1. **Reproducibility (primary).** Every model artifact hash **matches its pre-FULL value**
   (`reproducibility.all_artifacts_reproduced == true`) and the drift monitor reports **zero
   movement** on all three established results. **Any nonzero is a DEFECT** (unpinned RNG,
   nondeterministic ordering, or upstream data revision) — **NOT a finding.** If hashes differ,
   **STOP and diagnose before accepting Gate 7**; do not interpret the delta as drift.
2. **Input-data hashing.** Per-table, per-season (row-count + content hash) of the model-input
   tables for 2013–2025 recorded pre- and post-FULL (`hash_model_inputs`). Report whether
   `inputs_2013_2025_identical == true`; if inputs changed, a silent **nflverse revision** — not
   drift — is the cause, and artifact changes are then expected and must be attributed correctly.
3. **Fault injection (required, not optional).** Kill FULL mid-build; confirm the live warehouse
   is **byte-identical** to its pre-run state; run `--rollback` and verify it restores the retained
   snapshot. Criterion 4 stays **pending** until this executes. Plus: `_free_disk_ok` fails early
   with a clear message if free disk can't hold a temp build + a snapshot.

## ✅ FULL validation — reproducibility defects DIAGNOSED & FIXED (5-cross-process byte-match PASS)
The pre-registered check caught two real defects; both are now fixed and verified. **Determinism
criterion: all 7 artifacts byte-identical across 5 independent fresh-process refits**
(`tests/test_reproducibility.py`).

**Mechanism diagnosis (item 1 controls):** NONE of DuckDB `threads=1`, pinned `PYTHONHASHSEED`, or
single-thread BLAS changed the artifact bytes (`jobs/diagnose_determinism.py`) — ruling out
parallel-reduction / hash-ordering / float-order. The cause was **missing explicit ordering in the
query→polars pipeline**.

**Defect 1 (model nondeterminism) — FIXED.** (a) `survival.py` appended `clock_a`/`clock_b` rows in
nondeterministic group-iteration order → **sorted outputs by key before writing**. (b)
`aging_curves.py` iterated `deltas["archetype"].unique()` **unsorted** → `sorted(...)`. (c)
`survival_cox.py` `.first()` on `position`/`birthdate` over unordered groups → added `ORDER BY
player_uid, season` + `maintain_order=True` so `.first()` is deterministic. Values were already
deterministic in (a)/(b); only row-order differed (which is why `aging_deltas`/`survival_curves`
already byte-matched).

**Defect 2 (non-hermetic build) — FIXED.** `transform/warehouse.py` + `identity.py` now read
`rosters_weekly`/`snap_counts`/`schedules`/`player_stats` from the **frozen raw cache**
(`_cached_nflverse`), never live nflverse. Verified: a full warehouse+metrics rebuild runs in 27s
with **no network fetch** (the transient `RemoteDisconnected` path is gone) and is reproducible.
`load_teams` (static 32-row lookup) remains the one residual live call — negligible-risk, noted.

### Item 3 — REFIT spread (determinism only) vs the still-open robustness question
| result | **refit** spread (cross-process) | scope of that claim |
|---|---|---|
| trade consensus E[Δ] | sd 0.000 | pipeline deterministic |
| trade corpus E[Δ] | ~~sd 3.18~~ → **sd 0.000 after fix** | was the SAME unordered-read bug (seeded RNG × unordered pool), NOT pool uncertainty — see item 4 |
| archetype (model−capital) gap | sd 0.000 | pipeline deterministic |
| college min perm-p | sd 0.000 | pipeline deterministic |

**Correction (2nd-review item 3):** sd = 0.000 across 20 identical refits establishes
**determinism, not robustness** — "never crosses zero" is a tautology over identical inputs and is
withdrawn. The RELEVANT uncertainty is **sampling variance (CV folds / bootstrap over players),
which remains UNMEASURED here.** A separate, larger uncertainty *is* now visible: **data-vintage
variance** — the archetype gap ranges −0.014/−0.018/0.000 across nflverse vintages (**exceeds the
effect**; ADDENDUM_B finding). The negative results (model ≤ capital; 5.4B null — pinned
pre-registered rule NOT met (0/3), coherent Westfall–Young family-wise p **0.645**,
`models/cfb_5_4b_perm.json`; the earlier "0.118"/[0.0,0.091]/0.098 framings are retired) hold under
every observed vintage and are cross-corroborated, but are NOT established by the refit sd.
**Drift thresholds:** archetype fires on **ANY nonzero** gap move (refit sd=0 → any move is real,
classified as input vs code by the same run's input-hash check); trade keys on **winner-flip**
(now also deterministic); college on the 2-consecutive rule.

### Item 4 — trade corpus arm RELABELED & FIXED
The corpus arm's sd 3.18 (vs consensus 0.000) was **not** empirical-pool uncertainty and **not**
refit variance — the RNG *is* seeded (1729), but the corpus pool query lacked `ORDER BY`, so fixed
RNG indices sampled a differently-ordered pool (the same unordered-read class). **Fixed** (sorted
the pools in `engine/trade_engine.py:_pools`) → corpus E[Δ] now **sd 0.000**. The E[Δ] magnitudes
shifted (+6→+9, −74→−78) because sorting changed which rows the seeded RNG draws; **verdicts
unchanged** (package / 1.11).

### Item 4 — the escalated upstream revision
`survival_clockB` 14→15 is **consistent across refits (15/15/15) → data-driven, not RNG**. The new
group is **(TE, R3)** — a tight-end-round-3 cohort that now crosses the min-events threshold,
i.e. **nflverse revised 2013–2025 draft/production data since the Phase-5 fit** (the non-hermetic
build was reading it live). Now pinned by the hermetic freeze. Other 2013–2025 tables: the freeze
records the current input signature as the reproducible baseline (`data/raw/nflverse/FROZEN.json`);
future divergence is caught by the bump procedure, not silently absorbed.

### Item 5 — versioned freeze
`data/raw/nflverse/FROZEN.json` (vintage 2026-07-29, input signature over 2013–2025 model inputs) +
a documented **bump procedure** (re-pull → rebuild → re-run reproducibility → deliberate re-baseline
if changed) and a note that upstream corrections are now invisible-by-design and surfaced only by a
**monthly manual diff probe**, not silent drift.

### Item 6 — the two orchestration bugs (found during this FULL run)
1. **`_write_status` KeyError.** It did `STAGES[rec["stage"]]`, but guard/drift/validate records
   (`guard_2026`, `drift_monitor`, `validate_db`, `disk_check`) aren't in `STAGES` → **KeyError
   crashed the run before the manifest was written** (the FULL exit-1). Undetected, it would have
   aborted every FULL that reached the guard stage with no manifest and no status table written.
   **Did NOT affect the FAST run** (FAST has no guard/drift records). Fixed: `STAGES.get(...)`.
2. **post-stages ran after a failed db build.** `models`/`engine` executed even when `warehouse`
   failed, refitting on the **stale/unchanged** warehouse. Undetected, a FULL with a broken db
   build would silently publish artifacts fit on old data as if fresh. **Did NOT affect FAST**
   (FAST has no post stages). Fixed: post + backtester now guarded on `db_ok`.
   *(A third, backtester corpus-gate gap was also closed: it keyed only on the transaction corpus,
   so an nflverse revision to 2013–2025 scoring data wouldn't trigger a re-run — now keyed on the
   `fact_player_week` 2011–2025 signature too.)*

### The old ⛔ diagnosis (retained for provenance)

**Adjudication (git HEAD Phase-5 fit vs refit; libs unchanged (uv.lock identical), 0 fit-module
commits since the artifacts' producing commit):**

| artifact | byte | maxΔabs | branch |
|---|---|--:|---|
| aging_deltas.parquet | Y | 0.0 | PASS (reproducible) |
| survival_curves.parquet | Y | 0.0 | PASS (reproducible) |
| aging_curves.parquet | N | 1.45e1 | **model nondeterminism** |
| survival_clockA.parquet | N | 4.40e2 | **model nondeterminism** |
| cox_age_only.csv | N | 1.72e-1 | **model nondeterminism** |
| cox_age_capital.csv | N | 3.40e0 | **model nondeterminism** |
| survival_clockB.parquet | N | shape 14→15 | **input changed → upstream revision (escalate)** |

**Defect 1 — model nondeterminism on IDENTICAL input.** Refitting **twice on the same unchanged
warehouse** still yields different `aging_curves`, `cox_*`, `survival_clockA` (only `aging_deltas`
matches). The modules use **no RNG/seed** and don't sample — the cause is **unordered DuckDB reads
feeding order-dependent operations** (groupby/dedup/rank without a stable `ORDER BY`; the large
deltas rule out pure float-ordering noise). Fits are not reproducible bit-for-bit.

**Defect 2 — non-hermetic warehouse build.** `transform/warehouse.py` calls `nflreadpy` loaders
**LIVE at build time** (`load_rosters_weekly`:54, `load_snap_counts`:58, `load_schedules`:63,
`load_teams`:298; `identity.py:278 load_player_stats`) instead of the frozen `data/raw` cache. So
historical **2013–2025 inputs change whenever nflverse revises** (the `survival_clockB` 14→15 shape
change is input-driven — RNG cannot change group count), and the build depends on live network
(the transient `RemoteDisconnected` that broke this FULL). This violates the "frozen corpus" spirit
for nflverse and makes every FULL rebuild a silent surface for input change.

**Remediation (required before Gate 7 can pass):**
1. **Deterministic model reads** — add stable `ORDER BY` (and `maintain_order` on groupbys) to the
   queries feeding `aging_curves`/`survival`/`survival_cox`; re-verify byte-reproducibility on
   identical input.
2. **Hermetic build** — freeze the nflverse raw (a `FROZEN.json` like the corpus) and read
   `load_rosters_weekly`/`snap_counts`/`schedules`/`teams`/`player_stats` from **cached raw**, not
   live. Then the drift monitor's zero-movement guarantee actually holds.
3. Re-run the reproducibility check; require byte-match on all seven (or documented serialization-
   only mismatch) before accepting.

**Interim posture:** the atomic build, staleness, 2026 guard, read-policy, drift monitor, lock, TZ
guard, and FAST cadence are sound; **but the weekly FULL refit cannot be trusted to reproduce
until Defects 1 & 2 are fixed.** Until then, FULL should be treated as **regenerate-and-review**,
not unattended — and the drift monitor will false-positive on its own nondeterminism.

## Schedule change (2nd review): backtester removed from weekly FULL
The ~13-min startup backtester's inputs are the **frozen corpus**, so its output **cannot change
until the corpus grows.** It is **removed from the weekly FULL set** and now runs **only when the
corpus signature changes** (`_corpus_changed`) or **on-demand** (`--only startup_backtester`) —
eliminating recurring identical recompute and a weekly surface for a spurious "change." The
**trade engine stays in FULL** (it depends on the weekly-refreshed dynasty values).

---

## AMENDMENT 2026-07-29 — Gate-7 status audit (pre-registered criteria above UNTOUCHED)

Per-criterion status of the pre-registered Gate-7 acceptance criteria. This is a status record; the
criteria text above is immutable (append-only discipline). **Phase 7 is code-complete, GATE OPEN.**

| # | criterion | status |
|--:|---|---|
| 1 | `--dry-run` correct stages + phases | **PASSED** |
| 2 | FAST completes, updates current-season tables, manifest, freeze intact | **PASSED** (live FAST 2026-07-29, 33.8s — an offseason wall-clock) |
| 3 | FULL regenerates exports, manifest ok | **NOT YET OBSERVED** — no live FULL run |
| 4 | Atomic: failed build leaves warehouse unchanged; `--rollback` restores snapshot | **NOT YET OBSERVED** — mechanism built + unit-tested, but live kill-mid-build + rollback of a real warehouse never executed |
| 5 | Staleness written every run; failed stage marks tables stale | **PASSED (mechanism)**; the completeness-driven stale-marking is **NOT YET OBSERVED** (offseason-vacuous — never evaluated a week with games; needs the first in-season Wednesday) |
| 6 | 2026 guard passes and would fail on a 2026 model row | **PASSED** (built + verified) |
| 7 | Artifacts hashed to registry; drift monitor no false positives | **PASSED** (drift monitor verified; determinism byte-match ×5 cross-process). Caveat: FAST does no refits, so drift is exercised by FULL/repro, not FAST |
| 8 | launchd installed at Wed AM ET; missed-run-on-wake confirmed | **NOT YET OBSERVED** — plists built + lint-OK; install + wake-test are user/live steps |
| 9 | Idempotent: running twice back-to-back is a safe no-op | **NOT YET OBSERVED** — no back-to-back live run recorded |

None WAIVED. Blocking for Gate-7 close: 3, 4, 8, 9, and the in-season half of 5 — all require a
human/live step (see the internal project notes OPEN ITEMS). `ingest/sleeper_live.py` (live target-league state) is a
prerequisite for the in-season FAST path and does not exist yet.

### AMENDMENT 2026-07-29 (b) — schedule for the NOT-YET-OBSERVED criteria (item 8d)
Not left unlisted; each has a date/trigger. All are one maintenance session (~30 min) + one wake test.
| # | criterion | schedule / trigger |
|--:|---|---|
| 3 | live FULL run regenerates exports, manifest ok | **run once before NFL Week 1 (target Wed 2026-09-02)**, same session as 4/9; FULL est. 20-30 min |
| 4 | fault injection: kill mid-build + `--rollback` restores snapshot | **same 2026-09-02 session** (kill a FULL mid-stage, verify warehouse byte-identical, run --rollback) |
| 9 | idempotency: back-to-back run is a safe no-op | **same 2026-09-02 session** (run FAST twice; diff should be only the forced current-season pull) |
| 8 | launchd install + missed-run-on-wake | install 2026-09-02; **wake-test observed on the first sleep-through-Wed** thereafter |
| 5 (in-season) | completeness marks stale after games | **first in-season Wednesday (after NFL Week 1 MNF, ~2026-09-16)** |
None waived — all are cheap and gate real in-season behavior. If `ingest/sleeper_live.py` is not built
by 2026-09-02, criteria 3/4/9 can still run (they don't need it); the in-season FAST path (and the
target-league state) does need it before Week 1 use.
