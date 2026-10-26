"""Pre-registered test: market calculator (DynastyProcess value_2qb) vs engine on rookie picks.

Implements exports/prereg_market_vs_engine.md (+ amendments A1-A6) exactly. H1: rookie picks
underdeliver realized VORP relative to veterans of equal market value. Run once; report as-is.

Archive: dynastyprocess/data git history, files/values.csv at the commits resolved by the locked
snapshot rule (A2). Cached under data/raw/dynastyprocess_archive/<sha>/values.csv.
"""
from __future__ import annotations
import sys, urllib.request
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import duckdb, numpy as np, polars as pl
from config import CONFIG

SNAPS = {2021: "5faea363dec24824435a0d1e14dc964fee655e69",
         2022: "f8689a57893580dfacc237e970d20465d45424d9",
         2023: "eb9cb5cff6bcb2eaca70e49f2e2265575b65a28a"}
H, DELTA, DECAY, LAST = 6, 0.82, 0.85, 2025
K, BAND, MIN_VETS = 5, 0.15, 3
NBOOT, SEED, THRESH, N_ENGINE, N_CLASS = 2000, 1729, 25.0, 20, 10
ROUND = {"1st": 1, "2nd": 2, "3rd": 3, "4th": 4}
THIRD = {"Early": 0, "Mid": 1, "Late": 2}
CACHE = Path(__file__).resolve().parent.parent / "data/raw/dynastyprocess_archive"


def load_snapshot(S):
    p = CACHE / SNAPS[S] / "values.csv"
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://raw.githubusercontent.com/dynastyprocess/data/{SNAPS[S]}/files/values.csv"
        p.write_bytes(urllib.request.urlopen(url, timeout=60).read())
    return pl.read_csv(p, null_values="NA", infer_schema_length=0)


def pick_range(label):
    """'2022 Mid 1st' -> (D, lo, hi, round) on continuous ADP (A5); None if excluded (A3/A4)."""
    parts = label.split()
    D, rest = int(parts[0]), parts[1:]
    if rest[0] == "Pick" or rest[-1] not in ROUND:
        return None
    r = ROUND[rest[-1]]
    lo = 12 * (r - 1) + 0.5
    if len(rest) == 2:
        lo += 4 * THIRD[rest[0]]
        return D, lo, lo + 4, r
    return D, lo, lo + 12, r


