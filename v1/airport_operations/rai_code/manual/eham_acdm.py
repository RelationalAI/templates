"""EHAM A-CDM Demo - manually-built ontology over ACDM_DEMO.EHAM.

Full coverage of 11 source tables. Concepts:
    Dim:        Operator, Aircraft, Stand, Runway, GroundHandler, Fix
    Reference:  TaxiTimeIn, TaxiTimeOut
    Events:     WeatherEvent, AtfmRegulation
    Core:       Flight (one row per callsign; 16 milestone timestamps)
    Subtypes:   Departure(Flight), Arrival(Flight)   (derived from FLIGHT_TYPE)
    Derived:    feeds_callsign(Flight, Flight)       (explicit rotation edge)
                shares_stand(Flight, Flight)         (stand-contention edge)
                TOBTViolation(Flight)                (ARDT vs TOBT > 5 min)
                StormWindowDeparture(Flight)         (TSAT in [15:00, 17:00))
                PreservedFlight(Flight)              (KL pax_conn > 80, Act 5)

Run from project root:
    .venv/bin/python rai_code/manual/eham_acdm.py
"""
import os

from relationalai.semantics import Boolean, Float, Integer, Model, String
from relationalai.semantics.std import aggregates as aggs

# -----------------------------------------------------------------------------
# Engine sizing - named engines so they stay warm between runs and back both
# the notebook and the deployed Cortex agent.
# -----------------------------------------------------------------------------
_LOGIC_NAME, _LOGIC_SIZE = "acdm_logic_l", "HIGHMEM_X64_L"
_PRESC_NAME, _PRESC_SIZE = "acdm_prescriptive_m", "HIGHMEM_X64_M"


def _build_config():
    """Auto-discover config (active Snowpark session inside Snowflake, or the
    snow CLI's connections.toml locally), then pin the reasoners to named engines."""
    try:
        from snowflake.snowpark.context import get_active_session  # type: ignore

        get_active_session()
        from relationalai.config import ConfigFromActiveSession

        cfg = ConfigFromActiveSession()
    except Exception:
        from relationalai.config import create_config

        cfg = create_config()
    cfg.reasoners.logic.name = _LOGIC_NAME
    cfg.reasoners.logic.size = _LOGIC_SIZE
    cfg.reasoners.prescriptive.name = _PRESC_NAME
    cfg.reasoners.prescriptive.size = _PRESC_SIZE
    if os.environ.get("ACDM_DISABLE_DEPLOYMENT_CONFIG") == "1":
        cfg.deployment = None
    return cfg


model = Model("eham_acdm", config=_build_config())

# =============================================================================
# CONCEPTS
# =============================================================================

# --- dimensions
Operator = model.Concept("CarrierOperator", identify_by={"iata": String})
Aircraft = model.Concept("Aircraft", identify_by={"registration": String})
Stand = model.Concept("Stand", identify_by={"code": String})
Runway = model.Concept("Runway", identify_by={"designator": String})
GroundHandler = model.Concept("GroundHandler", identify_by={"code": String})
Fix = model.Concept("NavigationFix", identify_by={"name": String})

# --- taxi-time matrices (junctions)
TaxiTimeIn = model.Concept(
    "TaxiTimeIn",
    identify_by={"arrival_fix": Fix, "landing_runway": Runway, "stand_pier": String},
)
TaxiTimeOut = model.Concept(
    "TaxiTimeOut",
    identify_by={"stand_pier": String, "departure_runway": Runway},
)

# --- events
WeatherEvent = model.Concept("WeatherEvent", identify_by={"event_id": String})
AtfmRegulation = model.Concept(
    "AtfmRegulation", identify_by={"regulation_id": String}
)

# --- core
Flight = model.Concept("Flight", identify_by={"callsign": String})

# =============================================================================
# PROPERTIES
# =============================================================================

# --- Operator
Operator.icao = model.Property(f"{Operator} has {String:icao}")
Operator.name = model.Property(f"{Operator} called {String:name}")
Operator.alliance = model.Property(f"{Operator} in {String:alliance}")
Operator.min_turn_narrowbody_min = model.Property(
    f"{Operator} has {Integer:min_turn_narrowbody_min}"
)
Operator.min_turn_widebody_min = model.Property(
    f"{Operator} has {Integer:min_turn_widebody_min}"
)

