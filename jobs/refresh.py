"""Phase 7 — weekly refresh orchestrator (see docs/PHASE7_PLAN.md).

Two cadences (FAST / FULL); one entrypoint. Hardened for unattended runs (2nd-review items):
  - ATOMIC DB build (item 7): warehouse+metrics build into a TEMP db, are validated, then
    atomic-renamed into place; the previous db is snapshotted (retain last N) with a rollback
    command. A crash mid-build never leaves a broken live warehouse.
  - STALENESS first-class (item 4): a machine-readable status (data/refresh_status.json +
    fact_refresh_status table) records per-table last_successful_refresh + stale. Fail-soft MARKS
    STALE, it does not just log. Phase 8/9 consumers MUST read fact_refresh_status (contract).
  - 2026 GUARD (item 6): an assertion fails the run if any 2026 row reaches a model artifact /
    derived-metric. 2026 is allowed only in raw + fact_player_week/fact_adp (recorded).
  - MODEL VERSIONING + DRIFT (item 5): FULL hashes artifacts (never overwrite) and runs the drift
    monitor on the three established results.
  - MIXED-VINTAGE recorded (item 6): the manifest logs each source's as-of date (fresh nflverse
    vs corpus frozen 2026-07-27).
The corpus stays FROZEN (never re-pulled). Current season from Sleeper /state/nfl.

CLI:  uv run python -m jobs.refresh --mode {fast|full} [--dry-run] [--only a,b] [--force]
      uv run python -m jobs.refresh --rollback            # restore the latest db snapshot
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
import traceback
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CONFIG
from ingest._common import get_logger, resolve_current_season

log = get_logger("refresh")
SNAP_DIR = CONFIG.path("data_raw").parent / "snapshots"
LOCKFILE = CONFIG.path("data_raw").parent / ".refresh.lock"
KEEP_SNAPSHOTS = 5
EXPECTED_TZ = "America/New_York"


def _assert_timezone() -> None:
    """Item 6a: launchd/cron fire on the machine's LOCAL wall clock, so the ET schedule silently
    breaks if the machine TZ changes (travel). Fail loudly at run start if not America/New_York."""
    zone = None
    lt = Path("/etc/localtime")
    if lt.is_symlink():
        tgt = os.readlink(lt)
        if "zoneinfo/" in tgt:
            zone = tgt.split("zoneinfo/", 1)[1]
    if zone != EXPECTED_TZ:
        raise AssertionError(
            f"TIMEZONE GUARD: machine TZ is {zone!r}, expected {EXPECTED_TZ!r}. launchd fires on "
            f"local wall clock — the ET schedule is wrong until the TZ is restored. Aborting.")
    log.info("timezone ok (%s)", zone)


class _Lock:
    """Item 1: exclusive advisory lock. A second refresh (FAST overrunning into FULL, or vice
    versa) EXITS immediately with a logged skip rather than contending for DuckDB's single writer."""
    def __init__(self):
        self.fh = None

    def __enter__(self):
        import fcntl
        LOCKFILE.parent.mkdir(parents=True, exist_ok=True)
        self.fh = open(LOCKFILE, "w")
        try:
            fcntl.flock(self.fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.fh.close(); self.fh = None
            return False
        self.fh.write(str(os.getpid())); self.fh.flush()
        return True

    def __exit__(self, *a):
        if self.fh:
            import fcntl
            fcntl.flock(self.fh, fcntl.LOCK_UN); self.fh.close()


# ============================================================================
# stage implementations (lazy imports; fail-soft at the orchestrator)
# ============================================================================
def _s_nflverse_current(force):
    from ingest import nflverse
    cur = resolve_current_season(); nflverse.run(seasons=[cur], force=True)
    return f"nflverse season {cur} (forced)"


def _s_nflverse_all(force):
    from ingest import nflverse
    nflverse.run(force=force); return "nflverse all seasons (cached)"


def _s_mfl_adp(force):
    from ingest import mfl_adp
    cur = resolve_current_season(); mfl_adp.run_sweep(seasons=[cur], force=force)
    return f"mfl_adp sweep season {cur}"


def _s_dynastyprocess(force):
    from ingest import dynastyprocess
    dynastyprocess.run(force=force); return "dynastyprocess values snapshot"


def _s_corpus_frozen(force):
    from ingest import sleeper_corpus
    sleeper_corpus.run(); return "sleeper_corpus (frozen no-op)"


def _s_cfb(force):
    from ingest import cfb
    cfb.run(); return "cfb (cached)"


def _s_warehouse(force):
    from transform import warehouse
    warehouse.run(); return "warehouse built (into temp db)"


def _s_metrics(force):
    from transform import metrics
    metrics.run(); return "metrics built (into temp db)"


def _s_models(force):
    from models import aging_curves, survival, survival_cox, adp_calibration, projection, archetypes
    aging_curves.build(); survival.build(); survival_cox.run()
    adp_calibration.build(); projection.run(); archetypes.build()
    return "models refit"


def _s_engine(force):
    from engine import trade_engine
    trade_engine.run(); return "trade_engine regenerated"


def _s_startup_backtester(force):
    from models import startup_backtester
    startup_backtester.run(); return "startup_backtester regenerated"


# name -> (fn, modes, phase, tables_fed)
#   phase: 'ingest' (raw, pre-db) | 'db' (atomic warehouse build) | 'post' (reads live db)
STAGES = {
    # FULL is a strict SUPERSET of FAST (item 1): it also forces the current-season pull, so a
    # Wednesday FULL fully replaces a FAST — hence they never both run on the same morning.
    "nflverse_current":   (_s_nflverse_current, {"fast", "full"},  "ingest", ["fact_player_week"]),
    "nflverse_all":       (_s_nflverse_all,     {"full"},          "ingest", ["fact_player_week"]),
    "mfl_adp":            (_s_mfl_adp,          {"full"},          "ingest", ["fact_adp"]),
    "dynastyprocess":     (_s_dynastyprocess,   {"fast", "full"},  "ingest", ["fact_dynasty_value"]),
    "corpus_frozen":      (_s_corpus_frozen,    {"full"},          "ingest", []),
    "cfb":                (_s_cfb,              {"full"},          "ingest", []),
    "warehouse":          (_s_warehouse,        {"fast", "full"},  "db",     ["fact_player_week", "fact_adp", "fact_player_season"]),
    "metrics":            (_s_metrics,          {"fast", "full"},  "db",     ["fact_player_week_metrics", "fact_player_season_metrics", "fact_replacement"]),
    "models":             (_s_models,           {"full"},          "post",   ["_models"]),
    "engine":             (_s_engine,           {"full"},          "post",   ["_trade_verdict"]),
    # backtester is NOT in the weekly FULL set: its inputs are the FROZEN corpus, so its output
    # cannot change until the corpus grows. FULL runs it ONLY when the corpus signature changed
    # (see _corpus_changed), or on-demand via `--only startup_backtester`.
    "startup_backtester": (_s_startup_backtester, {"ondemand"},    "post",   ["_startup_strategy"]),
}
ORDER = ["nflverse_current", "nflverse_all", "mfl_adp", "dynastyprocess", "corpus_frozen", "cfb",
         "warehouse", "metrics", "models", "engine", "startup_backtester"]


def plan(mode, only):
    if only:                                        # --only selects ANY stage, mode-independent
        return [n for n in ORDER if n in set(only)]
    return [n for n in ORDER if mode in STAGES[n][1]]


# ============================================================================
# guards + validation (item 6) + staleness (item 4)
# ============================================================================
MODEL_INPUT_TABLES = ["fact_player_week", "fact_player_season", "fact_player_season_metrics",
                      "fact_adp"]


def hash_model_inputs(db_path: Path, seasons=(2013, 2025)) -> dict:
    """Item 2: per-table, per-season (row_count, order-independent content hash) of the tables the
    model fits read. Lets a silent nflverse revision to 2013–2025 be distinguished from model
    drift (hashing artifacts alone cannot). sum(hash(row)) is commutative -> order-independent."""
    import duckdb
    con = duckdb.connect(str(db_path), read_only=True)
    out = {}
    for t in MODEL_INPUT_TABLES:
        try:
            rows = con.execute(
                f"SELECT season, count(*) n, CAST(sum(hash({t}::VARCHAR)) AS HUGEINT) h "
                f"FROM {t} WHERE season BETWEEN {seasons[0]} AND {seasons[1]} GROUP BY season "
                f"ORDER BY season").fetchall()
            out[t] = {int(s): [int(n), str(h)] for s, n, h in rows}
        except Exception as e:  # noqa: BLE001
            out[t] = {"_error": repr(e)}
    con.close()
    return out


def _artifact_hashes() -> dict:
    from jobs.drift_monitor import _hash
    md = CONFIG.path("models")
    return {p.name: _hash(p) for p in sorted(list(md.glob("*.parquet")) + list(md.glob("*.csv")))}


def _free_disk_ok(target: Path) -> tuple:
    """Item 3: fail early if free disk can't hold a temp build + the retained snapshots."""
    live = CONFIG.path("warehouse")
    need = (live.stat().st_size if live.exists() else 500 * 1024**2) * 2  # temp + one snapshot
    free = shutil.disk_usage(target.parent).free
    return (free >= need, free, need)


def _corpus_changed() -> tuple:
    """Gate the backtester on ANY change to its inputs. It reads BOTH (a) the corpus draft picks
    AND (b) realized production (fact_player_week 2011–2025) for scoring — so an nflverse revision
    to historical outcome data would change backtester results WITHOUT changing the corpus. The
    signature therefore keys on both (fixes the 'transaction-corpus-only gate' gap)."""
    import duckdb
    sig_file = CONFIG.path("models") / "_versions" / "corpus_sig.json"
    con = duckdb.connect(str(CONFIG.path("warehouse")), read_only=True)
    try:
        n, h = con.execute("SELECT count(*), CAST(sum(hash(player_uid||pick_no)) AS HUGEINT) "
                           "FROM fact_league_draft_pick WHERE source='corpus'").fetchone()
        pw = con.execute("SELECT count(*), CAST(sum(hash(player_uid||season||week||fp_ppr)) AS HUGEINT) "
                         "FROM fact_player_week WHERE season BETWEEN 2011 AND 2025").fetchone()
    finally:
        con.close()
    sig = f"{n}:{h}|pw:{pw[0]}:{pw[1]}"
    prev = json.loads(sig_file.read_text()).get("sig") if sig_file.exists() else None
    changed = sig != prev
    if changed:
        sig_file.parent.mkdir(parents=True, exist_ok=True)
        sig_file.write_text(json.dumps({"sig": sig, "ts": int(time.time())}))
    return changed, sig


def _validate_db(db_path: Path) -> None:
    """Integrity assertions on the freshly-built (temp) db, before it is swapped in."""
    import duckdb
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        for t in ("fact_player_week", "fact_player_season", "dim_player"):
            n = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
            if n == 0:
                raise AssertionError(f"validation: {t} is empty in temp db")
    finally:
        con.close()


def assert_no_2026_in_models() -> str:
    """Item 6: FAIL if any 2026 row reached a model artifact / derived metric. 2026 is allowed
    ONLY in raw + fact_player_week/fact_adp (offseason ADP); model fits exclude it."""
    import polars as pl
    offenders = []
    for pq in CONFIG.path("models").glob("*.parquet"):
        try:
            df = pl.read_parquet(pq)
        except Exception:
            continue
        for col in ("season", "year", "s0"):
            if col in df.columns and df.filter(pl.col(col) == 2026).height > 0:
                offenders.append(f"{pq.name}:{col}")
    if offenders:
        raise AssertionError(f"2026 GUARD TRIPPED — 2026 rows in model artifacts: {offenders}")
    return "2026 guard ok (no 2026 in model artifacts)"


def _write_status(mode: str, stage_recs: list, sources: dict, completeness: dict | None = None) -> None:
    """Item 4: machine-readable freshness. Writes data/refresh_status.json + fact_refresh_status.
    A table is marked stale=True if a FAILED stage fed it OR (item 5) its completeness check did
    not pass — freshness is verify-then-mark, not schedule-trust."""
    now = int(time.time())
    # item 5: map the source-data tables to their completeness verdict
    incomplete = set()
    comp = completeness or {}
    if isinstance(comp.get("pbp"), dict):
        if not comp["pbp"].get("complete", True):
            incomplete.add("fact_player_week")
    failed_tables = set(incomplete)
    ok_tables = {}
    for rec in stage_recs:
        tables = STAGES.get(rec["stage"], (None, None, None, []))[3]   # guard/drift/validate not in STAGES
        for t in tables:
            if rec["status"] == "ok" and t not in incomplete:
                ok_tables[t] = now
            else:
                failed_tables.add(t)
    status = {}
    for t, ts in ok_tables.items():
        status[t] = {"last_successful_refresh": ts, "stale": t in failed_tables}
    for t in failed_tables:
        status.setdefault(t, {"last_successful_refresh": None, "stale": True})
    payload = {"mode": mode, "updated": now, "sources_as_of": sources, "tables": status}
    (CONFIG.path("data_raw").parent / "refresh_status.json").write_text(json.dumps(payload, indent=2))
    # also into the warehouse for Phase 8/9 consumers (contract: they MUST read this)
    try:
        import duckdb
        con = duckdb.connect(str(CONFIG.path("warehouse")))
        con.execute("CREATE TABLE IF NOT EXISTS fact_refresh_status "
                    "(table_name TEXT, last_successful_refresh BIGINT, stale BOOLEAN, updated BIGINT)")
        con.execute("DELETE FROM fact_refresh_status")
        con.executemany("INSERT INTO fact_refresh_status VALUES (?,?,?,?)",
                         [(t, v["last_successful_refresh"], v["stale"], now) for t, v in status.items()])
        con.close()
    except Exception as e:  # noqa: BLE001
        log.warning("could not write fact_refresh_status: %r", e)


def completeness_check() -> dict:
    """Item 5: verify the CURRENT week's completed games are present in pbp / snap_counts /
    depth_charts BEFORE those tables are marked fresh — robust to publish-time drift in a way no
    fixed schedule is. Returns {table: {expected, observed, complete}} + observed publish lag.
    Offseason / no completed games this week -> trivially complete (expected 0)."""
    import duckdb
    from datetime import datetime, timezone
    try:
        cur = resolve_current_season()
        st = _sleeper_state()
        week = int(st.get("week") or 0); stype = st.get("season_type", "")
    except Exception as e:  # noqa: BLE001
        return {"_note": f"could not resolve state ({e!r}); completeness skipped"}
    raw = CONFIG.path("data_raw") / "nflverse"
    sched_p = raw / "schedules" / "all.parquet"
    if week == 0 or stype not in ("regular", "post") or not sched_p.exists():
        return {"_note": f"offseason/no-games (season={cur} week={week} type={stype}) — nothing due"}
    con = duckdb.connect(":memory:")
    # expected: games for (season, week) whose kickoff is already in the past
    try:
        exp = con.execute(f"""SELECT count(*) FROM read_parquet('{sched_p}')
            WHERE season={cur} AND week={week} AND CAST(gameday AS DATE) < current_date""").fetchone()[0]
    except Exception:
        exp = con.execute(f"""SELECT count(*) FROM read_parquet('{sched_p}')
            WHERE season={cur} AND week={week}""").fetchone()[0]
    out = {}
    now = datetime.now(timezone.utc)
    for tbl, sub, gid in (("pbp", "pbp", "game_id"), ("snap_counts", "snap_counts", "game_id"),
                          ("depth_charts", "depth_charts", None)):
        p = raw / sub / f"{cur}.parquet"
        obs = 0
        if p.exists():
            try:
                q = (f"SELECT count(DISTINCT {gid}) FROM read_parquet('{p}') WHERE week={week}"
                     if gid else f"SELECT count(*) FROM read_parquet('{p}') WHERE week={week}")
                obs = con.execute(q).fetchone()[0]
                lag_h = round((now.timestamp() - p.stat().st_mtime) / 3600, 1)
            except Exception:
                lag_h = None
        else:
            lag_h = None
        out[tbl] = {"expected": int(exp), "observed": int(obs),
                    "complete": obs >= exp and exp > 0 or exp == 0, "file_age_hours": lag_h}
    con.close()
    return out


def _sleeper_state() -> dict:
    import httpx
    r = httpx.get(f"{CONFIG['sleeper']['base_url']}/state/nfl",
                  headers={"User-Agent": CONFIG["sleeper"]["user_agent"]}, timeout=30)
    return r.json()


def upstream_probe() -> dict:
    """Item 6 (Phase-7 2nd review): DETECT upstream nflverse revisions as a JOB STEP, not a
    calendar note. Fetches current nflverse-data release asset timestamps for the model-input
    datasets and diffs against the stored probe; reports which changed since the freeze. NEVER
    changes the frozen inputs or auto-bumps — a change is REPORTED (manifest + status) for a
    deliberate, reviewed re-baseline."""
    import urllib.request
    store = CONFIG.path("models") / "_versions" / "upstream_probe.json"
    prev = json.loads(store.read_text()) if store.exists() else {}
    cur = {}
    for rel in ("weekly_rosters", "snap_counts", "player_stats", "pbp"):
        try:
            with urllib.request.urlopen(
                    f"https://api.github.com/repos/nflverse/nflverse-data/releases/tags/{rel}", timeout=20) as r:
                d = json.loads(r.read())
            a2025 = [a for a in d.get("assets", []) if "2025" in a["name"] and a["name"].endswith(".parquet")]
            cur[rel] = a2025[0]["updated_at"] if a2025 else d.get("published_at")
        except Exception as e:  # noqa: BLE001
            cur[rel] = f"probe_error:{e!r}"
    changed = {k: (prev.get(k), cur[k]) for k in cur if prev and prev.get(k) != cur[k]
               and not str(cur[k]).startswith("probe_error")}
    store.parent.mkdir(parents=True, exist_ok=True)
    store.write_text(json.dumps({"probed": int(time.time()), "assets": cur}, indent=2))
    return {"asset_updated_at": cur, "changed_since_last_probe": changed,
            "note": "REPORT-ONLY; frozen inputs untouched — re-baseline is a deliberate review step"}


def _source_as_of() -> dict:
    """Item 6: record each source's vintage (mixed-vintage state)."""
    frozen = "unknown"
    fp = CONFIG.path("data_raw") / "sleeper_corpus" / "FROZEN.json"
    if fp.exists():
        try:
            frozen = json.loads(fp.read_text()).get("frozen_at", "2026-07-27")
        except Exception:
            frozen = "2026-07-27"
    return {"nflverse_pulled": str(date.today()), "mfl_adp_pulled": str(date.today()),
            "dynastyprocess_snapshot": str(date.today()), "corpus_frozen": frozen}


# ============================================================================
# atomic db swap (item 7)
# ============================================================================
def _snapshot_and_swap(temp_db: Path) -> None:
    live = CONFIG.path("warehouse")
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    if live.exists():
        snap = SNAP_DIR / f"warehouse_{int(time.time())}.db"
        shutil.copy2(live, snap)
        snaps = sorted(SNAP_DIR.glob("warehouse_*.db"))
        for old in snaps[:-KEEP_SNAPSHOTS]:
            old.unlink()
        log.info("snapshotted live db -> %s (retain last %d)", snap.name, KEEP_SNAPSHOTS)
    os.replace(temp_db, live)                       # atomic on same filesystem
    log.info("atomic swap: temp db -> %s", live)


def rollback() -> int:
    snaps = sorted(SNAP_DIR.glob("warehouse_*.db"))
    if not snaps:
        log.error("no snapshots to roll back to"); return 1
    latest = snaps[-1]
    shutil.copy2(latest, CONFIG.path("warehouse"))
    log.info("rolled back warehouse from %s", latest.name)
    return 0


# ============================================================================
# run
# ============================================================================
def _run_stage(name, force):
    fn = STAGES[name][0]; t0 = time.time(); rec = {"stage": name}
    try:
        rec.update(status="ok", detail=fn(force))
        log.info("[ok] %-20s %.1fs — %s", name, time.time() - t0, rec["detail"])
    except Exception as e:  # noqa: BLE001
        rec.update(status="FAILED", error=repr(e))
        log.error("[FAILED] %-20s %.1fs — %r", name, time.time() - t0, e)
        log.debug("%s", traceback.format_exc())
    rec["seconds"] = round(time.time() - t0, 1)
    return rec


def run(mode, dry_run=False, only=None, force=False) -> int:
    stages = plan(mode, only)
    log.info("refresh mode=%s stages=%s%s", mode, stages, " [DRY-RUN]" if dry_run else "")
    if dry_run:
        for n in stages:
            print(f"  would run: {n} [{STAGES[n][2]}]")
        return 0

    _assert_timezone()                              # item 6a — fail loudly on TZ drift
    lock = _Lock()
    if lock.__enter__() is False:                   # item 1 — another refresh holds the lock
        log.warning("another refresh is running (lock held) — SKIPPING this %s run.", mode)
        return 0
    try:
        return _run_locked(mode, stages, force)
    finally:
        lock.__exit__()


def _run_locked(mode, stages, force) -> int:
    import time as _t
    t_start = _t.time()
    recs = []
    ingest = [s for s in stages if STAGES[s][2] == "ingest"]
    db = [s for s in stages if STAGES[s][2] == "db"]
    post = [s for s in stages if STAGES[s][2] == "post"]
    repro = {}   # item 1/2: pre/post reproducibility evidence for FULL

    # item 1/2: capture PRE-FULL model-input hashes (2013–2025) + artifact hashes for the
    # reproducibility criterion (frozen corpus + 2026-blocked -> a clean FULL must reproduce exactly)
    if mode == "full":
        try:
            repro["input_pre"] = hash_model_inputs(CONFIG.path("warehouse"))
            repro["artifacts_pre"] = _artifact_hashes()
        except Exception as e:  # noqa: BLE001
            repro["_capture_error"] = repr(e)

    # 1) ingest (raw, safe)
    for s in ingest:
        recs.append(_run_stage(s, force))

    # 2) atomic db build (item 7): build warehouse+metrics into a temp db, validate, swap
    db_ok = True                                   # if a db build is present, post stages depend on it
    if db:
        live = CONFIG.path("warehouse")
        temp_db = live.with_suffix(".build.db")
        ok_disk, free, need = _free_disk_ok(temp_db)   # item 3: fail early on low disk
        if not ok_disk:
            db_ok = False
            msg = f"insufficient disk: free {free/1e9:.1f}GB < need {need/1e9:.1f}GB"
            recs.append({"stage": "disk_check", "status": "FAILED", "error": msg, "seconds": 0})
            log.error("[FAILED] disk_check — %s (aborting build; live db UNCHANGED)", msg)
        else:
            if temp_db.exists():
                temp_db.unlink()                    # FRESH temp (warehouse INSERTs -> no seed)
            saved = CONFIG._raw["paths"]["warehouse"]
            CONFIG._raw["paths"]["warehouse"] = str(temp_db)
            for s in db:
                r = _run_stage(s, force); recs.append(r); db_ok = db_ok and r["status"] == "ok"
            try:
                if db_ok:
                    _validate_db(temp_db)
            except Exception as e:  # noqa: BLE001
                db_ok = False
                recs.append({"stage": "validate_db", "status": "FAILED", "error": repr(e), "seconds": 0})
                log.error("[FAILED] validate_db — %r (keeping existing live db)", e)
            CONFIG._raw["paths"]["warehouse"] = saved
            if db_ok:
                _snapshot_and_swap(temp_db)
            else:
                if temp_db.exists():
                    temp_db.unlink()
                log.error("db build failed validation — live warehouse UNCHANGED (rollback-safe)")

    # item 2: POST-build input hashes -> did 2013–2025 change (upstream revision) vs pre?
    if mode == "full" and "input_pre" in repro:
        try:
            repro["input_post"] = hash_model_inputs(CONFIG.path("warehouse"))
            repro["inputs_2013_2025_identical"] = (repro["input_post"] == repro["input_pre"])
        except Exception as e:  # noqa: BLE001
            repro["_input_post_error"] = repr(e)

    # 3) post (against live db) — SKIP if the db build failed (don't refit models on a stale db)
    if post and not db_ok:
        for s in post:
            recs.append({"stage": s, "status": "skipped",
                         "detail": "db build failed — not refitting on the unchanged/old warehouse",
                         "seconds": 0})
        log.error("post stages (%s) SKIPPED — db build failed; live db is stale for a refit.", post)
    else:
        for s in post:
            recs.append(_run_stage(s, force))

    # item 1: POST-refit artifact hashes -> reproduced exactly? (defect if not, NOT drift)
    if mode == "full" and db_ok and "artifacts_pre" in repro:
        post_h = _artifact_hashes()
        repro["artifacts_post"] = post_h
        repro["artifact_match"] = {k: (post_h.get(k) == v) for k, v in repro["artifacts_pre"].items()}
        repro["all_artifacts_reproduced"] = all(repro["artifact_match"].values())

    # corpus-gated backtester: only rerun when the frozen corpus actually changed (else identical)
    if mode == "full" and db_ok:
        changed, sig = _corpus_changed()
        if changed or "startup_backtester" in stages:
            recs.append(_run_stage("startup_backtester", force))
        else:
            recs.append({"stage": "startup_backtester", "status": "skipped",
                         "detail": f"corpus unchanged ({sig[:24]}…) — output cannot change; gated",
                         "seconds": 0})
            log.info("startup_backtester SKIPPED — corpus unchanged (output cannot change)")

    # 4) guards + versioning/drift (item 5/6)
    if mode == "full" and any(r["stage"] == "models" and r["status"] == "ok" for r in recs):
        recs.append(_run_stage_guard("guard_2026", assert_no_2026_in_models))
        try:
            from jobs import drift_monitor
            d = drift_monitor.run(run_id=f"full_{int(time.time())}")
            recs.append({"stage": "drift_monitor", "status": "ok",
                         "detail": f"{d['n_artifacts']} artifacts, drift_flagged={d['drift_flagged']}",
                         "alerts": d["alerts"], "seconds": 0})
        except Exception as e:  # noqa: BLE001
            recs.append({"stage": "drift_monitor", "status": "FAILED", "error": repr(e), "seconds": 0})

    # upstream-revision probe (FULL only; report-only, never bumps the freeze)
    upstream = {}
    if mode == "full":
        try:
            upstream = upstream_probe()
            if upstream.get("changed_since_last_probe"):
                log.warning("UPSTREAM nflverse revision detected (report-only): %s",
                            list(upstream["changed_since_last_probe"]))
        except Exception as e:  # noqa: BLE001
            upstream = {"_error": repr(e)}

    # 5) completeness gate (item 5) + staleness + manifest
    completeness = {}
    try:
        completeness = completeness_check()
    except Exception as e:  # noqa: BLE001
        completeness = {"_note": f"completeness check errored: {e!r}"}
    sources = _source_as_of()
    _write_status(mode, recs, sources, completeness)
    failed = sum(1 for r in recs if r["status"] == "FAILED")
    wall = round(time.time() - t_start, 1)
    manifest = {"mode": mode, "wall_seconds": wall, "sources_as_of": sources,
                "completeness": completeness, "upstream_probe": upstream, "failed": failed, "stages": recs,
                "reproducibility": {k: repro[k] for k in
                                    ("inputs_2013_2025_identical", "artifact_match",
                                     "all_artifacts_reproduced", "_capture_error",
                                     "_input_post_error") if k in repro},
                "ts": int(time.time())}
    out = CONFIG.path("logs") / f"refresh_{mode}_{manifest['ts']}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2))
    log.info("refresh %s complete in %.0fs: %d failed -> %s", mode, wall, failed, out)
    return 1 if failed else 0


def _run_stage_guard(name, fn):
    t0 = time.time(); rec = {"stage": name}
    try:
        rec.update(status="ok", detail=fn())
        log.info("[ok] %-20s — %s", name, rec["detail"])
    except Exception as e:  # noqa: BLE001
        rec.update(status="FAILED", error=repr(e))
        log.error("[FAILED] %-20s — %r", name, e)
    rec["seconds"] = round(time.time() - t0, 1)
    return rec


def main():
    ap = argparse.ArgumentParser(description="dynasty-engine weekly refresh (Phase 7)")
    ap.add_argument("--mode", choices=["fast", "full"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", type=str, default=None)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--rollback", action="store_true", help="restore the latest db snapshot")
    a = ap.parse_args()
    if a.rollback:
        sys.exit(rollback())
    if not a.mode:
        ap.error("--mode required (unless --rollback)")
    only = [s.strip() for s in a.only.split(",")] if a.only else None
    sys.exit(run(a.mode, dry_run=a.dry_run, only=only, force=a.force))


if __name__ == "__main__":
    main()
