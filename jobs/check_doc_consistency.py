"""Build-time guard: DOCS ARE NOT A SECOND SOURCE OF TRUTH.

The `.sort()` incident showed hardcoded numeric copies in the internal project notes / ADDENDUM_B / the GATE reports
drifting from the pinned artifacts while the bundle (which reads the artifacts live) stayed correct.
This validator cross-checks the load-bearing pinned statistics against the prose docs and FAILS the
build on mismatch.

Four guards:
  1. CANONICAL presence + SIGN — every current pinned value must appear (rounded, verbatim) in the
     docs WITH THE CORRECT SIGN. A wrong-sign occurrence FAILS (sign is the verdict for the dual-pool
     result and the archetype gap — a magnitude-only guard would be blind there).
  2. SUB-ROUNDING DRIFT — canonicals carry the pinned artifact's FULL precision; the live model
     artifact is compared against the pinned baseline with an explicit per-value tolerance, so drift
     smaller than the display rounding is caught (the archetype gap and college min-p both once moved
     at sub-rounding scale).
  3. SUPERSEDED denylist — no retired value may appear on a LIVE (non-history) doc line.
  4. COVERAGE — every number in the internal project notes' STANDING CONSTRAINTS section must map to a registry
     entry (or the year/structural allowlist), so a new pinned stat cannot enter the docs unguarded.

    uv run python -m jobs.check_doc_consistency        # print registry + report; exit 1 on mismatch
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CONFIG, REPO_ROOT

DOCS = ["docs/STANDING_CONSTRAINTS.md", "docs/KEY_RESULTS.md", "docs/ADDENDUM_B.md", "docs/GATE5_4B_REPORT.md", "docs/PHASE7_PLAN.md",
        "docs/PHASE8_PLAN.md"]
SIGN_CHARS = "+-−"          # ASCII plus/hyphen and Unicode minus (U+2212)

SKIP_MARKERS = ("supersed", "older", "prior", "retract", "withdraw", "history", "was wrong",
                "was a", "interim", "→", "->", "amended", "not seeded-pinned", "artifact)",
                "rng-stream", "wobble", "the report's original", "originally-documented",
                "earlier", "no longer", "0.11 →", "reproduces", "predate", "consistent with but")

SUPERSEDED = ["0.098", "0.0546", "0.4882", "0.5753", "0.744", "0.118", "0.091"]

# Numbers in STANDING CONSTRAINTS that are structure, not pinned stats (constraint indices, gate
# numbers, years). Everything else in that section MUST have a registry entry (coverage guard).
NON_STAT = ({str(d) for d in range(10)}                     # bare single digits are structural
            | {"6.5", "5.4", "39", "10"}                    # gate/phase labels, registry size
            | {str(y) for y in range(2010, 2031)})          # years


def _load():
    art = json.loads((CONFIG.path("models") / "cfb_5_4b_perm.json").read_text())
    base = json.loads((REPO_ROOT / "jobs" / "drift_baseline.json").read_text())
    ag_path = CONFIG.path("models") / "archetype_gap.json"
    arch = json.loads(ag_path.read_text()) if ag_path.exists() else None
    tmc_path = CONFIG.path("models") / "trade_mc200.json"
    tmc = json.loads(tmc_path.read_text()) if tmc_path.exists() else None
    de_path = CONFIG.path("models") / "design_effect.json"
    de = json.loads(de_path.read_text()) if de_path.exists() else None
    return art, base, arch, tmc, de


def _num(name, value, places, tol, signed=False, display=None, live=None):
    """A numeric canonical. `value` is signed full precision (pinned baseline). `display` overrides
    the rounded magnitude string as it appears in docs. `live` = the current artifact value for the
    same quantity (sub-rounding-drift check), or None."""
    mag = display if display is not None else (
        str(int(round(abs(value)))) if places == 0 else f"{abs(value):.{places}f}")
    return {"name": name, "value": value, "mag": mag, "tol": tol,
            "sign": (1 if value > 0 else -1 if value < 0 else 0) if signed else 0, "live": live}


def numeric_canonicals() -> list[dict]:
    art, base, arch, tmc, de = _load()
    pre = art["pre_registered"]
    wyp, wyd = art["westfall_young_pre_reg_set"], art["westfall_young_domshuffle_set"]
    bpre = base["college_perm_p"]["pre_registered"]
    bdom = base["college_perm_p"]["westfall_young_domshuffle"]
    au, tv, su = base["archetype_auc"], base["trade_verdict"], base["startup_6_5"]
    de2020 = (de["years"]["2020"]["primary_expost_3yr_mean"] if de else {})
    de2021 = (de["years"]["2021"]["primary_expost_3yr_mean"] if de else {})
    depool = (de["years"]["pooled"]["primary_expost_3yr_mean"] if de else {})
    return [
        # --- college PRIMARY (pre-registered) --- live vs baseline drift-checked at TIGHT tol ---
        # SUB-MILLI quantities use tol 1e-6, not the 5e-4 default: 5e-4 exceeds the archetype gap
        # magnitude (0.00025) and matches the .sort() drift scale (3e-4), so it could not detect
        # drift at that scale. 1e-6 catches any change visible at the artifact's 4dp rounding.
        _num("college pre-reg min marginal p", bpre["min_marginal_p"], 4, 1e-6,
             live=pre["min_marginal_p"]),
        _num("college pre-reg median marginal p", bpre["median_marginal_p"], 4, 1e-6,
             live=pre["median_marginal_p"]),
        _num("college pre-reg coherent WY family-wise p", bpre["family_wise_p"], 3, 1e-6,
             live=wyp["family_wise_p"]),
        # --- college SECONDARY (dom-shuffle, different exchangeable set) ---
        _num("college dom-shuffle WY family-wise p", bdom["family_wise_p"], 4, 1e-6,
             live=wyd["family_wise_p"]),
        _num("college dom-shuffle min marginal p", bdom["min_marginal_p"], 4, 1e-6,
             live=wyd["min_marginal_p"]),
        _num("college dom-shuffle median marginal p", bdom["median_marginal_p"], 4, 1e-6,
             live=wyd["median_marginal_p"]),
        # --- archetype AUCs + gap (SIGNED) --- full precision, display 3dp, TIGHT tol ---
        # NOW wired to the live artifact models/archetype_gap.json (item 6): the drift check compares
        # registry vs live at tol 1e-6, closing the former ~4e-6 blind spot on the gap.
        _num("archetype model AUC", au["model_full"], 3, 1e-6, display="0.901",
             live=(arch["model_auc"] if arch else None)),
        _num("archetype capital-only AUC", au["capital_full"], 3, 1e-6, display="0.901",
             live=(arch["capital_auc"] if arch else None)),
        _num("archetype gap point (signed)", au["gap_full"], 5, 1e-6, signed=True,
             live=(arch["gap"] if arch else None)),
        # test-set fixed-model estimand (the SE that pairs with the point) — DeLong + bootstrap
        _num("archetype test-set DeLong SE", au["testset_delong_se"], 4, 5e-4),
        _num("archetype test-set CI lo (signed)", au["testset_ci_lo"], 4, 5e-4, signed=True),
        _num("archetype test-set CI hi (signed)", au["testset_ci_hi"], 4, 5e-4, signed=True),
        _num("archetype AUC correlation", au["auc_corr"], 3, 5e-4),
        # --- recomputed 2026-07-29 manager-deduped corpus counts (originals 158/23 kept below) ---
        _num("distinct managers 2020", su["distinct_managers_2020"], 0, 0.5),
        _num("distinct managers 2021", su["distinct_managers_2021"], 0, 0.5),
        _num("distinct managers pooled", su["distinct_managers_pooled"], 0, 0.5),
        _num("multi-league managers (recomputed 159)", su["multi_league_managers_recomputed"], 0, 0.5),
        _num("max leagues/manager (recomputed 25)", su["max_leagues_per_manager_recomputed"], 0, 0.5),
        _num("SF-startups founded 2022-2025 (leagues)", su["corpus_2022_2025_leagues"], 0, 0.5),
        # measured design effect (item 1) — RE-PINNED 2026-07-31, now LIVE-WIRED to the byte-checked
        # producer models/design_effect.json (both seasons UNESTIMABLE->conservative deffs; A19).
        _num("roster ICC 2020", su["roster_icc_2020"], 2, 5e-4, live=de2020.get("icc")),
        _num("mbar 2020 (arith)", su["mbar_2020"], 2, 5e-4),
        _num("mbar 2021 (arith)", su["mbar_2021"], 2, 5e-4),
        _num("design effect 2020 (arith)", su["deff_2020"], 2, 5e-4, live=de2020.get("deff_arith_conservative")),
        _num("effective leagues 2020 (arith)", su["eff_leagues_2020"], 0, 0.5, live=de2020.get("eff_leagues_arith_conservative")),
        _num("effective leagues pooled (arith)", su["eff_leagues_pooled"], 0, 0.5, live=depool.get("eff_leagues_arith_conservative")),
        _num("mbar 2020 (Kish)", su["mbar_2020_kish"], 2, 5e-4),
        _num("mbar pooled (Kish)", su["mbar_pooled_kish"], 2, 5e-4),
        _num("design effect 2020 (Kish)", su["deff_2020_kish"], 2, 5e-4, live=de2020.get("deff_kish_conservative")),
        _num("design effect 2021 (Kish)", su["deff_2021_kish"], 2, 5e-4, live=de2021.get("deff_kish_conservative")),
        _num("effective leagues 2021 (Kish)", su["eff_leagues_2021_kish"], 1, 0.5, live=de2021.get("eff_leagues_kish_conservative")),
        _num("design effect pooled (Kish)", su["deff_pooled_kish"], 2, 5e-4, live=depool.get("deff_kish_conservative")),
        _num("effective leagues 2020 (Kish)", su["eff_leagues_2020_kish"], 0, 0.5, live=de2020.get("eff_leagues_kish_conservative")),
        _num("effective leagues pooled (Kish)", su["eff_leagues_pooled_kish"], 0, 0.5, live=depool.get("eff_leagues_kish_conservative")),
        _num("managers in both seasons (42)", su["managers_both_seasons"], 0, 0.5),
        _num("roster ICC pooled", su["roster_icc_pooled"], 3, 5e-4, live=depool.get("icc")),
        # youth-2020 terminal EVIDENCE (replaces the retired +0.001 "marginal edge": the B=160 5-seed
        # L0 mean, signed — negative, confirming the lower bound straddles 0; Colby NOTE 0038).
        _num("youth-2020 L₀ B=160 5-seed mean (signed)", su["youth_2020_L0_5seed_b160_mean"], 4, 1e-6,
             signed=True),
        _num("archetype gap CI lo (signed)", au["gap_ci_lo"], 3, 5e-4, signed=True),
        # gap CI hi magnitude 0.018 collides with the documented vintage gap −0.018 (a DIFFERENT
        # quantity), so it is guarded as a signed INTERVAL string (below), not a lone bound.
        _num("archetype gap CI hi", au["gap_ci_hi"], 3, 5e-4, signed=False),
        # --- trade dual-pool E[Δ] + CIs (SIGNED — sign IS the verdict) ---
        # NOW live-wired to models/trade_mc200.json (jobs/g104_trade200.py producer) — closes the
        # trade-block copy_step: the canon is compared against a byte-reproducible artifact, not a
        # second hand-typed copy. -76.1/+8.6 had NO producer (superseded 2026-07-31).
        _num("trade corpus E[Δ] (signed)", tv["corpus_e_delta"], 1, 0.05, signed=True,
             live=(tmc["corpus"]["mean"] if tmc else None)),
        _num("trade corpus CI lo (signed)", tv["corpus_ci_lo"], 1, 0.05, signed=True,
             live=(tmc["corpus"]["ci_lo"] if tmc else None)),
        _num("trade corpus CI hi (signed)", tv["corpus_ci_hi"], 1, 0.05, signed=True,
             live=(tmc["corpus"]["ci_hi"] if tmc else None)),
        _num("trade consensus E[Δ] (signed)", tv["consensus_e_delta"], 1, 0.05, signed=True,
             live=(tmc["consensus"]["mean"] if tmc else None)),
        _num("trade consensus CI lo (signed)", tv["consensus_ci_lo"], 1, 0.05, signed=True,
             live=(tmc["consensus"]["ci_lo"] if tmc else None)),
        _num("trade consensus CI hi (signed)", tv["consensus_ci_hi"], 1, 0.05, signed=True,
             live=(tmc["consensus"]["ci_hi"] if tmc else None)),
        _num("trade sign-consistency (200/200)", tv["sign_consistency"], 0, 0.5),
        _num("rookie unknowability discount (0.92)", tv["rookie_discount"], 2, 0.005),
        _num("trade pick 1.11", 1.11, 2, 0.005),
        # --- startup 6.5 ---
        # youth-2020 Δ_bal canonicals (+0.152 / +0.001 / +0.281 / 0.116) RETIRED 2026-07-31 (Colby
        # NOTE 0038, COND-A terminal): the +0.001 lower bound was a SINGLE-SEED (1729) artifact — L0
        # straddles 0 across seeds (B=160 mean -0.0146). The guard MUST NOT keep serving the superseded
        # "marginal edge", so these are no longer live doc canonicals; the historical single-seed values
        # are preserved in drift_baseline `_youth_2020_terminal_2026_07_31` + the GATE6_5 amendment.
        # The terminal STATUS is now the guarded canonical (string_canonicals, below).
        _num("corpus leagues (62)", su["corpus_leagues"], 0, 0.5),
        _num("corpus picks (20,304)", su["corpus_picks"], 0, 0.5, display="20,304"),
        _num("effective units 2021 (15)", su["effective_units_2021"], 0, 0.5),
        _num("corpus 2020 leagues (47)", su["corpus_2020_leagues"], 0, 0.5),
        _num("multi-league managers (158)", su["multi_league_managers"], 0, 0.5),
        _num("max leagues per manager (23)", su["max_leagues_per_manager"], 0, 0.5),
        _num("archetype test-set n (704)", au["test_n"], 0, 0.5),
        _num("archetype test-set hits (43)", 43, 0, 0.5),
    ]


def string_canonicals() -> list[dict]:
    art, base, arch, tmc, de = _load()
    vi = base["vintages"]
    B, seed = art["B"], art["seed"]
    return [
        {"name": "WY permutation B", "any": [f"B={B}", f"B {B}", str(B)]},
        {"name": "seed", "any": [f"seed {seed}", f"seed={seed}", str(seed)]},
        {"name": "archetype test years", "any": ["2019-2022", "2019–2022", "2019-22", "2019–22"]},
        {"name": "nflverse vintage", "any": [vi["nflverse"]]},
        {"name": "corpus freeze date", "any": [vi["corpus_freeze"]]},
        {"name": "nflverse FROZEN signature", "any": [vi["nflverse_signature"]]},
        {"name": "pre-reg rule outcome (0/3, NOT met)", "any": ["0/3"]},
        {"name": "dom-shuffle count (0/24)", "any": ["0/24"]},
        # signed gap CI as an interval (guards BOTH bound signs as a unit; avoids the lone-0.018
        # collision with the vintage-gap −0.018):
        {"name": "archetype gap CI interval [−0.084, +0.018]",
         "any": ["[−0.084, +0.018]", "[-0.084, +0.018]", "[−0.084,+0.018]", "[-0.084,+0.018]"]},
        # youth-2020 terminal status (replaces the retired +0.152/+0.001/+0.281/0.116 canonicals;
        # Colby NOTE 0038). The guard now enforces the CLOSED status text, not the artifact edge.
        {"name": "youth-2020 terminal status", "any": ["UNADJUDICATED-AND-CLOSED"]},
    ]


def _signed_hits(mag: str, line: str):
    """Yield the sign (+1 / -1 / 0-for-bare) of each standalone occurrence of `mag` on `line`.
    NOTE: the sign class is `[+\\-\\u2212]` with the hyphen ESCAPED — writing it as `[+-−]` would be
    a character RANGE (+ .. U+2212) that matches almost anything (a false-sign-flip bug)."""
    for m in re.finditer(rf"(?<![\d.])([+\-−]?)\s?{re.escape(mag)}(?![\d])", line):
        s = m.group(1)
        # NB: `s in "-−"` is True for the EMPTY string (a bare number) — must compare explicitly.
        yield (-1 if s in ("-", "−") else 1 if s == "+" else 0)


def line_sign_flips(line: str, nums: list[dict] | None = None) -> list[str]:
    """Return sign-flip findings for a single line: a sign-checked canonical whose magnitude appears
    with the OPPOSITE explicit sign. Exposed so the guard's sign-blindness fix is directly testable."""
    nums = nums if nums is not None else numeric_canonicals()
    out = []
    for c in nums:
        if not c["sign"]:
            continue
        for sign in _signed_hits(c["mag"], line):
            if sign and sign != c["sign"]:
                out.append(f"{c['name']}: {'+' if sign > 0 else '-'}{c['mag']} but canonical "
                           f"{c['value']}")
    return out