# --- Aircraft
Aircraft.icao_type = model.Property(f"{Aircraft} has {String:icao_type}")
Aircraft.wtc = model.Property(f"{Aircraft} has {String:wtc}")
Aircraft.owning_operator = model.Property(f"{Aircraft} of {Operator:aircraft_operator}")
Aircraft.seats = model.Property(f"{Aircraft} has {Integer:seats}")

# --- Stand
Stand.pier = model.Property(f"{Stand} on {String:pier}")
Stand.is_contact = model.Property(f"{Stand} has {Boolean:is_contact}")
Stand.max_wtc = model.Property(f"{Stand} has {String:max_wtc}")
Stand.schengen = model.Property(f"{Stand} has {Boolean:schengen}")

# --- Runway
Runway.name = model.Property(f"{Runway} called {String:name}")
Runway.length_m = model.Property(f"{Runway} has {Integer:length_m}")
Runway.used_for = model.Property(f"{Runway} has {String:used_for}")

# --- GroundHandler
GroundHandler.name = model.Property(f"{GroundHandler} called {String:name}")

# --- Fix
Fix.fix_type = model.Property(f"{Fix} has {String:fix_type}")
Fix.typical_landing_rwy = model.Property(f"{Fix} typically lands on {String:typical_landing_rwy}")

# --- TaxiTimeIn
TaxiTimeIn.avg_minutes = model.Property(f"{TaxiTimeIn} has {Integer:avg_minutes}")
TaxiTimeIn.stdev_minutes = model.Property(f"{TaxiTimeIn} has {Integer:stdev_minutes}")

# --- TaxiTimeOut
TaxiTimeOut.avg_minutes = model.Property(f"{TaxiTimeOut} has {Integer:avg_minutes}")
TaxiTimeOut.stdev_minutes = model.Property(f"{TaxiTimeOut} has {Integer:stdev_minutes}")

# --- WeatherEvent
from relationalai.semantics import DateTime  # noqa: E402

WeatherEvent.start_time = model.Property(f"{WeatherEvent} starts at {DateTime:start_time}")
WeatherEvent.end_time = model.Property(f"{WeatherEvent} ends at {DateTime:end_time}")
WeatherEvent.description = model.Property(f"{WeatherEvent} has {String:description}")
WeatherEvent.affected_runways = model.Property(
    f"{WeatherEvent} affects {String:affected_runways}"
)

# --- AtfmRegulation
AtfmRegulation.affected_destination_icao = model.Property(
    f"{AtfmRegulation} affects destination {String:affected_destination_icao}"
)
AtfmRegulation.start_time = model.Property(f"{AtfmRegulation} starts at {DateTime:start_time}")
AtfmRegulation.end_time = model.Property(f"{AtfmRegulation} ends at {DateTime:end_time}")
AtfmRegulation.reason = model.Property(f"{AtfmRegulation} has {String:reason}")

# --- Flight: static attributes and FKs
Flight.flight_type = model.Property(f"{Flight} has {String:flight_type}")
Flight.operating_operator = model.Property(f"{Flight} flown by {Operator:flight_operator}")
Flight.assigned_aircraft = model.Property(f"{Flight} uses {Aircraft:flight_aircraft}")
Flight.icao_type = model.Property(f"{Flight} has {String:icao_type}")
Flight.wtc = model.Property(f"{Flight} has {String:wtc}")
Flight.origin_icao = model.Property(f"{Flight} from {String:origin_icao}")
Flight.destination_icao = model.Property(f"{Flight} to {String:destination_icao}")
Flight.assigned_stand = model.Property(f"{Flight} at {Stand:flight_stand}")
Flight.assigned_runway = model.Property(f"{Flight} on {Runway:flight_runway}")
Flight.entry_fix = model.Property(f"{Flight} via {Fix:entry_fix}")
Flight.handler = model.Property(f"{Flight} handled by {GroundHandler:handler}")
Flight.pax_connections = model.Property(f"{Flight} has {Integer:pax_connections}")
Flight.atfm_penalty = model.Property(f"{Flight} has {Float:atfm_penalty}")

