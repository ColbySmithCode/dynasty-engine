# ADP Calibration — Phase 5.3

Two asset classes, priced separately and labeled throughout.

## ASSET CLASS 1 — STARTUP picks (dynasty-startup ADP → player caliber)
Realized value by startup ADP round × position (dynasty K ADP, AUG15, 2019+, era-adjusted via VORP). fwd3_vorp = summed VORP over the pick year + next 2.

| startup_rd | pos | n | top-12 hit | mean fwd3 VORP | median |
|--:|---|--:|--:|--:|--:|
| 1 | RB | 71 | 54% | +326 | +339 |
| 1 | WR | 45 | 58% | +304 | +277 |
| 2 | QB | 16 | 81% | +330 | +328 |
| 2 | RB | 47 | 36% | +207 | +182 |
| 2 | WR | 51 | 33% | +261 | +252 |
| 3 | QB | 15 | 47% | +284 | +279 |
| 3 | RB | 33 | 21% | +156 | +143 |
| 3 | WR | 47 | 26% | +184 | +155 |
| 4 | QB | 14 | 57% | +231 | +206 |
| 4 | RB | 40 | 10% | +96 | +76 |
| 4 | TE | 12 | 67% | +125 | +129 |
| 4 | WR | 50 | 28% | +158 | +139 |
| 5 | QB | 13 | 46% | +164 | +128 |
| 5 | RB | 23 | 22% | +88 | +49 |
| 5 | TE | 16 | 31% | +54 | +45 |
| 5 | WR | 40 | 10% | +99 | +83 |
| 6 | QB | 18 | 61% | +201 | +138 |
| 6 | RB | 28 | 14% | +54 | +23 |
| 6 | TE | 12 | 33% | -9 | +7 |
| 6 | WR | 39 | 10% | +104 | +89 |
| 7 | QB | 18 | 17% | +135 | +120 |
| 7 | RB | 26 | 15% | +60 | +23 |
| 7 | TE | 18 | 22% | -19 | -19 |
| 7 | WR | 42 | 7% | +88 | +71 |
| 8 | QB | 18 | 44% | +164 | +122 |
| 8 | RB | 32 | 0% | -14 | -32 |
| 8 | TE | 12 | 58% | +19 | +26 |
| 8 | WR | 37 | 3% | +18 | -23 |
| 9 | QB | 23 | 22% | +98 | +92 |
| 9 | RB | 36 | 3% | +6 | -22 |
| 9 | TE | 22 | 50% | +21 | +13 |
| 9 | WR | 40 | 2% | +26 | +4 |
| 10 | QB | 34 | 32% | +106 | +54 |
| 10 | RB | 45 | 0% | -5 | -22 |
| 10 | TE | 23 | 26% | -38 | -69 |
| 10 | WR | 43 | 0% | -10 | -29 |
| 11 | QB | 49 | 12% | +67 | +40 |
| 11 | RB | 47 | 2% | -18 | -33 |
| 11 | TE | 34 | 9% | -77 | -62 |
| 11 | WR | 66 | 0% | -18 | -52 |
| 12 | QB | 23 | 9% | +32 | +1 |
| 12 | RB | 84 | 0% | -21 | -30 |
| 12 | TE | 51 | 16% | -64 | -61 |
| 12 | WR | 91 | 1% | -43 | -55 |
| 13 | RB | 51 | 2% | -34 | -35 |
| 13 | TE | 28 | 14% | -66 | -61 |
| 13 | WR | 61 | 0% | -42 | -51 |
| 14 | RB | 13 | 0% | -51 | -37 |
| 14 | TE | 10 | 20% | -55 | -66 |
| 14 | WR | 28 | 4% | -54 | -49 |

## ASSET CLASS 2 — ROOKIE picks: fantasy slot → NFL draft CAPITAL (Decision 1)
MFL rookie ADP (1QB, 2020+) → the player actually taken → their NFL draft round. This mapping is LOAD-BEARING; its spread is the uncertainty that propagates into every rookie-pick valuation. **1QB-calibrated — see SF adjustment below.**

| rookie_rd | n | mean NFL rd | P25–P75 NFL rd | % R1 | % R1-2 | % UDFA/late |
|--:|--:|--:|--:|--:|--:|--:|
| 1 | 81 | 1.3 | 1–2 | 72% | 95% | 0% |
| 2 | 88 | 2.1 | 1–3 | 33% | 69% | 0% |
| 3 | 102 | 2.8 | 2–3 | 20% | 39% | 4% |
| 4 | 143 | 3.6 | 2–5 | 16% | 29% | 17% |

**Format (superflex) adjustment.** MFL rookie ADP has no SF dimension. In SF, rookie QBs are drafted materially earlier, so 1QB slot→capital understates QB value in QB-heavy classes. The trade engine applies the Decision-3 SF translation to the QB component of any rookie-pick class and WIDENS the interval for QB-heavy classes; the mapping uncertainty above (P25–P75 spanning ~2 NFL rounds per rookie round) is carried as a distribution, not a point, in pick valuation.

## Market efficiency — realized fwd3 VORP regressed on ln(ADP)
Baseline: fwd3_VORP ≈ 585 -122·ln(ADP). Positive residual = ADP UNDERvalued the position (market inefficiency, if it persists).

| position | n | mean residual | interpretation |
|---|--:|--:|---|
| QB | 256 | +87.0 | market UNDERvalues |
| WR | 683 | -1.0 | ≈efficient |
| RB | 576 | -18.6 | market OVERvalues |
| TE | 259 | -42.7 | market OVERvalues |

## ADP velocity study (dynasty K, 2019+; Decision 2 scope)
Movement DRAFT→AUG15; does the late-summer riser/faller signal predict realized value?

| mover | n | mean fwd3 VORP | median |
|---|--:|--:|--:|
| stable | 1158 | +106 | +67 |
| riser | 140 | +7 | -13 |
| faller | 488 | -4 | -29 |

corr(ADP velocity, fwd3 VORP) = +0.149 (risers outperform — actionable in August).