def _commit_pointers_ok(doc_lines) -> list:
    """Item-10 regression fix: the coverage git-hash strip means an 'as of <commit>' status pointer
    is not magnitude-checked, so a STALE/typo'd hash would pass silently. Verify every such pointer
    resolves to a real commit that is an ANCESTOR of HEAD."""
    import subprocess
    bad = []
    seen = set()
    for rel, lines in doc_lines.items():
        for i, line in enumerate(lines, 1):
            for h in re.findall(r"as of (?:commit )?`?([0-9a-f]{7,40})`?", line):
                if h in seen:
                    continue
                seen.add(h)
                try:
                    r = subprocess.run(["git", "merge-base", "--is-ancestor", h, "HEAD"],
                                       cwd=str(REPO_ROOT), capture_output=True)
                    if r.returncode != 0:
                        bad.append(f"STALE POINTER {rel}:{i} 'as of {h}' is not an ancestor of HEAD")
                except Exception as e:  # noqa: BLE001
                    bad.append(f"POINTER CHECK failed for {h}: {e!r}")
    return bad


def check() -> dict:
    art, base, arch, tmc, de = _load()
    nums, strs = numeric_canonicals(), string_canonicals()
    doc_lines = {rel: (REPO_ROOT / rel).read_text().splitlines() for rel in DOCS
                 if (REPO_ROOT / rel).exists()}
    mismatches, missing = _commit_pointers_ok(doc_lines), []

    # (2) sub-rounding drift: live artifact vs pinned baseline
    for c in nums:
        if c["live"] is not None and abs(c["live"] - c["value"]) > c["tol"]:
            mismatches.append(f"DRIFT {c['name']}: artifact {c['live']} vs baseline {c['value']} "
                              f"(> tol {c['tol']})")

    def _frozen_preg(rel, line, state):
        if rel.endswith("PHASE8_PLAN.md"):
            if line.strip().startswith("## AMENDMENTS"):
                state[0] = False
            return state[0]
        return False

    # (1) numeric presence + SIGN, and (3) superseded denylist
    for rel, lines in doc_lines.items():
        state = [rel.endswith("PHASE8_PLAN.md")]   # frozen pre-registration region flag
        for i, line in enumerate(lines, 1):
            frozen = _frozen_preg(rel, line, state)
            skip = frozen or any(m in line.lower() for m in SKIP_MARKERS)
            if not skip:
                for old in SUPERSEDED:
                    if re.search(rf"(?<![\d.]){re.escape(old)}(?![\d])", line):
                        mismatches.append(f"SUPERSEDED {old} on live line {rel}:{i} | "
                                          f"{line.strip()[:90]}")
                for flip in line_sign_flips(line, nums):
                    mismatches.append(f"SIGN FLIP {flip} | {rel}:{i} {line.strip()[:70]}")
    # presence (across all live lines, any doc)
    for c in nums:
        seen = any(re.search(rf"(?<![\d.]){re.escape(c['mag'])}(?![\d])", ln)
                   for lines in doc_lines.values() for ln in lines)
        if not seen:
            missing.append(f"{c['name']} (mag {c['mag']})")
    for c in strs:
        seen = any(any(alt in ln for alt in c["any"]) for lines in doc_lines.values() for ln in lines)
        if not seen:
            missing.append(f"{c['name']} ({' | '.join(c['any'])})")
    # pre-reg rule boolean must be false in the artifact
    if art["pre_registered"]["rule_met"] is not False:
        mismatches.append("ARTIFACT pre_registered.rule_met is not False (primary college verdict)")

    # tolerance VACUITY: a comparison tol >= 0.1*|value| cannot discriminate the value (and, for a
    # signed sub-|value| tol, a full sign flip fits inside it). Flag any such entry.
    vacuous = [f"{c['name']}: tol {c['tol']:g} > 0.1*|value| ({0.1 * abs(c['value']):g})"
               for c in nums if c["value"] and c["tol"] > 0.1 * abs(c["value"])]

    # (4) coverage over the internal project notes STANDING CONSTRAINTS
    cov = _coverage(nums, strs)
    return {"mismatches": mismatches + vacuous, "missing": missing, "nums": nums, "strs": strs,
            "coverage": cov, "vacuous": vacuous, "n_sign_checked": sum(1 for c in nums if c["sign"])}