# --- Flight: 16 A-CDM milestone timestamps (stored as TIMESTAMP_NTZ in Snowflake;
#     keep as String for portability, parse when needed).
# Departures populate EOBT, TOBT, TSAT, CTOT, ATOT_UPSTATION, FIR_ENTRY_TIME,
# ABDT, ARDT, ASRT, ASAT, TTOT, AOBT, ATOT.
# Arrivals populate TLDT, ELDT, ALDT, AIBT, ACGT.
# Both populate SOBT.
Flight.sobt = model.Property(f"{Flight} sobt {DateTime:sobt}")
Flight.eobt = model.Property(f"{Flight} eobt {DateTime:eobt}")
Flight.ctot = model.Property(f"{Flight} ctot {DateTime:ctot}")
Flight.atot_upstation = model.Property(f"{Flight} atot_up {DateTime:atot_upstation}")
Flight.fir_entry_time = model.Property(f"{Flight} fir_entry {DateTime:fir_entry_time}")
Flight.tldt = model.Property(f"{Flight} tldt {DateTime:tldt}")
Flight.eldt = model.Property(f"{Flight} eldt {DateTime:eldt}")
Flight.aldt = model.Property(f"{Flight} aldt {DateTime:aldt}")
Flight.aibt = model.Property(f"{Flight} aibt {DateTime:aibt}")
Flight.acgt = model.Property(f"{Flight} acgt {DateTime:acgt}")
Flight.tobt = model.Property(f"{Flight} tobt {DateTime:tobt}")
Flight.tsat = model.Property(f"{Flight} tsat {DateTime:tsat}")
Flight.abdt = model.Property(f"{Flight} abdt {DateTime:abdt}")
Flight.ardt = model.Property(f"{Flight} ardt {DateTime:ardt}")
Flight.asrt = model.Property(f"{Flight} asrt {DateTime:asrt}")
Flight.asat = model.Property(f"{Flight} asat {DateTime:asat}")
Flight.ttot = model.Property(f"{Flight} ttot {DateTime:ttot}")
Flight.aobt = model.Property(f"{Flight} aobt {DateTime:aobt}")
Flight.atot = model.Property(f"{Flight} atot {DateTime:atot}")

# --- Derived flags
# Subtype-style unary relationships (loaded from FLIGHT_TYPE column)
Departure = model.Relationship(f"{Flight} is a departure", short_name="departure_flight")
Arrival = model.Relationship(f"{Flight} is an arrival", short_name="arrival_flight")

# Rotation edge: this Flight feeds the next Flight (explicit FEEDS_CALLSIGN).
feeds_callsign = model.Relationship(
    f"{Flight} feeds {Flight:next_flight}", short_name="feeds_callsign"
)

# Slot-blocks edge: this Flight occupies a runway/pushback slot that
# downstream blocks another flight (FLIGHT.SLOT_BLOCKS_CALLSIGN).
# Captures operational cascade across stands/piers (e.g., KL1235 on E18 blocks
# HV5821 on D54 via shared pushback queueing). Distinct from feeds_callsign,
# which is strictly the same-aircraft rotation chain.
slot_blocks = model.Relationship(
    f"{Flight} slot-blocks {Flight:blocked_flight}", short_name="slot_blocks"
)

# Stand-overlap edge: two flights share a stand with overlapping occupancy.
# Built around AIBT/AOBT for arrivals and prior-arrival-AIBT->AOBT for departures.
shares_stand = model.Relationship(
    f"{Flight} shares stand with {Flight:other_flight}", short_name="shares_stand"
)

# TOBT violation (Act 1): abs(diff(minute, TOBT, ARDT)) > 5 on departures with ARDT set.
TOBTViolation = model.Concept("TOBTViolation", extends=[Flight])

# Storm window departures (Act 4 scope): TSAT in [15:00, 17:00) on 2026-10-14.
StormWindowDeparture = model.Concept("StormWindowDeparture", extends=[Flight])

# Preserved flight (Act 5): KL departure with pax_connections > 80.
PreservedFlight = model.Concept("PreservedFlight", extends=[Flight])