def main():
    con = duckdb.connect(str(CONFIG.path("warehouse")), read_only=True)
    vorp = con.execute("SELECT player_uid, season, vorp_ppr_total v FROM fact_player_season_metrics").pl()
    radp = con.execute("""SELECT player_uid, season, adp FROM fact_adp
        WHERE format='R' AND ppr=-1 AND period='DRAFT' AND adp IS NOT NULL""").pl()
    fpmap = con.execute("SELECT fantasypros_id fp_id, player_uid FROM dim_player WHERE fantasypros_id IS NOT NULL").pl()
    con.close()
    V = {(u, s): v for u, s, v in vorp.iter_rows()}

    def realized(uid, S, extrap):
        out, last = 0.0, 0.0
        for t in range(H):
            y = S + t
            if y <= LAST:
                last = V.get((uid, y), 0.0) or 0.0
                x = last
            elif extrap:
                last = last * DECAY
                x = last
            else:
                break
            out += DELTA ** t * x
        return out

    rows, log = [], []
    for S in SNAPS:
        df = load_snapshot(S).with_columns(pl.col("value_2qb").cast(pl.Float64))
        picks = df.filter(pl.col("pos") == "PICK")
        vets = (df.filter(pl.col("pos") != "PICK")
                  .with_columns(pl.col("draft_year").cast(pl.Int32, strict=False)))
        n_all = len(vets)
        vets = vets.filter(pl.col("draft_year").is_not_null() & (pl.col("draft_year") < S))
        n_vet = len(vets)
        vets = vets.join(fpmap, on="fp_id", how="inner").unique("player_uid").sort("player_uid")  # A7
        log.append(f"  S={S} commit {SNAPS[S][:7]}: player rows {n_all}, veterans (draft_year<S) {n_vet}, "
                   f"matched to dim_player {len(vets)} (dropped {n_vet - len(vets)}), pick rows {len(picks)}")
        vv = vets.select("player_uid", "value_2qb").to_numpy()
        kept = dropped = excl = 0
        for lab, pv in picks.select("player", "value_2qb").iter_rows():
            pr = pick_range(lab)
            if pr is None or not (S + 1 <= pr[0] <= S + 2):
                excl += 1
                continue
            D, lo, hi, rnd = pr
            vals = vv[:, 1].astype(float)
            ok = np.abs(vals - pv) <= BAND * pv
            cand = np.where(ok)[0]
            cand = cand[np.argsort(np.abs(vals[cand] - pv), kind="stable")][:K]  # A7: ties -> player_uid asc
            if len(cand) < MIN_VETS:
                dropped += 1
                continue
            rk = radp.filter((pl.col("season") == D) & (pl.col("adp") >= lo) & (pl.col("adp") < hi))["player_uid"].to_list()
            rows.append(dict(S=S, label=lab, D=D, rnd=rnd, lo=lo, hi=hi, pv=pv,
                             rookies=rk, vets=[vv[i, 0] for i in cand]))
            kept += 1
        log.append(f"           pick rows used {kept}, dropped (<{MIN_VETS} vets in ±15%) {dropped}, "
                   f"excluded by rule (D∉{{S+1,S+2}} / 5th / slot picks) {excl}")

    # ---- unique players for the bootstrap (rookies within class, veterans pooled) ----
    classes = sorted({r["D"] for r in rows})
    rk_ids = {D: sorted({u for r in rows if r["D"] == D for u in r["rookies"]}) for D in classes}
    vet_ids = sorted({u for r in rows for u in r["vets"]})
    vix = {u: i for i, u in enumerate(vet_ids)}
    rix = {D: {u: i for i, u in enumerate(rk_ids[D])} for D in classes}

    def stats(extrap):
        P, Vt, rmap, vmap = [], [], [], []
        for r in rows:
            P.append(np.array([realized(u, r["S"], extrap) for u in r["rookies"]]))
            Vt.append(np.array([realized(u, r["S"], extrap) for u in r["vets"]]))
            rmap.append(np.array([rix[r["D"]][u] for u in r["rookies"]], dtype=int))
            vmap.append(np.array([vix[u] for u in r["vets"]], dtype=int))
        return P, Vt, rmap, vmap

    def deltas(P, Vt, rmap, vmap, wr=None, wv=None):
        d = np.full(len(rows), np.nan)
        for i, r in enumerate(rows):
            a = np.ones(len(P[i])) if wr is None else wr[r["D"]][rmap[i]]
            b = np.ones(len(Vt[i])) if wv is None else wv[vmap[i]]
            if a.sum() == 0 or b.sum() == 0:
                continue
            d[i] = (P[i] * a).sum() / a.sum() - (Vt[i] * b).sum() / b.sum()
        return d

    def boot(extrap):
        P, Vt, rmap, vmap = stats(extrap)
        point = deltas(P, Vt, rmap, vmap)
        rng = np.random.default_rng(SEED)
        reps = np.empty((NBOOT, len(rows)))
        for b in range(NBOOT):
            wr = {D: rng.multinomial(len(rk_ids[D]), np.ones(len(rk_ids[D])) / len(rk_ids[D])) for D in classes}
            wv = rng.multinomial(len(vet_ids), np.ones(len(vet_ids)) / len(vet_ids))
            reps[b] = deltas(P, Vt, rmap, vmap, wr, wv)
        return point, reps, P, Vt

    print("=" * 100)
    print("PRE-REGISTERED TEST  exports/prereg_market_vs_engine.md (+A1-A6)   h=6  delta=0.82  seed 1729  2000 boots")
    print("=" * 100)
    print("\n".join(log))
    print(f"  unique veterans used {len(vet_ids)} | rookies per class " +
          ", ".join(f"{D}: {len(rk_ids[D])}" for D in classes))
    empty = [r["label"] + f" (S={r['S']})" for r in rows if not r["rookies"]]
    print(f"  pick rows with NO rookie in slot range: {len(empty)} {empty if empty else ''}")

    res = {}
    for extrap, name in ((True, "EXTRAPOLATED (canon 0.85 decay past 2025)"), (False, "OBSERVED-ONLY (seasons <= 2025)")):
        point, reps, P, Vt = boot(extrap)
        res[extrap] = (point, reps)

        def cell(mask):
            m = np.nanmean(point[mask])
            bm = np.nanmean(reps[:, mask], axis=1)
            lo, hi = np.nanquantile(bm, [.025, .975])
            return m, lo, hi, int(mask.sum())

        print()
        print("=" * 100)
        print(f"{name}   Delta = realized(pick) - mean realized(matched vets), discounted VORP")
        print("=" * 100)
        print(f"{'slice':34s} {'n rows':>6s} {'Delta':>8s}   {'95% CI':>20s}  {'half-w':>7s}  {'pick':>7s} {'vets':>7s}")
        print("-" * 100)
        allm = np.ones(len(rows), bool)
        groups = [("ALL", allm)]
        groups += [(f"snapshot S={S}", np.array([r["S"] == S for r in rows])) for S in SNAPS]
        groups += [(f"draft class D={D}", np.array([r["D"] == D for r in rows])) for D in classes]
        groups += [(f"round {k}", np.array([r["rnd"] == k for r in rows])) for k in (1, 2, 3, 4)]
        pm = np.array([P[i].mean() if len(P[i]) else np.nan for i in range(len(rows))])
        vm = np.array([Vt[i].mean() for i in range(len(rows))])
        for nm, mask in groups:
            if mask.sum() == 0:
                continue
            m, lo, hi, n = cell(mask)
            print(f"{nm:34s} {n:6d} {m:+8.1f}   [{lo:+8.1f},{hi:+8.1f}]  {(hi - lo) / 2:7.1f}  "
                  f"{np.nanmean(pm[mask]):+7.1f} {np.nanmean(vm[mask]):+7.1f}")

        print("\n  per pick row:")
        print(f"  {'S':>4s} {'pick':16s} {'DP v2qb':>7s} {'nRk':>4s} {'pick':>7s} {'vets':>7s} {'Delta':>7s}  matched veterans")
        for i, r in enumerate(rows):
            print(f"  {r['S']:4d} {r['label']:16s} {r['pv']:7.0f} {len(r['rookies']):4d} {pm[i]:+7.1f} {vm[i]:+7.1f} "
                  f"{point[i]:+7.1f}  {','.join(r['vets'])}")

    # ---- verdict, mechanically per the LOCKED rules ----
    print()
    print("=" * 100)
    print("LOCKED PASS/FAIL (evaluated mechanically)")
    print("=" * 100)
    verdicts = {}
    for extrap, nm in ((True, "extrapolated"), (False, "observed-only")):
        point, reps = res[extrap]
        m = np.nanmean(point)
        lo, hi = np.nanquantile(np.nanmean(reps, axis=1), [.025, .975])
        hw = (hi - lo) / 2
        cls = {D: np.nanmean(point[[r["D"] == D for r in rows]]) for D in classes
               if sum(r["D"] == D for r in rows) >= N_CLASS}
        if hw > THRESH:
            v = "UNDERPOWERED"
        elif m <= -THRESH and hi < 0 and all(x < 0 for x in cls.values()):
            v = "SUPPORTED"
        else:
            v = "NOT SUPPORTED"
        verdicts[nm] = v
        print(f"  {nm:14s} Delta {m:+7.1f}  CI [{lo:+7.1f},{hi:+7.1f}]  half-width {hw:5.1f} (limit {THRESH:.0f})  "
              f"classes>={N_CLASS} rows: " + ", ".join(f"{D}:{x:+.1f}" for D, x in cls.items()) + f"  -> {v}")
    vs = set(verdicts.values())
    overall = ("UNDERPOWERED" if "UNDERPOWERED" in vs else
               "SUPPORTED" if vs == {"SUPPORTED"} else "NOT SUPPORTED")
    print(f"  H1 overall (must hold in BOTH reads; underpowered checked first): {overall}")

    # ---- engine leg: leak rule (comparable season + 2 < S), n >= 20 per cell ----
    print()
    print("=" * 100)
    print("ENGINE LEG  leak-free comparables (row season + 2 < S); cell NOT ESTIMABLE if n < 20")
    print("=" * 100)
    from engine.trade_gw_kcc import pools
    cons, corp, rook, _ = pools()
    n_ok = 0
    for S in SNAPS:
        rk = rook.filter(pl.col("season") + 2 < S)
        cn = cons.filter(pl.col("season") + 2 < S)
        cp = corp.filter(pl.col("season") + 2 < S)
        cells = sorted({(r["lo"], r["hi"]) for r in rows if r["S"] == S})
        ns = [len(rk.filter((pl.col("adp") >= lo) & (pl.col("adp") < hi))) for lo, hi in cells]
        n_ok += sum(n >= N_ENGINE for n in ns)
        print(f"  S={S}: rookie-pool comparables per pick cell {ns} (max {max(ns)})  | leak-free startup pool "
              f"size (upper bound on any veteran band): consensus {len(cn)}, corpus {len(cp)}")
    if n_ok:
        print(f"  {n_ok} pick cell(s) estimable -- engine pricing NOT IMPLEMENTED in this run; amend before computing.")
    else:
        print("  -> ENGINE LEG NOT ESTIMABLE in both pools (every pick needs a priced pick cell). "
              "Market-vs-engine question UNANSWERED per prereg; no leaky substitute run.")


if __name__ == "__main__":
    main()
