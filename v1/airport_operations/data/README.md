# EHAM A-CDM Demo - Synthetic Data

Snowflake-ready synthetic dataset for the RelationalAI A-CDM Decision Hub demo.
Anchored to Amsterdam Schiphol (EHAM) ops on Wednesday 14 October 2026.

## What's here

```
data/
├── README.md                       <-- this file
├── build_eham_demo_data.py         <-- the generator (run to regenerate)
└── out/
    ├── eham_demo_ddl.sql           <-- CREATE DATABASE/SCHEMA/TABLE
    ├── eham_demo_reference.sql     <-- INSERT for dim tables (~13KB)
    ├── eham_demo_aircraft.sql      <-- INSERT for dim_aircraft (auto-derived)
    ├── eham_demo_flights.csv       <-- 320 flights with 16 ICAO milestones
    ├── eham_demo_load.sql          <-- CREATE STAGE + COPY INTO
    └── eham_demo_validation.sql    <-- queries that prove the data fits the talk track
```

## What's in the data

- **320 flights** spanning 24h on Wednesday 14 October 2026
- **All 16 ICAO A-CDM milestones** modeled per the procedure template
- **Real EHAM infrastructure**: 6 runways with correct designators (18R Polderbaan, 18C Zwanenburgbaan, 18L Aalsmeerbaan, 06/24 Kaagbaan, 09/27 Buitenveldertbaan, 04/22 Schiphol-Oost), real IAFs (ARTIP, SUGOL, RIVER, NIRSI), real pier layout (B/C/D/E/F/G/H/M/R)
- **Real carrier mix** matching EHAM proportions: 52% KL, 8% HV, 4% AF, 3% DL, plus BA/LH/EZY/FR/W6/TK/EK/SQ/KQ
- **Type-correct fleet**: KL operates B737/B738/B739/E-Jets/A330/B777/B787/A350; HV is 100% B737/MAX; DL widebody only on F/G non-Schengen; etc.
- **Stand assignments respect Schengen/non-Schengen pier split** (intra-EU flights to B/C/D north/E/H; long-haul non-EU to F/G/M)
- **Polderbaan (18R/NIRSI) modeled with 11-13 min taxi-in** (the famous long taxi - a Schiphol controller will check this)
- **22% of departures regulated with CTOT**, 78% slot-adherent (matches published Eurocontrol numbers)

## Curated narrative flights (the demo depends on these existing)

| Flight    | Type      | Role in talk track                              |
|-----------|-----------|--------------------------------------------------|
| KL1234    | ARRIVAL   | The late flight at MS5 (KJFK, 35 min late, E18) |
| KL1235    | DEPARTURE | Rotation partner of KL1234 (same tail, E18)     |
| KL1402    | DEPARTURE | 2nd-hop stand-conflict victim on E18            |
| KL1601    | DEPARTURE | 3rd-hop rotation off KL1402 aircraft (C08)      |
| HV5821    | DEPARTURE | Cross-operator stand-conflict victim on D54     |
| KL0641    | ARRIVAL   | Upstream KL widebody parked at D54 (creates HV5821 conflict) |
| AF1241    | DEPARTURE | 2nd-hop stand-conflict victim on F08            |
| KL0712    | ARRIVAL   | Upstream KL widebody parked at F08 (creates AF1241 conflict) |
| DL0036    | ARRIVAL   | MS5 forecast candidate (E18, TLDT 14:35)        |
| KL0691    | ARRIVAL   | MS5 forecast candidate (F04, TLDT 14:44)        |
| AF1641    | ARRIVAL   | MS5 forecast candidate (D88, TLDT 15:00)        |
| BA0432    | ARRIVAL   | MS5 forecast candidate (B26, TLDT 14:52)        |
| KL691     | DEPARTURE | High-connector preserved flight (RJTT, 137 pax conn) |
| KL7000..6 | DEPARTURE | 7 KLG TOBT violations for Act 1                 |
| HV7100..4 | DEPARTURE | 5 AGS TOBT violations for Act 1                 |
| AF8000..2 | DEPARTURE | 3 DNATA TOBT violations (early-ready) for Act 1 |
| BA8100..1 | DEPARTURE | 2 MENZIES TOBT violations for Act 1             |

## Expected query results (so you know the data is right)

Run `eham_demo_validation.sql` after loading. Expect:

| Query | Expected |
|-------|----------|
| Q1 TOBT violations by handler, last 4h | KLG 7 / AGS 5 / DNATA 3 / MENZIES 2 |
| Q2 KL1234 rotation chain | 6 flights (KL1234, KL1235, KL1402, KL1601, HV5821, AF1241) |
| Q3 Stand conflicts E18/D54/F08 | 3+ overlapping pairs |
| Q4 MS5 candidates (TLDT 14:30-15:00, ALDT NULL) | 5 flights (KL1234 + 4 forecast candidates) |
| Q5 TSAT window 15:00-17:00 departures | 47 |
| Q6 High-connector KL departures in TSAT window | KL691 (137 pax) + 1-2 others |
| Q7 Carrier mix | KL ~52%, HV ~8%, AF ~4%, DL ~3% (rest distributed) |
| Q10 CTOT regulation rate | ~22% of departures |

## How to load it into Snowflake

### Option A: SnowSQL CLI