# =============================================================================
# ACT 4/5: storm-window LP scaffolding
# =============================================================================
# 120 one-minute slots covering the storm window [15:00, 17:00) on 2026-10-14.
# Materialised as ACDM_DEMO.EHAM.STORM_SLOT (minute_offset 0..119; absolute_min
# = 900..1019 = minutes-since-midnight).
Slot = model.Concept("Slot", identify_by={"minute_offset": Integer})
Slot.absolute_min = model.Property(f"{Slot} absolute_min {Integer:absolute_min}")

# FlightSlot: junction between a storm-window departure and a slot. The Float
# property `assign` is the binary decision variable (LP returns 0.0/1.0).
FlightSlot = model.Concept(
    "FlightSlot", identify_by={"flight_ref": Flight, "slot_ref": Slot}
)
# Two decision-variable Properties so Acts 4 and 5 can each populate their
# own assign without violating the functional-dependency rule (a Problem may
# only own one Property at a time).
FlightSlot.assign_base = model.Property(
    f"{FlightSlot} assign_base {Float:assign_base}"
)
FlightSlot.assign_preserved = model.Property(
    f"{FlightSlot} assign_preserved {Float:assign_preserved}"
)
# delay_min: derived in PyRel as slot.absolute_min - flight.sobt_min_storm.
# Pre-computing here (rather than inline in the select expression) sidesteps
# an Int128Array arithmetic edge case in the result-helper layer.
FlightSlot.delay_min = model.Property(f"{FlightSlot} delay_min {Integer:delay_min}")

# Storm-LP helper Properties: SOBT and CTOT expressed as minutes-since-midnight
# so we can do plain integer arithmetic against Slot.absolute_min in the
# constraint and objective expressions.
Flight.sobt_min_storm = model.Property(
    f"{Flight} sobt_min_storm {Integer:sobt_min_storm}"
)
Flight.ctot_min_storm = model.Property(
    f"{Flight} ctot_min_storm {Integer:ctot_min_storm}"
)
Flight.preservation_delay_cap_min = model.Property(
    f"{Flight} preservation_delay_cap_min {Integer:preservation_delay_cap_min}"
)

# =============================================================================
# SOURCE TABLES
# =============================================================================
DB = "ACDM_DEMO.EHAM"


class Sources:
    flight_src = model.Table(f"{DB}.FLIGHT")
    aircraft_src = model.Table(f"{DB}.DIM_AIRCRAFT")
    operator_src = model.Table(f"{DB}.DIM_OPERATOR")
    stand_src = model.Table(f"{DB}.DIM_STAND")
    runway_src = model.Table(f"{DB}.DIM_RUNWAY")
    handler_src = model.Table(f"{DB}.DIM_GROUND_HANDLER")
    fix_src = model.Table(f"{DB}.DIM_FIX")
    taxi_in_src = model.Table(f"{DB}.TAXI_TIME_IN")
    taxi_out_src = model.Table(f"{DB}.TAXI_TIME_OUT")
    weather_src = model.Table(f"{DB}.WEATHER_EVENT")
    atfm_src = model.Table(f"{DB}.ATFM_REGULATION")
    storm_slot_src = model.Table(f"{DB}.STORM_SLOT")
    slot_block_src = model.Table(f"{DB}.SLOT_BLOCK")


# =============================================================================
# LOAD: dims
# =============================================================================
model.define(
    op := Operator.new(iata=Sources.operator_src.IATA),
    op.icao(Sources.operator_src.ICAO),
    op.name(Sources.operator_src.NAME),
    op.alliance(Sources.operator_src.ALLIANCE),
    op.min_turn_narrowbody_min(Sources.operator_src.MIN_TURN_NARROWBODY_MIN),
    op.min_turn_widebody_min(Sources.operator_src.MIN_TURN_WIDEBODY_MIN),
)

model.define(
    ac := Aircraft.new(registration=Sources.aircraft_src.REGISTRATION),
    ac.icao_type(Sources.aircraft_src.ICAO_TYPE),
    ac.wtc(Sources.aircraft_src.WTC),
    ac.owning_operator(Operator.filter_by(iata=Sources.aircraft_src.OPERATOR_IATA)),
    ac.seats(Sources.aircraft_src.SEATS),
)

model.define(
    st := Stand.new(code=Sources.stand_src.CODE),
    st.pier(Sources.stand_src.PIER),
    st.is_contact(Sources.stand_src.IS_CONTACT),
    st.max_wtc(Sources.stand_src.MAX_WTC),
    st.schengen(Sources.stand_src.SCHENGEN),
)

