"""Gate 8 — one test per pre-registered criterion G8.1-G8.6 (docs/PHASE8_PLAN.md) for the
chat-assistant bundle. The bundle's whole reason to exist is that uncertainty + provenance ARE
the product; these tests fail if any of that is silently dropped.

    uv run python -m tests.test_bundle_gate8

Setup/teardown: several tests mutate fact_refresh_status; every one restores it from the
authoritative data/refresh_status.json in a finally block so runs don't poison each other.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import duckdb

from config import CONFIG
from jobs import build_bundle as B
from jobs import read_policy as rp


def _set_stale(table: str, stale: bool) -> None:
    con = duckdb.connect(str(CONFIG.path("warehouse")))
    con.execute(
        "CREATE TABLE IF NOT EXISTS fact_refresh_status "
        "(table_name TEXT, last_successful_refresh BIGINT, stale BOOLEAN, updated BIGINT)")
    # upsert-ish: delete + reinsert the row
    con.execute("DELETE FROM fact_refresh_status WHERE table_name = ?", [table])
    con.execute("INSERT INTO fact_refresh_status VALUES (?, 1, ?, 1)", [table, stale])
    con.close()


def _drop_status_table() -> None:
    con = duckdb.connect(str(CONFIG.path("warehouse")))
    con.execute("DROP TABLE IF EXISTS fact_refresh_status")
    con.close()


# ==============================================================================================
# G8.1 — read-side scope + 2026 policy
# ==============================================================================================
def g8_1() -> list:
    fails = []
    B.restore_freshness_from_json()
    bundle = B.build_bundle()
    md = B.render_markdown(bundle)

    # (a) no table read that isn't enumerated
    for t in bundle["read_scope"]["warehouse_tables_read"]:
        if t not in B.WAREHOUSE_TABLES:
            fails.append(f"G8.1: bundle read a non-enumerated table: {t}")
    if set(bundle["read_scope"]["export_artifacts_read"]) - set(B.EXPORT_ARTIFACTS):
        fails.append("G8.1: bundle read a non-enumerated export artifact")
    if set(bundle["read_scope"].get("model_artifacts_read", [])) - set(B.MODEL_ARTIFACTS):
        fails.append("G8.1: bundle read a non-enumerated model artifact (see PHASE8_PLAN §A2)")

    # (b) the whole human doc passes the read-side 2026 guard (all 2026 labelled/offseason)
    try:
        rp.assert_no_unlabeled_2026(md)
    except AssertionError as e:
        fails.append(f"G8.1: rendered bundle has an unlabeled 2026 mention: {e}")

    # (c) inject a BARE 2026 row into user-facing text -> the guard MUST catch it
    injected = md + "\nProjected 2026 breakout: Player X leads all WRs."
    try:
        rp.assert_no_unlabeled_2026(injected)
        fails.append("G8.1: injected bare-2026 row was NOT caught (assert_no_unlabeled_2026)")
    except AssertionError:
        pass  # correctly caught

    # (d) any season-2026 fact in the bundle is explicitly labelled in-progress
    for c in bundle["claims"]:
        if c.get("id") == "adp_head":
            if c.get("season_label") != rp.LABEL:
                fails.append("G8.1: 2026 ADP claim not labelled '2026 (in-progress)'")
            for r in c.get("rows", []):
                if r.get("season_label") != rp.LABEL:
                    fails.append("G8.1: a 2026 ADP row is unlabelled")
    return fails


# ==============================================================================================
# G8.2 — freshness propagation
# ==============================================================================================
def _section(md: str, claim_id: str) -> str:
    return md.split(f"## {claim_id}")[1].split("\n## ")[0] if f"## {claim_id}" in md else ""


def g8_2() -> list:
    fails = []
    try:
        # (a) a GENUINELY stale table -> every claim derived from it renders a visible STALE marker
        _set_stale("fact_player_season", True)
        bundle = B.build_bundle()
        md = B.render_markdown(bundle)
        derived = [c for c in bundle["claims"] if "fact_player_season" in c.get("source_tables", [])]
        if not derived:
            fails.append("G8.2: no claim maps to fact_player_season (mapping missing)")
        for c in derived:
            if c.get("freshness_state") != "stale":
                fails.append(f"G8.2: claim {c['id']} derives from a stale table but state="
                             f"{c.get('freshness_state')!r}")
            if "STALE" not in _section(md, c["id"]):
                fails.append(f"G8.2: claim {c['id']} rendered without a visible STALE marker")

        # (b) frozen_by_design is DISTINCT from stale (item 4): _startup_strategy is flagged stale in
        #     fact_refresh_status but is corpus-gated -> must render FROZEN BY DESIGN with its gating
        #     condition, NOT ⚠ STALE (else consumers learn to ignore the marker).
        st = next((c for c in bundle["claims"] if c["id"] == "startup_strategy"), {})
        if st.get("freshness_state") != "frozen_by_design":
            fails.append(f"G8.2: startup_strategy must be frozen_by_design, got "
                         f"{st.get('freshness_state')!r}")
        sec = _section(md, "startup_strategy")
        if "FROZEN BY DESIGN" not in sec:
            fails.append("G8.2: frozen_by_design claim lacks a distinct FROZEN BY DESIGN marker")
        if "STALE" in sec:
            fails.append("G8.2: frozen_by_design claim wrongly rendered as STALE")
        if "corpus-gated" not in sec or "cannot update" not in sec:
            fails.append("G8.2: frozen_by_design marker missing its gating condition")
        if "_startup_strategy" not in bundle["freshness"]["frozen_by_design"] or \
                bundle["freshness"]["stale"]:
            # (_startup_strategy must be under frozen_by_design; nothing genuinely stale remains
            #  after we restore below — here fact_player_season is stale, so allow that one)
            if "_startup_strategy" not in bundle["freshness"]["frozen_by_design"]:
                fails.append("G8.2: freshness summary did not classify _startup_strategy as frozen")

        # (c) missing fact_refresh_status HARD-FAILS the build (freshness is mandatory)
        _drop_status_table()
        try:
            B.build_bundle()
            fails.append("G8.2: build did NOT hard-fail when fact_refresh_status was missing")
        except AssertionError:
            pass  # correctly hard-failed
    finally:
        B.restore_freshness_from_json()
    return fails


# ==============================================================================================
# G8.3 — uncertainty preservation (the core criterion)
# ==============================================================================================
def g8_3() -> list:
    fails = []
    B.restore_freshness_from_json()
    bundle = B.build_bundle()
    md = B.render_markdown(bundle)
    claims = {c["id"]: c for c in bundle["claims"]}
    blob = json.dumps(bundle, ensure_ascii=False)

    # .1 dual-pool trade verdict — BOTH pools, each WITH a CI
    tv = claims.get("trade_verdict", {})
    pools = tv.get("pools", {})
    if set(pools) != {"consensus", "corpus"}:
        fails.append("G8.3.1: trade verdict does not carry BOTH pools")
    for pk, pv in pools.items():
        ed = pv.get("e_delta_vorp", {})
        if ed.get("uncertainty_status") != "measured" or ed.get("ci_lo") is None:
            fails.append(f"G8.3.1: trade pool {pk} E[Δ] missing its CI")

    # .2 archetype — 'indistinguishable', gap CI spans zero, no 'beats/loses to capital'
    ar = claims.get("archetypes", {})
    if "INDISTINGUISHABLE" not in ar.get("verdict", "").upper():
        fails.append("G8.3.2: archetype verdict is not 'indistinguishable'")
    if ar.get("gap_auc", {}).get("uncertainty_status") != "measured":
        fails.append("G8.3.2: archetype gap AUC ships without its sampling CI")
    low = (ar.get("headline", "") + ar.get("verdict", "")).lower()
    if "beats capital" in low or "loses to capital" in low or "lost to capital" in low:
        fails.append("G8.3.2: archetype claim uses forbidden 'beats/loses to capital' phrasing")

    # .3 college null — sourced from the PINNED artifact. PRIMARY = pre-registered decision-rule
    #    outcome + Westfall-Young family-wise p (scheme-robust); SECONDARY = threshold-fragile 0/24
    #    count, explicitly post-hoc. Retracted CI absent; NO independence 'expected-min ≈0.04'; not
    #    bare p=0.11; the fragile count must NOT be the headline.
    co = claims.get("college_production_5_4b", {})
    art = json.loads((B.CONFIG.path("models") / B.MODEL_ARTIFACTS[0]).read_text())
    pre = art["pre_registered"]
    wyp = art["westfall_young_pre_reg_set"]        # correction FOR the pre-reg test (same set)
    wyd = art["westfall_young_domshuffle_set"]     # DIFFERENT-set robustness
    prim, sec = co.get("primary", {}), co.get("secondary_different_null", {})
    # PRIMARY: pre-registered rule outcome present and NOT met
    if prim.get("rule_met") is not False or pre["rule_met"] is not False:
        fails.append("G8.3.3: pre-registered decision-rule outcome (NOT met) not represented")
    if prim.get("n_ceiling_strata_significant", {}).get("point") != pre["n_ceiling_strata_significant"]:
        fails.append("G8.3.3: pre-registered n-strata-significant != pinned artifact")
    # PRIMARY family-wise p MUST be the COHERENT one (perm_diff exchangeable set), not the dom-shuffle
    if prim.get("westfall_young_family_wise_p", {}).get("point") != wyp["family_wise_p"]:
        fails.append("G8.3.3: primary family-wise p is not the coherent perm_diff-set correction")
    if wyp["family_wise_p"] == wyd["family_wise_p"]:
        fails.append("G8.3.3: the two nulls' family-wise p are identical (suspicious — should differ)")
    # SECONDARY must be explicitly a DIFFERENT null / robustness, not presented as confirming
    if "westfall_young_family_wise_p" not in sec or \
            sec["westfall_young_family_wise_p"]["point"] != wyd["family_wise_p"]:
        fails.append("G8.3.3: dom-shuffle robustness family-wise p missing/!= pinned")
    sec_blob = json.dumps(sec).lower()
    if "different" not in sec_blob or "not the" not in sec_blob or "fragile" not in sec_blob:
        fails.append("G8.3.3: secondary not labelled DIFFERENT-null / NOT-the-correction / fragile")
    # the headline must frame the result as UNINFORMATIVE (not a null) and carry the pre-registered
    # WY p; it must NOT report the effect as demonstrably absent.
    head = co.get("headline", "")
    if "UNINFORMATIVE" not in head.upper() or str(wyp["family_wise_p"]) not in head:
        fails.append("G8.3.3: headline does not carry UNINFORMATIVE framing + pre-registered WY p")
    if "no detectable lift" in head.lower():
        fails.append("G8.3.3: headline still claims 'no detectable lift' (over-claims a null)")
    # forbidden framings
    if "expected_min_under_null" in blob or "1/25" in blob or "1/(24+1)" in blob:
        fails.append("G8.3.3: withdrawn independence benchmark (E[min]≈0.04) still present")
    if "0.091" in blob or "[0.0, 0.091]" in blob or "[0.0,0.091]" in blob:
        fails.append("G8.3.3: RETRACTED min-selection CI [0.0, 0.091] appears in the bundle")
    if "p=0.11" in blob or "p ≥ 0.11" in blob:
        fails.append("G8.3.3: college null shipped as a bare/incorrect 'p=0.11'")

    # .4 startup — no strategy recommended + opponent-model dependence
    st = claims.get("startup_strategy", {})
    if "no" not in st.get("verdict", "").lower() or "validated edge" not in st.get("verdict", "").lower():
        fails.append("G8.3.4: startup claim does not carry 'no strategy has a validated edge'")
    if "opponent" not in st.get("opponent_dependence", "").lower():
        fails.append("G8.3.4: startup claim missing the opponent-model-dependence caveat")

    # .5 corpus-size bind present on the startup claim
    if not any("≤15" in mc or "corpus size" in mc.lower() for mc in st.get("must_carry", [])):
        fails.append("G8.3.5: startup claim missing the corpus-size (≤15 units) bind")

    # numeric schema: no estimate/rate/auc/p/winrate ships as exact; unmeasured renders visibly
    for x in B._iter_numerics(bundle):
        st_, kind = x["uncertainty_status"], x.get("kind", "estimate")
        if st_ == "exact" and kind not in B.EXACT_KINDS:
            fails.append(f"G8.3: exact used for non-allowlisted kind {kind}: {x}")
        if kind in B.ESTIMATE_KINDS and st_ == "exact":
            fails.append(f"G8.3: estimate kind {kind} shipped as exact: {x}")
        if st_ == "unmeasured" and B.UNMEASURED_TEXT not in B.fmt_num(x):
            fails.append(f"G8.3: unmeasured numeric renders without visible text: {x}")

    # validate() must REJECT a deliberately-mislabelled estimate (guard is live, not decorative)
    bad = copy.deepcopy(bundle)
    bad["claims"].append({"id": "bad", "source_tables": [],
                          "x": {"point": 0.5, "ci_lo": None, "ci_hi": None,
                                "uncertainty_status": "exact", "kind": "rate"}})
    try:
        B.validate(bad, md)
        fails.append("G8.3: validate() did NOT reject an estimate mislabelled 'exact'")
    except AssertionError:
        pass
    return fails


# ==============================================================================================
# G8.4 — vintage stamping (provenance)
# ==============================================================================================
def g8_4() -> list:
    fails = []
    B.restore_freshness_from_json()
    bundle = B.build_bundle()
    prov = bundle.get("provenance") or {}
    for k in ("nflverse_vintage", "corpus_freeze_date", "artifact_baseline_commit"):
        if not prov.get(k):
            fails.append(f"G8.4: provenance missing/empty field {k}")
    # consistent with live repo
    if B.verify_provenance(bundle):
        fails.append(f"G8.4: provenance mismatch vs live repo: {B.verify_provenance(bundle)}")
    # a deliberate mismatch is FLAGGED
    tampered = copy.deepcopy(bundle)
    tampered["provenance"]["artifact_baseline_commit"] = "deadbeef"
    if not B.verify_provenance(tampered):
        fails.append("G8.4: a tampered commit hash was NOT flagged by verify_provenance")
    return fails


# ==============================================================================================
# G8.5 — size + completeness (what is dropped first)
# ==============================================================================================
def g8_5() -> list:
    fails = []
    B.restore_freshness_from_json()

    # (a) the normal bundle is under the hard 100KB ceiling
    normal = B.build_bundle()
    if B._bundle_bytes(normal) > B.SIZE_BUDGET_BYTES:
        fails.append(f"G8.5: normal bundle {B._bundle_bytes(normal)} exceeds 100KB")

    # (b) a deliberately-oversized input triggers the drop path; DATA rows go, caveats stay
    over = B.build_bundle(inject_bloat_rows=600)
    if B._bundle_bytes(over) > B.SIZE_BUDGET_BYTES:
        fails.append(f"G8.5: oversized bundle not reduced under 100KB ({B._bundle_bytes(over)})")
    if not over.get("drop_log"):
        fails.append("G8.5: size reduction ran but drop_log is empty (silent truncation)")

    # (c) every retained claim STILL carries its CIs + freshness + the standing caveats
    if not over.get("freshness"):
        fails.append("G8.5: freshness dropped during size reduction")
    if not over.get("provenance"):
        fails.append("G8.5: provenance dropped during size reduction")
    for c in over["claims"]:
        if c.get("id") in ("trade_verdict", "archetypes", "college_production_5_4b",
                            "startup_strategy") and not c.get("must_carry"):
            fails.append(f"G8.5: claim {c['id']} lost its must_carry caveats during reduction")
    # measured numerics keep their CI after reduction
    for x in B._iter_numerics(over):
        if x["uncertainty_status"] == "measured" and (x["ci_lo"] is None or x["ci_hi"] is None):
            fails.append("G8.5: a measured numeric lost its CI during reduction")
            break
    return fails


# ==============================================================================================
# G8.6 — consumer-side retention + refusal manifest + preamble
# ==============================================================================================
def g8_6() -> list:
    fails = []
    B.restore_freshness_from_json()
    bundle = B.build_bundle()

    # (a) round-trip over the FULL probe set (retain / refuse / freeze incl. adversarial phrasings).
    #     NOTE: this offline consumer is a STRUCTURAL responder, NOT a model call — it verifies the
    #     bundle BINDS caveats/refusals/freezes to each probe. The live-model round-trip is run and
    #     reported separately (see the report), and any failure there is a Gate-8 blocker too.
    for r in B.run_round_trip(bundle, consumer=B.compliant_consumer):
        if not r["passed"]:
            fails.append(f"G8.6a: probe FAILED ({r['type']}) '{r['question']}': {r['detail']}")
    # ...and the validator PROVABLY catches a non-compliant consumer (proves it is not a no-op)
    caught = 0
    for r in B.run_round_trip(bundle, consumer=B.naive_consumer):
        if not r["passed"]:
            caught += 1
    if caught != len(B.RETENTION_PROBES):
        fails.append(f"G8.6a: naive consumer caught on only {caught}/{len(B.RETENTION_PROBES)} "
                     "probes — the validator is not adversarial enough")
    # the refuse + freeze probe types must both be exercised (adversarial coverage)
    types = {p.get("type", "retain") for p in B.RETENTION_PROBES}
    for need in ("retain", "refuse", "freeze"):
        if need not in types:
            fails.append(f"G8.6a: probe set is missing a '{need}' probe")

    # (b) cannot_answer manifest present, each entry has a question + reason
    ca = bundle.get("cannot_answer") or []
    if len(ca) < 3:
        fails.append("G8.6b: cannot_answer manifest missing or too small")
    for entry in ca:
        if not entry.get("question") or not entry.get("reason"):
            fails.append(f"G8.6b: cannot_answer entry missing question/reason: {entry}")
    # the canonical single-player-value refusal must be present
    if not any("context-free" in e["reason"] or "context-free" in e["question"] for e in ca):
        fails.append("G8.6b: cannot_answer missing the single-player context-free value refusal")

    # (c) instruction preamble states that omitting a CI/caveat is an ERROR
    pre = bundle.get("preamble", "").upper()
    if "ERROR" not in pre or "SUMMARIZATION" not in pre:
        fails.append("G8.6c: preamble does not state that omitting a CI/caveat is an ERROR")

    # (d) CONFIRMATION: the 6.5 no-edge verdict is stated as a STANDING conclusion (cannot update
    #     until the corpus grows) — not a pending one.
    st = next((c for c in bundle["claims"] if c["id"] == "startup_strategy"), {})
    sc = st.get("standing_conclusion", "")
    if "STANDING" not in sc or "corpus" not in sc.lower() or "grow" not in sc.lower():
        fails.append("G8.6d: startup claim does not state the no-edge verdict is a STANDING "
                     "conclusion that cannot update until the corpus grows")
    if not any("STANDING" in mc for mc in st.get("must_carry", [])):
        fails.append("G8.6d: 'standing conclusion' not in the startup claim's must_carry")
    return fails


# ==============================================================================================
# Doc-consistency guard — signs, sub-rounding drift, coverage (Phase-8 hardening pass)
# ==============================================================================================
def doc_guard() -> list:
    from jobs import check_doc_consistency as dc

    fails = []
    # the live registry must be clean right now
    r = dc.check()
    n = len(r["mismatches"]) + len(r["missing"]) + len(r["coverage"]["uncovered"])
    if n:
        fails.append(f"doc-guard: {n} live mismatch(es): {r['mismatches'] + r['missing']}")

    # SIGN is the verdict for the dual-pool result & the archetype gap — the guard MUST catch a flip.
    # corpus E[Δ] is canonically NEGATIVE (−77.9, re-pinned 2026-07-31); a doc writing +77.9 must fail.
    if not dc.line_sign_flips("corpus E[Δ] +77.9 [+84.5, +71.4] — package wins"):
        fails.append("doc-guard: sign-flip of corpus E[Δ] (+77.9) NOT caught")
    # archetype gap point is canonically NEGATIVE (−0.00025); +0.00025 must fail.
    if not dc.line_sign_flips("archetype gap +0.00025 favours the model"):
        fails.append("doc-guard: sign-flip of the archetype gap (+0.00025) NOT caught")
    # a CORRECTLY-signed line must NOT trip the guard
    if dc.line_sign_flips("corpus E[Δ] −77.9 [−84.5, −71.4]; consensus +10.3 [+4.9, +16.1]"):
        fails.append("doc-guard: correctly-signed dual-pool line wrongly flagged")

    # coverage over the internal project notes STANDING CONSTRAINTS must be complete (new pinned stats can't sneak in)
    cov = r["coverage"]
    if cov["total"] and cov["covered"] != cov["total"]:
        fails.append(f"doc-guard: STANDING-CONSTRAINTS coverage {cov['covered']}/{cov['total']}, "
                     f"uncovered {cov['uncovered']}")

    # sub-milli quantities (|value| < 3e-3 — e.g. archetype gap 0.00025, youth CI-lo 0.001) must
    # keep tol below the .sort()-drift scale (3e-4) so that scale of drift is detectable. Value-based,
    # NOT name-based (name-based wrongly caught the 0.777 AUC correlation).
    subm = [c for c in dc.numeric_canonicals() if 0 < abs(c["value"]) < 3e-3]
    if any(c["tol"] >= 3e-4 for c in subm):
        fails.append(f"doc-guard: a sub-milli quantity has tol >= 3e-4: "
                     f"{[c['name'] for c in subm if c['tol'] >= 3e-4]}")
    # NO entry may have a vacuous tolerance (tol >= 0.1*|value|): a comparison that can't
    # discriminate the value, and for a signed value could swallow a sign flip.
    if r["vacuous"]:
        fails.append(f"doc-guard: vacuous tolerance(s): {r['vacuous']}")
    # only the SIGNED estimates are sign-checked — not all 39 entries; keep that count honest
    if r["n_sign_checked"] != sum(1 for c in dc.numeric_canonicals() if c["sign"]):
        fails.append("doc-guard: sign-checked count drifted from the signed-entry count")
    return fails


def g10_2() -> list:
    """G10.2 (PHASE10_PLAN A7): the backtest FAILS-BAR finding is LIVE-SOURCED into the projection
    claim's must_carry (G9.4 read-not-restate) — any response with projection values carries
    'projection loses to last-year-PPG, matched info, dAUC -0.0224 [-0.0365,-0.0085]'."""
    fails = []
    p = CONFIG.path("models") / "backtest_g102.json"
    if not p.exists():
        return ["G10.2: models/backtest_g102.json missing (run `python -m models.backtest_baselines`)"]
    art = json.loads(p.read_text())
    if "last-year-PPG" not in art["must_carry"]:
        fails.append("G10.2: artifact must_carry missing the matched-info last-year-PPG headline")
    if art["must_carry"] not in B._projection_must_carry():
        fails.append("G10.2: projection claim does not carry the backtest finding")
    orig = p.read_text()
    try:  # liveness: mutate the artifact, assert the bundle tracks it (not a restated literal)
        p.write_text(json.dumps({**art, "must_carry": "SENTINEL-LIVE-CHECK-XYZ"}))
        if "SENTINEL-LIVE-CHECK-XYZ" not in B._projection_must_carry():
            fails.append("G10.2: must_carry is NOT live-sourced from the artifact (restated literal)")
    finally:
        p.write_text(orig)
    return fails


def run() -> None:
    suites = [("G8.1", g8_1), ("G8.2", g8_2), ("G8.3", g8_3),
              ("G8.4", g8_4), ("G8.5", g8_5), ("G8.6", g8_6), ("DOC-GUARD", doc_guard),
              ("G10.2", g10_2)]
    all_fails = []
    for name, fn in suites:
        fs = fn()
        status = "PASS" if not fs else "FAIL"
        print(f"[{status}] {name}")
        for f in fs:
            print("    -", f)
        all_fails += fs
    B.restore_freshness_from_json()  # leave the table in its real (fresh) state
    if all_fails:
        print(f"\n{len(all_fails)} failure(s).")
        sys.exit(1)
    print("\nPASS: Gate 8 (G8.1-G8.6) all criteria satisfied.")


if __name__ == "__main__":
    run()
