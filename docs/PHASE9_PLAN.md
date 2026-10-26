# PHASE 9 — Read-only MCP server over the warehouse (plan / pre-registration)

> Pre-registered **before any server code** (project convention). Phase 9 exposes the Phase-3→8
> outputs to an MCP client (e.g. Claude Desktop) as a **read-only** tool surface. The hard rule
> inherited from Phases 6.5–8: **the uncertainty, freshness, and provenance ARE the product.** An
> MCP tool that returns a bare number without its interval/estimand/caveat/freshness silently undoes
> every correction the prior phases made. Gate 9 exists to prevent that at the tool boundary.
>
> **AMENDED 2026-07-29 (pre-approval review).** Schema hardened (§Schema), G9.4 rewritten to READ not
> restate, G9.1 made behavioral, G9.2/G9.3 pre-register their definitions, G9.5 fail-closed, G9.6
> split, and G9.7/G9.8 added. Guard regression (item 10) fixed in code: the coverage git-hash strip
> would let a stale `as of <commit>` pointer pass, so `jobs/check_doc_consistency` now verifies every
> such pointer is an ANCESTOR of HEAD (chosen over dropping the hash — the hash pinpoints the live
> amendment). `02e7f88` verified as an ancestor.

## Goal
A local (stdio) MCP server (`jobs/mcp_server.py`) that answers dynasty questions over
`data/warehouse.db` + the pinned artifacts (`exports/assistant_bundle.json`,
`models/cfb_5_4b_perm.json`, `models/archetype_gap.json`, `jobs/drift_baseline.json`), **read-only**,
never re-deriving/rescaling a statistic and never writing to the warehouse. It is the programmatic
sibling of the Phase-8 bundle: same claims, same caveats, enforced in code at every tool call.

## SCHEMA — the numeric shape that cannot collapse estimands (test-enforced)
Every numeric a tool emits uses:
```
{ point,
  interval_lo, interval_hi,
  interval_type: DELONG_PAIRED_CI | PERCENTILE_BOOTSTRAP_CI | MC_PRECISION_BAND | EXACT_CI | NONE,
  estimand:      <free text naming what the interval is ABOUT — e.g. "test-set fixed-model AUC gap"
                  vs "AUC gap under refit-on-resample">,
  uncertainty_status: ESTIMATED | UNINFORMATIVE | AT_RISK | OVERTURNED | UNPROPAGATED | OPEN }
```
- **No `ci_*` field name anywhere.** Intervals are `interval_lo/interval_hi` + `interval_type`.
- **Trade outputs MUST use `interval_type = MC_PRECISION_BAND`** and must **never** populate a field
  named `ci_*` (a lint test greps the emitted JSON keys).
- **`interval_type` set + `estimand` empty → HARD FAIL.** (Test: every emitted interval carries both
  a non-NONE `interval_type` *and* a non-empty `estimand`, or `interval_type = NONE` with no bounds.)
