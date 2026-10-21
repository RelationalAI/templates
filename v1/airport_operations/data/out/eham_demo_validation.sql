-- =====================================================================
-- EHAM A-CDM Demo - Validation queries
-- =====================================================================
-- These queries prove the synthetic data supports the talk track narrative.
-- Run them after loading and verify the expected counts.

USE DATABASE ACDM_DEMO;
USE SCHEMA EHAM;

-- Q1 (Act 1 expected output): TOBT violations in last 4h, binned by handler
-- Expected: KLG ~7, AGS ~5, DNATA ~3, MENZIES ~2 (all positive deltas
-- except DNATA which is negative)
WITH demo_now AS (
    SELECT TO_TIMESTAMP_NTZ('2026-10-14 14:30:00') AS now
)
SELECT
    handler_code AS handler,
    COUNT(*) AS violations,
    ROUND(AVG(DATEDIFF('minute', tobt, ardt)), 1) AS avg_deviation_min
FROM flight, demo_now
WHERE flight_type = 'DEPARTURE'
  AND ardt IS NOT NULL
  AND ardt >= DATEADD('hour', -4, demo_now.now)
  AND ardt <= demo_now.now
  AND ABS(DATEDIFF('minute', tobt, ardt)) > 5
GROUP BY handler_code
ORDER BY violations DESC;

-- Q2 (Act 2 expected output): KL1234 rotation feed chain
-- Expected: KL1234 -> KL1235 (rotation), and same aircraft chain
SELECT callsign, sobt, aircraft_registration, flight_type, stand_code,
       feeds_callsign, feeds_sobt
FROM flight
WHERE callsign = 'KL1234'
   OR callsign = 'KL1235'
   OR callsign = 'KL1402'
   OR callsign = 'KL1601'
   OR callsign = 'HV5821'
   OR callsign = 'AF1241'
ORDER BY sobt;

-- Q3 (Act 2): Stand E18 conflict pair (KL1235 and KL1402 share E18 window)
SELECT
    f1.callsign AS flight_1,
    f2.callsign AS flight_2,
    f1.stand_code,
    f1.aibt AS f1_in, f1.aobt AS f1_out,
    f2.aibt AS f2_in, f2.aobt AS f2_out
FROM flight f1
JOIN flight f2
  ON f1.stand_code = f2.stand_code
 AND f1.callsign < f2.callsign
 AND f1.aibt <= f2.aobt
 AND f2.aibt <= f1.aobt
WHERE f1.stand_code IN ('E18', 'D54', 'F08')
  AND f1.sobt::DATE = '2026-10-14';

-- Q4 (Act 3 expected output): Flights at MS5 right now (TLDT set, ALDT not),
-- in the next 30 min
WITH demo_now AS (
    SELECT TO_TIMESTAMP_NTZ('2026-10-14 14:30:00') AS now
)
SELECT
    callsign,
    stand_code,
    tldt AS predicted_landing,
    DATEADD('minute', 7, tldt) AS predicted_aibt   -- avg taxi-in placeholder
FROM flight, demo_now
WHERE flight_type = 'ARRIVAL'
  AND tldt IS NOT NULL
  AND aldt IS NULL
  AND tldt BETWEEN demo_now.now AND DATEADD('minute', 30, demo_now.now)
ORDER BY tldt;

-- Q5 (Act 4 expected output): Departures with TSAT in the 15:00-17:00 window
WITH window AS (
    SELECT TO_TIMESTAMP_NTZ('2026-10-14 15:00:00') AS s,
           TO_TIMESTAMP_NTZ('2026-10-14 17:00:00') AS e
)
SELECT COUNT(*) AS flights_in_tsat_window
FROM flight, window
WHERE flight_type = 'DEPARTURE'
  AND tsat >= window.s AND tsat < window.e;
-- Expected: ~47

-- Q6 (Act 5): High-connector KL flights for the preservation rule
SELECT callsign, sobt, destination_icao, pax_connections, tsat
FROM flight
WHERE operator_iata = 'KL'
  AND flight_type = 'DEPARTURE'
  AND pax_connections > 80
  AND tsat BETWEEN TO_TIMESTAMP_NTZ('2026-10-14 15:00:00')
              AND TO_TIMESTAMP_NTZ('2026-10-14 17:00:00')
ORDER BY pax_connections DESC;
-- Expected: KL691 to RJTT (137 pax conn), plus possibly 1-2 others

-- Q7: Overall day distribution by carrier
SELECT operator_iata, COUNT(*) AS flights
FROM flight
GROUP BY operator_iata
ORDER BY flights DESC;

-- Q8: Stand utilization
SELECT s.pier, COUNT(*) AS movements
FROM flight f
JOIN dim_stand s ON f.stand_code = s.code
GROUP BY s.pier
ORDER BY movements DESC;

-- Q9: Storm scenario check (weather event in 15:00-17:00)
SELECT * FROM weather_event;

-- Q10: CTOT regulation rate
SELECT
    COUNT_IF(ctot IS NOT NULL) AS regulated,
    COUNT_IF(ctot IS NULL) AS unregulated,
    COUNT(*) AS total,
    ROUND(100.0 * COUNT_IF(ctot IS NOT NULL) / NULLIF(COUNT_IF(flight_type = 'DEPARTURE'), 0), 1)
        AS regulated_pct_of_departures
FROM flight
WHERE flight_type = 'DEPARTURE';
-- Expected: ~22% regulated
