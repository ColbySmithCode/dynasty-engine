# Player Projections — Phase 5.5 (Bayesian posterior, 90% credible intervals)

Composition: VORP(t)=P_play·games·(PPG|play − replacement). 10000 MC draws. Aging Δ from 5.1 posterior (QB buckets wide → wide QB intervals). Availability from position/age + injury history. **All outputs are distributions, not points.**

## Established players — projected PPG (mean [5–95%]) by future year

| player | pos | age | yr1 PPG | yr2 PPG | yr3 PPG |
|---|---|--:|--:|--:|--:|
| Christian McCaffrey | RB | 30 | 17.1 [15,19] | 15.3 [13,18] | 14.0 [10,18] |
| Puka Nacua | WR | 25 | 18.0 [16,20] | 17.9 [16,20] | 17.3 [15,19] |
| Josh Allen | QB | 30 | 19.8 [17,22] | 19.3 [17,22] | 20.5 [16,25] |
| Bijan Robinson | RB | 24 | 16.4 [14,18] | 15.7 [14,18] | 15.8 [14,18] |
| Jahmyr Gibbs | RB | 24 | 16.2 [14,18] | 15.6 [14,18] | 15.6 [14,18] |
| Jonathan Taylor | RB | 27 | 15.2 [13,17] | 14.4 [12,16] | 14.4 [12,17] |
| Matthew Stafford | QB | 38 | 17.9 [16,20] | 17.1 [15,19] | 16.3 [14,18] |
| Jaxon Smith-Njigba | WR | 24 | 16.4 [15,18] | 16.2 [14,18] | 16.1 [14,18] |
| Patrick Mahomes | QB | 31 | 17.7 [15,20] | 18.8 [15,23] | 17.2 [12,22] |
| De'Von Achane | RB | 25 | 14.6 [13,17] | 14.6 [13,17] | 13.7 [11,16] |
| Trevor Lawrence | QB | 27 | 17.2 [15,20] | 17.8 [15,20] | 17.3 [14,20] |
| Drake Maye | QB | 24 | 18.2 [16,20] | 18.1 [16,20] | 18.0 [16,20] |
| Ja'Marr Chase | WR | 26 | 14.9 [13,17] | 14.3 [12,16] | 13.1 [11,15] |
| Amon-Ra St. Brown | WR | 27 | 14.2 [12,16] | 13.0 [11,15] | 11.7 [10,14] |
| Caleb Williams | QB | 25 | 17.4 [15,19] | 17.3 [15,20] | 16.4 [14,19] |

## Uncertainty is carried, not collapsed

- yr3 PPG 90% width: Josh Allen (QB) = 5.4 vs Puka Nacua (WR) = 3.9 → QB interval WIDER (Decision 6: QB aging CIs wide).

## Rookie RB·R1 — P(relevant) carries the survival interval (n=20)

| year | P(relevant) mean [5–95%] | VORP mean [5–95%] |
|--:|---|---|
| 1 | 0.77 [0.62,0.89] | +28 [-63,+140] |
| 3 | 0.71 [0.55,0.85] | +22 [-63,+138] |
| 5 | 0.50 [0.33,0.67] | +2 [-70,+127] |