def _coverage(nums, strs) -> dict:
    # Coverage is checked over BOTH the STANDING CONSTRAINTS section AND the SESSION HANDOFF section
    # (item 9: the handoff claims meant for pasting into new sessions are brought under the guard).
    blocks = []
    oi = REPO_ROOT / "docs" / "OPEN_ITEMS.md"                            # the single live open-items list
    if oi.exists():
        blocks.append(oi.read_text())
    sc = REPO_ROOT / "docs" / "STANDING_CONSTRAINTS.md"                  # public copy of the standing constraints
    if sc.exists():
        blocks.append(sc.read_text())
    kr = REPO_ROOT / "docs" / "KEY_RESULTS.md"                           # public copy of the handoff claims
    if kr.exists():
        blocks += re.findall(r"## Results.*?(?=\n## |\Z)", kr.read_text(), re.S)
    if not blocks:
        return {"total": 0, "covered": 0, "uncovered": []}
    text = "\n".join(blocks)
    # strip doc-reference numerals that are NOT statistics: ISO dates, PHASE8/§A4/G6.5/Gate 6.5,
    # "5.4B", percentages, file:line, ranges, hashes. [Gg] so lowercase module names (g104_repro) strip.
    for pat in (r"\d{4}-\d{2}-\d{2}", r"PHASE\d+", r"§?A\d+", r"\b[Gg]\d+(?:\.\d+)?",
                r"Gate \d+(?:\.\d+)?", r"\d+(?:\.\d+)?%", r"\d+\.\dB",
                r"NOTE\s+\d+", r"\bB\s*=?\s*\d+",        # review-channel note IDs (may line-wrap); bootstrap replicate counts (B=160)
                r"\.md:\d+", r"\d+\s*[–-]\s*\d+",       # file:line refs; numeric ranges (e.g. 60–270)
                r"\b[0-9a-f]{7,40}\b"):                 # git short/long hashes (e.g. commit 02e7f88)
        text = re.sub(pat, " ", text)
    toks = re.findall(r"\d+(?:\.\d+)?", text)
    string_vals = {a for c in strs for a in c["any"]}
    mags = {c["mag"] for c in nums}                          # match the DISPLAY magnitude directly
    covered, uncovered = [], []
    for tok in toks:
        v = float(tok)
        hit = (tok in NON_STAT or tok in string_vals or tok in mags or
               any(abs(abs(c["value"]) - v) <= c["tol"] for c in nums))
        (covered if hit else uncovered).append(tok)
    return {"total": len(toks), "covered": len(covered), "uncovered": sorted(set(uncovered))}


