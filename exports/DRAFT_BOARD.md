# DRAFT BOARD — 12-team Superflex · Full-PPR · No TE-premium

*Live-draft reference, from engine artifacts (adp_calibration.md, aging_curves.md, hit_rates_by_slot.md, trade_verdict.md). **Structural/base-rate facts only — the engine's forward point-projections FAILS-BAR (lose to last-year-PPG in backtest), so nothing here is a per-player forecast; use it as board shape, not gospel.***

> **PROVENANCE (read once):** §1 (ADP value) and §3 (aging) are from **committed HEAD** artifacts — those files were never regenerated, so they are HEAD-accurate. **§4 (rookie/pick hit rates) is from POST-G10.4-FIX REGENERATION, not committed HEAD.** The committed HEAD `hit_rates_by_slot.md` is **stale** (predates the G10.4 warehouse/determinism fix); the §4 numbers here are the more-correct post-fix values, which regenerate deterministically. Every §4 shift vs HEAD sits **inside the Wilson CIs and changes no draft call** (e.g. RB·R1 0.79 vs stale-HEAD 0.83 — both "≈ likely relevant"). §2 (replacement ranks) and §5 (trade) are pinned decisions / trade_verdict.md.

---

## 1 · ROUND-BY-ROUND — what to target at each startup round
*Realized top-12 hit% and mean 3-yr forward VORP, by dynasty-startup round × position. **Descriptive (2019+ corpus, era-adjusted), not predictive.** Per-cell n is 10–90 — read the shape, not the decimals.*

| Rd | TARGET (best cells) | Avoid / thin |
|--:|---|---|
| **1** | **RB 54% +326 · WR 58% +304** — anchor with a stud RB/WR | — |
| **2** | **QB 81% +330** ← highest-value single cell on the board · WR 33% +261 · RB 36% +207 | — |
| **3** | **QB 47% +284** · WR 26% +184 · RB 21% +156 | RB starting to thin |
| **4** | **QB 57% +231** · WR 28% +158 · *TE 67% +125 (n=12, noisy)* | **RB 10% +96 — cliff starts** |
| **5** | **QB 46% +164** · RB 22% +88 · WR 10% +99 | RB/WR both thin |
| **6** | **QB 61% +201** · WR 10% +104 | RB 14% +54 · TE −9 |
| **7** | QB 17% +135 · RB 15% +60 | WR 7% · TE −19 |
| **8** | **QB 44% +164 — QB still startable this deep** · *TE 58% +19 (n=12)* | **RB 0% −14 · WR 3% +18 — dead** |
| **9–12** | **QB only** stays positive (rd10 32% +106, rd11 12% +67, rd12 9% +32) | RB/WR/TE all ≤0 VORP |

**Three rules of thumb:** ① Rd-2 QB is the single best value — take a QB there if the board falls. ② **RB cliff hits at rd 4–5** and RB is worthless by rd 8 — get your RBs early or punt them. ③ **QB value holds to ~rd 8** (+164) — SF lets you wait on your QB2/QB3 far longer than RB/WR.

---

## 2 · SF POSITIONAL STRUCTURE — one line each
- **Replacement ranks (SF-adjusted):** **QB21 · RB34 · WR48 · TE16.** ~21 QBs start in a 12-team SF → QB is genuinely scarce; elite-QB VORP is large. *(Structural fact of the format.)*
- **Market residuals (realized fwd3 VORP vs ADP):** **QB +87 (UNDERvalued) · WR −1 (efficient) · RB −18.6 (OVERvalued) · TE −42.7 (OVERvalued).** *Descriptive "if it persists," not a forecast.*
- **Era-sliced read (2022+):** QB edge **+12 and shrinking** · RB **+23 and growing** · TE **−55 persistent short.** *Directional.*
- **Net:** prioritize QB (scarce + undervalued); don't reach for TE (overvalued, replacement is TE16); RB is overvalued at market but the *cliff* means the early RBs still matter.

---

## 3 · AGING — discount a vet on the clock
*Ages where the decline CI **excludes zero** (i.e. real, not noise). Delta-method ΔPPG; descriptive measured curves.*
- **RB:** decline real from **age 25** (−0.63), clear at **27–28**, steep by **30–31** (−1.8). Fade RB **volume** (not efficiency) from ~25. *Sell on role erosion.*
- **WR:** decline real from **age 27** (−0.65), accelerates **28–29+** (−1.2 to −1.3), steep 31–32 (−2.1). Discount WRs from 27.
- **QB:** **no age** where decline CI excludes zero — flat + wide. **Don't over-discount an older QB.**
- **TE:** **no age** where decline CI excludes zero — gentle. Soft-discount only ~30+.
- *RB-receiving subsample too thin to use (n<min).*

---

## 4 · ROOKIE / PICK VALUES — Clock A P(relevant), for valuing picks in-draft
*Empirical base rates, NFL draft cohort 2010+. Format: y1 / y3 P(relevant). **Descriptive base rates — robust.** Small-n cells have wide CIs. **Values are POST-G10.4-fix regeneration (not committed HEAD — see PROVENANCE); shifts vs stale HEAD are within the CIs.***

| Pos | R1 | R2 | R3 | R4-7 / UDFA |
|---|--:|--:|--:|--:|
| **QB** | 0.66 / 0.59 | — | 0.19 / 0.10 | 0.04 / ~0 |
| **RB** | **0.79 / 0.73** | 0.45 / 0.63 | 0.41 / 0.53 | 0.13 / 0.03 |
| **WR** | 0.65 / 0.65 | 0.39 / 0.44 | 0.20 / 0.41 | 0.07 / 0.02 |
| **TE** | 0.47 / — (y2 0.67) | 0.15 / 0.45 | 0.10 / 0.28 | 0.01 / ~0 |

**Reading it:** R1 capital is the line — a **1st ≈ a likely-relevant player** (RB·R1 0.79, QB·R1 0.66, WR·R1 0.65). After **R3 the hit rate collapses**; a **3rd/4th or UDFA is a lottery ticket** (≤0.13, near-zero for QB/TE/WR late). Value a future rookie 1st as real; value a 3rd+ as a dart.

---

## 5 · TRADE ON THE CLOCK — always read BOTH pools, never one number
*The engine prices picks two ways; the choice can flip the verdict. Report both, always. CI brackets are **MC precision bands only** — they do NOT include aging/survival/pool/rookie-discount uncertainty.*

| Pool | Meaning | Points to |
|---|---|---|
| **CONSENSUS** | you draft the best-available optimally | **picks/quantity WIN** — accumulating picks is good |
| **CORPUS-AVG** | you draft like the median manager (busts in) | **the premium single asset WINS** — picks scatter |

*(Worked example in trade_verdict.md: 1.11 vs 3rd+4th+2027-2nd → **+11 (package wins) CONSENSUS** vs **−75 to −82 (keep 1.11) CORPUS-AVG**.)*

**THE RULE:** the **spread between the two pools IS your uncertainty band.** If you trust your own board and discipline → lean toward **taking the picks / trading down**. If you don't → **keep the premium player.** Never quote a single number to yourself or a trade partner.

---

> ## BOTTOM LINE
> **Draft discipline — taking the best available at each slot — dominates any archetype plan. No named strategy has a validated edge.**
