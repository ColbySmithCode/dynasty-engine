# GATE 3 — Canonical schema + fantasy-point reconciliation

DuckDB warehouse at `data/warehouse.db`. DDL: `migrations/schema.sql`.
Rebuild: `uv run python -m transform.warehouse`. Reconcile: `uv run python -m transform.reconcile`.

## Row counts
| table | rows |
|---|--:|
| dim_player | 12,685 |
| dim_team | 36 |
| dim_season | 17 |
| dim_week | 341 |
| **fact_player_week** | 86,384 |
| fact_player_season | 9,579 |
| fact_adp | 114,760 |
| fact_injury | 71,297 |
| fact_dynasty_value | 542 |
| fact_league_roster | 151,620 |
| fact_league_draft_pick (SFB flow) | 141,504 |
| fact_league_traded_pick | 26,902 |

`fact_player_week` holds every player-week with offensive pbp involvement (2010–2025),
scored under 6 profiles: std, half_ppr, ppr, te_premium, superflex, **your_league**
(live from Sleeper: rec 1.0, pass_int −1, no TE bonus).

## Reconciliation vs nflverse fantasy_points / fantasy_points_ppr
- matched player-weeks: **80,078** | only in mine: 6,306 (nflverse scored 0) | only in nflverse: 212
- **exact (|Δ|≤0.02): 79,815 / 80,078 = 99.67%**
- Δ_std: mean −0.0023, std 0.129; |Δ|>0.5: 182 (0.23%); |Δ|>3: 26 (0.03%); |Δ|>6: 7 (0.009%)
- (Δ_ppr identical distribution — PPR is additive receptions on both sides.)

## Season vs player clustering  → **PLAYER-clustered**
- per-season disagreement rate: min 0.22%, max 0.60% (2024), **CV 0.32, span 2.8×** — flat,
  no season stands out → **no unhandled rule change**.
- disagreements concentrate in players: top-10 hold 25% of all |Δ|, top-50 hold 63%,
  top-100 hold 86%; only 206 players disagree at all across 16 seasons.
- **Cause = laterals / trick plays.** The worst offenders are Le'Veon Bell, Jahmyr Gibbs,
  Jameson Williams, Amon-Ra St. Brown, Kenyan Drake, Julian Edelman — Lions hook-and-lateral
  plays and passing-back TDs. nflverse credits lateral yards/TDs to the play-ender; our
  aggregation credits the primary `rusher/receiver_player_id`. Player-specific, not systemic.
- The one QB in the tail (Josh Allen 2024 wk13, Δ −6.7) is a rushing/lateral edge, not a
  passing-rule gap (his passing_tds/yards match exactly).

**Verdict:** the pbp fantasy engine matches nflverse to 99.67% exactly; residual deltas are
player-clustered lateral/trick-play attribution (bounded, understood), NOT a season-level
rule change. Return TDs are intentionally included in our scoring (nflverse's offense-only
`fantasy_points` omits them) — a deliberate difference, not an error.

## Face-validity spot checks
- Top-10 PPR WRs 2019 (from our pbp): Michael Thomas 388.6 (1), Hopkins, Godwin, Julio,
  Lockett, Adams, Kupp, Edelman, Allen, Robinson — matches the real 2019 finish.
- your_league vs ppr QBs 2023: Josh Allen 474.8 vs 456.8 (−1 INT lifts QBs, as expected).

## Known deferrals
- Laterals not yet folded into the primary carrier (bounded to ~206 players, <0.03% of
  weeks at >3 pts) — candidate refinement, tracked.
- fact_league transaction bodies were counted (Phase 1G) but not persisted; not loaded here.