model.define(
    rw := Runway.new(designator=Sources.runway_src.DESIGNATOR),
    rw.name(Sources.runway_src.NAME),
    rw.length_m(Sources.runway_src.LENGTH_M),
    rw.used_for(Sources.runway_src.USED_FOR),
)

model.define(
    gh := GroundHandler.new(code=Sources.handler_src.CODE),
    gh.name(Sources.handler_src.NAME),
)

model.define(
    fx := Fix.new(name=Sources.fix_src.NAME),
    fx.fix_type(Sources.fix_src.FIX_TYPE),
    fx.typical_landing_rwy(Sources.fix_src.TYPICAL_LANDING_RWY),
)

# =============================================================================
# LOAD: taxi-time matrices
# =============================================================================
model.define(
    tin := TaxiTimeIn.new(
        arrival_fix=Fix.filter_by(name=Sources.taxi_in_src.FIX),
        landing_runway=Runway.filter_by(designator=Sources.taxi_in_src.LANDING_RUNWAY),
        stand_pier=Sources.taxi_in_src.STAND_PIER,
    ),
    tin.avg_minutes(Sources.taxi_in_src.AVG_MINUTES),
    tin.stdev_minutes(Sources.taxi_in_src.STDEV_MINUTES),
)

model.define(
    tout := TaxiTimeOut.new(
        stand_pier=Sources.taxi_out_src.STAND_PIER,
        departure_runway=Runway.filter_by(designator=Sources.taxi_out_src.DEPARTURE_RUNWAY),
    ),
    tout.avg_minutes(Sources.taxi_out_src.AVG_MINUTES),
    tout.stdev_minutes(Sources.taxi_out_src.STDEV_MINUTES),
)

# =============================================================================
# LOAD: events
# =============================================================================
model.define(
    we := WeatherEvent.new(event_id=Sources.weather_src.EVENT_ID),
    we.start_time(Sources.weather_src.START_TIME),
    we.end_time(Sources.weather_src.END_TIME),
    we.description(Sources.weather_src.DESCRIPTION),
    we.affected_runways(Sources.weather_src.AFFECTED_RUNWAYS),
)

model.define(
    ar := AtfmRegulation.new(regulation_id=Sources.atfm_src.REGULATION_ID),
    ar.affected_destination_icao(Sources.atfm_src.AFFECTED_DESTINATION_ICAO),
    ar.start_time(Sources.atfm_src.START_TIME),
    ar.end_time(Sources.atfm_src.END_TIME),
    ar.reason(Sources.atfm_src.REASON),
)

# =============================================================================
# LOAD: Flight (core, all 16 milestone timestamps + FKs)
# =============================================================================
model.define(
    f := Flight.new(callsign=Sources.flight_src.CALLSIGN),
    f.flight_type(Sources.flight_src.FLIGHT_TYPE),
    f.sobt(Sources.flight_src.SOBT),
    f.icao_type(Sources.flight_src.ICAO_TYPE),
    f.wtc(Sources.flight_src.WTC),
    f.origin_icao(Sources.flight_src.ORIGIN_ICAO),
    f.destination_icao(Sources.flight_src.DESTINATION_ICAO),
)

# FKs: bind separately so a NULL key on any single column doesn't drop the row.
# (Same pattern used for Disruption nullable FKs in supply_chain.py.)
model.define(
    Flight.filter_by(callsign=Sources.flight_src.CALLSIGN).operating_operator(
        Operator.filter_by(iata=Sources.flight_src.OPERATOR_IATA)
    )
)
model.define(
    Flight.filter_by(callsign=Sources.flight_src.CALLSIGN).assigned_aircraft(
        Aircraft.filter_by(registration=Sources.flight_src.AIRCRAFT_REGISTRATION)
    )
)
model.define(
    Flight.filter_by(callsign=Sources.flight_src.CALLSIGN).assigned_stand(
        Stand.filter_by(code=Sources.flight_src.STAND_CODE)
    )
)
model.define(
    Flight.filter_by(callsign=Sources.flight_src.CALLSIGN).assigned_runway(
        Runway.filter_by(designator=Sources.flight_src.RUNWAY_DESIGNATOR)
    )
)
model.define(
    Flight.filter_by(callsign=Sources.flight_src.CALLSIGN).entry_fix(
        Fix.filter_by(name=Sources.flight_src.ENTRY_FIX)
    )
)
model.define(
    Flight.filter_by(callsign=Sources.flight_src.CALLSIGN).handler(
        GroundHandler.filter_by(code=Sources.flight_src.HANDLER_CODE)
    )
)
model.define(
    Flight.filter_by(callsign=Sources.flight_src.CALLSIGN).pax_connections(
        Sources.flight_src.PAX_CONNECTIONS
    )
)
model.define(
    Flight.filter_by(callsign=Sources.flight_src.CALLSIGN).atfm_penalty(
        Sources.flight_src.ATFM_PENALTY
    )
)

