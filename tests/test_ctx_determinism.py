"""G10.5 strengthening — cross-process byte-determinism of the startup-backtester ctx.

WHY THIS EXISTS (Colby NOTE 0042 req 1): the G10.4 determinism sweep + tests/test_reproducibility.py
byte-checked the WAREHOUSE BUILD path and a FIXED list of persisted MODEL artifacts (aging/survival/
cox/cfb/archetype/calibration). Neither touched `startup_backtester._build_ctx` — a models/-layer
RUNTIME in-memory object, never persisted, so a table-diff sweep is structurally blind to it and the
byte-check artifact set never exercised it. The non-hermetic ctx (`corpus_pools`/`market_board`/`uids`
unordered) was therefore the 4th instance of the SAME unordered-group_by/dict-iteration class to ship
past a green determinism check. This guard closes that gap for the ctx path directly.

Fast (no bootstrap): builds ctx in N fresh processes and compares a hash over uids + every
position-indexed / draw-relevant array. Fails if any process disagrees.
"""
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
N = 3


def _worker() -> None:
    import contextlib, io
    with contextlib.redirect_stdout(io.StringIO()):
        from models.startup_backtester import _build_ctx
        h = hashlib.sha256()
        for year in (2020, 2021):
            c = _build_ctx(year, 1, 5, None)
            h.update(("|".join(map(str, c.uids))).encode())
            h.update(c.board_order.tobytes()); h.update(c.board_rank.tobytes()); h.update(c.pos.tobytes())
            for k in sorted(c.pool_pr):
                h.update(str(k).encode()); h.update(c.pool_pr[k].tobytes())
            for k in sorted(c.pool_pe):
                h.update(str(k).encode()); h.update(c.pool_pe[k].tobytes())
            for k in sorted(c.pool_so):
                h.update(str(k).encode()); h.update(c.pool_so[k].tobytes())
    print(h.hexdigest()[:16])


def run() -> None:
    hashes = []
    for i in range(N):
        r = subprocess.run([sys.executable, "-m", "tests.test_ctx_determinism", "--worker"],
                           cwd=str(ROOT), capture_output=True, text=True)
        line = [l for l in r.stdout.strip().splitlines() if l.strip()]
        if not line:
            print(f"run {i} FAILED: {r.stderr[-300:]}"); sys.exit(1)
        hashes.append(line[-1])
    ok = len(set(hashes)) == 1
    print(f"_build_ctx byte-hash across {N} fresh processes: {hashes} -> {'IDENTICAL' if ok else 'DIFFER'}")
    if not ok:
        print("FAIL: startup_backtester._build_ctx is NON-HERMETIC (unordered group_by/dict iteration).")
        sys.exit(1)
    print("PASS: _build_ctx is byte-deterministic across processes.")


if __name__ == "__main__":
    if "--worker" in sys.argv:
        _worker()
    else:
        run()
