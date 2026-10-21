#!/usr/bin/env bash
# Load the EHAM A-CDM demo data into Snowflake.
# Uses the default 'rai' snow CLI connection (override with CONN=<name>).
#
# Idempotent: re-running rebuilds tables (CREATE OR REPLACE), keeps the stage,
# and reloads the CSV. Safe to invoke multiple times.
#
# Usage:
#     bash data/load_to_snowflake.sh                # uses connection 'rai'
#     CONN=NDSOEBE-... bash data/load_to_snowflake.sh
set -euo pipefail

CONN="${CONN:-rai}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$HERE/out"

echo "==> Using snow connection: $CONN"

echo "==> [1/5] DDL: creating ACDM_DEMO.EHAM schema and tables ..."
snow sql -c "$CONN" -f "$OUT/eham_demo_ddl.sql" >/dev/null

echo "==> [2/5] Reference dim tables ..."
snow sql -c "$CONN" -f "$OUT/eham_demo_reference.sql" >/dev/null

echo "==> [3/5] dim_aircraft ..."
snow sql -c "$CONN" -f "$OUT/eham_demo_aircraft.sql" >/dev/null

echo "==> [4/5] Stage + PUT eham_demo_flights.csv ..."
snow sql -c "$CONN" -q "USE DATABASE ACDM_DEMO; USE SCHEMA EHAM; CREATE STAGE IF NOT EXISTS eham_demo_stage FILE_FORMAT = (TYPE = CSV SKIP_HEADER = 1 FIELD_OPTIONALLY_ENCLOSED_BY = '\"' NULL_IF = ('','NULL') EMPTY_FIELD_AS_NULL = TRUE);" >/dev/null
snow sql -c "$CONN" -q "PUT file://$OUT/eham_demo_flights.csv @ACDM_DEMO.EHAM.eham_demo_stage AUTO_COMPRESS=TRUE OVERWRITE=TRUE;" >/dev/null

echo "==> [5/5] COPY INTO flight ..."
snow sql -c "$CONN" -q "USE DATABASE ACDM_DEMO; USE SCHEMA EHAM; COPY INTO flight FROM @eham_demo_stage/eham_demo_flights.csv.gz FILE_FORMAT = (TYPE = CSV SKIP_HEADER = 1 FIELD_OPTIONALLY_ENCLOSED_BY = '\"' NULL_IF = ('','NULL') EMPTY_FIELD_AS_NULL = TRUE);"

echo "==> Done. Validating ..."
snow sql -c "$CONN" -q "USE DATABASE ACDM_DEMO; USE SCHEMA EHAM; SELECT COUNT(*) AS total_flights, COUNT_IF(flight_type = 'ARRIVAL') AS arrivals, COUNT_IF(flight_type = 'DEPARTURE') AS departures FROM flight;"

echo "==> Run all validation queries:  snow sql -c $CONN -f $OUT/eham_demo_validation.sql"
