# GATE 2 — Identity resolution

`dim_player`: **12,726 players**, stable `player_uid` (unique, zero nulls).
uid scheme: `M{mfl_id}` for crosswalk players, `S{sleeper_id}` for minted
Sleeper-only players. Rebuild: `uv run python -m transform.identity`.

## Resolution ladder (as specified)
1. nflverse `ff_playerids` (spine; `mfl_id` = 100% PK)
2. DynastyProcess `db_playerids` → **+225** mfl_ids missing from ff
3. Sleeper `/players/nfl` master → bridge `sleeper_id ↔ gsis_id` (+ name/pos)
4. Deterministic fallback: normalized name + position
5. Fuzzy (rapidfuzz ≥92) → **review queue, never auto-applied**
6. `data/manual_id_overrides.csv` for residue

## Match rates on fantasy-relevant (skill QB/RB/WR/TE) players — **all ≥98%**
| universe | matched | rate |
|---|---|---|
| MFL ADP (market consensus) | 661/661 | **100.0%** |
| Sleeper dynasty-corpus rosters | 1,372/1,372 | **100.0%** |
| nflverse production leaders (top-N/pos/season) | 757/757 | **100.0%** |

## Why the first pass read 96.9% / 97.8% — and why that was NOT a real failure
Scoping "fantasy-relevant" to actual **players** (coaches and team-units are not
players) removed pure artifacts from the denominator:
- **MFL 55 "misses"** = 22 team-kicker units (`TMPK`) + 21 team-QB units (`TMQB`)
  + 11 head coaches (Reid, Shanahan, Sirianni…) + 1 defunct id. **Zero real
  skill-player misses.**
- **Corpus 34 "misses"** = ultra-deep taxi/UDFA stashes (zero production/ADP),
  fuzzy 74–88 vs crosswalk → confidently *new* Sleeper-only players, **minted** as
  new identities (a resolution, not a failure).

## Audit that caught a genuine silent duplicate
A danger-zone check (best fuzzy match 85–92 among minted) flagged **Matt Hibner
(TE) ↔ "Matthew Hibner" (88.0)** — same person, split by the Matt/Matthew
abbreviation just under the 92 auto-cutoff. Fixed via `manual_id_overrides.csv`
(sleeper_id 13324 → M17627); Matthew Hibner now carries that sleeper_id and there
is **no duplicate**. The other two danger-zone cases (Griffin Hebert↔Robert
Griffin, Kendrick Rogers↔Da'Rick Rogers) are genuinely different people — correctly
minted. Net minted: **33**, all confirmed distinct.

## Cross-ID join coverage (dim_player)
mfl 12,693 · gsis 7,968 · sleeper 6,614 · pfr 9,796 · fantasypros 5,006.
gsis/sleeper are <100% by nature: retired players predate Sleeper (no sleeper_id);
never-played prospects have no NFL snap (no gsis). Both are populated for players
who need them.

## Residue mechanisms (live)
- `data/manual_id_overrides.csv`: 1 entry (Hibner).
- `data/id_review_queue.csv`: 0 rows.

## False-POSITIVE audit (two distinct players fused into one uid — the worse error)
Reverse check run after GATE 2. Test-1 known collisions (Adrian Peterson, both
Steve Smiths, Zach Miller, Alex Smith QB/TE, 3× Mike Williams, Michael Thomas,
Marvin Jones) are all kept as **separate uids** with distinct gsis/birthdate/college
— no upstream fusion. Josh Allen shows 1 (the QB; the EDGE defender is simply absent
from the fantasy crosswalk, not merged).

Four real issues found and fixed:
1. **`"NA"` sentinel bug (mine):** unioning `db_playerids` (CSV) imported the string
   `"NA"` for missing IDs → 200+ players shared a fake `sleeper_id="NA"`. Fixed:
   `_nullify()` converts NA/""/null sentinels to null on load. → 0 remaining.
2. **Ambiguous name+pos misattribution:** corpus **Joe Horn** (b.1994, Missouri
   Western) was auto-routed to one of two older crosswalk Joe Horns. Fixed: name+pos
   only auto-resolves when unique; ambiguous cases disambiguate by **birthdate** —
   matches none → minted as distinct (`S6686`).
3. **Mis-attached sleeper_ids (22):** e.g. Marshall Faulk carrying Darrell Williams's
   sleeper_id. Fixed: null any attachment whose Sleeper surname ≠ crosswalk surname.
4. **Over-splits (8):** same player on two mfl_ids (Tony Carter, Ray Agnew…). Fixed:
   `_canonicalize()` merges rows sharing a real gsis/sleeper **and** surname (surname
   guard prevents merging two different people who wrongly share an id, e.g. Fred
   Williams/Kevin Smith — flagged, not merged). Collapsed mfl_ids kept in an alias map.

Post-fix audit: 0 NA rows, 0 sleeper_id collisions, 0 surname-mismatch attachments,
0 silent ambiguous attributions, uids unique. dim_player = 12,685 base + 35 minted.

## N for nflverse production leaders
Gate used QB24/RB48/WR60/TE24 per season (2–5× startable depth) → 100%. Stress test
at QB48/RB84/WR108/TE48 (deep into unrostered tail) → 99.92% (1/1284, Micheal
Spurlock). Tail is covered, not just the top.
