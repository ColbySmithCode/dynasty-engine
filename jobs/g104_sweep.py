"""G10.4 order-sensitivity sweep (DIAGNOSTIC ONLY — not a gate, not committed).

Proves that transform.identity.build_dim_player() picks its per-uid representative /
canonical base order-sensitively (S1 identity.py:196-198, S2 identity.py:180), which is
the class of defect A14 reports. S3 (identity.py:107 unique keep-first) is shown inert
(0 duplicate mfl_ids). This does NOT reproduce the cross-process mechanism (identical
input + unstable parallel sort) — only g104_repro.fullrun(5) does that. It isolates the
in-repo order-sensitive sites.
"""
import hashlib
import polars as pl
from transform import identity


def content_hash(df: pl.DataFrame) -> str:
    # canonical content hash: order by ALL columns (identical rows tie -> order-immune),
    # matching g104_repro's `select * order by <all cols>` semantics.
    cols = sorted(df.columns)
    csv = df.sort(by=cols, nulls_last=True).write_csv()
    return hashlib.sha256(csv.encode()).hexdigest()[:16]


def main():
    orig_canon = identity._canonicalize

    # --- S3 evidence: is line-107 unique(keep=first) inert? ---
    cw = identity._load_crosswalk().unique(subset=["mfl_id"], keep="first")
    dups = cw.group_by("mfl_id").len().filter(pl.col("len") > 1).height
    nulls = cw.select(pl.col("mfl_id").is_null().sum()).item()
    print(f"[S3] crosswalk rows entering line-107 unique: {cw.height}; "
          f"duplicate mfl_ids: {dups}; null mfl_ids: {nulls} "
          f"-> S3 keep-first is {'INERT' if dups == 0 else 'LIVE'}")

    # --- (A) in-process repeat, NO shuffle: does polars-internal nondeterminism show? ---
    identity._canonicalize = orig_canon
    a_hashes = []
    for i in range(3):
        d = identity.build_dim_player()
        a_hashes.append((content_hash(d), d.height))
    print("\n[A] no-shuffle, 3 in-process rebuilds (content_hash, rows):")
    for i, (h, n) in enumerate(a_hashes):
        print(f"    run {i}: {h}  rows={n}")
    print(f"    -> {'STABLE in-process' if len({h for h,_ in a_hashes})==1 else 'VARIES in-process'}")

    # --- (B) shuffled input to _canonicalize (perturbs S1 representative + S2 base): ---
    def shuffled_canon(seed):
        def _c(dim):
            return orig_canon(dim.sample(fraction=1.0, shuffle=True, seed=seed))
        return _c

    b_hashes = []
    for s in (1, 2, 3, 4, 5):
        identity._canonicalize = shuffled_canon(s)
        d = identity.build_dim_player()
        b_hashes.append((s, content_hash(d), d.height))
    identity._canonicalize = orig_canon
    print("\n[B] shuffled _canonicalize input, 5 seeds (seed, content_hash, rows):")
    for s, h, n in b_hashes:
        print(f"    seed {s}: {h}  rows={n}")
    distinct = {h for _, h, _ in b_hashes}
    counts = {n for _, _, n in b_hashes}
    print(f"    -> distinct content hashes: {len(distinct)}; distinct row counts: {sorted(counts)}")
    print(f"    -> S1/S2 order-sensitivity: {'CONFIRMED (hash flips under input shuffle)' if len(distinct)>1 else 'NOT reproduced'}")
    print(f"    -> row count invariant under shuffle: {'YES' if len(counts)==1 else 'NO — resolution changed!'}")


if __name__ == "__main__":
    main()
