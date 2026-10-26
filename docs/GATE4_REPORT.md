# GATE 4 — Derived metrics

Tables: `fact_player_week_metrics` (194,181), `fact_player_season_metrics` (9,933),
`fact_replacement` (6,824 = season×week×position×profile). Dictionary:
`exports/metric_dictionary.md`. Rebuild: `uv run python -m transform.metrics`.

## Categories covered
- **Opportunity**: target_share, air_yards_share, WOPR, aDOT, RACR, rush_share,
  rz_targets/carries, opportunities, touches, snap_share.
- **Efficiency**: epa_per_target, epa_per_rush, rec/rush success.
- **Context**: team_proe (pass rate over expected), team pass rate / xpass.
- **Fantasy-native**: ppg, pts_per_snap, pts_per_opp, weekly positional rank,
  VORP, boom/bust rate, volatility (stdev/cv), consistency.
- **Replacement level**: weekly, per profile, per position (superflex-adjusted).

## GATE-1 constraints honored
- `snap_share` NULL for all pre-2013 player-weeks (14,357 nulls), **never zero-filled**
  (verified: 2012 = 0 non-null, 2013 = fully populated).
- `yprr` / `route_participation` NULL league-wide (no route data) — not zero-filled.
- `depth_charts` deliberately NOT consumed here; its 2025 source-break normalization
  is deferred to Phase 5 and flagged in the dictionary.

## Distributions (played QB/RB/WR/TE weeks)
| metric | min | p25 | median | p75 | p95 | max |
|---|--:|--:|--:|--:|--:|--:|
| target_share | 0 | 0 | 0.049 | 0.128 | 0.25 | 0.581 |
| wopr | −0.40 | 0 | 0.072 | 0.254 | 0.608 | 1.746 |
| adot | −46 | 2.0 | 6.33 | 11.2 | 20.0 | 56 |
| racr | −102 | 0.2 | 0.79 | 1.38 | 5.0 | 150 |
| rush_share | 0 | 0 | 0 | 0.071 | 0.545 | 1.0 |
| snap_share | 0 | 0.207 | 0.489 | 0.805 | 1.0 | 1.0 |
| epa_per_target | −11.96 | −0.39 | 0.126 | 0.662 | 1.674 | 7.97 |
| team_proe | −0.571 | −0.093 | −0.04 | 0.014 | 0.087 | 0.322 |
| vorp_ppr (weekly) | −18.8 | −7.4 | −3.6 | 2.9 | 14.6 | 49.9 |

Season (≥8 games):
| metric | p25 | median | p75 | p95 | max |
|---|--:|--:|--:|--:|--:|
| ppg_ppr | 2.72 | 6.56 | 11.57 | 18.06 | 29.45 |
| consistency | 0 | 0.197 | 0.417 | 0.597 | 0.82 |
| boom_rate | 0 | 0 | 0.10 | 0.313 | 0.833 |
| bust_rate | 0.286 | 0.625 | 0.875 | 1.0 | 1.0 |
| vorp_ppr_total | −71 | −26 | 39.6 | 138.9 | 331.8 |

Fat tails on adot/racr/epa are single-play, low-volume artifacts → **volume-gate in
Phase 5**. VORP centered negative is correct: most player-weeks are below replacement.

## Face validity
- 2023 WR by avg WOPR: Tyreek Hill 0.75 (256.7 season VORP, 0.53 boom), Davante Adams
  0.74, Keenan Allen 0.72, Garrett Wilson 0.68, A.J. Brown 0.67 — the real alphas.
- 2023 weekly replacement (ppr): QB 9.7 > TE 8.1 ≈ WR 8.0 > RB 7.2 — sane ordering.
- CeeDee Lamb 2023 snap_share 0.894 (full-time WR).
