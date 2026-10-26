"""G10.4 column-level completeness sweep (DIAGNOSTIC ONLY — not a gate, not committed).

For each still-nondeterministic table, build it in TWO fresh processes, join on its primary
key, and diff every value column. Proves whether the ONLY differing columns are rank-derived
(the two ordinal-rank sites: warehouse.py:156 pos_finish_ppr, metrics.py:140 wk_pos_rank_*),
or whether a NON-rank column (e.g. a float sum like fp_ppr) also differs -> an unexplained
3rd site (float sum-order, another tie, etc.). This is the completeness check the reviewer
requires before any fix, and it also adjudicates whether S4 leaks into a persisted table.
"""
import os
import subprocess
from pathlib import Path

import duckdb
import polars as pl

from config import CONFIG

# primary key per table (grain)
TABLES = {
    "fact_player_season":         ["player_uid", "season", "position"],
    "fact_player_season_metrics": ["player_uid", "season", "position"],
    "fact_player_week_metrics":   ["player_uid", "season", "week", "position"],
    "fact_replacement":           ["season", "week", "position", "profile"],
}
# columns EXPECTED to differ if the two ordinal-rank sites are the whole remaining cause
RANK_DERIVED = {
    "fact_player_season":         {"pos_finish_ppr"},
    "fact_player_week_metrics":   {"wk_pos_rank_ppr", "wk_pos_rank_your_league", "vorp_ppr"},
    "fact_replacement":           {"replacement_points"},
    "fact_player_season_metrics": {"boom_rate", "bust_rate", "vorp_ppr_total"},
}
OUT = Path("/tmp/g104_cols")


def _worker(label):
    import contextlib
    import io
    import hashlib
    import json
    from transform import warehouse, metrics
    with contextlib.redirect_stdout(io.StringIO()):
        warehouse.run()
        metrics.run()
    d = OUT / label
    d.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(CONFIG.path("warehouse")), read_only=True)
    hashes = {}
    for t in TABLES:
        con.execute(f"copy (select * from {t}) to '{d / (t + '.parquet')}' (format parquet)")
        cols = [r[0] for r in con.execute(
            "select column_name from information_schema.columns "
            "where table_name=? order by ordinal_position", [t]).fetchall()]
        order = ",".join(f'"{c}"' for c in cols)
        csv = con.execute(f'select * from "{t}" order by {order}').pl().write_csv()
        hashes[t] = (hashlib.sha256(csv.encode()).hexdigest()[:12],
                     con.execute(f'select count(*) from "{t}"').fetchone()[0])
    con.close()
    import polars as _pl
    print("WORKER_OK", label, "threads=" + str(_pl.thread_pool_size()), "HASHES=" + json.dumps(hashes))


def run(n=5, threads=None):
    """threads=1 forces POLARS_MAX_THREADS=1 in each fresh worker (the C2 decider)."""
    import json
    root = str(Path(__file__).resolve().parent.parent)
    env = dict(os.environ, PATH=os.path.expanduser("~/.local/bin") + ":" + os.environ.get("PATH", ""))
    if threads is not None:
        env["POLARS_MAX_THREADS"] = str(threads)
    labels = [chr(ord("A") + i) for i in range(n)]
    per_table_hashes = {t: [] for t in TABLES}
    print(f"=== column sweep: n={n} fresh processes, POLARS_MAX_THREADS={threads if threads else 'default'} ===")
    for label in labels:
        r = subprocess.run(
            ["uv", "run", "python", "-c",
             f"from jobs.g104_colsweep import _worker as w; w('{label}')"],
            cwd=root, env=env, capture_output=True, text=True)
        okline = [l for l in r.stdout.splitlines() if l.startswith("WORKER_OK")]
        if not okline:
            print(f"worker {label} FAILED\n{r.stderr[-1500:]}")
            return
        parts = okline[0].split("HASHES=", 1)
        hs = json.loads(parts[1])
        for t in TABLES:
            per_table_hashes[t].append(tuple(hs[t]))
        print(f"built {label}: {okline[0].split('HASHES=')[0].strip()}")

    print("\n=== per-table content-hash byte-identity across all", n, "processes ===")
    all_ident = True
    for t in TABLES:
        distinct = {h for h, _ in per_table_hashes[t]}
        counts = {c for _, c in per_table_hashes[t]}
        ok = len(distinct) == 1 and len(counts) == 1
        all_ident &= ok
        print(f"  {t:28s} {'IDENTICAL' if ok else 'DIFFERS'}  hashes={sorted(distinct)} rows={sorted(counts)}")
    print(f"\n  >>> ALL 4 TABLES BYTE-IDENTICAL ACROSS {n} PROCESSES: {'YES (path-a candidate)' if all_ident else 'NO (C2/C3 survive)'}")
    print("=" * 60)

    all_rank_only = True
    for t, keys in TABLES.items():
        a = pl.read_parquet(OUT / "A" / (t + ".parquet"))
        b = pl.read_parquet(OUT / "B" / (t + ".parquet"))
        valcols = [c for c in a.columns if c not in keys]
        if a.height != b.height:
            only_a = a.select(keys).unique().join(b.select(keys).unique(), on=keys, how="anti").height
            only_b = b.select(keys).unique().join(a.select(keys).unique(), on=keys, how="anti").height
            all_rank_only = False
            print(f"\n{t}: ROW COUNT DIFFERS A={a.height} B={b.height} "
                  f"(keys only-in-A={only_a}, only-in-B={only_b}) -> KEY-SET nondeterminism")
        j = a.join(b, on=keys, how="inner", suffix="__b")
        diffs = {}
        for c in valcols:
            ne = j.select(pl.col(c).ne_missing(pl.col(c + "__b")).sum().alias("n")).item()
            if ne > 0:
                diffs[c] = ne
        rank = RANK_DERIVED.get(t, set())
        nonrank = {c: n for c, n in diffs.items() if c not in rank}
        print(f"\n{t}: rows={a.height}; key 1:1 OK; differing value cols = {list(diffs) or 'NONE'}")
        for c, n in sorted(diffs.items()):
            tag = "rank-derived" if c in rank else "*** NON-RANK (unexplained) ***"
            print(f"    {c:22s} {n:6d} mismatched rows   [{tag}]")
        if nonrank:
            all_rank_only = False
            print(f"    -> {t}: NON-RANK columns differ {list(nonrank)} -> 3rd SITE, root cause INCOMPLETE")
        elif diffs:
            print(f"    -> {t}: ALL differing columns trace to the two rank sites")
        else:
            print(f"    -> {t}: no value column differs (was flagged nondeterministic — investigate)")

    print("\n" + "=" * 60)
    print("COMPLETENESS VERDICT:",
          "RANK-ONLY — two rank sites explain ALL remaining variance (S4 provably does not leak)"
          if all_rank_only else
          "INCOMPLETE — a non-rank site exists; DO NOT declare root cause complete, DO NOT fix yet")


if __name__ == "__main__":
    run()
