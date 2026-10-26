# GATE 1 — Ingest report (Phases 1A, 1B, 1D, 1G)

Generated 2026-07-27. Current NFL season = 2026 (Sleeper `/state/nfl`, week 0,
pre-draft). Regenerate anytime with `uv run python -m ingest.report`.
Full per-cell ADP matrix: `exports/adp_sweep_cells.csv` (765 rows).

## 1A — nflverse backbone  ✅ complete
Seasons 2010–2025 dense; 2026 is offseason (no in-season data yet — expected).

| dataset | coverage | notes |
|---|---|---|
| pbp | 2010–2025, 46.9k–49.9k rows/season | ground truth; 2026=0 (offseason) |
| player_stats | 2010–2025, ~17k–19k/season | 2026 not yet published |
| rosters / rosters_weekly | 2010–2025 | weekly 35k–52k |
| depth_charts | 2010–2025 | ⚠️ 2025=554k, 2026=375k vs ~37k prior — source/granularity changed |
| snap_counts | **2013**–2025, ~238k–266k | ⚠️ 2012 returned 0 (effectively 2013+, not 2012+) |
| injuries | 2010–2025, ~45k–62k | |
| nextgen_{passing,receiving,rushing} | 2016–2025 | gated correctly |
| ftn_charting | 2022–2025 | gated correctly |
| seasonless | draft_picks 12,927 (1980+) · combine 8,968 · contracts 51,741 · ff_playerids 12,468 · players 25,035 · schedules 7,548 | |

Failures: only 2026 season-gated datasets (offseason). Non-fatal, per-season caught.

## 1B / 1G-a — MFL ADP sweep  ✅ 765/765 cells
Grid: seasons 2010–2026 × format {N,K,R} × ppr {-1,0,1} × fcount 12 × 5 periods.
Sample size = MFL `totalDrafts` per cell. **Confidence census (<500 = LOW):
OK 235 · LOW 155 · EMPTY 375.**

**Data-support (first season ≥500 drafts):** redraft 2011 · dynasty 2011 · **rookie 2020**.

Dynasty/keeper (K), ppr=-1, drafts per cell:

| season | DRAFT | JUNE | JULY | AUG1 | AUG15 |
|--:|--:|--:|--:|--:|--:|
| 2011–2018 | 0 | 0 | 0 | 0 | 2667→3646 (peak '14), dip ~1.5k mid-decade |
| **2019** | 4780 | 3519 | 3090 | 2759 | 1714 |
| 2020 | 715 | 709 | 688 | 662 | 642 |
| 2023 | 768 | 762 | 744 | 697 | 662 |
| 2025 | 723 | 718 | 694 | 641 | 599 |
| 2026 | 37 | 34 | 28 | 0 | 0 |

Rookie (R), ppr=-1, drafts per cell:

| season | DRAFT | JUNE | JULY | AUG1 | AUG15 |
|--:|--:|--:|--:|--:|--:|
| 2011–2019 | 0–10 | ~0 | 0 | 0 | 3–14 (UNUSABLE) |
| 2020 | 1990 | 695 | 442 | 280 | 192 |
| 2023 | 2338 | 999 | 632 | 372 | 227 |
| 2025 | 1984 | 890 | 607 | 383 | 254 |
| 2026 | 1446 | 447 | 162 | 0 | 0 |

Structural findings:
1. **Multi-snapshot velocity begins 2019** (K) / 2020 (R). 2011–2018 K/R exist only
   in the AUG15 bucket → single-snapshot only. Confirms Decision 2 scoping.
2. **Rookie ADP unusable pre-2020.** Confirms Decision 1 (build rookie hit rates
   from draft capital, calibrate on 2020/2021+).
3. Dynasty volume spikes in 2019 (4,780) then settles ~650–790 (2020+). Redraft
   robust throughout (peak 5,802 in 2023); 2025 redraft thin (1,046).

## 1D — DynastyProcess  ✅
values-players 646 · values-picks 85 · db_playerids 12,468 · db_fpecr **1,795,423**
rows (ECR history). Snapshot 2026-07-27; value/ECR columns incl. `value_1qb`/`value_2qb`.

## 1G-b — Scott Fish Bowl  ✅
536 Sleeper leagues (sfb12/13/14), **141,504 draft picks** (~6,432 team-drafts).
All type 0 (best-ball redraft) → draft-behavior signal, non-dynasty. MFL id lists
(189) stored, **not harvested** (1G-d).

## 1G-c — Sleeper snowball  ✅
**400 dynasty leagues** (type 2), seasons 2020–2026, **55,309 draft picks**,
26,902 traded picks, **70,159 transactions** (bounded 150-league sample, logged).

Settings distribution vs YOUR league (skew — biases downstream):
- superflex **384/400 (96%)** → matches; 1QB thin (16)
- full PPR **381/400 (95%)** → matches
- 12-team **351/400 (87%)** → matches
- **TE-premium 382/400 (95%) → MISMATCH** (yours has none): corpus over-values TEs.
- recency skew: leagues cluster 2022–2024 (Sleeper is young); pre-2020 absent.

## Deferred (documented, not silently dropped)
- MFL fcount sensitivity (8/10/14/16) — gate ran fcount=12 only; full grid → weekly job.
- MFL `TYPE=aav` auction values — not yet swept.
- PFR backfill (1E) — disabled by default; only for documented gaps.
- KTC / FantasyPros (1F) — registry present, disabled.
