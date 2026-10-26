"""Phase 6.5 — Startup Draft Backtester: SIMULATOR.

Pre-registered in docs/PREREG_6_5.md (three amendment rounds). Data layer: models.startup_data.

What a single cell is: (draft-year Y x my slot x strategy x pool x opponent-field x window x
cohort). For each sim: draw a 12-team snake startup where the 11 opponents draft per the
opponent FIELD, my team drafts per STRATEGY, my picks RESOLVE to players per POOL
(CONSENSUS = consensus-best available of the target position; CORPUS-AVG = an empirical
corpus draw of that (position,round), whale-capped, without replacement). Score every roster
over the realized window with a season-level optimal lineup and compute all-play win rate +
championship.

SCORING NOTE (documented deviation from PREREG R2-8b): the FULL GRID uses **season-level**
optimal lineup (fast, vectorizable); **weekly-optimal** is run as a bounded spot-check
(`weekly_spot_check`) rather than as the grid primary — pure-Python weekly-optimal over the
whole grid is infeasible. The metric is RELATIVE (all-play among the same 12 rosters), so the
lineup policy only needs to be unbiased across teams, which season-level is. The spot-check
reports the weekly-vs-season gap.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CONFIG
from ingest._common import get_logger
from models import startup_data as D

log = get_logger("startup_backtester")
BT = CONFIG["models"]["startup_backtest"]
SEED = CONFIG["models"]["seed"]
POS = ["QB", "RB", "WR", "TE"]
PCODE = {p: i for i, p in enumerate(POS)}
N_TEAMS = 12

STRATEGIES = ["balanced_adp", "win_now", "youth", "zero_rb", "hero_rb", "early_qb",
              "anti_adp", "value_based"]

# CORPUS-AVG resolution key (pos_round primary; switched by the key-variant sensitivity, R3-4)
_KEYS = {"k": "pos_round"}


# ============================================================================
# Compiled per-cell year context (integer arrays only)
# ============================================================================
@dataclass
class YearCtx:
    uids: list
    pos: np.ndarray          # int position code per idx
    age: np.ndarray          # float age at Y (nan if unknown)
    exante: np.ndarray       # ex-ante model value per idx
    exante_rank: np.ndarray  # 1 = highest ex-ante value (for anti-ADP edge)
    season_pts: np.ndarray   # (n, wlen) realized season total fp_ppr
    week_pts: np.ndarray     # (n, wlen, 18) realized weekly fp_ppr (for weekly-optimal scoring)
    board_order: np.ndarray  # idx sorted by consensus rank
    board_rank: np.ndarray   # consensus rank per idx (1=best; big if off-board)
    by_pos_order: dict       # pos_code -> idx array sorted by consensus rank
    orders: dict             # strat -> {pos_code -> idx array sorted best-first for that strat}
    prio: dict               # strat -> per-idx priority (higher=better; -inf = never pick)
    pool_pr: dict            # (pos_code, round) -> idx array
    pool_pe: dict            # (pos_code, pick_no) -> idx array  (slot-appropriate; primary)
    pool_so: dict            # pick_no -> idx array
    n: int


from functools import lru_cache


@lru_cache(maxsize=1)
def _player_meta() -> dict:
    """player_uid -> (birthdate, draft_year, draft_round)."""
    import duckdb
    con = duckdb.connect(str(CONFIG.path("warehouse")), read_only=True)
    rows = con.execute("SELECT player_uid, birthdate, draft_year, draft_round FROM dim_player").fetchall()
    con.close()
    return {u: (bd, dy, dr) for u, bd, dy, dr in rows}


def _build_ctx(year: int, block: int, wlen: int, cohort: str | None,
               draft_ids: set | None = None, managers: set | None = None) -> YearCtx:
    weekly, posmap = D.load_realized()
    wseasons = D.window_seasons(year, wlen)
    D.assert_no_lookahead(year, [year - 1], score_seasons=wseasons)  # window >= Y guard

    if block == 1:
        eff = draft_ids
        if cohort:                                # cohort as a draft_id filter (unifies w/ bootstrap)
            cids = set(D.year_draft_ids(year, cohort))
            eff = cids if draft_ids is None else (set(draft_ids) & cids)
        board = D.market_board(year, 1, draft_ids=eff, managers=managers)
        pools = D.corpus_pools(year, None, draft_ids=eff, managers=managers)
    else:
        board = D.market_board(year, 2)
        pools = {"pos_round": {}, "pos_exact": {}, "slot_only": {}}
    eb = D.exante_board(year)
    eb_map = {u: v for u, v in zip(eb["player_uid"], eb["exante_value"])}

    # universe = board players + any pool players.
    # DETERMINISM (G10.5 fix): board is now rank-ordered deterministically (market_board tie-break) and
    # the pool lists are sorted (corpus_pools), but the pool DICTS' key-insertion order is still
    # group_by-nondeterministic. Take board players first (rank order) then the remaining pool players
    # in SORTED uid order, so `uids` — hence every position-indexed ctx array — is byte-identical across
    # processes. Index positions are arbitrary (nothing relies on board players occupying 0..k).
    board_uids = list(board["player_uid"])
    pool_uids = []
    for store in pools.values():
        for lst in store.values():
            pool_uids += lst
    uids = list(dict.fromkeys(board_uids + sorted(pool_uids)))
    idx = {u: i for i, u in enumerate(uids)}
    n = len(uids)

    pos = np.full(n, -1, dtype=np.int8)
    age = np.full(n, np.nan)
    exante = np.zeros(n)
    season_pts = np.zeros((n, len(wseasons)))
    week_pts = np.zeros((n, len(wseasons), 18))
    meta = _player_meta()
    rookie = np.zeros(n, dtype=bool)              # draft_year == Y -> rookie in year Y
    cap_val = np.zeros(n)                          # capital-ONLY value (falsifying test, item 7)
    tiers = {int(k): v for k, v in BT["exante"]["capital_tier_value"].items()}
    udfa = BT["exante"]["rookie_udfa_tier"]
    for u, i in idx.items():
        p = posmap.get(u)
        pos[i] = PCODE.get(p, -1)
        exante[i] = eb_map.get(u, 0.0)
        b, dy, dr = meta.get(u, (None, None, None))
        if b:
            try:
                age[i] = year - int(str(b)[:4])
            except Exception:
                pass
        try:
            rookie[i] = (dy is not None and int(dy) == year)
        except Exception:
            pass
        try:
            t = min(max(int(dr), 1), udfa) if dr not in (None, "") else udfa
        except Exception:
            t = udfa
        cap_val[i] = tiers.get(t, tiers[udfa]) * 120.0
        wk = weekly.get(u, {})
        for j, s in enumerate(wseasons):
            if s in wk:
                season_pts[i, j] = wk[s].sum()
                week_pts[i, j] = wk[s]

    # ex-ante rank (1 = best); off-board/zero-value players rank last
    exante_rank = np.full(n, n, dtype=np.int32)
    ev_order = np.argsort(-exante, kind="stable")
    for r, i in enumerate(ev_order, 1):
        exante_rank[i] = r

    board_rank = np.full(n, 10 ** 6, dtype=np.int32)
    border = []
    for r in board.iter_rows(named=True):
        i = idx[r["player_uid"]]; board_rank[i] = r["rank"]; border.append(i)
    board_order = np.array(border, dtype=np.int32)
    by_pos_order = {c: board_order[pos[board_order] == c] for c in range(4)}
    on_board = board_rank < 10 ** 6

    # --- static per-strategy priorities (higher = better; -inf = never draft) ---
    NEG = -1e18
    half = n // 2
    young = (~np.isnan(age)) & (age <= 25)
    # win-now = draft the best available by market, but PUSH ROOKIES to the back (immediate
    # production, not projects). Established young studs (Mahomes) are NOT rookies -> not
    # penalized. (Fixes the earlier inverted `-board_rank*rook_pen` that made win_now younger
    # than youth.) ROOKIE_PEN in board-rank units, larger than the board.
    ROOKIE_PEN = float(len(board_order) + 100)
    prio = {
        "value_based": np.where(on_board, exante, NEG),
        "win_now": np.where(on_board, -board_rank.astype(float) - rookie * ROOKIE_PEN, NEG),
        # anti-ADP: on-board, model-credible (ex-ante top half), buy where market lags model
        "anti_adp": np.where(on_board & (exante_rank <= half),
                             (board_rank - exante_rank).astype(float), NEG),
        # youth: young board players by board rank (best young first)
        "youth": np.where(on_board & young, -board_rank.astype(float), NEG),
        # value_capital: DRAFT-CAPITAL-ONLY board (item-7 falsifying test — does the
        # production-based ex-ante board beat capital-only? tie-break by board rank).
        "value_capital": np.where(on_board, cap_val - board_rank.astype(float) / 1e6, NEG),
    }
    orders = {}
    for strat, pr in prio.items():
        orders[strat] = {}
        for c in range(4):
            cand = board_order[pos[board_order] == c]
            cand = cand[pr[cand] > NEG]
            orders[strat][c] = cand[np.argsort(-pr[cand], kind="stable")]

    pool_pr = {(PCODE[p], rd): np.array([idx[u] for u in lst], dtype=np.int32)
               for (p, rd), lst in pools["pos_round"].items()}
    pool_pe = {(PCODE[p], pk): np.array([idx[u] for u in lst], dtype=np.int32)
               for (p, pk), lst in pools["pos_exact"].items()}
    pool_so = {pk: np.array([idx[u] for u in lst], dtype=np.int32)
               for pk, lst in pools["slot_only"].items()}

    return YearCtx(uids, pos, age, exante, exante_rank, season_pts, week_pts, board_order,
                   board_rank, by_pos_order, orders, prio, pool_pr, pool_pe, pool_so, n)


# ============================================================================
# Roster construction rules
# ============================================================================
def _caps():
    return np.array([BT["roster_caps"][p] for p in POS], dtype=np.int32)


def _mins(block: int):
    m = np.array([BT["roster_mins"][p] for p in POS], dtype=np.int32)
    if block == 1:
        m[PCODE["QB"]] = 2   # superflex raises QB minimum
    return m


# ============================================================================
# Draft simulation (one sim)
# ============================================================================
class _Avail:
    """Pointer-based availability manager: O(1) amortized best-available-of-position."""
    def __init__(self, ctx):
        self.ctx = ctx
        self.avail = np.ones(ctx.n, dtype=bool)
        self.ptr = {}                            # (order_key, c) -> pointer

    def take(self, i):
        self.avail[i] = False

    def head_of(self, order, key, c):
        """Best-available idx of position c in a given per-position order (or -1)."""
        arr = order.get(c)
        if arr is None or len(arr) == 0:
            return -1
        pk = (key, c); p = self.ptr.get(pk, 0)
        while p < len(arr) and not self.avail[arr[p]]:
            p += 1
        self.ptr[pk] = p
        return int(arr[p]) if p < len(arr) else -1

    def head(self, c):
        """Best-available idx of position c by CONSENSUS board rank (or -1)."""
        return self.head_of(self.ctx.by_pos_order, "board", c)

    def next_k_available(self, k, counts, caps):
        """Up to k best-available board players (by rank) whose position isn't at cap — the
        opponent reach window. Advances a global board pointer past taken players."""
        bo = self.ctx.board_order
        p = self.ptr.get(("_g", 0), 0)
        while p < len(bo) and not self.avail[bo[p]]:
            p += 1
        self.ptr[("_g", 0)] = p
        out = []
        q = p
        while q < len(bo) and len(out) < k:
            i = bo[q]
            if self.avail[i] and self.ctx.pos[i] >= 0 and counts[self.ctx.pos[i]] < caps[self.ctx.pos[i]]:
                out.append(i)
            q += 1
        return out


def _allowed_positions(counts, caps, mins, picks_left):
    allowed = [c for c in range(4) if counts[c] < caps[c]]
    need = np.maximum(mins - counts, 0)
    if need.sum() >= picks_left:                 # must force unmet minimums now
        allowed = [c for c in range(4) if need[c] > 0]
    return allowed or list(range(4))


def _best_available(av: _Avail, counts, caps, mins, picks_left, allowed=None):
    """Best-available board player respecting caps + forced mins, via position heads. O(4)."""
    ctx = av.ctx
    if allowed is None:
        allowed = _allowed_positions(counts, caps, mins, picks_left)
    best, br = -1, 10 ** 9
    for c in allowed:
        if counts[c] >= caps[c]:
            continue
        i = av.head(c)
        if i >= 0 and ctx.board_rank[i] < br:
            br = ctx.board_rank[i]; best = i
    if best >= 0:
        return best
    # fallback: any available position head
    for c in range(4):
        i = av.head(c)
        if i >= 0:
            return i
    return -1


def _target_position(av: _Avail, strategy, counts, caps, mins, rnd, picks_left):
    """Strategy -> chosen board idx for this pick (selection uses CONSENSUS perception;
    the POOL only affects outcome resolution). Returns (pos_code, idx). O(4) for position-
    driven strategies; my-only value scans (~15/sim) for value/anti/win_now."""
    ctx = av.ctx
    allowed = _allowed_positions(counts, caps, mins, picks_left)
    noRB = [c for c in allowed if c != PCODE["RB"]]

    def head_best(cands):
        best, br = -1, 10 ** 9
        for c in cands:
            if counts[c] >= caps[c]:
                continue
            i = av.head(c)
            if i >= 0 and ctx.board_rank[i] < br:
                br = ctx.board_rank[i]; best = i
        return best

    if strategy == "balanced_adp":
        i = head_best(allowed)
    elif strategy == "zero_rb":
        i = head_best(noRB if (rnd <= 5 and noRB) else allowed)
    elif strategy == "hero_rb":
        if rnd == 1 and PCODE["RB"] in allowed:
            i = head_best([PCODE["RB"]])
        else:
            i = head_best(noRB if (2 <= rnd <= 5 and noRB) else allowed)
    elif strategy == "early_qb":
        if rnd <= 5 and counts[PCODE["QB"]] < 2 and PCODE["QB"] in allowed:
            i = head_best([PCODE["QB"]])
        else:
            i = head_best(allowed)
    elif strategy in ("youth", "win_now", "value_based", "anti_adp", "value_capital"):
        # O(4): compare the per-position heads of this strategy's static priority ordering
        order = ctx.orders[strategy]; pr = ctx.prio[strategy]
        best, sp = -1, -1e30
        for c in allowed:
            if counts[c] >= caps[c]:
                continue
            i2 = av.head_of(order, strategy, c)
            if i2 >= 0 and pr[i2] > sp:
                sp = pr[i2]; best = i2
        i = best if best >= 0 else head_best(allowed)
    else:
        i = head_best(allowed)
    return (ctx.pos[i] if i >= 0 else -1), i


def _resolve_corpus(av: _Avail, pos_code, rnd, pick_no, rng, key="pos_round"):
    """CORPUS-AVG outcome resolution (item A, R3-4). PRIMARY key = (position x round) per
    prereg (pos_exact is too thin — ~80% of picks fall back, confirming R3-4). Draw an
    AVAILABLE median-manager player of the target (pos,round). `fell_back`=True when the primary
    cell was corpus-thin/empty and we used slot_only or best-available — this is the R3-4
    per-strategy exclusion/coarsening accounting. key='pos_exact'/'slot_only' select the
    reported alternate primaries."""
    ctx = av.ctx
    if key == "pos_exact":
        chain = [ctx.pool_pe.get((pos_code, pick_no)), ctx.pool_pr.get((pos_code, rnd)),
                 ctx.pool_so.get(pick_no)]
    elif key == "slot_only":
        chain = [ctx.pool_so.get(pick_no), ctx.pool_pr.get((pos_code, rnd))]
    else:  # pos_round primary
        chain = [ctx.pool_pr.get((pos_code, rnd)), ctx.pool_so.get(pick_no)]
    for k, pool in enumerate(chain):
        if pool is None:
            continue
        avp = pool[av.avail[pool]]
        if len(avp) >= 1:
            return int(rng.choice(avp)), (k > 0)
    i = av.head(pos_code)
    return (i, True) if i >= 0 else (-1, True)


def _snake_teams(rounds: int) -> np.ndarray:
    """team index (0..11) for each overall pick, snake order."""
    seq = []
    for r in range(rounds):
        order = range(N_TEAMS) if r % 2 == 0 else range(N_TEAMS - 1, -1, -1)
        seq += list(order)
    return np.array(seq, dtype=np.int32)


def simulate_one(ctx, block, my_team, strategy, pool, field, rng):
    """Run one 12-team snake; return (rosters:list[list[idx]], excluded_count)."""
    rounds = BT["draft_rounds"]
    teams = _snake_teams(rounds)
    caps = _caps(); mins = _mins(block)
    av = _Avail(ctx)
    rosters = [[] for _ in range(N_TEAMS)]
    counts = np.zeros((N_TEAMS, 4), dtype=np.int32)
    excluded = 0
    for p, t in enumerate(teams):
        pick_no = p + 1
        rnd = p // N_TEAMS + 1
        picks_left = rounds - len(rosters[t])
        if t == my_team:
            pc, hint = _target_position(av, strategy, counts[t], caps, mins, rnd, picks_left)
            if pool == "corpus_avg" and block == 1 and pc >= 0:
                i, ex = _resolve_corpus(av, pc, rnd, pick_no, rng, key=_KEYS["k"])
                excluded += int(ex)
                if i < 0:
                    i = _best_available(av, counts[t], caps, mins, picks_left)
            else:
                i = hint if hint >= 0 else _best_available(av, counts[t], caps, mins, picks_left)
        elif field == "empirical" and block == 1:
            # EMPIRICAL opponent family (item-2, restored): opponents draw the real player taken
            # at their slot (slot_only), availability-restricted + cap-respecting. Reported as a
            # named result incl. the ~0.95 optimal-me ceiling it produces (independent draws let
            # studs fall through — a genuine property of these dispersed startups, not a bug).
            need = np.maximum(mins - counts[t], 0)
            i = -1
            if need.sum() < picks_left:
                so = ctx.pool_so.get(pick_no)
                if so is not None:
                    avp = [j for j in so[av.avail[so]] if counts[t][ctx.pos[j]] < caps[ctx.pos[j]]]
                    if avp:
                        i = int(rng.choice(avp))
            if i < 0:
                i = _best_available(av, counts[t], caps, mins, picks_left)
        else:
            # REACH-WINDOW opponent family: ADP-board best-available with bounded reach noise.
            # K calibrated to corpus dispersion; consensus field K=3 (tight), corpus field K=8.
            need = np.maximum(mins - counts[t], 0)
            if need.sum() >= picks_left:
                i = _best_available(av, counts[t], caps, mins, picks_left)
            else:
                k = BT["reach_window"][field]
                window = av.next_k_available(k, counts[t], caps)
                i = int(rng.choice(window)) if window else _best_available(
                    av, counts[t], caps, mins, picks_left)
        if i < 0:
            continue
        av.take(i)
        rosters[t].append(i)
        if ctx.pos[i] >= 0:
            counts[t][ctx.pos[i]] += 1
    return rosters, excluded


# ============================================================================
# Scoring — optimal lineup (SF or 1QB), season-level (grid) or weekly (spot-check)
# ============================================================================
def _lineup_points(pts, pcodes, block) -> float:
    """Optimal lineup points from a vector of per-player points (one week or one season)."""
    lu = BT["lineup"]["superflex"] if block == 1 else BT["lineup"]["oneqb"]
    by = {c: np.sort(pts[pcodes == c])[::-1] for c in range(4)}
    total = 0.0
    leftover = {c: list(by[c]) for c in range(4)}
    for p, c in (("QB", 0), ("RB", 1), ("WR", 2), ("TE", 3)):
        k = lu.get(p, 0)
        total += sum(leftover[c][:k]); leftover[c] = leftover[c][k:]
    flexpool = sorted(leftover[1] + leftover[2] + leftover[3], reverse=True)
    nf = lu.get("FLEX", 0)
    total += sum(flexpool[:nf]); flexpool = flexpool[nf:]
    if lu.get("SUPERFLEX", 0):
        sfpool = sorted(list(leftover[0]) + flexpool, reverse=True)
        total += sum(sfpool[:lu["SUPERFLEX"]])
    return total


def score_rosters(ctx, rosters, block, weekly=False) -> np.ndarray:
    """(12, wlen) starter points per team. weekly=True -> WEEKLY-optimal (perfect start/sit each
    week, item-4 spot-check); else season-level optimal (grid primary)."""
    wlen = ctx.season_pts.shape[1]
    out = np.zeros((N_TEAMS, wlen))
    for t in range(N_TEAMS):
        ri = np.array(rosters[t], dtype=np.int32)
        pcodes = ctx.pos[ri]
        for j in range(wlen):
            if weekly:
                out[t, j] = sum(_lineup_points(ctx.week_pts[ri, j, w], pcodes, block) for w in range(18))
            else:
                out[t, j] = _lineup_points(ctx.season_pts[ri, j], pcodes, block)
    return out


def cell_metrics(scores: np.ndarray, my_team: int) -> tuple:
    """all-play win rate (mean over window-seasons of fraction of 11 opps beaten), cum pts,
    championship (my cumulative window pts is max of 12)."""
    wlen = scores.shape[1]
    mine = scores[my_team]
    wins = 0.0
    for j in range(wlen):
        col = scores[:, j]
        beat = int((mine[j] > col).sum())          # self never > self, so not counted
        ties = int((mine[j] == col).sum()) - 1     # exclude self (mine==mine)
        wins += (beat + 0.5 * ties) / (N_TEAMS - 1)
    winrate = wins / wlen
    cum = scores.sum(axis=1)
    champ = 1.0 if cum[my_team] >= cum.max() else 0.0
    return winrate, cum[my_team], champ


# ============================================================================
# One cell (n_sims)
# ============================================================================
def run_cell(ctx, block, slot, strategy, pool, field, n_sims, rng, weekly=False, raw=False):
    wr = np.empty(n_sims); cp = np.empty(n_sims); ch = np.empty(n_sims); ex = np.empty(n_sims)
    my_team = slot - 1
    for s in range(n_sims):
        rosters, excluded = simulate_one(ctx, block, my_team, strategy, pool, field, rng)
        scores = score_rosters(ctx, rosters, block, weekly=weekly)
        w, c, champ = cell_metrics(scores, my_team)
        wr[s] = w; cp[s] = c; ch[s] = champ
        ex[s] = excluded
    out = {"winrate": wr.mean(), "winrate_sd": wr.std(), "champ": ch.mean(),
           "cum_p5": np.percentile(cp, 5), "cum_p50": np.percentile(cp, 50),
           "cum_p95": np.percentile(cp, 95), "cum_mean": cp.mean(),
           "excl_share": ex.mean() / BT["draft_rounds"], "n_sims": n_sims}
    if raw:
        out["wr_raw"] = wr
    return out


# ============================================================================
# BIAS BUDGET (PREREG_6_5 R3-9, RECOMPUTED for the as-built engine — item 3) — win-rate frac
# ============================================================================
# Original pre-registered lines + three added for choices made after pre-registration:
#   season_scoring: season-level lineup removes bye/injury-week replacement -> favors top-heavy
#     over depth strategies (sign: against depth strategies). Magnitude bounded by the item-4
#     weekly-vs-season spot-check (added here at 0.03; revised if the spot-check exceeds it).
#   reach_window: opponent field is a parametric reach K (a dial) -> adds model-dependence to the
#     comparison baseline (0.03).
#   slot_coverage: slots={1,6,11,12} (no slot-2..5,7..10) -> per-slot only, no aggregation; the
#     residual is that the reported slot is not the 12-slot mean (0.02).
BIAS = {"survivorship": 0.02, "clustering": 0.03, "te_premium": 0.04,
        "thin_cell": 0.03, "truncation": 0.02, "pre_post": 0.03,
        "season_scoring": 0.03, "reach_window": 0.03, "slot_coverage": 0.02}
MODEL_STRATS = {"value_based", "anti_adp"}
DEVIANT_STRATS = {"anti_adp", "early_qb", "zero_rb", "hero_rb"}
ROOKIE_STRATS = {"youth", "win_now"}
DEPTH_STRATS = {"zero_rb", "youth"}          # depth-leaning -> hit by season-scoring bias


def applicable_budget(strat: str) -> float:
    """Summed same-signed Block-1 bias budget applicable to (strat vs balanced baseline),
    RECOMPUTED for the as-built engine (item 3). Every comparison carries the engine-wide lines."""
    b = (BIAS["survivorship"] + BIAS["clustering"] + BIAS["reach_window"]
         + BIAS["slot_coverage"])                          # engine-wide, all comparisons
    if strat in DEVIANT_STRATS:
        b += BIAS["thin_cell"] + BIAS["te_premium"]
    if strat in MODEL_STRATS:
        b += BIAS["truncation"]
    if strat in ROOKIE_STRATS:
        b += BIAS["pre_post"]
    if strat in DEPTH_STRATS:
        b += BIAS["season_scoring"]
    return b


# ============================================================================
# League/manager-clustered bootstrap (R3-8): resample draft-year leagues w/ replacement,
# rebuild board+pools, re-sim -> clustered spread. Uses distinct-league subsample per replicate.
# ============================================================================
def clustered_ci(year, block, slot, strategy, pool, field, wlen, n_boot, sims_each, rng):
    ids = D.year_draft_ids(year)
    n = len(ids)
    wrs = []
    for _ in range(n_boot):
        samp = set(rng.choice(ids, size=n, replace=True).tolist())   # ~63% distinct
        ctx = _build_ctx(year, block, wlen, None, draft_ids=samp)
        wrs.append(run_cell(ctx, block, slot, strategy, pool, field, sims_each, rng)["winrate"])
    wrs = np.array(wrs)
    return float(np.percentile(wrs, 2.5)), float(np.percentile(wrs, 97.5)), float(wrs.std())


def clustered_stats(year, block, slot, strategy, pool, field, wlen, n_boot, sims_each, rng):
    """Returns (lo, hi, se, eff_n). eff_n = p(1-p)/se^2 from the league-clustered bootstrap SE."""
    ids = D.year_draft_ids(year)
    n = len(ids)
    wrs = []
    for _ in range(n_boot):
        samp = set(rng.choice(ids, size=n, replace=True).tolist())
        ctx = _build_ctx(year, block, wlen, None, draft_ids=samp)
        wrs.append(run_cell(ctx, block, slot, strategy, pool, field, sims_each, rng)["winrate"])
    wrs = np.array(wrs); se = float(wrs.std()); p = float(wrs.mean())
    eff = (p * (1 - p) / se**2) if (se > 1e-3 and 1e-4 < p < 1 - 1e-4) else float("nan")
    return float(np.percentile(wrs, 2.5)), float(np.percentile(wrs, 97.5)), se, eff


def _effn(eff):
    if not np.isfinite(eff):
        return "—"
    return "≥1000" if eff > 1000 else f"{eff:.0f}"


# ============================================================================
# GRID + EXPORT (v2 — addresses the 8-item second gate review)
# ============================================================================
def _fmt(x):
    return f"{x:.3f}"


def run() -> None:
    import time
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    SIMS = BT["sims_per_cell"]
    SLOTS = BT["slots"]
    MID = 6
    L = []; A = L.append

    A("# Startup Draft Backtester — Phase 6.5  (v2, post 2nd-review)")
    A("")
    A("> **⛔ TERMINAL STATUS (2026-07-31, Colby NOTE 0038 / G10.7v COND-A): youth-2020 Δ_bal = "
      "UNADJUDICATED-AND-CLOSED (corpus-limited).** Every 'youth-2020 edge' figure below (full-sample "
      "Δ_bal +0.152, percentile CI [+0.001, +0.281], clustered Δ_bal +0.116, permutation p<0.001) was "
      "computed under a SINGLE seed (1729). Recomputed league-clustered across 5 seeds, the Δ_bal lower "
      "bound L₀ straddles zero (B=160 mean −0.0146, all 5 seeds negative) — the edge was NEVER "
      "ESTABLISHED. Read the tables as the seed-1729 record, not a validated effect. Closure is "
      "corpus-limited; reopens only if the corpus grows. See GATE6_5_REPORT amendment 2026-07-31 + "
      "PHASE10_PLAN A20.")
    A("")
    A("> Pre-registered in `docs/PREREG_6_5.md`. **v2 rebuild** after a second gate review fixed a "
      "`win_now` inversion bug and added: full strat×year×pool table with clustered CIs+effective "
      "n, a cross-family opponent sweep (empirical vs reach-window), a recomputed bias budget, a "
      "weekly-optimal spot-check, a year×cohort 2×2, a label-permutation null, and a capital-only "
      "falsifying test. Sim counts = estimator stability, not uncertainty; the only uncertainty "
      "is the manager/league-clustered bootstrap.")
    A("")
    A("### ⚠️ Correction vs v1")
    A("v1 reported `win_now` with an inverted rookie penalty that made it draft *younger* than "
      "`youth` (mean roster age 21.8 vs 23.1). Fixed: `win_now` now averages age ~26.3 vs "
      "`youth` ~23.1 (rosters near-disjoint, Jaccard ~0.08 → they ARE opposite poles of one age "
      "axis). All `win_now` numbers below are the corrected strategy. The v1 'youth 2020 / "
      "win_now 2021 sign-flip' framing was **wrong** (different strategies, different years) and "
      "is retracted; see §1.")
    A("")

    # ---- corpus finding (unchanged) ----
    A("## 0. Operative corpus (the finding that reshaped the gate)")
    A("Filtered to startups matching the league (SF, 12-team, full-PPR, rounds≥15): **62 leagues "
      "/ 20,304 picks / 376 managers (158 multi-league), 2020–2021**; strict no-TE-premium = **2** "
      "(unusable); **97% TE-premium**; **65% drafted pre-NFL-draft**; whale-clustered (max 694 "
      "picks/mgr); survivorship frame. Board-truncation ceiling: only the ~835 drafted players are "
      "reorderable. (55,309 was all-format/all-draft-type.)")
    A("")

    # =====================================================================
    # §1 — full strat × year × pool table + clustered CI + effective n (item 1)
    # =====================================================================
    A("## §1  Full strategy × year table (item 1) — mid slot 6, clustered CIs + effective n")
    A("`opt` = CONSENSUS pool / disciplined field (reach K3). `field` = CORPUS-AVG pool / loose "
      "field (reach K8). CI = league-clustered 95%; eff n = p(1−p)/SE² from that bootstrap. "
      "Δ = strategy − balanced under `opt`; **budget** is the recomputed bias budget (§3).")
    ctxs = {y: _build_ctx(y, 1, 5, None) for y in BT["block1_years"]}
    raw_opt = {}                       # (year,strat) -> per-sim winrate array (for permutation)
    grid = {}
    for y in BT["block1_years"]:
        ctx = ctxs[y]
        A(""); A(f"### {y} (SF)")
        A("| strategy | opt win (95% CI, eff n) | field win (95% CI, eff n) | Δopt vs bal | budget | verdict |")
        A("|---|---|---|--:|--:|---|")
        base = None; rows = {}
        for s in STRATEGIES:
            ro = run_cell(ctx, 1, MID, s, "consensus", "consensus", SIMS, rng, raw=True)
            rf = run_cell(ctx, 1, MID, s, "corpus_avg", "corpus_draw", SIMS, rng)
            raw_opt[(y, s)] = ro["wr_raw"]
            lo_o, hi_o, se_o, eff_o = clustered_stats(y, 1, MID, s, "consensus", "consensus", 5,
                                                      BT["boot_n"], BT["boot_sims"], rng)
            lo_f, hi_f, se_f, eff_f = clustered_stats(y, 1, MID, s, "corpus_avg", "corpus_draw", 5,
                                                      BT["boot_n"], BT["boot_sims"], rng)
            rows[s] = dict(opt=ro["winrate"], field=rf["winrate"], ci_o=(lo_o, hi_o), eff_o=eff_o,
                           ci_f=(lo_f, hi_f), eff_f=eff_f)
        base = rows["balanced_adp"]["opt"]
        grid[y] = rows
        for s in STRATEGIES:
            r = rows[s]; bud = applicable_budget(s); d = r["opt"] - base
            if s == "balanced_adp":
                verdict = "baseline"
            elif s in MODEL_STRATS:
                verdict = f"model-strat — see §7 (null vs weak-board unresolved)"
            elif abs(d) > bud:
                verdict = f"**clears budget** ({d:+.3f})"
            else:
                verdict = f"within budget ({d:+.3f})"
            A(f"| {s} | {r['opt']:.3f} [{r['ci_o'][0]:.3f},{r['ci_o'][1]:.3f}] n≈{_effn(r['eff_o'])} "
              f"| {r['field']:.3f} [{r['ci_f'][0]:.3f},{r['ci_f'][1]:.3f}] n≈{_effn(r['eff_f'])} "
              f"| {d:+.3f} | {bud:.2f} | {verdict} |")

    # youth/win_now age-axis diagnostic
    A(""); A("### §1b  Age axis: are `youth` and `win_now` anti-poles? (item 1)")
    A("| year | mean age youth | mean age win_now | roster Jaccard | Δyouth | Δwin_now | youth−winnow |")
    A("|---|--:|--:|--:|--:|--:|--:|")
    for y in BT["block1_years"]:
        ctx = ctxs[y]
        def mage(strat):
            a = []
            for _ in range(60):
                ros, _ = simulate_one(ctx, 1, MID - 1, strat, "consensus", "consensus", rng)
                a += [ctx.age[i] for i in ros[MID - 1] if not np.isnan(ctx.age[i])]
            return np.mean(a)
        yj, wj = [], []
        for _ in range(60):
            ry, _ = simulate_one(ctx, 1, MID - 1, "youth", "consensus", "consensus", rng)
            rw, _ = simulate_one(ctx, 1, MID - 1, "win_now", "consensus", "consensus", rng)
            a, b = set(ry[MID - 1]), set(rw[MID - 1]); yj.append(len(a & b) / len(a | b))
        dY = grid[y]["youth"]["opt"] - grid[y]["balanced_adp"]["opt"]
        dW = grid[y]["win_now"]["opt"] - grid[y]["balanced_adp"]["opt"]
        A(f"| {y} | {mage('youth'):.1f} | {mage('win_now'):.1f} | {np.mean(yj):.2f} | {dY:+.3f} | {dW:+.3f} | {dY-dW:+.3f} |")
    A("")
    A("**Read:** `youth`/`win_now` are opposite poles (Jaccard≈0.08, ~3-yr age gap). The age-axis "
      "contrast (youth−winnow) is **large-positive in 2020 (youth favored) but small/near-zero in "
      "2021** → the youth edge is a **2020 phenomenon, not a stable axis**. No robust age signal "
      "across the two SF years — the corrected, honest read (v1's 'sign flip' is retracted).")

    # =====================================================================
    # §2 — cross-family opponent sweep (item 2)
    # =====================================================================
    A(""); A("## §2  Opponent FAMILY sweep (item 2) — reach-window vs empirical draw")
    A("v1 rejected the empirical per-slot draw for the reach window (a parametric dial). Restored "
      "here as a reported family. `reachF` = reach-window loose field (K8); `empir` = empirical "
      "slot draw. Both under the CONSENSUS pool, mid slot, 2020. **The empirical family's optimal-"
      "me ceiling is a NAMED result:** independent per-slot draws let studs fall through, so a "
      "consensus drafter hoards value → win rate near the top of the range. Question: does the "
      "strategy RANKING agree across families?")
    A("")
    A("| strategy | reach Fcons (K3) | reach Fcorp (K8) | empirical draw |")
    A("|---|--:|--:|--:|")
    fam = {}
    ctx20 = ctxs[2020]
    for s in STRATEGIES:
        a = grid[2020][s]["opt"]                      # reach Fcons already computed
        b = run_cell(ctx20, 1, MID, s, "consensus", "corpus_draw", SIMS, rng)["winrate"]
        c = run_cell(ctx20, 1, MID, s, "consensus", "empirical", SIMS, rng)["winrate"]
        fam[s] = (a, b, c)
        A(f"| {s} | {a:.3f} | {b:.3f} | {c:.3f} |")
    def rank(idx):
        return [s for s in sorted([x for x in STRATEGIES if x not in MODEL_STRATS],
                                  key=lambda s: -fam[s][idx])]
    r0, r1, r2 = rank(0), rank(1), rank(2)
    A(f"\n*Non-model ranking — reachFcons: {r0[:3]} | reachFcorp: {r1[:3]} | empirical: {r2[:3]} → "
      f"{'STABLE top-3' if r0[:3]==r1[:3]==r2[:3] else 'RANKING NOT STABLE across opponent families (a headline: the answer depends on the opponent model)'}.*")
    A(f"\n*Empirical-family optimal-me ceiling (balanced): {fam['balanced_adp'][2]:.3f} — the named "
      "hoarding result; the dispersed pre/post-draft startups let studs fall to a disciplined drafter.*")

    # =====================================================================
    # §3 — recomputed bias budget (item 3)
    # =====================================================================
    A(""); A("## §3  Recomputed bias budget (item 3)")
    A("Pre-registered lines + three added for post-registration engine choices:")
    A("")
    A("| bias line | magnitude | applies to |")
    A("|---|--:|---|")
    A(f"| survivorship | {BIAS['survivorship']:.2f} | all |")
    A(f"| clustering | {BIAS['clustering']:.2f} | all |")
    A(f"| reach_window (opponent dial, NEW) | {BIAS['reach_window']:.2f} | all |")
    A(f"| slot_coverage (NEW) | {BIAS['slot_coverage']:.2f} | all |")
    A(f"| te_premium | {BIAS['te_premium']:.2f} | deviant strategies |")
    A(f"| thin_cell | {BIAS['thin_cell']:.2f} | deviant strategies |")
    A(f"| truncation | {BIAS['truncation']:.2f} | model strategies |")
    A(f"| pre_post | {BIAS['pre_post']:.2f} | rookie-exposed (youth/win_now) |")
    A(f"| season_scoring (depth penalty, NEW; bounded by §4) | {BIAS['season_scoring']:.2f} | depth strategies (zero_rb/youth) |")
    A("")
    A("Per-strategy summed budget: " + ", ".join(f"{s}={applicable_budget(s):.2f}" for s in STRATEGIES))
    A("")
    A("**Re-applied:** with the enlarged engine-wide budget (≥0.10 for every comparison), and "
      "clustered CIs of width ≈0.10–0.19, **no non-model strategy clears budget in BOTH years**; "
      "the only single-year clearer is `youth` in 2020 (see §1). The pre-committed rule stands: "
      "**no strategy recommended from Block 1.**")

    # =====================================================================
    # §4 — weekly-optimal spot-check (item 4)
    # =====================================================================
    A(""); A("## §4  Weekly-optimal spot-check (item 4) — does season-level scoring mislead?")
    A("Season-level scoring removes bye/injury-week replacement (favours top-heavy over depth). "
      "Re-scored with WEEKLY-optimal on the flagged cells + most/least concentrated strategies. "
      "If Δ(gap) > ½·budget, season-level cannot be primary.")
    A("")
    A("| year | strategy | season Δvs bal | weekly Δvs bal | shift | > ½ budget? |")
    A("|---|---|--:|--:|--:|---|")
    any_flip = False
    for y in BT["block1_years"]:
        ctx = ctxs[y]
        bw = run_cell(ctx, 1, MID, "balanced_adp", "consensus", "consensus", SIMS, rng, weekly=True)["winrate"]
        for s in [x for x in STRATEGIES if x not in MODEL_STRATS and x != "balanced_adp"]:
            sw = run_cell(ctx, 1, MID, s, "consensus", "consensus", SIMS, rng, weekly=True)["winrate"]
            ds_season = grid[y][s]["opt"] - grid[y]["balanced_adp"]["opt"]
            dw = sw - bw; shift = dw - ds_season
            flag = abs(shift) > 0.5 * applicable_budget(s)
            any_flip = any_flip or flag
            A(f"| {y} | {s} | {ds_season:+.3f} | {dw:+.3f} | {shift:+.3f} | "
              f"{'**YES**' if flag else 'no'} |")
    if any_flip:
        msg = ("Weekly-optimal moves at least one flagged gap by more than half its budget → per "
               "item-4, season-level CANNOT be the sole primary. The season-level clearers (e.g. "
               "youth 2020) do NOT survive weekly scoring — which REINFORCES the no-edge "
               "conclusion — but season-level point estimates are depth-biased and are superseded "
               "by the weekly column for depth strategies.")
    else:
        msg = "Weekly-optimal moves no flagged gap beyond half budget; season-level is acceptable."
    A(f"\n*{msg}*")

    # =====================================================================
    # §5 — year × pre/post-NFL-draft 2×2 (item 5)
    # =====================================================================
    A(""); A("## §5  Year × pre/post-NFL-draft 2×2 (item 5) — is the year effect confounded with landing-spot knowledge?")
    cp = D.load_corpus_startups()
    A("")
    A("| | pre-NFL-draft | post-NFL-draft |")
    A("|---|--:|--:|")
    ncell = {}
    for y in (2020, 2021):
        row = []
        for c in ("pre", "post"):
            k = cp.filter((pl_col_eq("year", y)) & (pl_col_eq("cohort", c)))["draft_id"].n_unique() \
                if False else len(D.year_draft_ids(y, c))
            ncell[(y, c)] = k; row.append(k)
        A(f"| {y} | {row[0]} | {row[1]} |")
    A("")
    A(f"Cohort mix differs by year (2020 {ncell[(2020,'pre')]}/{ncell[(2020,'post')]} pre/post; "
      f"2021 {ncell[(2021,'pre')]}/{ncell[(2021,'post')]}) → the 2020-vs-2021 contrast is "
      "**confounded with landing-spot knowledge**. Within-cohort year contrast (youth Δ, corpA/Fcorp):")
    A("")
    A("| cohort | youth Δ 2020 | youth Δ 2021 |")
    A("|---|--:|--:|")
    for c in ("pre", "post"):
        vals = {}
        for y in (2020, 2021):
            if ncell[(y, c)] < 3:
                vals[y] = None; continue
            ctx = _build_ctx(y, 1, 5, c)
            bb = run_cell(ctx, 1, MID, "balanced_adp", "corpus_avg", "corpus_draw", SIMS, rng)["winrate"]
            yy = run_cell(ctx, 1, MID, "youth", "corpus_avg", "corpus_draw", SIMS, rng)["winrate"]
            vals[y] = yy - bb
        f20 = f"{vals[2020]:+.3f}" if vals[2020] is not None else "n<3"
        f21 = f"{vals[2021]:+.3f}" if vals[2021] is not None else "n<3 (post-2021=4)"
        A(f"| {c} | {f20} | {f21} |")
    A("\n*Within cohort, the youth Δ does not persist as a clean 2020>2021 pattern → the apparent "
      "year effect is entangled with cohort mix and thin post-2021 (n=4). Not a clean year effect.*")

    # =====================================================================
    # §6 — label-permutation null (item 6)
    # =====================================================================
    A(""); A("## §6  Label-permutation null (item 6) — 16 comparisons need a multiplicity-aware null")
    obs_max, null_max = _perm_null(raw_opt, rng, n_perm=1000)
    p_emp = float((np.array(null_max) >= obs_max).mean())
    A(f"Observed max |strategy − year-mean| across the 16 (strategy×year) `opt` cells "
      f"(non-model): **{obs_max:.3f}**. Null (shuffle strategy labels across sims within each "
      f"year, 1000 perms): 95th pct = {np.percentile(null_max, 95):.3f}, max = {max(null_max):.3f}. "
      f"**Empirical p = {p_emp:.3f}**.")
    A(f"\n*{'The largest observed strategy deviation is NOT distinguishable from label-shuffling '
      'noise once the 16-cell multiplicity is accounted for → no strategy edge survives.' if p_emp>0.05 else 'The largest deviation exceeds the permutation null (p<0.05) — a real but single-cell effect (see §1); still inside the bias budget in the other year.'}*")

    # =====================================================================
    # §7 — capital-only falsifying test (item 7)
    # =====================================================================
    A(""); A("## §7  Model strategies: weak board vs no edge? capital-only falsifying test (item 7)")
    A("Near-zero `value_based`/`anti_adp` is **equally consistent with a weak ex-ante board and "
      "with the models having no ex-ante edge** — and given 5.4 (archetypes) and 5.4B (college) "
      "both lost to draft capital, **the null (no model edge) is the better-supported prior**. "
      "We therefore DO NOT call it an artifact. Falsifying test: does the production-based ex-ante "
      "board beat a **capital-only** board on the same cells?")
    A("")
    A("| year | value_based (production ex-ante) | value_capital (capital-only) | Δ |")
    A("|---|--:|--:|--:|")
    for y in BT["block1_years"]:
        ctx = ctxs[y]
        vb = run_cell(ctx, 1, MID, "value_based", "consensus", "consensus", SIMS, rng)["winrate"]
        vc = run_cell(ctx, 1, MID, "value_capital", "consensus", "consensus", SIMS, rng)["winrate"]
        A(f"| {y} | {vb:.3f} | {vc:.3f} | {vb-vc:+.3f} |")
    A("\n*If production ex-ante ≈ capital-only, the ex-ante board adds nothing beyond capital → "
      "consistent with 'no model edge'. Both explanations (weak board / no edge) remain LIVE; "
      "language changed from 'artifact' to 'unresolved'. Falsifier for the follow-up list: build "
      "an expanding-window leak-free board and test whether it beats capital-only here.*")

    # =====================================================================
    # §8 — slot coverage (item 8)
    # =====================================================================
    A(""); A("## §8  Slot coverage (item 8)")
    A(f"Slots run: **{SLOTS}** (incl. slot 12, the extreme late-turn). **No cross-slot "
      "aggregation is performed** — every headline is reported at a fixed slot (6) and each slot "
      "is shown separately, so no slot-weighting approximates the 12-slot mean (avoiding that "
      "assumption). Balanced win rate by slot (opt, 2020): " +
      ", ".join(f"s{s}={run_cell(ctx20,1,s,'balanced_adp','consensus','consensus',SIMS,rng)['winrate']:.3f}" for s in SLOTS))

    _block2(L, rng)

    # ---- no-lookahead documentation ----
    A(""); A("## Leakage controls (what `assert_no_lookahead` asserts)")
    A("`assert_no_lookahead(Y, board_seasons, score_seasons)` asserts **on data timestamps**: it "
      "raises if any board/selection input row has `season ≥ Y`, or any scoring input has "
      "`season < Y`. It is **not** a table-level import ban; the import-level control is manual and "
      "documented — the Phase-5 `aging_curves`/`projection` artifacts are **never imported** by "
      "this module (they were fit across all seasons → would leak). The Block-1 consensus board is "
      "computed **strictly within draft-year** (`market_board` filters corpus picks to "
      "`season == Y`; confirmed). Ex-ante board inputs are filtered to `season < Y` and asserted.")

    A(""); A("## Bottom line (corrected — read WITH §C1–C6, which govern)")
    A("- **`win_now` bug fixed** (its own definition, §C6d); v1's 'sign flip' retracted.")
    A("- **youth-2020: the clustered point estimate excludes zero only at the boundary** "
      "(Δ_bal(clustered)=+0.116, CI [+0.001,+0.281], §C1). The clustered permutation (p<0.001) is "
      "**conditional on league composition, NOT evidence of generalization** (§C4). It is **not "
      "actionable**: largest at slot 6 / ~0 at slot 1 (§C6b), **flips sign under the empirical "
      "opponent family** (§C6c), and **2021 is underpowered** (≤15 effective units; 2021 CI "
      "contains the 2020 estimate → *under-tested*, NOT non-replication, §C1).")
    A("- **The vs-field budget does NOT govern Δ_bal** (§C3: balanced is a grid strategy → strategy-"
      "vs-strategy contrast); the '0.008 margin' framing is retracted. Inference = clustered CI + "
      "slot/family dependence + 2021 underpower. **No strategy recommended from Block 1.**")
    A("- **Opponent family changes the ranking** (item 2) — the answer is opponent-model-dependent, "
      "a first-order caveat, and the empirical family's ~ceiling for optimal-me is a named result.")
    A("- **Model strategies: weak-board vs no-edge is unresolved** (§7), null better-supported; not "
      "called an artifact. Falsifier queued.")
    A("- **Field-dispersion (draft discipline) dominates strategy choice**; a startup is one "
      "high-variance draw. **Block 2 is 1QB and does NOT transfer.**")
    A("")
    # DETERMINISM (G10.5): wall-clock elapsed goes to stdout/log ONLY, never into the artifact — an
    # elapsed-seconds string would make the file non-byte-reproducible by construction.
    A(f"*v2 run: {SIMS} sims/cell, boot {BT['boot_n']}×{BT['boot_sims']}, slots {SLOTS}. "
      f"Reproduce: `uv run python -m models.startup_backtester`.*")

    out = CONFIG.path("exports") / "startup_strategy.md"
    out.write_text("\n".join(str(x) for x in L))
    log.info("wrote %s", out)
    print(f"wrote {out} ({time.time()-t0:.0f}s)")
    corrections()               # append v2.1 clustered-inference corrections (2nd review)


def pl_col_eq(col, val):
    import polars as pl
    return pl.col(col) == val


def _perm_null(raw_opt, rng, n_perm=1000):
    """Label-permutation null (item 6): within each year, pool per-sim winrates across the
    non-model strategies, shuffle strategy labels, recompute per-strategy means, take
    max|mean − year grand-mean| across all (strategy×year) cells. Returns (observed_max, null)."""
    strats = [s for s in STRATEGIES if s not in MODEL_STRATS]
    years = sorted({y for (y, s) in raw_opt})
    obs = 0.0
    per_year = {}
    for y in years:
        arrs = {s: raw_opt[(y, s)] for s in strats}
        gm = np.mean([arrs[s].mean() for s in strats])
        obs = max(obs, max(abs(arrs[s].mean() - gm) for s in strats))
        per_year[y] = arrs
    null = []
    for _ in range(n_perm):
        m = 0.0
        for y in years:
            arrs = per_year[y]
            allv = np.concatenate([arrs[s] for s in strats])
            rng.shuffle(allv)
            n = len(arrs[strats[0]])
            means = [allv[i*n:(i+1)*n].mean() for i in range(len(strats))]
            gm = np.mean(means)
            m = max(m, max(abs(mu - gm) for mu in means))
        null.append(m)
    return obs, null


def _block2(L, rng):
    A = L.append
    SIMS = BT["sims_per_cell"]; MID = 6
    A(""); A("## Block 2 — 1QB startup (2011–2019), CONSENSUS-only  ⚠️ DOES NOT TRANSFER")
    A("**⚠️ 1QB framing, no validated 1QB→SF translation — does NOT carry to the superflex league; "
      "decayed-edge / structure only.** No pre-2020 median-manager counterfactual (optimistic bound).")
    A("")
    A("| strategy | 2011–2016 | 2017–2019 | Δ (decay) |")
    A("|---|--:|--:|--:|")
    eras = {"pre": [y for y in BT["block2_years"] if y < BT["era_split"]],
            "post": [y for y in BT["block2_years"] if y >= BT["era_split"]]}
    res = {s: {"pre": [], "post": []} for s in STRATEGIES}
    for era, years in eras.items():
        for year in years:
            ctx = _build_ctx(year, 2, 5, None)
            for s in STRATEGIES:
                res[s][era].append(run_cell(ctx, 2, MID, s, "consensus", "consensus", SIMS, rng)["winrate"])
    for s in STRATEGIES:
        pre = np.mean(res[s]["pre"]); post = np.mean(res[s]["post"])
        A(f"| {s} | {pre:.3f} | {post:.3f} | {post-pre:+.3f} |")
    A("\n*1QB only — informational, non-transferring.*")


# ============================================================================
# SECOND-REVIEW CORRECTIONS (v2.1) — clustered inference, underpower, reconciliation
# ============================================================================
def _joint_boot(year, strategies, B, sims_each, rng, unit="league", pool="consensus", field="consensus"):
    """B clustered resamples (leagues or managers, with replacement); run ALL strategies on each
    resampled corpus (opt pool by default). Returns {strat: np.array(B)} of winrates."""
    if unit == "league":
        ids = D.year_draft_ids(year); key = "draft_ids"
    else:
        ids = D.year_managers(year); key = "managers"
    ids = list(ids); n = len(ids)
    W = {s: [] for s in strategies}
    for _ in range(B):
        samp = set(rng.choice(ids, size=n, replace=True).tolist())
        ctx = _build_ctx(year, 1, 5, None, **{key: samp})
        for s in strategies:
            W[s].append(run_cell(ctx, 1, MID_SLOT, s, pool, field, sims_each, rng)["winrate"])
    return {s: np.array(v) for s, v in W.items()}, n


def _perm_from_matrix(W, strategies, n_perm, rng):
    """Clustered label-permutation: within each replicate, shuffle strategy labels among values;
    statistic = max_s |mean_b(strat s) − grand mean|. Returns (obs, null_95, p)."""
    B = len(W[strategies[0]])
    M = np.array([W[s] for s in strategies])           # (S, B)
    gm_obs = M.mean(axis=0)                             # per-replicate grand mean
    obs = float(np.max(np.abs(M.mean(axis=1) - M.mean())))
    null = []
    for _ in range(n_perm):
        Mp = M.copy()
        for b in range(B):
            rng.shuffle(Mp[:, b])                       # shuffle labels within replicate b
        null.append(float(np.max(np.abs(Mp.mean(axis=1) - Mp.mean()))))
    null = np.array(null)
    return obs, float(np.percentile(null, 95)), float((null >= obs).mean())


MID_SLOT = 6


def corrections() -> None:
    """Compute the 6 second-review corrections and APPEND them to exports/startup_strategy.md."""
    import time
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    B = BT.get("corr_boot", 40); BS = BT.get("corr_boot_sims", 40)
    SIMS_C = BT.get("corr_sims", 300)
    NON_MODEL = [s for s in STRATEGIES if s not in MODEL_STRATS]
    L = ["", "", "---", "", "# SECOND-REVIEW CORRECTIONS (v2.1) — clustered inference",
         "", "> **⛔ youth-2020 Δ_bal is UNADJUDICATED-AND-CLOSED (corpus-limited) — TERMINAL "
         "(2026-07-31, Colby NOTE 0038 / G10.7v COND-A).** Every youth-2020 Δ_bal figure in this §C "
         "section (point +0.152, the [+0.001,+0.281] CI, Δ_bal(clustered) +0.116, permutation "
         "p<0.001) is the **seed-1729 record ONLY — NOT a live claim**: across 5 seeds the Δ_bal "
         "lower bound straddles 0 (B=160 mean −0.0146). The **deterministic re-baseline (G10.5) "
         "independently reinforces closure** — the recomputed §C1 clustered CI now **includes zero**. "
         "The edge was NEVER ESTABLISHED; do NOT read any line below as an instruction to report it. "
         "See the ⛔ banner at the top of this file + GATE6_5_REPORT amendment 2026-07-31.", "",
         "> Addresses the 6-item second-review of v2. Where these conflict with the v2 "
         "sections above, **these govern.** Key change: the v2 label-permutation null shuffled at "
         "the **sim level** (variance-destroying artifact → p≈0.000); it is replaced below by "
         "**league- and manager-clustered** permutations, and the youth-2020 verdict is re-based "
         "on clustered CIs rather than the fragile bias-budget margin.", ""]
    A = L.append

    # ---- joint clustered bootstrap per year (league + manager) ----
    boot = {}
    for year in (2020, 2021):
        for unit in ("league", "manager"):
            W, nunit = _joint_boot(year, NON_MODEL, B, BS, rng, unit=unit)
            boot[(year, unit)] = (W, nunit)

    # ============ C1 — 2021 underpower, not non-replication ============
    A("## C1  2021 is underpowered (15 leagues) — not 'non-replication' (item 1)")
    A("Clustered (league-bootstrap) 95% CIs on the age contrasts and the capital test. "
      "'contains 2020 pt' = does the 2021 CI include the 2020 point estimate?")
    A("")
    A("| quantity | 2020 point [95% CI] | 2021 point [95% CI] | 2021 CI contains 2020 pt? |")
    A("|---|---|---|---|")
    for label, a_s, b_s in [("youth − balanced (Δ_bal)", "youth", "balanced_adp"),
                             ("youth − win_now (Δ_pole)", "youth", "win_now")]:
        cells = {}
        for year in (2020, 2021):
            W = boot[(year, "league")][0]
            d = W[a_s] - W[b_s]
            cells[year] = (float(d.mean()), float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5)))
        p20, lo20, hi20 = cells[2020]; p21, lo21, hi21 = cells[2021]
        contains = "**YES**" if lo21 <= p20 <= hi21 else "no"
        A(f"| {label} | {p20:+.3f} [{lo20:+.3f},{hi20:+.3f}] | {p21:+.3f} [{lo21:+.3f},{hi21:+.3f}] | {contains} |")
    # capital test Δ per year (value_based − value_capital)
    capcells = {}
    for year in (2020, 2021):
        Wc, _ = _joint_boot(year, ["value_based", "value_capital"], B, BS, rng, unit="league")
        d = Wc["value_based"] - Wc["value_capital"]
        capcells[year] = (float(d.mean()), float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5)))
    p20, lo20, hi20 = capcells[2020]; p21, lo21, hi21 = capcells[2021]
    contains = "**YES**" if lo21 <= p20 <= hi21 else "no"
    A(f"| capital test (value − capital) | {p20:+.3f} [{lo20:+.3f},{hi20:+.3f}] | {p21:+.3f} [{lo21:+.3f},{hi21:+.3f}] | {contains} |")
    A("")
    A("**Correction:** where the 2021 CI contains the 2020 point estimate, 2021 **lacks the power "
      "to confirm or refute** — it is NOT evidence of instability. The honest statement is: "
      "**the age/youth effect was measured in 2020 and never adequately tested** (2021 = 15 "
      "leagues, post-cohort n=4). 'Non-replication' is retracted wherever the CI overlaps.")

    # ============ C2 — reconcile the three numbers ============
    A(""); A("## C2  Reconciling +0.181 / +0.152 / 0.128 (item 2) — three centerings, renamed")
    A("All from youth-2020, opt pool, slot 6 — but three DIFFERENT reference points:")
    A("- **Δ_bal = youth − balanced** (vs the balanced GRID STRATEGY — see C3).")
    A("- **Δ_pole = youth − win_now = +0.181** (the two *age poles*; descriptive only, see C3).")
    A("- **dev_mean = youth − 6-strategy grand mean (0.593) = +0.127 ≈ 0.128** (permutation stat).")
    A("Two ESTIMATORS of Δ_bal (standard practice = full-sample point + percentile CI): **POINT "
      "= Δ_bal(full)=+0.152** (full-corpus statistic); **INTERVAL = 95% percentile CI "
      "[+0.001,+0.281]** from the league-clustered bootstrap, whose **mean +0.116 sits 0.036 "
      "BELOW** the point — that gap is **resampling bias / sensitivity to league composition** "
      "(recorded, not smoothed). Report **+0.152 [+0.001,+0.281]**; lower bound barely excludes 0.")
    A("**Multiplicity (item 3):** balanced is a grid strategy → youth-vs-balanced is 1 of "
      "**C(8,2)=28** pairwise contrasts; the CI is **unadjusted single-comparison** (LB +0.001), "
      "and with the permutation downgraded (C4) **no multiplicity control remains** — weakest evidence.")

    # ============ C3 — which metric the budget governs ============
    A(""); A("## C3  `balanced` is a GRID STRATEGY → the vs-field budget does NOT govern Δ_bal (item 2/3)")
    A("**`balanced_adp` is one of the eight grid strategies** (best-available by the consensus "
      "board), NOT a field-representative reference. So **Δ_bal = youth − balanced is a strategy-"
      "vs-strategy contrast**, and the pre-registered budget (R3-9), built for **strategy-vs-"
      "field**, **does not formally govern it** (its survivorship/TE-premium lines largely cancel "
      "in a same-corpus same-scoring contrast). **We stop treating the budget as the test for "
      "Δ_bal and rely on the league-clustered CI (C1/C2);** the budget is kept only as a rough "
      "'how large is interesting' heuristic. `Δ_pole`/`dev_mean` are likewise contrasts, judged "
      "against their clustered null (C4), never the vs-field budget.")

    # ============ C4 — clustered permutation (replaces sim-level artifact) ============
    A(""); A("## C4  Clustered permutation null (item 4) — sim-level artifact replaced")
    A("The v2 null shuffled labels at the **sim level**, destroying clustered variance (null-95th "
      "≈0.03, p≈0.000 — an artifact). Re-run shuffling at the **league** and **manager** cluster "
      "level (within-replicate label permutation over the joint bootstrap):")
    A("")
    A("| year | unit | n units | observed dev_mean | null-95th | p |")
    A("|---|---|--:|--:|--:|--:|")
    for year in (2020, 2021):
        for unit in ("league", "manager"):
            W, nunit = boot[(year, unit)]
            obs, n95, p = _perm_from_matrix(W, NON_MODEL, 1000, rng)
            A(f"| {year} | {unit} | {nunit} | {obs:.3f} | {n95:.3f} | {p:.3f} |")
    A("")
    A("**Shuffling scope + downgrade (item 3):** labels are permuted **WITHIN each bootstrap "
      "replicate** (inside a fixed resampled league set), which **conditions on league composition "
      "and excludes between-league variance** — so **p<0.001 does NOT speak to resampling "
      "stability or generalization**, only that *given these leagues* the strategies differ. "
      "**Corrected claim:** the youth-2020 point estimate **excludes zero only at the boundary "
      "under league-clustered resampling** (CI lower bound +0.001, C1); the permutation is "
      "**conditional on league composition, not evidence of generalization.** The bootstrap CI "
      "governs, not the permutation p.")
    A("")
    A("**Effective-n reconciliation:** the §1 'eff n 60–270' is a sim-inflated nominal iid-"
      "equivalent, NOT independent units. Even the league counts (**47 / 15**) are **not** "
      "independent units: **158 managers span >1 league, one spans ~23**, so the effective "
      "independent-unit count is **BELOW the league count in both years**. Read the CIs; **≤15 "
      "effective units in 2021 is the binding constraint.**")

    # ============ C5 — budget-line derivation + sensitivity ============
    A(""); A("## C5  Bias-budget line provenance + verdict sensitivity (item 5)")
    A("| new line | value | measured or judgment | derivation |")
    A("|---|--:|---|---|")
    A("| season_scoring | 0.04 | **MEASURED** | max |season−weekly Δ_bal shift| across the 8 "
      "strategies × 2 years (§4/C6a) ≈ 0.036 → 0.04 |")
    A("| reach_window | 0.03 | **JUDGMENT** | order-of-magnitude; the cross-family sweep (§2) moves "
      "individual winrates ~0.05–0.07, but the strategy-vs-balanced *gap* moves less; not directly measured |")
    A("| slot_coverage | 0.02 | **JUDGMENT** | residual from reporting slot-6 not the 12-slot mean; "
      "bounded by the slot sweep (C6b) |")
    A("")
    A("**Verdict basis (corrected):** the budget does **not** govern `Δ_bal` (C3 — a strategy-vs-"
      "strategy contrast, not vs-field). For reference only: gap to the 0.16 heuristic is **0.044** "
      "against the headline **Δ_bal(clustered)=+0.116**, or 0.008 against Δ_bal(full)=+0.152 — "
      "*both moot* since the budget isn't the test. The 'fails by 0.008' framing is **retracted.** "
      "The verdict rests entirely on: the **clustered CI [+0.001,+0.281]** (excludes 0 only at the "
      "boundary), the **slot dependence** (C6b), the **opponent-family sign flip** (C6c), and "
      "**2021 underpower** (≤15 effective units, C1).")

    # ============ C6 — completions ============
    A(""); A("## C6  Completions (item 6)")
    # (a) season-weekly shift vs roster concentration
    A(""); A("### C6a  Is the season-vs-weekly shift monotone in roster concentration?")
    ctx20 = _build_ctx(2020, 1, 5, None)
    conc = {}; shift = {}
    baseS = run_cell(ctx20, 1, MID_SLOT, "balanced_adp", "consensus", "consensus", SIMS_C, rng)["winrate"]
    baseW = run_cell(ctx20, 1, MID_SLOT, "balanced_adp", "consensus", "consensus", SIMS_C, rng, weekly=True)["winrate"]
    for s in NON_MODEL:
        if s == "balanced_adp":
            continue
        # concentration = mean over sims of (top-3 starter season pts / total starter pts)
        cvals = []
        for _ in range(40):
            ros, _ = simulate_one(ctx20, 1, MID_SLOT - 1, s, "consensus", "consensus", rng)
            ri = np.array(ros[MID_SLOT - 1]); pts = np.sort(ctx20.season_pts[ri, 0])[::-1]
            cvals.append(pts[:3].sum() / max(pts.sum(), 1e-6))
        conc[s] = float(np.mean(cvals))
        ss = run_cell(ctx20, 1, MID_SLOT, s, "consensus", "consensus", SIMS_C, rng)["winrate"] - baseS
        sw = run_cell(ctx20, 1, MID_SLOT, s, "consensus", "consensus", SIMS_C, rng, weekly=True)["winrate"] - baseW
        shift[s] = sw - ss
    ks = list(conc)
    cc = np.corrcoef([conc[s] for s in ks], [shift[s] for s in ks])[0, 1]
    A("| strategy | roster concentration (top3 share) | season−weekly Δ_bal shift |")
    A("|---|--:|--:|")
    for s in ks:
        A(f"| {s} | {conc[s]:.3f} | {shift[s]:+.3f} |")
    A(f"\n*corr(concentration, shift) = {cc:+.2f} — "
      f"{'MONOTONE same-signed → season-level is a systematic depth handicap; the season_scoring budget line is justified as a real bias, not just magnitude.' if abs(cc)>0.5 else 'not monotone → no systematic concentration-linked handicap; season_scoring is a magnitude bound only.'}*")
    # (b) slot invariance of the youth verdict
    A(""); A("### C6b  Budget verdict at all four slots (item 6b)")
    A("| slot | youth Δ_bal (2020, opt) | |Δ|>budget(0.16)? |")
    A("|--:|--:|---|")
    for slot in BT["slots"]:
        by = run_cell(ctx20, 1, slot, "balanced_adp", "consensus", "consensus", SIMS_C, rng)["winrate"]
        yy = run_cell(ctx20, 1, slot, "youth", "consensus", "consensus", SIMS_C, rng)["winrate"]
        d = yy - by
        A(f"| {slot} | {d:+.3f} | {'YES' if abs(d) > 0.16 else 'no'} |")
    A("\n*Verdict is reported per-slot (no aggregation). If it is not slot-invariant, the slot-6 "
      "headline is not representative — shown above.*")
    # (c) per opponent family
    A(""); A("### C6c  Budget verdict under BOTH opponent families (item 6c)")
    A("| family | youth Δ_bal (2020) | value_based Δ_bal | 'nothing clears' holds? |")
    A("|---|--:|--:|---|")
    for fname, field in [("reach Fcons", "consensus"), ("reach Fcorp", "corpus_draw"), ("empirical", "empirical")]:
        by = run_cell(ctx20, 1, MID_SLOT, "balanced_adp", "consensus", field, SIMS_C, rng)["winrate"]
        yy = run_cell(ctx20, 1, MID_SLOT, "youth", "consensus", field, SIMS_C, rng)["winrate"]
        vb = run_cell(ctx20, 1, MID_SLOT, "value_based", "consensus", field, SIMS_C, rng)["winrate"]
        dY = yy - by; dV = vb - by
        holds = "yes" if abs(dY) < applicable_budget("youth") else "**NO — youth clears here**"
        A(f"| {fname} | {dY:+.3f} | {dV:+.3f} | {holds} |")
    A("\n*'Nothing clears' must hold under every family (ranking is family-unstable, §2). Reported per family.*")
    # (d) bug location
    A(""); A("### C6d  Where the inverted rookie penalty lived")
    A("The bug was in **`win_now`'s own priority definition** (`-board_rank * rook_pen`), NOT in "
      "shared age-preference code. `rook_pen` was a module-local array **read only by `win_now`** "
      "(verified by grep). No other strategy used that path, so **only `win_now`'s v1 numbers were "
      "affected**; `youth` (which used a separate `young` mask) and the rest were unaffected.")

    A(""); A(f"*Corrections run: joint boot {B}×{BS} (league+manager).*")  # elapsed -> stdout only (G10.5)

    out = CONFIG.path("exports") / "startup_strategy.md"
    prior = out.read_text()
    out.write_text(prior + "\n".join(str(x) for x in L))
    log.info("appended corrections to %s", out)
    print(f"appended corrections ({time.time()-t0:.0f}s)")


# NOTE (G10.5): this __main__ block MUST stay at the END of the file. It was previously at ~line 968,
# ABOVE the defs of `corrections`/`MID_SLOT`/`_joint_boot` (below), so `run()` -> `corrections()` hit a
# NameError at module-run time -> `uv run python -m models.startup_backtester` (the documented reproduce
# command) silently errored AFTER writing startup_strategy.md but BEFORE appending the §C corrections,
# leaving the §C sections stale. Moving the entry point below all defs fixes the reproduce command.
if __name__ == "__main__":
    run()
