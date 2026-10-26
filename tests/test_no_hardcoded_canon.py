"""Standing guard against the canon re-pin BLAST RADIUS (PHASE10_PLAN A16/A17; review NOTES 0018/0020).

A trade E[Δ] re-pin briefly ran Gate 8 AND Gate 9 red because FIVE hardcoded copies of the canon value
lived in GENERATOR + CONSUMER + TEST code that the doc-consistency registry does not cover. A canon
value must be READ from its registry entry / producer artifact — never embedded as a literal in the
code that GENERATES or CONSUMES it. This test fails if a current producer-backed canon literal appears
in generator/consumer source, and asserts the read-from-source wiring is present.

SCOPE: generator/consumer CODE only. Docs legitimately DISPLAY canon values (covered by
check_doc_consistency); TEST files legitimately ASSERT them. This guards the surfaces that must read.
Complement: the post-re-pin CHECKLIST (the internal project notes CONVENTIONS) greps the whole tree for the OLD literal
and runs the FULL gate suite — this test cannot know past values, so the checklist covers the old-literal
sweep and this test covers re-embedding the current one.
"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# generator/consumer code that MUST read canon values, never embed them, + the read-pattern each uses.
WIRED = {
    "jobs/build_bundle.py": 'reg["corpus_e_delta"]',
    "jobs/mcp_server.py": '_fact("trade_corpus_e_delta")',
}


def _trade_canon_literals() -> dict:
    tv = json.loads((REPO / "jobs" / "drift_baseline.json").read_text())["trade_verdict"]
    keys = ["corpus_e_delta", "corpus_ci_lo", "corpus_ci_hi",
            "consensus_e_delta", "consensus_ci_lo", "consensus_ci_hi"]
    return {k: repr(tv[k]) for k in keys}


def test_no_hardcoded_trade_canon():
    lits = _trade_canon_literals()
    failures = []
    for rel, read_pattern in WIRED.items():
        src = (REPO / rel).read_text()
        # (a) the full-precision canon literal must NOT be embedded (must be read, not hardcoded)
        for k, lit in lits.items():
            if lit in src:
                failures.append(f"{rel}: hardcoded trade-canon literal {lit} ({k}) — READ it from "
                                f"the registry/artifact, do not embed it")
        # (b) the read-from-source wiring must be PRESENT (positive control: the file reads the canon)
        if read_pattern not in src:
            failures.append(f"{rel}: expected canon read-pattern `{read_pattern}` absent — the "
                            f"registry/artifact wiring was removed?")
    assert not failures, "BLAST-RADIUS GUARD FAILED:\n" + "\n".join(failures)


if __name__ == "__main__":
    test_no_hardcoded_trade_canon()
    print("PASS: no hardcoded trade-canon literal in generator/consumer code; read-wiring present.")