# Milestone timestamps (each bound separately to tolerate NULLs)
for _ms in (
    "EOBT", "CTOT", "ATOT_UPSTATION", "FIR_ENTRY_TIME", "TLDT", "ELDT",
    "ALDT", "AIBT", "ACGT", "TOBT", "TSAT", "ABDT", "ARDT", "ASRT",
    "ASAT", "TTOT", "AOBT", "ATOT",
):
    _attr = _ms.lower()
    model.define(
        getattr(
            Flight.filter_by(callsign=Sources.flight_src.CALLSIGN), _attr
        )(getattr(Sources.flight_src, _ms))
    )
del _ms, _attr

# =============================================================================
# DERIVED RULES
# =============================================================================

# Subtype-style flags
model.where(Flight.flight_type == "DEPARTURE").define(Departure(Flight))
model.where(Flight.flight_type == "ARRIVAL").define(Arrival(Flight))

# feeds_callsign: explicit FEEDS_CALLSIGN -> next flight's callsign
_next = Flight.ref()
model.where(
    Flight.callsign == Sources.flight_src.CALLSIGN,
    _next.callsign == Sources.flight_src.FEEDS_CALLSIGN,
).define(feeds_callsign(Flight, _next))

# slot_blocks: loaded from ACDM_DEMO.EHAM.SLOT_BLOCK (source_callsign,
# target_callsign).
_sb_a = Flight.ref()
_sb_b = Flight.ref()
model.where(
    _sb_a.callsign == Sources.slot_block_src.SOURCE_CALLSIGN,
    _sb_b.callsign == Sources.slot_block_src.TARGET_CALLSIGN,
).define(slot_blocks(_sb_a, _sb_b))

# shares_stand: two flights f1, f2 share a stand. Use a conservative window
# defined by SOBT proximity rather than AIBT/AOBT (mixed populations across
# arrivals/departures). Two flights "share a stand" if same stand and the
# |sobt diff| <= 90 min.
from relationalai.semantics.std.datetime import datetime as _dt  # noqa: E402

_f1 = Flight.ref()
_f2 = Flight.ref()
model.where(
    _f1.assigned_stand == _f2.assigned_stand,
    _f1.callsign != _f2.callsign,
    _dt.diff("minute", _f1.sobt, _f2.sobt) >= -90,
    _dt.diff("minute", _f1.sobt, _f2.sobt) <= 90,
).define(shares_stand(_f1, _f2))

# TOBTViolation: |ARDT - TOBT| > 5 minutes (per ICAO MS12 +/- 5 min rule)
# Two derived rules to capture both signs.
model.where(
    _dt.diff("minute", Flight.tobt, Flight.ardt) > 5,
).define(TOBTViolation(Flight))

model.where(
    _dt.diff("minute", Flight.ardt, Flight.tobt) > 5,
).define(TOBTViolation(Flight))

# StormWindowDeparture: TSAT in [15:00, 17:00) on 2026-10-14, DEPARTURE only.
_storm_start = _dt(2026, 10, 14, 15, 0)
_storm_end = _dt(2026, 10, 14, 17, 0)
model.where(
    Departure(Flight),
    Flight.tsat >= _storm_start,
    Flight.tsat < _storm_end,
).define(StormWindowDeparture(Flight))

