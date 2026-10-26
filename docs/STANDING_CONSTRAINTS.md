# Standing constraints

> The binding rules every result in this repo is reported under. Numbers here are checked against
> the computed artifacts by `jobs/check_doc_consistency.py`, so this file cannot silently drift.
## STANDING CONSTRAINTS (from Gate 6.5 — carry into ALL later phases)
1. **Corpus size, not model quality, is the binding constraint on any startup-strategy claim.**
   The operative SF-startup corpus is 47 leagues (2020) / **15 (2021)**, and effective independent
   units are *below* those counts (158 multi-league managers; one in ~23 leagues). No modeling
   improvement relieves this — only more corpus (Phase 7's live pipeline) does.
   _(Recompute 2026-07-29, originals above preserved. Name the quantities distinctly — stop calling
   more than one "effective independent units": **(i) leagues** 47/15/62 (drafts); **(ii) distinct
   managers** 291/128/377 (people — NOT an independent-unit count); **(iii) manager-deduped
   independent league-components** = **2 / 2 / 2** — a TOPOLOGICAL DESCRIPTOR ONLY (single-linkage
   "shares ≥1 manager" saturates; NOT a design effect). The **ceiling** on independent units is set
   by the **MEASURED design effect** (deff = 1+(mbar−1)·ICC), not (iii). ICC of manager
   roster-strength (ex-post 3-yr MEAN forward VORP, a PROXY for the win-rate outcome, which needs the
   sim) — **RE-PINNED 2026-07-31 to the producer `models/design_effect.py` (byte-checked ×5); the old
   hand-typed design-effect values had NO producer, SUPERSEDED (originals in registry `_superseded` +
   PHASE10_PLAN A19)** — = **0.11 (2020, UNESTIMABLE — CI spans 0)**; **2021 also UNESTIMABLE**
   (half-width exceeds the estimability bound) and **pooled ESTIMABLE** (2021/pooled point ICCs in
   A19). Under UNESTIMABLE→CONSERVATIVE (upper ICC bound) with the **Kish mbar** (3.68 (2020) / 4.08
   (pooled)): **deff ≈ 1.62 (2020) / 1.73 (2021) / 1.66 (pooled)** → **effective leagues ≈ 29 (2020) /
   8.7 (2021) / 37 (pooled)** (2021 falls 15→8.7 — the sharpest tightening), arithmetic mbar 1.94
   (2020) / 1.41 (2021) → deff 1.22 → 39 / 51. **ALL
   changes are CONSERVATIVE** (higher deff, fewer effective units) vs the superseded values; the corpus
   still binds. The **42 managers who appear in BOTH 2020
   and 2021** (why pooled ≠ 2020+2021 additive) are unchanged. Either way
   **≈ the league count, mildly reduced; NOT 2.** The prior "**≤15**" = the **2021 league count**
   (`docs/GATE6_5_REPORT.md:142`). 159 multi-league (was 158); max 25 leagues/manager (was ~23). CORRECTION to
   "only Phase 7 relieves it": the frozen corpus ALREADY holds **37** SF-startup leagues founded
   2022-2025 (out-of-sample; excluded by config `block1_years=[2020,2021]` — but their 5-yr outcome
   window is incomplete, see PREREG_FALSIFIER §2nd-amendment). The falsifier trigger cites the SAME
   design-effect quantity, not the saturated component count. (The earlier component-based "ceiling
   ≈ 2 / everything overturned" reading is RETRACTED — the measured design effect is mild.))_
2. **All strategy results are opponent-model-dependent** — ranking is unstable across opponent
   families (reach-window vs empirical draw). Any strategy claim MUST be reported under BOTH
   families or it is incomplete.
3. **The expanding-window leak-free ex-ante board falsifier stays QUEUED** until the corpus grows
   (it would only re-litigate a null against the same thin corpus). Revisit post-Phase-7.
4. **Trade-engine output MUST lead with BOTH pools and their CIs — NEVER a single verdict.**
   **The engine is PROSPECTIVE-CAPABLE VIA COMPARABLES** (G10.3 backlog): it prices each pick/slot by
   the realized VORP distribution of COMPARABLE players at that slot, NOT the realized future of the
   specific traded players — so it can value a trade offered today, and the corpus E[Δ] is a
   prospective valuation, not a hindsight evaluation of a historical trade.
   corpus E[Δ] **−77.9 [−84.5, −71.4]** (1.11 wins) vs consensus E[Δ] **+10.3 [+4.9, +16.1]**
   (package wins): non-overlapping, sign-consistent 200/200 — **but these brackets are MC PRECISION
   BANDS (200-seed simulator precision ONLY; they do NOT propagate aging/survival posterior
   uncertainty, pool choice, or the 0.92× rookie discount — that input-posterior uncertainty is
   UNPROPAGATED, magnitude UNKNOWN and UNQUEUED; the per-draw VORP band is NOT a proxy for it).**
   The pick-resolution assumption doesn't
   merely shift the verdict — it **reverses it decisively in both directions**. Any answer that
   states one pool's number without the other (and both CIs) is wrong by construction.

---
