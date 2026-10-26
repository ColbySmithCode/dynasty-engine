"""Phase 7 item 3 / criterion 4 — REQUIRED fault-injection test for the atomic FULL build.

Kills a FULL build mid-warehouse-write, confirms the LIVE warehouse is byte-identical to its
pre-run state (the build was happening in a temp db), then runs --rollback and confirms it
restores the retained snapshot exactly. Criterion 4 stays pending until this passes.
    uv run python -m tests.test_atomic_fault
"""
from __future__ import annotations

import glob
import hashlib
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CONFIG

LIVE = CONFIG.path("warehouse")
TEMP = LIVE.with_suffix(".build.db")
SNAP_DIR = CONFIG.path("data_raw").parent / "snapshots"


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run() -> None:
    import shutil
    fails = []
    assert LIVE.exists(), "no live warehouse to test against"
    live_before = _sha(LIVE)
    backup = LIVE.with_suffix(".pretest.db")        # non-destructive: restore state at the end
    shutil.copy2(LIVE, backup)

    # 1) launch a FULL db-build and KILL it mid-warehouse-write
    if TEMP.exists():
        TEMP.unlink()
    env = dict(os.environ, PATH=os.path.expanduser("~/.local/bin") + ":" + os.environ.get("PATH", ""))
    proc = subprocess.Popen(
        ["uv", "run", "python", "-m", "jobs.refresh", "--mode", "full", "--only", "warehouse"],
        cwd=str(Path(__file__).resolve().parent.parent), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # wait until the temp build db is being written (mid-build), then kill
    deadline = time.time() + 60
    while time.time() < deadline:
        if TEMP.exists() and TEMP.stat().st_size > 1_000_000:
            break
        if proc.poll() is not None:
            break
        time.sleep(0.2)
    os.kill(proc.pid, signal.SIGKILL)
    proc.wait()
    time.sleep(0.5)

    # 2) LIVE must be byte-identical (build was in temp; live never touched)
    live_after_kill = _sha(LIVE)
    if live_after_kill != live_before:
        fails.append("live warehouse CHANGED after a killed mid-build (atomicity violated)")
    else:
        print("  ok: live warehouse byte-identical after mid-build kill")
    if TEMP.exists():
        print(f"  ok: partial temp build db left behind ({TEMP.stat().st_size/1e6:.1f}MB) — not swapped")

    # 3) --rollback restores the latest snapshot exactly
    snaps = sorted(glob.glob(str(SNAP_DIR / "warehouse_*.db")), key=os.path.getmtime)
    if not snaps:
        fails.append("no snapshot to roll back to (run a successful FAST/FULL first)")
    else:
        snap = Path(snaps[-1]); snap_sha = _sha(snap)
        rc = subprocess.run(["uv", "run", "python", "-m", "jobs.refresh", "--rollback"],
                            cwd=str(Path(__file__).resolve().parent.parent), env=env,
                            capture_output=True, text=True).returncode
        if rc != 0:
            fails.append(f"--rollback exited {rc}")
        elif _sha(LIVE) != snap_sha:
            fails.append("after --rollback, live warehouse != latest snapshot (restore incorrect)")
        else:
            print(f"  ok: --rollback restored {snap.name} byte-for-byte")

    if TEMP.exists():
        TEMP.unlink()
    # restore the pre-test warehouse (the rollback intentionally clobbered it with an older snapshot)
    shutil.copy2(backup, LIVE)
    backup.unlink()
    print("  ok: restored pre-test warehouse (test is non-destructive)")
    if fails:
        print("FAIL:"); [print("  -", f) for f in fails]; sys.exit(1)
    print("PASS: mid-build kill leaves live db untouched; --rollback restores the snapshot exactly.")


if __name__ == "__main__":
    run()
