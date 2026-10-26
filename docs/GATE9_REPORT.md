# GATE 9 — Read-only MCP server over the warehouse (evidence & honest limits)

**Status: PASS — 9/9 sub-criteria.** The nine are `G9.1, G9.2, G9.3, G9.4, G9.5,
G9.6a, G9.6b, G9.7, G9.8` (G9.6 is split into 6a provenance + 6b determinism). **There is no
G9.9** — "9/9" counts these nine pre-registered sub-criteria, not nine top-level gates.

Pre-registration: `docs/PHASE9_PLAN.md` (with the 2026-07-29 pre-approval amendments). Server:
`jobs/mcp_server.py`. Test (one per sub-criterion): `tests/test_mcp_gate9.py`. Reproduce:
`uv run python -m tests.test_mcp_gate9`.

---

## Provenance triple (stamped on every server response — G9.6a)
```
nflverse raw-cache vintage     2026-07-29   (signature d9c462197311a92e)
corpus freeze date             2026-07-27
warehouse build id             1785335302   (= max fact_refresh_status.last_successful_refresh)
artifact baseline commit       e277ace
git commit (HEAD at gate)      e128110
```

---

## 1. Tool manifest as exposed, and the G9.7 statistic count

### Manifest (`jobs.mcp_server.TOOLS`, as currently wired)
```
tool                 kind        emits G9 numerics?   claim family
-------------------  ----------  ------------------   ---------------------------------------
trade_delta          claim       yes (6)              trade dual-pool E[Δ] VORP
archetype_gap        claim       yes (6)              5.4 archetype vs draft-capital
college_null         claim       yes (1)              5.4B college-production null
startup_strategy     claim       yes (3)              6.5 startup backtester (youth-2020)
season_state         metadata    no                   season-state resolution (G9.3)
answer               router      via routed claim     fail-closed manifest router (G9.5)
```

### The 16 statistics G9.7 verified (every emitted statistical numeric, per tool)
```
trade_delta         6   consensus {point, interval_lo, interval_hi}  +  corpus {point, interval_lo, interval_hi}
archetype_gap       6   gap (DeLong test-set) {point,lo,hi}          +  refit_estimand (percentile bootstrap) {point,lo,hi}
college_null        1   family_wise_p {point}    (interval_type NONE → no bounds counted)
startup_strategy    3   youth_2020_delta_bal {point, interval_lo, interval_hi}
                   --
                   16
```

### Claim families & intervals COVERED by those 16
```
trade dual-pool          consensus E[Δ] +8.6 [3.3, 14.5]  AND  corpus E[Δ] −76.1 [−82.8, −69.5]   (both MC_PRECISION_BAND)
archetype gap            −0.00025 [−0.0303, +0.0298]  (DELONG_PAIRED_CI)  AND  refit [−0.084, +0.018]  (PERCENTILE_BOOTSTRAP_CI)
college WY family-wise   p = 0.645  (interval_type NONE — a p-value, no CI)
youth-2020 Δ_bal         +0.152 [+0.001, +0.281]  (PERCENTILE_BOOTSTRAP_CI; uncertainty_status OVERTURNED)
```

### Claim families present in the warehouse/bundle but NOT YET exposed as tools
```
survival / hit-rates (Clock A P(relevant), Clock B career KM, per-slot rates)   — no tool
projection posteriors (5.5 shrinkage×aging×availability, QB wide intervals)      — no tool
replacement levels (SF-adjusted QB21/RB34/WR48/TE16)                             — no tool
ADP calibration & velocity (5.3; slot→capital map, SF residuals)                 — no tool
aging curves (5.1 per-age deltas)                                                — no tool
archetype/capital AUCs individually (0.901 / 0.901), AUC correlation             — not emitted as numerics
college pre-reg marginals (0/24, min 0.1035, median 0.7431) & dom-shuffle set    — not emitted as numerics
design-effect numbers (ICC, Kish mbar, deff, effective leagues)                  — not emitted (unpinned; see open items)
```

**Scope note (binding).** G9.7's pass — "every emitted statistical numeric is found at full
precision in the pinned artifact set" — is **scoped to the current manifest of 16**. It is NOT a
statement about the un-exposed families above. **Adding any tool that emits a new numeric REQUIRES
re-running Gate 9**; the 16-count and the G9.7 pass are only valid for the manifest as committed at
`e128110`.

---

## 2. The `registry_key` cross-check — derivation path on BOTH sides

The server reconciles each served value against a second pinned copy before emitting it (G9.4
DISAGREEMENT). For each `mcp_fact` the two sides trace as follows:

