-- dynasty-engine canonical warehouse (DuckDB). Phase 3.
-- Scoring profiles are first-class: fantasy points are stored per profile,
-- computed from play-by-play (never from precomputed totals).

CREATE TABLE IF NOT EXISTS dim_player (
    player_uid      TEXT PRIMARY KEY,
    mfl_id          TEXT, gsis_id TEXT, sleeper_id TEXT, pfr_id TEXT, espn_id TEXT,
    fantasypros_id  TEXT, sportradar_id TEXT, yahoo_id TEXT, ktc_id TEXT,
    name TEXT, norm_name TEXT, position TEXT, team TEXT,
    birthdate TEXT, draft_year TEXT, draft_round TEXT, draft_pick TEXT, college TEXT
);

CREATE TABLE IF NOT EXISTS dim_team (
    team TEXT PRIMARY KEY, name TEXT, conf TEXT, division TEXT
);

CREATE TABLE IF NOT EXISTS dim_season (season INTEGER PRIMARY KEY);

CREATE TABLE IF NOT EXISTS dim_week (
    season INTEGER, week INTEGER, season_type TEXT,
    PRIMARY KEY (season, week, season_type)
);

-- one row per ACTIVE skill player per week (incl. zero-production).
-- status/played/team_had_game/offense_snaps drive the Phase 5.5 availability model.
CREATE TABLE IF NOT EXISTS fact_player_week (
    player_uid TEXT, gsis_id TEXT, season INTEGER, week INTEGER, position TEXT,
    team TEXT, status TEXT, played BOOLEAN, team_had_game BOOLEAN, offense_snaps DOUBLE,
    pass_yd DOUBLE, pass_td DOUBLE, pass_int DOUBLE,
    rush_yd DOUBLE, rush_td DOUBLE,
    rec DOUBLE, rec_yd DOUBLE, rec_td DOUBLE,
    fumble_lost DOUBLE, pass_2pt DOUBLE, rec_2pt DOUBLE, rush_2pt DOUBLE, st_td DOUBLE,
    fp_std DOUBLE, fp_half_ppr DOUBLE, fp_ppr DOUBLE,
    fp_te_premium DOUBLE, fp_superflex DOUBLE, fp_your_league DOUBLE
);

CREATE TABLE IF NOT EXISTS fact_player_season (
    player_uid TEXT, season INTEGER, position TEXT, games INTEGER,
    fp_std DOUBLE, fp_half_ppr DOUBLE, fp_ppr DOUBLE,
    fp_te_premium DOUBLE, fp_superflex DOUBLE, fp_your_league DOUBLE,
    ppg_ppr DOUBLE, pos_finish_ppr INTEGER
);

CREATE TABLE IF NOT EXISTS fact_adp (
    player_uid TEXT, mfl_id TEXT, season INTEGER, format TEXT, ppr INTEGER,
    league_size INTEGER, period TEXT, adp DOUBLE, min_pick DOUBLE, max_pick DOUBLE,
    draft_pct DOUBLE, drafts_selected_in INTEGER
);

CREATE TABLE IF NOT EXISTS fact_injury (
    player_uid TEXT, gsis_id TEXT, season INTEGER, week INTEGER,
    report_status TEXT, practice_status TEXT, report_primary_injury TEXT
);

CREATE TABLE IF NOT EXISTS fact_dynasty_value (
    player_uid TEXT, snapshot_date TEXT, source TEXT, position TEXT,
    value_1qb DOUBLE, value_2qb DOUBLE, ecr_1qb DOUBLE, ecr_2qb DOUBLE
);

-- your Sleeper league + the dynasty corpus (source column distinguishes)
CREATE TABLE IF NOT EXISTS fact_league_roster (
    source TEXT, league_id TEXT, season TEXT, roster_id INTEGER,
    owner_id TEXT, player_uid TEXT, sleeper_id TEXT, slot TEXT
);

CREATE TABLE IF NOT EXISTS fact_league_draft_pick (
    source TEXT, league_id TEXT, draft_id TEXT, round INTEGER, pick_no INTEGER,
    roster_id INTEGER, player_uid TEXT, sleeper_id TEXT
);

CREATE TABLE IF NOT EXISTS fact_league_traded_pick (
    source TEXT, league_id TEXT, season TEXT, round INTEGER,
    roster_id INTEGER, owner_id INTEGER, previous_owner_id INTEGER
);

-- snowball manager-tendency / FAAB-prior data (ADDENDUM_A A5)
CREATE TABLE IF NOT EXISTS fact_league_transaction (
    source TEXT, league_id TEXT, type TEXT, status TEXT, week INTEGER,
    roster_ids TEXT, adds TEXT, drops TEXT, waiver_bid INTEGER, created BIGINT
);