```bash
# 1. Set environment
export SNOWFLAKE_USER=your_user
export SNOWFLAKE_ACCOUNT=your_account
export SNOWFLAKE_WAREHOUSE=your_warehouse
export SNOWFLAKE_ROLE=SYSADMIN  # or rai_developer if RAI app is installed

# 2. Run DDL (creates DB + schema + tables)
snowsql -f out/eham_demo_ddl.sql

# 3. Load reference / dim tables
snowsql -f out/eham_demo_reference.sql
snowsql -f out/eham_demo_aircraft.sql

# 4. Upload the CSV to an internal stage
cd out
snowsql -q "USE DATABASE ACDM_DEMO; USE SCHEMA EHAM; \
  CREATE STAGE IF NOT EXISTS eham_demo_stage FILE_FORMAT = ( \
    TYPE = CSV SKIP_HEADER = 1 FIELD_OPTIONALLY_ENCLOSED_BY = '\"' \
    NULL_IF = ('','NULL') EMPTY_FIELD_AS_NULL = TRUE);"
snowsql -q "PUT file://eham_demo_flights.csv @ACDM_DEMO.EHAM.eham_demo_stage AUTO_COMPRESS=TRUE"

# 5. Run the COPY INTO + sanity check
snowsql -f eham_demo_load.sql

# 6. Run validation queries
snowsql -f eham_demo_validation.sql
```

### Option B: Snowsight web UI

1. Open a SQL Worksheet, paste the contents of `eham_demo_ddl.sql`, run.
2. Paste `eham_demo_reference.sql`, run.
3. Paste `eham_demo_aircraft.sql`, run.
4. In Data > Databases > ACDM_DEMO > EHAM > Stages, create a new stage called `eham_demo_stage`. Use the GUI uploader to upload `eham_demo_flights.csv`.
5. Paste `eham_demo_load.sql`, run.
6. Paste `eham_demo_validation.sql`, run cell by cell.

### Option C: Single-script via Snowpark or python connector

```python
import snowflake.connector
con = snowflake.connector.connect(...)
cur = con.cursor()
for path in ["eham_demo_ddl.sql", "eham_demo_reference.sql", "eham_demo_aircraft.sql"]:
    with open(f"out/{path}") as fh:
        for stmt in fh.read().split(";"):
            if stmt.strip():
                cur.execute(stmt)
# PUT + COPY INTO via snowsql or PUT API
```

## How to regenerate with a different seed

```bash
EHAM_DEMO_SEED=137 python3 build_eham_demo_data.py
```

The curated narrative flights are deterministic regardless of seed. Only the
~290 bulk background flights vary - carrier, stand, route, milestone noise.
This is useful for:

- A/B comparison runs (same query, different data)
- Stress-testing your RAI ontology with different distributions
- Bumping seed if a customer asks "show me a different day"

## How the data answers the talk track questions

**Act 1 (Rules / MS12):** The four ground handlers (KLG, AGS, DNATA, MENZIES)
have curated TOBT violations in the last 4h, with deviations in the 6-12 min
range. KLG and AGS skew positive (late-ready), DNATA skews negative
(early-ready). Bulk background flights are forced compliant in this window so
the curated rows dominate.

**Act 2 (Graph / cascade):** KL1234 inbound is linked to KL1235 outbound via
`feeds_callsign` (rotation). KL1235 and KL1402 both occupy stand E18 in
overlapping windows (stand conflict). KL1402's aircraft (PH-BXM) then feeds
KL1601 via `feeds_callsign`. KL0641 occupies D54 long enough to clash with
HV5821 at 14:35. KL0712 occupies F08 long enough to clash with AF1241 at 16:00.
Six downstream flights are at risk.

**Act 3 (Predictive / gate conflict at MS5):** Five inbound flights have TLDT
set in [14:30, 15:00] with ALDT still NULL (still en route): KL1234 (the
cascade flight, E18), DL0036 (E18), KL0691 (F04), AF1641 (D88), BA0432 (B26).
The predictive reasoner ranks these by conflict probability with the current
stand occupants. (You typically LIMIT 4 to show the top of the queue.)

**Act 4 (Prescriptive / TSAT optimization):** Exactly 47 departures have TSAT
in [15:00, 17:00). Wake categories are populated. Pier assignments are
populated for pushback contention. CTOT is set on ~22% of these (regulated
flights). Pax connections and ATFM penalty fields are populated for the
objective function.

**Act 5 (Superalignment):** KL691 outbound to RJTT (Tokyo) has 137 connecting
pax. Adding the preservation rule (`pax_connections > 80 AND operator = 'KL'`)
keeps KL691 within 8 min of SOBT in the re-solve.

## Limitations / what's deliberately out

- **De-icing season** is not modeled (October is too early for full de-ice ops)
- **Crew duty time** is not modeled
- **Pax bag connection sequencing** is not modeled
- **ATFM regulation prediction** is not modeled - CTOTs are pre-stamped
- **Cargo flights** are minimal - only 5X (UPS) shown briefly
- **GA on RWY 04/22** is excluded

State these up front in the demo. Owning what's out builds more trust than
pretending nothing is missing.

## Files map to the talk track sections

- **Talk-track Appendix A** (the data fabrication brief) <-> this `data/` folder
- **Talk-track Act 1** rules query <-> `validation.sql` Q1
- **Talk-track Act 2** graph cascade <-> `validation.sql` Q2, Q3
- **Talk-track Act 3** MS5 forecast <-> `validation.sql` Q4
- **Talk-track Act 4** prescriptive solve <-> `validation.sql` Q5
- **Talk-track Act 5** preservation rule <-> `validation.sql` Q6