```
fact key                    bundle point (server reads)          registry .value (doc-consistency reads)   pins
--------------------------  -----------------------------------  ----------------------------------------  --------
trade_consensus_e_delta     drift_baseline  tv.consensus_e_delta drift_baseline  tv.consensus_e_delta      ONE PIN
trade_corpus_e_delta        drift_baseline  tv.corpus_e_delta    drift_baseline  tv.corpus_e_delta         ONE PIN
archetype_gap               archetype_gap.json  arch.gap         drift_baseline  au.gap_full               TWO PINS
archetype_gap_refit         archetype_gap.json  arch.gap         drift_baseline  au.gap_full               TWO PINS
college_wy_family_wise_p    cfb_5_4b_perm.json  wy_pre_reg.fwp   drift_baseline  college.pre_reg.fwp       TWO PINS
youth_2020_delta_bal        drift_baseline  su.youth_2020_delta  drift_baseline  su.youth_2020_delta       ONE PIN
```

(The server reads the bundle point out of `assistant_bundle.json`, a copy built by `build_bundle`
from the source artifact named above; the doc-consistency registry reads the `.value` source
directly.)

**Finding, stated plainly:**
- **3 facts are TWO independent pins** — `archetype_gap`, `archetype_gap_refit`,
  `college_wy_family_wise_p`. The served point traces to `archetype_gap.json` /
  `cfb_5_4b_perm.json`; the registry canonical traces to `drift_baseline.json`. These are two
  separately-hashed, drift-monitored artifacts (the doc-guard's own DRIFT check keeps them agreeing
  at tol 1e-6). For these, the server cross-check **verifies the value** against an independent pin.
  *(Caveat: independent PINS, not independent MEASUREMENTS — both ultimately derive from the same
  upstream computation. The check catches divergence between the two stored copies, not a wrong
  measurement common to both.)*
- **3 facts are ONE pin** — `trade_consensus_e_delta`, `trade_corpus_e_delta`,
  `youth_2020_delta_bal`. Both sides read the **same key from `drift_baseline.json`**. For these the
  cross-check **verifies the COPY STEP** (`drift_baseline.json → assistant_bundle.json`), i.e. that
  the bundle was not built stale or mutated — **it does NOT verify the value against a second
  independent derivation.** A wrong value in `drift_baseline.json` would pass unflagged on both
  sides.

**Recorded as OPEN (G9-OI-1):** the three single-pin cross-checks (trade ×2, youth-2020) are
copy-step checks, not value checks. Remedy: repoint their `registry_key` at a second independent
pin (e.g. persist the trade dual-pool E[Δ] and youth-2020 Δ into a `models/*.json` produced by a
separate run and reconcile against that), OR relabel them in the artifact as `copy_step` so the
weaker guarantee is explicit. Until then, do not read the trade/youth reconciliation as
independent-value corroboration.

---

## 3. FINDING — `read_only=True` does not block filesystem/side-channel writes (transferable)

The most transferable result of this gate. **A DuckDB connection opened with `read_only=True`
rejects writes TO THE DATABASE (INSERT/UPDATE/DELETE/CREATE/DROP) but PERMITS statements that write
elsewhere or mutate connection state**, because those are not writes to the read-only database
file. Empirically, on the warehouse connection:

```
vector                                                    read_only=True alone   through guarded_query
--------------------------------------------------------  ---------------------  ---------------------
INSERT INTO …                                             REJECTED               refused
UPDATE … SET …                                            REJECTED               refused
DELETE FROM …                                             REJECTED               refused
CREATE TABLE …                                            REJECTED               refused
DROP TABLE …                                              REJECTED               refused
COPY … TO '<path>'          (filesystem write)            *** ALLOWED ***        refused
ATTACH '<db>' AS x (READ_WRITE)  (writable attach)        *** ALLOWED ***        refused
INSTALL <ext>               (extension dir write)         *** ALLOWED ***        refused
LOAD <ext>                  (load native code)            *** ALLOWED ***        refused
"SELECT 1; DROP TABLE …"    (dynamic multi-stmt write)    (write stmt runs)      refused
```

**Mitigation (as shipped).** `read_only=True` is retained as defense-in-depth, but the binding
control is that **the server executes no caller-supplied SQL**, and every internal query is routed
through `guarded_query`, a read-statement ALLOWLIST:

```python
_READ_STMT = ^\s*(select|with|pragma\s+table_info|pragma\s+database_list)\b     # must match
_FORBIDDEN = \b(insert|update|delete|drop|create|alter|truncate|replace|merge|  # must NOT match
                copy|attach|detach|install|load|export|import|call|vacuum|
                checkpoint|reset|set)\b
```

