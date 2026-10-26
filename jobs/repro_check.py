"""Phase 7 — reproducibility adjudication for a FULL refit (2nd-review, expanded).

Compares each refit artifact to its ORIGINAL Phase-5 fit (git HEAD) and names the decision-tree
branch — never a bare pass/fail. Causes are disambiguated on FOUR axes:

  byte-match ................................... PASS
  byte-mismatch + params EXACTLY equal ......... serialization noise (benign, documented)
  params differ + input-hash mismatch .......... upstream 2013–2025 revision — SEPARATE finding, escalate
  params differ + LIBRARY versions changed ..... numpy/scipy/lifelines drift (identical code+data+seed)
  params differ + fit-MODULE commits since fit . code drift
  params differ + none of the above ............ RNG nondeterminism

Per artifact we print the MAX ABSOLUTE and MAX RELATIVE parameter delta as numbers (so 0.0-exact
is distinguished from merely-small, and scale differences across parameters are visible).
Usage: uv run python -m jobs.repro_check
"""
from __future__ import annotations

import glob
import hashlib
import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CONFIG

ROOT = CONFIG.path("models").parent
MODELS = CONFIG.path("models")
ARTIFACTS = {
    "aging_curves.parquet": "models/aging_curves.py",
    "aging_deltas.parquet": "models/aging_curves.py",
    "survival_clockA.parquet": "models/survival.py",
    "survival_clockB.parquet": "models/survival.py",
    "survival_curves.parquet": "models/survival.py",
    "cox_age_only.csv": "models/survival_cox.py",
    "cox_age_capital.csv": "models/survival_cox.py",
}
LIBS = ["numpy", "scipy", "lifelines", "scikit-learn", "statsmodels", "polars", "pandas"]


def _git(args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=False)


def _git_show(path: str) -> bytes | None:
    r = _git(["show", f"HEAD:{path}"])
    return r.stdout if r.returncode == 0 else None


def _artifact_commit(path: str) -> str | None:
    """The commit that last modified this artifact (its 'producing' commit)."""
    r = _git(["log", "-1", "--format=%h", "--", path])
    out = r.stdout.decode().strip()
    return out or None


def _module_commits_since_artifact(module: str, artifact: str) -> int:
    """git-log the MODULE from the artifact-producing commit THROUGH HEAD (the correct check;
    working-tree status alone would miss a module edit committed after the fit)."""
    ac = _artifact_commit(artifact)
    if not ac:
        return -1
    r = _git(["rev-list", "--count", f"{ac}..HEAD", "--", module])
    try:
        return int(r.stdout.decode().strip() or "0")
    except ValueError:
        return -1


def _lib_versions(lock_bytes: bytes) -> dict:
    txt = lock_bytes.decode(errors="ignore")
    out = {}
    for lib in LIBS:
        # uv.lock: [[package]] name = "x" \n version = "y"
        m = re.search(rf'name\s*=\s*"{re.escape(lib)}"\s*\n\s*version\s*=\s*"([^"]+)"', txt)
        if m:
            out[lib] = m.group(1)
    return out


def _param_delta(name: str, head_bytes: bytes, cur_path: Path):
    """Return (max_abs, max_rel, exact, detail) comparing fitted parameters."""
    import numpy as np
    import polars as pl
    try:
        rd = (pl.read_parquet if name.endswith(".parquet") else pl.read_csv)
        a = rd(io.BytesIO(head_bytes)); b = rd(cur_path)
    except Exception as e:  # noqa: BLE001
        return None, None, False, f"load error: {e!r}"
    if a.shape != b.shape or a.columns != b.columns:
        return None, None, False, f"shape/cols differ {a.shape}{a.columns} vs {b.shape}{b.columns}"
    numcols = [c for c in a.columns if a[c].dtype.is_numeric()]
    strcols = [c for c in a.columns if c not in numcols]
    str_match = all(a[c].to_list() == b[c].to_list() for c in strcols)
    max_abs = 0.0; max_rel = 0.0
    for c in numcols:
        x = a[c].to_numpy().astype("float64"); y = b[c].to_numpy().astype("float64")
        d = np.abs(x - y)
        m = np.isfinite(d)
        if m.any():
            max_abs = max(max_abs, float(np.nanmax(d[m])))
            rel = d[m] / (np.abs(x[m]) + 1e-30)
            max_rel = max(max_rel, float(np.nanmax(rel))) if rel.size else max_rel
    exact = (max_abs == 0.0) and str_match
    return max_abs, max_rel, exact, ("str cols differ" if not str_match else "ok")


