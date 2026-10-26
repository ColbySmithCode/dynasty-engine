# Metric Dictionary (Phase 4)

Every metric is computed from the DuckDB warehouse (pbp-derived). Tables:
`fact_player_week_metrics`, `fact_player_season_metrics`, `fact_replacement`.
Rebuild: `uv run python -m transform.metrics`.

## Coverage constraints (read first)
- **snap_share / route metrics NULL before 2013** — `snap_counts` starts 2013.
  Never zero-filled (a 2011 snap share is unknown, not 0).
- **yprr, route_participation = NULL everywhere** — league-wide route data isn't
  available (FTN is 2022+ and doesn't expose routes cleanly here). Left NULL, not 0.
- **depth_charts is NOT consumed in Phase 4.** Its ~15× row jump in 2025–26 (nflverse
  source change) must be normalized in Phase 5 before any model uses it across the
  boundary; otherwise it manufactures a structural shift in the newest seasons.
- Per-week rate metrics (adot, racr, epa_per_*) have **fat tails at low volume**
  (e.g., racr on 1 target). Volume-gate before modeling (Phase 5).

## Opportunity (per player-week; season = mean/sum)
| metric | formula | notes |
|---|---|---|
| targets | pass plays where player is `receiver_player_id` | |
| target_share | targets / team_pass_att | 0–0.58 observed |
| air_yards | Σ air_yards on targets | can be negative (behind LOS) |
| air_yards_share | air_yards / team_air_yards | |
| **wopr** | 1.5·target_share + 0.7·air_yards_share | primary opportunity metric |
| adot | air_yards / targets | avg depth of target |
| racr | rec_yd / air_yards | efficiency-vs-depth; fat-tailed at low AY |
| carries | rush attempts as `rusher_player_id` | |
| rush_share | carries / team_rush_att | |
| rz_targets / rz_carries | opportunities inside opponent 20 | `yardline_100 ≤ 20` |
| opportunities | targets + carries | volume proxy |
| touches | receptions + carries | |
| snap_share | offense_snaps / team offensive plays (max OL snaps) | **NULL < 2013** |

## Efficiency (per player-week)
| metric | formula | notes |
|---|---|---|
| epa_per_target | Σ EPA on targets / targets | pbp `epa` |
| epa_per_rush | Σ EPA on carries / carries | |
| rec_success | mean pbp `success` on targets | |
| rush_success | mean pbp `success` on carries | |
| (yoe / cpoe / RYOE) | available via NGS 2016+ | wired in Phase 5 |

## Context (team-week)
| metric | formula | notes |
|---|---|---|
| team_proe | team_pass_rate − mean(xpass) | pass rate over expectation |
| team_pass_rate, team_xpass | from pbp | pace/OL/QB-quality proxies extend in Phase 5 |

## Fantasy-native
| metric | formula | notes |
|---|---|---|
| ppg_ppr | mean fp_ppr over **played** weeks | played = snaps>0 or production>0 |
| pts_per_snap | fp_ppr / offense_snaps | NULL < 2013 |
| pts_per_opp | fp_ppr / opportunities | |
| wk_pos_rank_{profile} | weekly rank within season·week·position | per scoring profile |
| **vorp_ppr** | fp_ppr − weekly replacement_points(pos) | per week; season = Σ |
| boom_rate | share of played weeks ranked ≤5 at position | |
| bust_rate | share of played weeks ranked >36 at position | |
| stdev_ppr / cv_ppr | week-to-week volatility | |
| consistency | 1 − clip(cv_ppr, 0, 1) | higher = steadier |

## Replacement level (`fact_replacement`)
Computed **weekly, per scoring profile, per position** — the Nth-best score that
week where N = league_size × (dedicated starters + flex/superflex allocation).
For the target **superflex / 12-team** league (config-driven):
`QB 24 · RB 34 · WR 47 · TE 16` (superflex sends its slot to QB; flex split
RB .40 / WR .45 / TE .15). Recomputed per season — a 2011 WR3 and a 2024 WR3 are
not the same, so replacement is never a season-long constant.

## Distributions — see `docs/GATE4_REPORT.md` for the full percentile tables.
Spot check (2023 WR by avg WOPR): Tyreek Hill 0.75, Davante Adams 0.74, Keenan
Allen 0.72, Garrett Wilson 0.68, A.J. Brown 0.67 — the actual target alphas.