def run() -> None:
    r = check()
    print(f"doc-consistency registry: {len(r['nums'])} numeric + {len(r['strs'])} string canonicals "
          f"({len(r['nums']) + len(r['strs'])} total); {r['n_sign_checked']} are SIGN-CHECKED "
          f"(signed estimates); the rest are magnitude/string presence only.\n")
    for c in r["nums"]:
        sign = "  [SIGN-CHECKED]" if c["sign"] else ""
        print(f"  {c['name']:42} value={c['value']!s:>11}  display_mag={c['mag']:>9}"
              f"  tol={c['tol']}{sign}")
    for c in r["strs"]:
        print(f"  {c['name']:42} any={c['any']}")
    cov = r["coverage"]
    frac = f"{cov['covered']}/{cov['total']}" if cov["total"] else "n/a"
    print(f"\nSTANDING-CONSTRAINTS coverage: {frac}"
          + (f"  UNCOVERED: {cov['uncovered']}" if cov["uncovered"] else "  (all covered)"))
    n = len(r["mismatches"]) + len(r["missing"]) + len(cov["uncovered"])
    for x in r["missing"]:
        print(f"  MISSING from docs: {x}")
    for x in r["mismatches"]:
        print(f"  MISMATCH: {x}")
    print(f"\nMISMATCHES RIGHT NOW: {n}")
    if n:
        sys.exit(1)
    print("PASS: docs are consistent with the pinned artifacts (signs, precision, coverage).")


if __name__ == "__main__":
    run()