def run() -> None:
    fulls = sorted(glob.glob(str(CONFIG.path("logs") / "refresh_full_*.json")), key=os.path.getmtime)
    inputs_identical = None
    if fulls:
        m = json.loads(Path(fulls[-1]).read_text())
        inputs_identical = m.get("reproducibility", {}).get("inputs_2013_2025_identical")

    # library-version comparison (uv.lock at artifact commit vs now)
    head_lock = _git_show("uv.lock"); cur_lock = (ROOT / "uv.lock").read_bytes()
    lock_changed = (head_lock is not None) and (_sha(head_lock) != _sha(cur_lock))
    hv = _lib_versions(head_lock) if head_lock else {}
    cv = _lib_versions(cur_lock)
    lib_diffs = {k: (hv.get(k), cv.get(k)) for k in LIBS if hv.get(k) != cv.get(k)}

    print("# Reproducibility adjudication (git HEAD Phase-5 fit vs post-FULL refit)")
    print(f"input hashes 2013–2025 identical (pre vs post FULL): {inputs_identical}")
    print(f"uv.lock changed since artifact commit: {lock_changed}; key-lib diffs: {lib_diffs or 'none'}")
    if inputs_identical is False:
        print("  >>> INPUT-HASH MISMATCH: upstream historical revision — SEPARATE FINDING, escalate.\n")

    print(f"\n{'artifact':26} {'byte':4} {'maxΔabs':>12} {'maxΔrel':>12} branch")
    print("-" * 96)
    overall = "PASS"
    for name, module in ARTIFACTS.items():
        cur = MODELS / name
        head = _git_show(f"models/{name}")
        if head is None or not cur.exists():
            print(f"{name:26} {'?':4} {'—':>12} {'—':>12} MISSING"); overall = "INCOMPLETE"; continue
        byte_match = _sha(head) == _sha(cur.read_bytes())
        max_abs, max_rel, exact, detail = _param_delta(name, head, cur)
        commits = _module_commits_since_artifact(module, f"models/{name}")
        if byte_match:
            branch = "PASS (byte-match)"
        elif exact:
            branch = "byte-mismatch + params EXACT(0.0) → serialization noise (benign)"
        elif max_abs is None:
            branch = f"UNCOMPARABLE ({detail})"; overall = "INVESTIGATE"
        elif inputs_identical is False:
            branch = "params differ + input-hash mismatch → upstream revision (escalate)"; overall = "ESCALATE"
        elif lock_changed and lib_diffs:
            branch = f"params differ → LIBRARY drift {lib_diffs}"; overall = "INVESTIGATE"
        elif commits and commits > 0:
            branch = f"params differ + {commits} fit-module commit(s) since fit → CODE DRIFT"; overall = "INVESTIGATE"
        else:
            branch = "params differ + inputs/libs/code unchanged → RNG nondeterminism"; overall = "INVESTIGATE"
        aa = f"{max_abs:.3e}" if isinstance(max_abs, float) else "—"
        rr = f"{max_rel:.3e}" if isinstance(max_rel, float) else "—"
        print(f"{name:26} {'Y' if byte_match else 'N':4} {aa:>12} {rr:>12} {branch}")

    print("-" * 96)
    print(f"OVERALL: {overall}")
    print("(a) fit-module commits since each artifact's producing commit:",
          {os.path.basename(mod): _module_commits_since_artifact(mod, f"models/{art}")
           for art, mod in ARTIFACTS.items()})


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()[:16]


if __name__ == "__main__":
    run()
