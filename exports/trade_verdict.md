# Trade Engine — 1.11  vs  (startup 3rd + startup 4th + 2027 rookie 2nd)

**STARTUP-draft trade, first-year league, NO roster (Decision 9):** consolidation is capital allocation across 20+ empty slots, not roster scarcity — no in-season penalty. The 2027 rookie 2nd has unknown slot + no finish history → near-uniform slot, wide variance, extra unknowability discount (0.92×). 10000 MC draws; Phase-5 posteriors carried.

## ⚠️ Highest-leverage assumption: pick-outcome POOL (reported under BOTH)
CONSENSUS = you draft the best-available at every slot (optimal). CORPUS-AVG = you draft like the median manager (busts included). This choice flipped the verdict −74↔+6; the truth is in between, so both are shown.

### CONSENSUS (optimal drafter)

| δ | E[1.11] | E[package] | E[Δ]=pkg−1.11 | P(package wins) |
|--:|--:|--:|--:|--:|
| 0.70 | +273 | +283 | +11 | 50% |
| 0.82 | +314 | +325 | +11 | 50% |
| 0.90 | +343 | +357 | +13 | 50% |

→ CONSENSUS (optimal drafter): **package WINS** across δ.

### CORPUS-AVG (median manager)

| δ | E[1.11] | E[package] | E[Δ]=pkg−1.11 | P(package wins) |
|--:|--:|--:|--:|--:|
| 0.70 | +129 | +48 | -82 | 36% |
| 0.82 | +149 | +69 | -80 | 38% |
| 0.90 | +165 | +89 | -75 | 40% |

→ CORPUS-AVG (median manager): **1.11 WINS** across δ.

**Spread between pools is the real uncertainty band on this trade** — if you draft well the package is even/ahead; if you draft like the field, keep the 1.11. Detailed sections below use the CONSENSUS pool.


## Value by ownership year (δ=0.82, mean VORP, undiscounted)

| asset | yr1 (2026) | yr2 (2027) | yr3 (2028) | yr4 (2029) |
|---|--:|--:|--:|--:|
| 1.11 | +133 | +108 | +81 | +69 |
| package | +150 | +100 | +83 | +69 |

1.11 is front-loaded (produces from 2026); the package is back-loaded (the rookie 2nd contributes nothing until 2027+). Same total ≠ same trade.

## P(I win) and credible spread (δ=0.82)

- E[Δ] (package − 1.11) = +11 VORP; 90% CI [-431, +491]
- **P(package wins) = 50%** — the wide band (rookie survival [0.30,0.70], slot uncertainty) means this is far from a lock either way.

## QB-depth interaction (superflex)

5.3 found QB value holds to startup round ~8 (+160 VORP) in your SF scoring. So trading DOWN from 1.11 forfeits less than in 1QB: the package's 3rd/4th picks still reach startable QBs.
corpus QB draft rate at those slots: rd3 13%, rd4 12%
→ the package retains real QB optionality; its downside is cushioned by SF QB depth (this is why the package is more competitive here than a 1QB calculator would say).

## Fairness solver — minimal add to the lighter side to reach E[Δ] within ±5%

Current E[Δ] = +11 (1.11 lighter); ±5% band = ±16 VORP. Top-3 balancing adds to the lighter side:

| rank | add asset | E[value] | residual |Δ| |
|--:|---|--:|--:|
| 1 | rookie 3rd | -29 | 39 |
| 2 | rookie 1st | +90 | 79 |
| 3 | startup 5th | +107 | 96 |

## Top-2 assumptions the verdict is most sensitive to

Base E[Δ] (pkg−1.11, δ=0.82) = +12 VORP.

- **1.11 exact slot value**: shifts E[Δ] by +50 VORP (FLIPS the verdict).
- **discount δ (0.70↔0.90)**: shifts E[Δ] by -3 VORP (does not flip it).