A statement is admitted only if it matches `_READ_STMT` and contains no `_FORBIDDEN` token; it
raises `BoundaryError` before the connection is touched. All 10 vectors are refused and **none
touch disk** (`tests/test_mcp_gate9.py::g9_1` asserts the two temp paths never appear). Transferable
lesson: **do not treat `read_only=True` as a sandbox** — pair it with a statement allowlist and no
SQL passthrough.

---

## Pre-registered acceptance criteria (verbatim from `docs/PHASE9_PLAN.md`)

> **G9.1 — READ-ONLY, behavioral (not just static).** Static: no `INSERT/UPDATE/DELETE/CREATE/DROP`
> in server code, no `transform.*`/`models.*` fit import, all connections `read_only=True`.
> Behavioral runtime tests that MUST be rejected (each attempt + its rejection printed): (a) INSERT /
> UPDATE / DELETE / CREATE / DROP through every exposed tool path; (b) `COPY … TO '<path>'`
> (filesystem write); (c) `ATTACH '<db>' AS x (READ_WRITE)`; (d) `INSTALL` and `LOAD`; (e) a
> dynamically-composed SQL string carrying a write. All must raise/refuse; none may touch disk.

> **G9.2 — FRESHNESS, defined.** Clock = last successful refresh (`fact_refresh_status.
> last_successful_refresh`), not wall-time-vs-live and not the nflverse vintage. No numeric age
> threshold (failure-driven staleness). "Fresh" for a frozen-vintage-cache table means it was
> successfully (re)built from the current frozen vintage. `frozen_by_design` and `stale` can BOTH
> apply — a table that is both MUST surface BOTH fields; "genuine stale dominates" governs only
> ordering/display precedence, never suppresses the other field. Test: a stale table renders a
> visible marker; `_startup_strategy` renders frozen_by_design when unchanged and BOTH when the
> signature is mutated; a missing `fact_refresh_status` hard-fails the tool.

> **G9.3 — 2026 state: NOT-STARTED vs IN-PROGRESS.** As of 2026-07-29, zero 2026 games have been
> played. 3-value season state: `NOT_STARTED` (no completed games) → `IN_PROGRESS` (≥1 completed
> Week-1 game) → `COMPLETE`. Transition condition (named): the first completed Week-1 game. 2026 is
> `NOT_STARTED`; ADP rows labelled `2026 (offseason, not started)`. Model-input exclusion deferred to
> the Phase-10 leakage audit (stated, not assumed). Test: a tool surfacing 2026 ADP labels it
> NOT_STARTED; an injected bare-2026 value fails the response validator.