- `uncertainty_status` values map to the project's live states: ESTIMATED (a real CI),
  UNINFORMATIVE (test couldn't detect the pre-set effect), AT_RISK / OVERTURNED (Gate-6.5 sub-claim),
  UNPROPAGATED (e.g. trade input-posterior uncertainty), OPEN (an unresolved open item).
- **`estimand`, `interval_type`, and `uncertainty_status` are STORED IN THE PINNED ARTIFACT next to
  each value and READ (same rule as G9.4) — never typed as string literals in server code.** Free
  text in server code would be a fifth uncontrolled copy of the claim language. If an artifact value
  has no `estimand` recorded, it is ADDED to the artifact (via `build_bundle` for bundle claims), not
  invented at the boundary.

## Gate-9 acceptance criteria (PRE-REGISTERED; a test must exist for each)

### G9.1 — READ-ONLY, behavioral (not just static)
- Static: no `INSERT/UPDATE/DELETE/CREATE/DROP` in server code, no `transform.*`/`models.*` fit
  import, all connections `read_only=True`.
- **Behavioral runtime tests that MUST be rejected** (each attempt + its rejection printed): (a)
  INSERT / UPDATE / DELETE / CREATE / DROP through every exposed tool path; (b) `COPY … TO
  '<path>'` (filesystem write); (c) `ATTACH '<db>' AS x (READ_WRITE)`; (d) `INSTALL` and `LOAD`; (e)
  a dynamically-composed SQL string carrying a write. All must raise/refuse; none may touch disk.

### G9.2 — FRESHNESS, defined (pre-registered)
- **Clock:** freshness is measured against the **last successful refresh run** (`fact_refresh_status.
  last_successful_refresh`), NOT wall-time-vs-live-nflverse and NOT the nflverse vintage — the raw
  cache is FROZEN by design, so "recently pulled from live" is never the question.
- **Threshold:** there is currently **NO numeric age threshold** — a table is `stale` iff a refresh
  stage feeding it FAILED or its in-season completeness check did not pass (failure-driven, per
  `jobs/refresh._write_status`). If an age-based threshold is ever added it is **author-supplied and
  PROVISIONAL** until derived (same convention as PREREG_FALSIFIER).
- **"Fresh" for a frozen-vintage-cache table** means: it was successfully (re)built from the current
  frozen vintage on the last refresh — NOT that the vintage is current-vs-live.
- **`frozen_by_design` vs `stale` can BOTH apply:** if a frozen_by_design artifact's gating condition
  (corpus signature) changed but it was not regenerated, it is `frozen_by_design AND stale`
  ("stale-within-frozen"). Pre-registered rule: a table that is both **MUST surface BOTH fields** —
  "genuine stale dominates" governs only **ordering/display precedence** (stale shown first / more
  prominently), and NEVER suppresses the frozen_by_design field (or vice versa).
- **Test:** a stale table renders a visible STALE marker; `_startup_strategy` renders
  frozen_by_design (+gating) when its signature is unchanged, and BOTH when the signature is mutated;
  a missing `fact_refresh_status` hard-fails the tool.

### G9.3 — 2026 state: NOT-STARTED vs IN-PROGRESS
- As of 2026-07-29, **zero 2026 games have been played**, so "in-progress" is wrong. Use a
  3-value season state: **`NOT_STARTED`** (no completed games) → **`IN_PROGRESS`** (≥1 completed
  Week-1 game) → `COMPLETE`. **Transition condition (named): the first completed Week-1 game.** 2026
  is `NOT_STARTED`; ADP rows are labelled `2026 (offseason, not started)`.
- **Model-input exclusion:** `jobs.read_policy.assert_no_2026_in_models` guards the WRITE side
  (model artifacts). Whether every model-CONSUMED input table is 2026-free is **NOT independently
  verified here** — deferred to the **Phase-10 leakage audit** (stated plainly, not assumed).
- **Test:** a tool surfacing 2026 ADP labels it NOT_STARTED; an injected bare-2026 value fails the
  response validator.

### G9.4 — UNCERTAINTY preserved by READING the source, not restating it
- The five Phase-8 representation rules are **sourced at request time** from the registry / pinned
  artifacts (`assistant_bundle.json`, `cfb_5_4b_perm.json`, `archetype_gap.json`, `drift_baseline.
  json`) — **never written as numeric literals in server code.**
- **If a source is missing, or the registry value disagrees with the artifact, the response
  HARD-FAILS** (no silent degrade to a stale literal).
- Rules carried: (1) trade → BOTH pools + `MC_PRECISION_BAND` + the UNPROPAGATED input-posterior
  caveat, never one pool; (2) archetype → indistinguishable, DELONG_PAIRED_CI estimand, refit CI a
  separate estimand; (3) college → UNINFORMATIVE-not-null, pre-registered WY p only; (4) startup →
  carry **BOTH markings: "no validated edge" (direction-safe, non-validation) AND "individual
  strategy edges UNINFORMATIVE"** — emitting the former alone overstates.
- **Tests (split — the liveness and disagreement checks are distinct and must not contradict):**
  - **(a) LIVENESS:** mutate the artifact AND the registry **consistently** (same new value in both),
    assert the tool output tracks the new value. Restore state; tree left clean.
  - **(b) DISAGREEMENT:** mutate **exactly one** of the two, assert the tool **hard-fails** (no silent
    degrade to a literal). Restore state; tree left clean.
  - **(c)** the startup tool emits BOTH markings ("no validated edge" AND "individual edges
    UNINFORMATIVE").

### G9.5 — FAIL-CLOSED refusals
- Pre-registered: any query **not matching the manifest** of supported questions returns a
  **structured refusal**, never a best-effort answer; the Phase-8 `cannot_answer` entries are the
  named refusals (context-free ranking, optimal strategy, in-season advice, completed-2026,
  archetype/college yes/no). **Test:** an off-manifest query returns a refusal, not an improvisation.

### G9.6 — Provenance + determinism (split)
- **G9.6a provenance:** every response carries **raw-cache vintage** (nflverse FROZEN vintage +
  signature), **warehouse build id** (`fact_refresh_status` max `last_successful_refresh` /
  refresh-manifest id), and **git commit** (HEAD short hash). A vintage/commit mismatch is flagged.
- **G9.6b determinism:** an identical query across **5 fresh processes** returns **byte-identical
  payloads**, excluding at most ONE explicitly-named `generated_at` timestamp field (the only
  permitted variation; test strips it and byte-compares the rest). The 5 processes MUST run against a
  **pinned `last_successful_refresh`** (freshness snapshot fixed for the check) so a mid-check refresh
  cannot break byte-identity — the determinism claim is about the server, not about refresh timing.

### G9.7 — NO STATISTICAL COMPUTATION AT THE BOUNDARY (scoped)
- **Scope = statistical quantities.** No statistic may be computed, rescaled, re-derived, or rounded
  at request time; every **statistical** numeric a response emits must appear at **full precision** in
  the pinned artifact set (`assistant_bundle.json` ∪ `cfb_5_4b_perm.json` ∪ `archetype_gap.json` ∪
  `drift_baseline.json`).
- **Permitted METADATA derivations — a CLOSED list** (these are not statistics; G9.2/G9.6a require
  them): (1) freshness-state resolution (fresh/stale/frozen_by_design from `fact_refresh_status`);
  (2) `max(last_successful_refresh)` as the warehouse build id; (3) the git-ancestry / HEAD-commit
  lookup for provenance; (4) the season-state resolution (count of completed 2026 games → NOT_STARTED
  / IN_PROGRESS / COMPLETE). **Anything not on this list is a FAIL.**
- **Test:** every statistical numeric in a response is found at full precision in the pinned artifact
  set; any statistic not found fails; any request-time derivation outside the closed metadata list
  fails.

### G9.8 — OPEN ITEMS surfaced
- Any response touching Gate-6.5 or the archetype/college negatives MUST carry the current
  open-item flags, **sourced from the registry** (not restated): **youth-2020 opt SE mismatch OPEN**;
  **2021 deff=1 anti-conservative**; **design-effect numbers unpinned (no live artifact)**;
  **win-rate ICC unmeasured (roster-strength proxy only)**.
- **Tests (split — silent omission must NOT be the pass condition, per G9.4's no-silent-degrade):**
  - **(a) TRACKS SOURCE:** mutate a flag's status in the source (e.g. `OPEN → RESOLVED`), assert the
    output follows the new status. Restore; tree clean.
  - **(b) MISSING SOURCE HARD-FAILS:** make the open-items source missing/unreadable, assert the tool
    **hard-fails** — NOT that it silently omits the flags. Restore; tree clean.

## Non-goals / constraints
- **Read-only. No new science. No computation at the boundary.** Phase 9 serves Phases 3–8. Missing/
  stale artifact ⇒ staleness or hard-fail, never a silent gap.
- Sources the same pinned artifacts the doc-consistency guard already covers; hand-maintains no
  second copy of any pinned number.
- Local/stdio; interactively-authenticated MCP servers may be absent in headless runs.

## Build order (after criteria are approved)
1. `jobs/mcp_server.py` — read-only DuckDB + artifact loader, tool registry, the SCHEMA emitter.
2. Freshness / season-state / provenance wrappers (reuse `jobs/read_policy` + Phase-8 helpers).
3. Tools (trade, archetype, college, startup, hit-rates, projections, replacement, adp), each
   READING the pinned artifacts and emitting the SCHEMA + caveats + open-item flags.
4. Fail-closed refusal routing from the `cannot_answer` manifest.
5. `tests/test_mcp_gate9.py` — one test per G9.1–G9.8 (incl. the behavioral write-rejection matrix,
   the live-read mutation test, and the 5× determinism byte-check).

**Do not write server code until these criteria are reviewed and approved.**

**AMENDMENT 2026-07-31 (Colby NOTE 0038):** the open-item flag list surfaced by the MCP no longer leads
with "youth-2020 opt SE mismatch OPEN" — that flag is **MOOT** (youth-2020 Δ_bal is
UNADJUDICATED-AND-CLOSED, a single-seed artifact). The primary live open item is now
`win_rate_ICC_unmeasured` (OPEN, G10.5). See PHASE10_PLAN A20.

---

## AMENDMENT 2026-08-02 — PHASE 9 EXTENSION: remote transport for Cowork / claude.ai access

> **Pre-registered BEFORE any transport/auth implementation code** (project convention; this section
> is APPEND-ONLY like the rest). **G9.1–G9.8 are unchanged** — none of their text is edited; the
> criteria below are ADDITIVE and gate the remote-transport work only.

### Motivation + revised threat model
Custom connectors on Claude / Cowork / Claude Desktop use **remote MCP over the public internet**;
Claude connects from Anthropic's cloud, not the local device, so a `claude_desktop_config.json`
stdio server is **not reachable from Cowork or claude.ai** (verified from Anthropic docs, 2026-08-02).
Exposing the G9 server this way **changes the threat model on the standing G9 security finding**:
`read_only=True` does NOT block `COPY … TO` / `ATTACH … (READ_WRITE)` / `INSTALL` / `LOAD`
(see G9.1 note) — those are closed ONLY by `guarded_query`'s allowlist. Under stdio that allowlist
was one control in front of a local process; under remote transport **`guarded_query` becomes the
only control between the open internet and the warehouse.** Therefore **auth is a BLOCKING
requirement of this extension, not a follow-up.**

### Author-supplied implementation scope (labels per project convention)
These are the concrete choices the criteria are tested against; each is **author-supplied /
PROVISIONAL** until reviewed, and none weakens `guarded_query` or changes any schema / mart / query
(constraint: transport + auth only).
- **Transport = a minimal Streamable-HTTP JSON-RPC-2.0-over-POST endpoint** built on the Python
  stdlib (`http.server`) — no MCP SDK or web framework is installed and none is added (deps
  unchanged). It implements the handshake subset a custom connector needs (`initialize`,
  `tools/list`, `tools/call`); full SSE server→client streaming is **NOT implemented** and is a
  documented gap (the tool surface is request/response, not streaming). This is a deliberate,
  labelled scope limit, not a silent omission.
- **Parity (G9.9) is defined on the TOOL PAYLOAD, envelope-stripped.** A JSON-RPC/HTTP envelope
  (`jsonrpc`/`id`/`result`, HTTP headers) necessarily differs from the stdio JSON-lines envelope, so
  "byte-identical" is asserted on the canonical tool-result object (what `mcp_server.handle()`
  returns), serialized identically (`json.dumps(sort_keys=True, ensure_ascii=False)`) on both paths.
  Parity is guaranteed **by construction**: the HTTP path calls the SAME `mcp_server.handle()` the
  stdio path calls — it does not re-implement any tool.
- **Auth = a static Bearer token** (`Authorization: Bearer <token>`), token supplied out-of-band via
  env `DYNASTY_MCP_TOKEN`, compared in constant time. The server is **fail-closed at startup**: it
  REFUSES TO START without a token (no accidental unauthenticated public server). This is the
  minimal control that satisfies G9.10 behaviorally; **OAuth 2.0 / mTLS is the documented production
  upgrade path** and is explicitly out of scope here (labelled, not assumed-sufficient).
- **`interval_type` coverage for G9.9 (author-supplied scope note):** the served tools span **four**
  of the five `interval_type` enum values — `DELONG_PAIRED_CI`, `PERCENTILE_BOOTSTRAP_CI`,
  `MC_PRECISION_BAND`, `NONE`. **`EXACT_CI` is emitted by NO current tool** (no served `mcp_fact`
  carries it), so parity for `EXACT_CI` is **vacuous / not-applicable**, recorded here rather than
  papered over. G9.9's "spanning all enum values" is satisfied over the reachable set; the fixed
  query set covers all four reachable values with ≥5 queries.
- **No deployment is performed by this work.** The server + a documented run/tunnel path are
  delivered; standing it up on the public internet (tunnel, TLS termination, token provisioning) is
  an operator step, not a code change, and is not exercised by the gates (which bind to localhost).

### Pre-registered acceptance criteria (reviewer text, verbatim; a test must exist for each)

- **G9.9 (BLOCKING) Transport parity.** Every tool exposed over stdio is exposed over Streamable HTTP
  with byte-identical response payloads for a fixed set of at least 5 manifest queries spanning all
  `interval_type` enum values. Diff must be empty. _(Parity defined on the envelope-stripped tool
  payload; `EXACT_CI` unreachable per scope note above.)_
- **G9.10 (BLOCKING) Auth.** No unauthenticated request reaches any tool handler. Verified
  behaviorally: an unauthenticated request to every registered endpoint returns 401/403 before any
  DuckDB connection is opened. **Log-based confirmation required, not code inspection.**
- **G9.11 (BLOCKING) Write-attempt suite over HTTP.** Re-run the full behavioral write-attempt
  battery from G9.6 [sic — the G9.1 matrix] against the **HTTP** transport, not the stdio one. The
  transport change is a plausible reintroduction path. Includes `COPY`, `ATTACH` in RW mode,
  `INSTALL`, `LOAD`, and dynamically composed SQL. All must be rejected by `guarded_query` before
  reaching DuckDB.
- **G9.12 (BLOCKING) Schema enforcement survives.** `interval_type` (enum: `DELONG_PAIRED_CI`,
  `PERCENTILE_BOOTSTRAP_CI`, `MC_PRECISION_BAND`, `EXACT_CI`, `NONE`) and `estimand` remain required
  fields over HTTP. Trade outputs still reject any `ci_*` key. Verified by attempting a response
  construction that omits each in turn.
- **G9.13 (BLOCKING) Dual-pool trade reporting intact.** A trade query over HTTP returns both corpus
  E[Δ] and consensus E[Δ] with their intervals. Any single-headline-verdict path is a gate failure.
- **G9.14 (NON-BLOCKING) Concurrency.** Document DuckDB file-access behavior under >1 simultaneous
  HTTP session. If the answer is "undefined," say so rather than asserting it is safe.

**Do not write transport/auth code until these criteria are recorded (above).** Build order:
1. `jobs/mcp_http.py` — auth gate (fail-closed) → JSON-RPC dispatch → `mcp_server.handle()` (reused
   verbatim), audit log + connection counter for the G9.10 pre-DuckDB proof.
2. `tests/test_mcp_gate9_http.py` — one test per G9.9–G9.14 against a live localhost server.
3. Run the FULL gate suite (`test_mcp_gate9`, `test_bundle_gate8`, `test_reproducibility`,
   `test_no_hardcoded_canon`) — transport work must not regress any prior gate.

### OUTCOME 2026-08-02 (post-review; Colby DECISION 1 + record corrections R1–R3, N1–N3, B2)

**G9.9–G9.14: implemented and evaluated; NOT DEPLOYED. Status: SHELVED, not FAILED.**
Blocking external constraint: the Claude custom-connector auth-type enumeration offers no mechanism
usable from an individual Pro/Max account for a self-hosted server without an OAuth 2.1 authorization
server. `static_headers` is **organization-administrator-only** (citation:
https://claude.com/docs/connectors/building/authentication, retrieved 2026-08-02 — verbatim:
`static_headers` = *"Fixed credential (API key or bearer token) entered by an organization
administrator"*; *"shared by the organization rather than pasted per user"*). This is a **platform
constraint, not a defect in the implementation.**
- **Re-open condition:** org-admin access to `static_headers`, OR a decision to build an OAuth 2.1 AS.
- **Auth targeting:** SHELVED. No auth type is targeted; `custom_connection` NOT implemented; OAuth NOT
  implemented; NOT deployed (Colby DECISION 1).
- **Note for any future re-open (preferred architecture):** the tunneled-live-warehouse design on this
  branch is **NOT** the preferred architecture. Because `guarded_query` constrains all access to a
  fixed manifest, the preferred design is to **precompute the manifest results as static artifacts and
  serve those from a Worker behind OAuth**, placing **no DuckDB instance on the public internet.** The
  code in `jobs/mcp_http.py` is retained as an evaluated reference, not a deployment target.

**Record corrections to the gate result (the record must be accurate whether or not it ships):**
- **R1 — G9.9 relabelled: WIRING-VERIFIED, NOT PARITY-TESTED.** G9.9 records only that the HTTP path
  dispatches to the same handler (`mcp_server.handle()`), so a parity break is **unreachable by
  construction** — the criterion has **no power to detect one** and must not be reported as a passing
  parity test. **GATE 9 (HTTP extension) is therefore 5/6 test-backed** (G9.10–G9.14), with **G9.9
  marked WIRING-VERIFIED**, not 6/6.
- **R2 — EXACT_CI stratum of G9.9 is UNINFORMATIVE.** Zero served tools emit `EXACT_CI`, so coverage of
  that enum value is **untested, not passing**. This UNINFORMATIVE marking travels with the criterion
  wherever it is cited. (The four reachable values — DELONG_PAIRED_CI / PERCENTILE_BOOTSTRAP_CI /
  MC_PRECISION_BAND / NONE — are wiring-verified identical; `EXACT_CI` is not.)
- **R3 — G9.11 evidence SPLIT (headline correction 2026-08-02).** G9.11 is reported as two distinct
  prongs; only the first is HTTP-test-backed and counted:
  - **Live-HTTP prong (test-backed, counted):** the five canonical write vectors (`COPY` /
    `ATTACH … (READ_WRITE)` / `INSTALL` / `LOAD` / dynamically-composed SQL) were run as **LIVE HTTP
    requests** by submitting each as tool ARGUMENTS (the only caller-influenced channel over HTTP) —
    per-attempt result: **HTTP 200, no statement executed, no disk artifact, no crash.**
  - **Allowlist prong (IN-PROCESS, carried from the stdio gate, NOT an HTTP test, NOT counted):**
    `guarded_query`'s statement-level rejection of the same five vectors is verified in-process (the
    stdio G9.1 write-battery — what the G9.11 text called "G9.6"). It is a control-integrity check, not
    HTTP-transport evidence, and does **not** count toward "5/5 test-backed."
  - **PROMOTED SECURITY FINDING (out of the caveat):** the HTTP surface exposes **NO SQL sink** — no
    tool advertises a `sql`/`query`/`statement` parameter — so **the write vector is UNREACHABLE BY
    CONSTRUCTION over HTTP.** This is a **stronger** result than a passing allowlist test and is stated
    as the finding. (No static reasoning is offered as evidence for the HTTP prong.)

**B2 — documented run command uses `--host 127.0.0.1`** (not `0.0.0.0`): `cloudflared`/tunnels connect
from localhost; binding all interfaces would expose the warehouse on the LAN in plaintext. The
`jobs/mcp_http.py` argparse default is already `127.0.0.1`; canonical command:
`DYNASTY_MCP_TOKEN=<secret> uv run python -m jobs.mcp_http --host 127.0.0.1 --port 8848`.

**N1–N3 — NOT EVALUATED** (Colby DECISION 2: not deploying ⇒ these are unresolved-and-irrelevant, not
unresolved-and-risky):
- **N1 (constant-time bearer compare):** NOT EVALUATED as a gate. (Observed in code, not gate-verified:
  the comparison uses `hmac.compare_digest`, which is the same primitive as `secrets.compare_digest`.)
- **N2 (request-body size limit / rate limiting):** NOT EVALUATED. Recorded as **ABSENT** — neither is
  implemented; per DECISION 2 they are **not added in this branch.**
- **N3 (GET/SSE requirement for the connector):** NOT EVALUATED. The connector's GET/SSE requirement was
  **not confirmed against the docs** (the authentication page did not cover it); `jobs/mcp_http.py`
  implements POST-only Streamable HTTP and returns 405 on GET. Left as an open documentation question,
  irrelevant while shelved.