# PreservedFlight: KL departure with > 80 connecting pax. Drives Act 5 rule.
model.where(
    Departure(Flight),
    Flight.operating_operator == Operator,
    Operator.iata == "KL",
    Flight.pax_connections > 80,
).define(PreservedFlight(Flight))
model.where(PreservedFlight(Flight)).define(Flight.preservation_delay_cap_min(8))

# =============================================================================
# Act 4/5 storm-LP scaffolding (Slot rows, FlightSlot population, helper Properties)
# =============================================================================
# Load 120 slots from Snowflake (STORM_SLOT, minute_offset 0..119, absolute_min
# 900..1019 = minutes-since-midnight of 15:00..16:59).
model.define(
    sl := Slot.new(minute_offset=Sources.storm_slot_src.MINUTE_OFFSET),
    sl.absolute_min(Sources.storm_slot_src.ABSOLUTE_MIN),
)

# FlightSlot rows: one per (StormWindowDeparture, Slot) pair. The decision
# variable `assign` is bound on these rows in the prescriptive Problem.
_fs_f = Flight.ref()
_fs_s = Slot.ref()
model.where(
    StormWindowDeparture(_fs_f),
    _fs_s,
).define(FlightSlot.new(flight_ref=_fs_f, slot_ref=_fs_s))

# Helper: SOBT and CTOT expressed as minute-of-day for arithmetic against
# Slot.absolute_min in the LP. Restricted to StormWindowDeparture (only those
# need the conversion for the LP).
model.where(StormWindowDeparture(Flight)).define(
    Flight.sobt_min_storm(
        _dt.hour(Flight.sobt) * 60 + _dt.minute(Flight.sobt)
    )
)
model.where(
    StormWindowDeparture(Flight),
    Flight.ctot,
).define(
    Flight.ctot_min_storm(
        _dt.hour(Flight.ctot) * 60 + _dt.minute(Flight.ctot)
    )
)

# delay_min per (Flight, Slot): the difference between the slot's absolute
# minute and the flight's SOBT-minute. Computed once at module load so query
# selects can read it directly (avoids array arithmetic in the result helper
# under nbconvert).
_dfs_f = Flight.ref()
_dfs_s = Slot.ref()
_dfs = FlightSlot.ref()
model.where(
    _dfs.flight_ref == _dfs_f,
    _dfs.slot_ref == _dfs_s,
).define(
    _dfs.delay_min(_dfs_s.absolute_min - _dfs_f.sobt_min_storm)
)


# =============================================================================
# DRIVER (validates loads, prints counts and a sample query)
# =============================================================================
def main():
    print("=== concept counts ===")
    concepts = [
        ("Operator", Operator),
        ("Aircraft", Aircraft),
        ("Stand", Stand),
        ("Runway", Runway),
        ("GroundHandler", GroundHandler),
        ("Fix", Fix),
        ("TaxiTimeIn", TaxiTimeIn),
        ("TaxiTimeOut", TaxiTimeOut),
        ("WeatherEvent", WeatherEvent),
        ("AtfmRegulation", AtfmRegulation),
        ("Flight", Flight),
    ]
    for name, c in concepts:
        df = model.where(c).select(aggs.count(c).alias(name)).to_df()
        n = int(df[name].iloc[0]) if not df.empty else 0
        print(f"  {name:18s} {n}")

    print("\n=== derived flags ===")
    for label, rel in (
        ("departures", Departure),
        ("arrivals", Arrival),
        ("tobt_violations", TOBTViolation),
        ("storm_window_deps", StormWindowDeparture),
        ("preserved_kl_high_pax", PreservedFlight),
    ):
        df = (
            model.where(rel(Flight))
            .select(aggs.count(Flight).alias(label))
            .to_df()
        )
        n = int(df[label].iloc[0]) if not df.empty else 0
        print(f"  {label:24s} {n}")

    print("\n=== feeds_callsign explicit edges ===")
    src = Flight.ref()
    tgt = Flight.ref()
    df = (
        model.where(feeds_callsign(src, tgt))
        .select(src.callsign.alias("from"), tgt.callsign.alias("to"))
        .to_df()
    )
    print(df.to_string(index=False))

    print("\n=== schema summary ===")
    print(f"Concepts declared: {len(concepts)}")
    print(f"Schema available; use inspect.schema(model) for details.")


if __name__ == "__main__":
    main()
