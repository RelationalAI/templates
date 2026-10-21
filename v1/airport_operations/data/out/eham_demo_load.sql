-- =====================================================================
-- EHAM A-CDM Demo - Load script
-- =====================================================================

USE DATABASE ACDM_DEMO;
USE SCHEMA EHAM;

-- 1) Create internal stage (idempotent — does NOT wipe uploaded files)
CREATE STAGE IF NOT EXISTS eham_demo_stage
    FILE_FORMAT = (
        TYPE = CSV
        SKIP_HEADER = 1
        FIELD_OPTIONALLY_ENCLOSED_BY = '"'
        NULL_IF = ('', 'NULL')
        EMPTY_FIELD_AS_NULL = TRUE
    );

-- 2) Upload the CSV using the snow CLI (run this from your local shell):
--    snow sql -c rai -q "PUT file://$(pwd)/eham_demo_flights.csv @ACDM_DEMO.EHAM.eham_demo_stage AUTO_COMPRESS=TRUE OVERWRITE=TRUE"
--
--    Or in Snowsight, open the stage and use the GUI uploader.
--    The bundled load_to_snowflake.sh script does this for you.

-- 3) Load flight rows
COPY INTO flight
FROM @eham_demo_stage/eham_demo_flights.csv.gz
FILE_FORMAT = (
    TYPE = CSV
    SKIP_HEADER = 1
    FIELD_OPTIONALLY_ENCLOSED_BY = '"'
    NULL_IF = ('', 'NULL')
    EMPTY_FIELD_AS_NULL = TRUE
);

-- 4) Quick sanity check
SELECT COUNT(*) AS total_flights,
       COUNT_IF(flight_type = 'ARRIVAL') AS arrivals,
       COUNT_IF(flight_type = 'DEPARTURE') AS departures,
       MIN(sobt) AS first_sobt,
       MAX(sobt) AS last_sobt
FROM flight;
