-- =====================================================================
-- EHAM A-CDM Demo - Snowflake DDL
-- Generated: 2026-05-18 12:44:14
-- Seed: 42
-- =====================================================================

CREATE DATABASE IF NOT EXISTS ACDM_DEMO;
USE DATABASE ACDM_DEMO;

CREATE SCHEMA IF NOT EXISTS EHAM;
USE SCHEMA EHAM;

-- ----- Reference / dimension tables -----------------------------------

CREATE OR REPLACE TABLE dim_operator (
    iata                       VARCHAR(3) PRIMARY KEY,
    icao                       VARCHAR(4),
    name                       VARCHAR(100),
    alliance                   VARCHAR(20),
    min_turn_narrowbody_min    INTEGER,
    min_turn_widebody_min      INTEGER
);

CREATE OR REPLACE TABLE dim_aircraft (
    registration               VARCHAR(10) PRIMARY KEY,
    icao_type                  VARCHAR(4),
    wtc                        VARCHAR(1),
    operator_iata              VARCHAR(3),
    seats                      INTEGER
);

CREATE OR REPLACE TABLE dim_stand (
    code                       VARCHAR(5) PRIMARY KEY,
    pier                       VARCHAR(1),
    is_contact                 BOOLEAN,
    max_wtc                    VARCHAR(1),
    schengen                   BOOLEAN
);

CREATE OR REPLACE TABLE dim_runway (
    designator                 VARCHAR(8) PRIMARY KEY,
    name                       VARCHAR(50),
    length_m                   INTEGER,
    used_for                   VARCHAR(10)
);

CREATE OR REPLACE TABLE dim_fix (
    name                       VARCHAR(5) PRIMARY KEY,
    fix_type                   VARCHAR(10),
    typical_landing_rwy        VARCHAR(8)
);

CREATE OR REPLACE TABLE dim_ground_handler (
    code                       VARCHAR(10) PRIMARY KEY,
    name                       VARCHAR(100)
);

CREATE OR REPLACE TABLE taxi_time_in (
    fix                        VARCHAR(5),
    landing_runway             VARCHAR(8),
    stand_pier                 VARCHAR(1),
    avg_minutes                INTEGER,
    stdev_minutes              INTEGER,
    PRIMARY KEY (fix, landing_runway, stand_pier)
);

CREATE OR REPLACE TABLE taxi_time_out (
    stand_pier                 VARCHAR(1),
    departure_runway           VARCHAR(8),
    avg_minutes                INTEGER,
    stdev_minutes              INTEGER,
    PRIMARY KEY (stand_pier, departure_runway)
);

-- ----- Main flight fact table (16 ICAO milestones) -------------------

CREATE OR REPLACE TABLE flight (
    callsign                   VARCHAR(10) NOT NULL,
    sobt                       TIMESTAMP_NTZ NOT NULL,
    operator_iata              VARCHAR(3),
    aircraft_registration      VARCHAR(10),
    icao_type                  VARCHAR(4),
    wtc                        VARCHAR(1),
    flight_type                VARCHAR(10),       -- ARRIVAL / DEPARTURE
    origin_icao                VARCHAR(4),
    destination_icao           VARCHAR(4),
    stand_code                 VARCHAR(5),
    runway_designator          VARCHAR(8),
    entry_fix                  VARCHAR(5),
    handler_code               VARCHAR(10),
    pax_connections            INTEGER,
    atfm_penalty               FLOAT,

    -- 16 ICAO Milestones
    eobt                       TIMESTAMP_NTZ,     -- MS1 filed flight plan
    ctot                       TIMESTAMP_NTZ,     -- MS2 calc'd take-off (regulated)
    atot_upstation             TIMESTAMP_NTZ,     -- MS3 take-off from origin
    fir_entry_time             TIMESTAMP_NTZ,     -- MS4 FIR entry
    tldt                       TIMESTAMP_NTZ,     -- MS5 target landing (AMAN)
    eldt                       TIMESTAMP_NTZ,     -- MS5 estimated landing
    aldt                       TIMESTAMP_NTZ,     -- MS6 actual landing
    aibt                       TIMESTAMP_NTZ,     -- MS7 actual in-block
    acgt                       TIMESTAMP_NTZ,     -- MS8 actual ground handling start
    tobt                       TIMESTAMP_NTZ,     -- MS9 target off-block
    tsat                       TIMESTAMP_NTZ,     -- MS10 target startup approval
    abdt                       TIMESTAMP_NTZ,     -- MS11 actual boarding start
    ardt                       TIMESTAMP_NTZ,     -- MS12 actual ready
    asrt                       TIMESTAMP_NTZ,     -- MS13 actual startup request
    asat                       TIMESTAMP_NTZ,     -- MS14 actual startup approved
    ttot                       TIMESTAMP_NTZ,     -- target take-off
    aobt                       TIMESTAMP_NTZ,     -- MS15 actual off-block
    atot                       TIMESTAMP_NTZ,     -- MS16 actual take-off

    feeds_callsign             VARCHAR(10),       -- inbound -> outbound rotation
    feeds_sobt                 TIMESTAMP_NTZ,
    is_eligible_acdm           BOOLEAN DEFAULT TRUE,

    PRIMARY KEY (callsign, sobt)
);

CREATE OR REPLACE TABLE atfm_regulation (
    regulation_id              VARCHAR(20) PRIMARY KEY,
    affected_destination_icao  VARCHAR(4),
    start_time                 TIMESTAMP_NTZ,
    end_time                   TIMESTAMP_NTZ,
    reason                     VARCHAR(100)
);

CREATE OR REPLACE TABLE weather_event (
    event_id                   VARCHAR(20) PRIMARY KEY,
    start_time                 TIMESTAMP_NTZ,
    end_time                   TIMESTAMP_NTZ,
    description                VARCHAR(200),
    affected_runways           VARCHAR(100)
);
