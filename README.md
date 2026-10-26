# dynasty-engine

A dynasty fantasy football analytics engine. It pulls public NFL and fantasy data, scores every play under your league's exact rules, fits statistical models, and puts a real number with real uncertainty on draft picks and trades.

The rule the whole project follows: **code owns every number.** An AI assistant can explain the results in plain English, but it never computes or changes a statistic.

## Why I built this

I play in a 12-team superflex dynasty league. Most trade advice comes from trade calculators that give one number and no sense of how sure they are. I wanted something that answers "is this trade good for me?" with a range, shows what the answer depends on, and can be rebuilt from scratch to get the same result every time.

## What it does

- **Pulls public data.** Sources are NFL play-by-play from nflverse (2010 onward), MyFantasyLeague ADP reports, DynastyProcess player values, Scott Fish Bowl public datasets, college stats from cfbfastR, and a capped sample of public Sleeper dynasty leagues.
- **Matches players across every source.** Each player gets one stable ID. Uncertain fuzzy matches go to a review queue instead of being applied automatically.
- **Scores fantasy points from play-by-play.** It supports standard, half-PPR, PPR, TE-premium, and superflex profiles. If you set your Sleeper league ID, it uses your league's live scoring settings. Otherwise it uses the bundled default league scoring.
- **Fits models.** These cover aging curves by position, career survival, ADP calibration, player archetypes, and multi-year projections with uncertainty.
- **Evaluates trades.** Every asset becomes a distribution of discounted future value from Monte Carlo simulation. You see who wins, how often, and how the answer changes with your competitive window.
- **Backtests startup-draft strategies.** It simulates past startup drafts to test which drafting approaches actually held up.
- **Answers questions through an MCP server.** A read-only server gives a chat assistant like Claude typed access to the computed results. The assistant reads numbers but can't change them.

## How it's built

```
public sources ──► ingest/ ──► data/raw ──► transform/ ──► DuckDB warehouse
                                                             │
                              exports/  ◄── engine/  ◄── models/
                                 │
                                 └──► jobs/mcp_server.py ──► chat assistant
```

- **Reproducible.** Every random step is seeded in `config.yaml`, and reproducibility checks in `tests/` confirm a rebuild gives the same numbers.
- **Results are documented with their uncertainty.** See `docs/KEY_RESULTS.md` and `docs/STANDING_CONSTRAINTS.md`. A checker fails the build if a doc ever disagrees with the computed numbers.
- **Pre-registered.** Big analyses had their pass/fail rules written down before the results were computed. Those plans are in `docs/PREREG_*.md`.
- **No future data leaks.** A guard fails the build if current-season data reaches a model it shouldn't.
- **One config file.** Seasons, scoring, roster rules, rate limits, and model settings all live in `config.yaml`. No magic numbers in code.

## Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12, managed with uv |
| Warehouse | DuckDB, a single-file database |
| Data | Polars, PyArrow, nflreadpy |
| Models | scikit-learn, lifelines (survival analysis), statsmodels |
| Fetching | httpx, with polite rate limits per source |
| Assistant access | Read-only MCP server |

## Run it

You need [uv](https://docs.astral.sh/uv/). It installs the right Python version for you.

```bash
git clone https://github.com/colbysmithcode/dynasty-engine
cd dynasty-engine
uv sync                      # install locked dependencies
cp .env.example .env         # optional: add your Sleeper league ID
uv run python config.py      # check the config and create data folders
```

Build everything from public sources, in this order. The first run downloads a lot of data, so expect it to take a while.

```bash
uv run python -m ingest.nflverse          # NFL play-by-play and player data
uv run python -m ingest.mfl_adp           # historical ADP sweep
uv run python -m ingest.dynastyprocess    # player values and ID crosswalk
uv run python -m ingest.sfb               # Scott Fish Bowl data, which seeds the league sample
uv run python -m ingest.sleeper_corpus    # sample public Sleeper dynasty leagues
uv run python -m ingest.corpus_backfill   # draft and transaction history for that sample
uv run python -m ingest.cfb               # college production stats
uv run python -m ingest.freeze_corpus     # lock the sample so rebuilds stay reproducible
uv run python -m jobs.refresh --mode full # build the warehouse, fit models, run the engine
```

After the first build, a weekly refresh keeps it current:

```bash
uv run python -m jobs.refresh --mode fast   # current season only
uv run python -m jobs.refresh --rollback    # restore the previous database if a build goes wrong
```

Templates for scheduling these on a Mac are in `jobs/launchd/`. Replace the `/path/to/` placeholders with your own paths.

To start the read-only assistant server:

```bash
uv run python -m jobs.mcp_server
```

## Configuration

Everything is in `config.yaml`. The settings you're most likely to change:

| Setting | What it controls |
|---|---|
| `SLEEPER_LEAGUE_ID` in `.env` | Optional. Pulls your league's live scoring settings. Without it, the bundled default in `data/default_league_scoring.json` is used |
| `roster` | League size and starting lineup. Defaults to 12-team superflex, full PPR, no TE premium |
| `scoring_profiles` | Point values for each scoring format |
| `trade_engine.discount_delta` | How much you value future seasons. Contenders go higher, rebuilders lower. Default 0.82 |
| `models.seed` | Random seed for reproducible results |

## Look at results without running anything

The `exports/` folder has the latest computed reports in plain Markdown:

- `startup_strategy.md` for startup-draft strategy backtests
- `aging_curves.md` for how production changes with age by position
- `hit_rates_by_slot.md` for how often picks at each draft slot hit
- `trade_verdict.md` for a worked example trade evaluation
- `DRAFT_BOARD.md` for a round-by-round startup draft reference

## Project layout

```
dynasty-engine/
├── config.yaml      # all settings
├── config.py        # loads config.yaml and .env
├── ingest/          # one module per data source
├── transform/       # identity matching, fantasy scoring, warehouse build, metrics
├── models/          # aging, survival, ADP calibration, archetypes, projection, backtester
├── engine/          # trade engine
├── jobs/            # weekly refresh, MCP server, drift and reproducibility checks
├── exports/         # computed reports
├── docs/            # phase plans, gate reports, pre-registrations
├── research/        # background research notes
├── migrations/      # warehouse schema
└── tests/           # run each with: uv run python -m tests.<name>
```

## Data use

Everything comes from public sources. The Sleeper sample is capped at a few hundred public leagues. It's pulled slowly, well under Sleeper's rate limits, and results are only reported in aggregate. MyFantasyLeague data comes from aggregate ADP reports only, never individual leagues. No raw downloads, league IDs, or league member data are committed to this repo. The only league-specific file is `data/default_league_scoring.json`, which holds point values and nothing else.

---

Built by [Colby Smith](https://github.com/colbysmithcode).