> **G9.4 — UNCERTAINTY preserved by READING the source, not restating it.** The five Phase-8
> representation rules are sourced at request time from the registry / pinned artifacts — never
> written as numeric literals in server code. If a source is missing, or the registry value disagrees
> with the artifact, the response HARD-FAILS. Tests (split): (a) LIVENESS — mutate the artifact AND
> the registry consistently, assert the output tracks; (b) DISAGREEMENT — mutate exactly one, assert
> hard fail; (c) the startup tool emits BOTH markings ("no validated edge" AND "individual edges
> UNINFORMATIVE").

> **G9.5 — FAIL-CLOSED refusals.** Any query not matching the manifest of supported questions returns
> a structured refusal, never a best-effort answer; the Phase-8 `cannot_answer` entries are the named
> refusals. Test: an off-manifest query returns a refusal, not an improvisation.

> **G9.6a — provenance.** Every response carries raw-cache vintage (nflverse FROZEN vintage +
> signature), warehouse build id (`fact_refresh_status` max `last_successful_refresh`), and git commit
> (HEAD short hash). A vintage/commit mismatch is flagged.

> **G9.6b — determinism.** An identical query across 5 fresh processes returns byte-identical payloads,
> excluding at most ONE explicitly-named `generated_at` field (test strips it). The 5 processes MUST
> run against a pinned `last_successful_refresh` so a mid-check refresh cannot break byte-identity.

> **G9.7 — NO STATISTICAL COMPUTATION AT THE BOUNDARY (scoped).** Scope = statistical quantities. No
> statistic may be computed, rescaled, re-derived, or rounded at request time; every statistical
> numeric a response emits must appear at full precision in the pinned artifact set
> (`assistant_bundle.json` ∪ `cfb_5_4b_perm.json` ∪ `archetype_gap.json` ∪ `drift_baseline.json`).
> Permitted METADATA derivations — a CLOSED list: (1) freshness-state resolution; (2)
> `max(last_successful_refresh)` as warehouse build id; (3) git-ancestry / HEAD-commit lookup; (4)
> season-state resolution. Anything not on this list is a FAIL.

> **G9.8 — OPEN ITEMS surfaced.** Any response touching Gate-6.5 or the archetype/college negatives
> MUST carry the current open-item flags, sourced from the registry (not restated). Tests (split): (a)
> TRACKS SOURCE — mutate a flag's status (OPEN → RESOLVED), assert the output follows; (b) MISSING
> SOURCE HARD-FAILS — make the source unreadable, assert hard fail (NOT silent omission).

---

## Results per criterion (from `tests/test_mcp_gate9.py`)
```
G9.1 read-only (behavioral)   PASS  static ok; 10/10 write vectors refused (incl. COPY/ATTACH/INSTALL/LOAD/dyn);
                                    legit SELECT admitted; no disk touched
G9.2 freshness (3-state)      PASS  frozen-only when signature unchanged (both_apply=False); stale+frozen surface
                                    BOTH fields (stale-first is display-only); missing fact_refresh_status hard-fails
G9.3 2026 NOT_STARTED         PASS  2026 → NOT_STARTED ('2026 (offseason, not started)'), 0 completed games,
                                    transition named; 2025 → COMPLETE; bare-2026 rejected, labelled ADP accepted
G9.4 read-not-restate         PASS  LIVENESS tracks consistent mutation; DISAGREEMENT (one-side) hard-fails;
                                    startup carries BOTH markings   [see §2 for the one-pin caveat]
G9.5 fail-closed              PASS  3 off-manifest queries → structured refusal (w/ cannot_answer); on-manifest answered
G9.6a provenance              PASS  vintage+sig, warehouse_build_id 1785335302, git e128110 present & non-empty
G9.6b determinism (5×)        PASS  byte-identical payloads across 5 fresh processes (pinned last_successful_refresh)
G9.7 no boundary computation  PASS  all 16 emitted statistics found at full precision in the pinned set;
                                    negative control absent; only the closed metadata derivations present
G9.8 open items               PASS  TRACKS SOURCE (OPEN→RESOLVED follows); MISSING SOURCE hard-fails (not omission)
```
Gate 8 (G8.1–G8.6), doc-consistency (134/134 coverage, 0 mismatches), and 5× cross-process
reproducibility were re-run and are unaffected.

---

## Open items (carried out of Gate 9)
- **G9-OI-1 — single-pin cross-checks (§2).** `trade_consensus_e_delta`, `trade_corpus_e_delta`,
  `youth_2020_delta_bal` reconcile against the SAME `drift_baseline.json` key on both sides → the
  guard verifies the copy step, not an independent value. Repoint to a second pin or relabel as
  `copy_step`.
- **Un-exposed claim families (§1).** survival/hit-rates, projections, replacement, ADP
  calibration, aging curves are in the bundle/warehouse but have no tool; the AUCs, college
  marginals, and design-effect numbers are not emitted as numerics. Adding any REQUIRES re-running
  Gate 9.
- **design-effect numbers unpinned** (from Gate-6.5 backlog, surfaced by every negative-touching
  tool): the ICC/Kish/deff values behind the youth-2020 OVERTURNED marking have no live artifact
  (`models/design_effect.json` TODO); doc-vs-registry only.
- **Season-state model-input exclusion** (G9.3): the server labels 2026 NOT_STARTED, but whether
  every model-CONSUMED input table is 2026-free is NOT verified here — deferred to the Phase-10
  leakage audit.
- **launchd not yet observed live** (Phase-7 carryover): staleness the server surfaces depends on
  `jobs/refresh.py` running on schedule; Gate-7 live install + missed-run-on-wake is still open.

---

**NOTE 2026-07-31 (Colby NOTE 0038 / G10.7v COND-A):** the `youth_2020_delta_bal` mcp_fact documented
above (`+0.152 [+0.001, +0.281]`, PERCENTILE_BOOTSTRAP_CI, uncertainty_status OVERTURNED) was
**RETIRED as a served numeric**. youth-2020 Δ_bal is now UNADJUDICATED-AND-CLOSED (corpus-limited) — a
single-seed (1729) artifact (L₀ straddles 0 across 5 seeds, B=160 mean −0.0146). `startup_strategy()`
now surfaces the closed STATUS (`youth_2020_status`) instead of a numeric; the youth registry canonical
was retired from `check_doc_consistency`. Gate-9 criteria all still PASS (9/9). See GATE6_5_REPORT
amendment 2026-07-31 + PHASE10_PLAN A20.
