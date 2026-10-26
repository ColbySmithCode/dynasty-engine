"""Freeze the live snowball corpus as an immutable dated artifact.

The Sleeper leagues are live and accruing (transactions came in 70,167 vs the
70,159 counted at snowball time). Re-pulling will never reproduce, which would
break Phase 10's "identical rebuild from raw". This writes a dated manifest with
per-file SHA-256 + aggregate counts, and installs a FROZEN marker that the corpus
ingest/backfill refuse to overwrite (unless VIGIL_UNFREEZE=1).
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CONFIG
from ingest._common import get_logger

log = get_logger("freeze_corpus")
CORPUS = CONFIG.path("data_raw") / "sleeper_corpus"
MARKER = CORPUS / "FROZEN.json"


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def is_frozen() -> bool:
    return MARKER.exists()


def freeze(freeze_date: str) -> None:
    files = sorted(p for p in CORPUS.rglob("*.json") if p.name != "FROZEN.json")
    manifest = {}
    n_leagues = n_picks = n_tx = n_rosters = 0
    for p in files:
        rel = str(p.relative_to(CORPUS))
        manifest[rel] = {"sha256": _sha(p), "bytes": p.stat().st_size}
        name = p.name
        if name == "league.json":
            n_leagues += 1
        elif name == "draft_picks.json":
            n_picks += len(json.loads(p.read_text()))
        elif name == "transactions.json":
            n_tx += len(json.loads(p.read_text()))
        elif name == "rosters.json":
            n_rosters += sum(len(t.get("players") or []) for t in json.loads(p.read_text()))
    # aggregate hash = hash of the sorted per-file hashes (order-independent identity)
    agg = hashlib.sha256(
        "".join(f"{k}:{v['sha256']}" for k, v in sorted(manifest.items())).encode()).hexdigest()
    marker = {
        "frozen": True, "freeze_date": freeze_date, "n_files": len(files),
        "n_leagues": n_leagues, "n_draft_picks": n_picks, "n_transactions": n_tx,
        "n_rostered_players": n_rosters, "aggregate_sha256": agg,
    }
    (CORPUS / "MANIFEST.json").write_text(json.dumps(manifest, indent=0))
    MARKER.write_text(json.dumps(marker, indent=2))
    log.info("froze corpus @ %s: %d files, %d leagues, %d picks, %d tx | agg=%s",
             freeze_date, len(files), n_leagues, n_picks, n_tx, agg[:16])
    print(json.dumps(marker, indent=2))


def verify() -> bool:
    """Re-hash current files and compare to the frozen manifest (Phase 10 check)."""
    if not MARKER.exists():
        log.warning("no FROZEN marker"); return False
    manifest = json.loads((CORPUS / "MANIFEST.json").read_text())
    ok = True
    for rel, meta in manifest.items():
        p = CORPUS / rel
        if not p.exists() or _sha(p) != meta["sha256"]:
            log.error("MISMATCH: %s", rel); ok = False
    log.info("corpus freeze verify: %s (%d files)", "OK" if ok else "FAILED", len(manifest))
    return ok


if __name__ == "__main__":
    import os
    if len(sys.argv) > 1 and sys.argv[1] == "verify":
        sys.exit(0 if verify() else 1)
    # freeze date must be passed (no Date.now determinism); use today's session date
    date = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("FREEZE_DATE", "2026-07-27")
    freeze(date)
