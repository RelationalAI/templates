#!/usr/bin/env python3
"""
EHAM Schiphol A-CDM Demo - Synthetic Data Generator
====================================================

Generates a defendable synthetic dataset for a RelationalAI A-CDM demo,
anchored to Amsterdam Schiphol (EHAM) ops on Wednesday 14 October 2026.

Outputs (written to ./out/):
  - eham_demo_ddl.sql              Snowflake DDL: database, schema, tables
  - eham_demo_reference.sql        INSERT statements for dim tables
  - eham_demo_load.sql             COPY INTO statements + sanity queries
  - eham_demo_flights.csv          ~320 flights with all 16 ICAO milestones
  - eham_demo_validation.sql       Queries that prove the data fits the talk track

The dataset is reproducible: run with --seed N for variations.

Curated narrative flights (hard-coded so the talk track returns the right rows):
  - KL1234 inbound KJFK late at MS5  -> feeds KL1235 outbound (rotation)
    Stand E18 conflict cascades to KL1402 (2nd hop)
    Stand D54 conflict to HV5821 (2nd hop)
    Stand F08 conflict to AF1241 (2nd hop)
    Rotation chain to KL1601 (3rd hop)
  - 4 MS5 forecast conflicts: DL0036/E18, KL0691/F04, AF1641/D88, BA0432/B26
  - TOBT violations in last 4h binned by handler: KLG 7, AGS 5, DNATA 3, MENZIES 2
  - 47 flights with TSAT in 15:00-17:00 window for the prescriptive solve
  - KL691: outbound to RJTT (Tokyo) with >80 connecting pax for the preservation rule

Author: Piotr Kraus
"""

from __future__ import annotations
import csv
import os
import random
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# 0. Configuration
# ---------------------------------------------------------------------------

DEMO_DATE = date(2026, 10, 14)
DEMO_NOW = datetime(2026, 10, 14, 14, 30)  # "current time" for the talk track
SEED = int(os.environ.get("EHAM_DEMO_SEED", "42"))

OUT_DIR = Path(__file__).parent / "out"
OUT_DIR.mkdir(exist_ok=True)

DB_NAME = "ACDM_DEMO"
SCHEMA_NAME = "EHAM"
FQN = f"{DB_NAME}.{SCHEMA_NAME}"


# ---------------------------------------------------------------------------
# 1. Reference data: operators, aircraft, stands, runways, fixes, handlers
# ---------------------------------------------------------------------------

@dataclass
class Operator:
    iata: str
    icao: str
    name: str
    alliance: Optional[str]
    min_turn_narrowbody_min: int
    min_turn_widebody_min: int


OPERATORS: list[Operator] = [
    Operator("KL", "KLM", "KLM Royal Dutch Airlines", "SkyTeam", 40, 90),
    Operator("HV", "TRA", "Transavia",                None,       25, 0),
    Operator("AF", "AFR", "Air France",               "SkyTeam", 45, 90),
    Operator("DL", "DAL", "Delta Air Lines",          "SkyTeam", 0,  120),
    Operator("KQ", "KQA", "Kenya Airways",            "SkyTeam", 0,  120),
    Operator("BA", "BAW", "British Airways",          "Oneworld", 35, 0),
    Operator("LH", "DLH", "Lufthansa",                "Star",     35, 0),
    Operator("EZY","EZY", "easyJet",                  None,       25, 0),
    Operator("FR", "RYR", "Ryanair",                  None,       25, 0),
    Operator("W6", "WZZ", "Wizz Air",                 None,       25, 0),
    Operator("TK", "THY", "Turkish Airlines",         "Star",     35, 90),
    Operator("EK", "UAE", "Emirates",                 None,       0,  90),
    Operator("SQ", "SIA", "Singapore Airlines",       "Star",     0,  90),
    Operator("5X", "UPS", "UPS Airlines",             None,       0,  90),
]
OP_BY_IATA = {o.iata: o for o in OPERATORS}

# Fleet types each operator commonly uses at EHAM
# (Wake category: L=Light, M=Medium, H=Heavy, J=Super)
AIRCRAFT_TYPES: dict[str, list[tuple[str, str, int]]] = {
    # operator: [(icao_type, wtc, seats), ...]
    "KL": [("B738", "M", 186), ("B739", "M", 188), ("B737", "M", 142),
           ("E175", "M", 88),  ("E190", "M", 100), ("E195", "M", 132),
           ("A332", "H", 268), ("A333", "H", 292),
           ("B772", "H", 320), ("B77W", "H", 408),
           ("B789", "H", 294), ("B78X", "H", 318),
           ("A359", "H", 314)],
    "HV": [("B738", "M", 189), ("B38M", "M", 197)],
    "AF": [("A20N", "M", 174), ("A320", "M", 174), ("A319", "M", 143), ("A223", "M", 149)],
    "DL": [("A333", "H", 282), ("A339", "H", 281), ("B764", "H", 241), ("A359", "H", 306)],
    "KQ": [("B788", "H", 234)],
    "BA": [("A319", "M", 144), ("A320", "M", 165), ("A321", "M", 192)],
    "LH": [("A319", "M", 138), ("A320", "M", 168), ("A21N", "M", 215)],
    "EZY":[("A319", "M", 156), ("A320", "M", 186), ("A20N", "M", 186)],
    "FR": [("B738", "M", 189)],
    "W6": [("A320", "M", 180), ("A21N", "M", 239)],
    "TK": [("A321", "M", 188), ("A333", "H", 289)],
    "EK": [("B77W", "H", 360)],
    "SQ": [("B77W", "H", 264), ("A359", "H", 253)],
    "5X": [("B763", "H", 0)],   # cargo
}

# Realistic registration patterns
REG_PATTERNS = {
    "KL": "PH-{l1}{l2}{l3}",     # e.g. PH-BXM
    "HV": "PH-H{d1}{l1}",        # e.g. PH-HSI
    "AF": "F-G{l1}{l2}{l3}",
    "DL": "N{d1}{d2}{d3}NW",
    "KQ": "5Y-KZ{l1}",
    "BA": "G-EU{l1}{l2}",
    "LH": "D-AI{l1}{l2}",
    "EZY": "G-EZ{l1}{l2}",
    "FR":  "EI-D{l1}{l2}",
    "W6":  "HA-LV{l1}",
    "TK":  "TC-JV{l1}",
    "EK":  "A6-EE{l1}",
    "SQ":  "9V-SW{l1}",
    "5X":  "N{d1}{d2}{d3}UP",
}


def gen_reg(op: str, rng: random.Random) -> str:
    pat = REG_PATTERNS[op]
    out = pat
    for ch in "123456789":
        out = out.replace("{d" + ch + "}", str(rng.randint(0, 9)), 1)
    for ch in "123456":
        out = out.replace("{l" + ch + "}", rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ"), 1)
    return out


# EHAM stands - real pier layout, contact/remote, Schengen flags
@dataclass
class Stand:
    code: str
    pier: str
    is_contact: bool
    max_wtc: str
    schengen: bool


def build_stands() -> list[Stand]:
    s: list[Stand] = []
    # B-pier: narrowbody Schengen, buses + some contact
    for n in range(11, 37):
        s.append(Stand(f"B{n:02d}", "B", n % 3 != 0, "M", True))
    # C-pier: Schengen contact, narrowbody
    for n in range(4, 17):
        s.append(Stand(f"C{n:02d}", "C", True, "M", True))
    # D-pier: split Schengen/non-Schengen, contact, all types
    for n in [2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 50, 52, 54, 56, 58, 60, 80, 82, 84, 86, 88]:
        s.append(Stand(f"D{n:02d}", "D", True, "H", n < 50))  # D02-D30 Schengen, D50+ non-Schengen
    # E-pier: Schengen contact
    for n in [2, 4, 6, 8, 10, 14, 16, 18, 20, 22, 24]:
        s.append(Stand(f"E{n:02d}", "E", True, "H", True))
    # F-pier: non-Schengen contact, widebody capable
    for n in [2, 3, 4, 5, 6, 7, 8, 9]:
        s.append(Stand(f"F{n:02d}", "F", True, "H", False))
    # G-pier: non-Schengen contact, widebody
    for n in [2, 3, 4, 5, 6, 7, 8, 9]:
        s.append(Stand(f"G{n:02d}", "G", True, "J", False))
    # H-pier (new 2024): Schengen
    for n in [1, 2, 3, 4, 5, 6, 7, 8]:
        s.append(Stand(f"H{n:02d}", "H", True, "M", True))
    # M-pier: non-Schengen overflow
    for n in [1, 2, 3, 4, 5, 6, 7]:
        s.append(Stand(f"M{n:02d}", "M", True, "H", False))
    # Remote stands (low cost, cargo)
    for n in range(1, 10):
        s.append(Stand(f"R{n:02d}", "R", False, "H", False))
    return s


STANDS = build_stands()
STAND_BY_CODE = {s.code: s for s in STANDS}


# Runways - real EHAM designators
@dataclass
class Runway:
    designator: str
    name: str
    length_m: int
    used_for: str  # LANDING, DEPARTURE, BOTH


RUNWAYS: list[Runway] = [
    Runway("18R/36L", "Polderbaan",       3800, "LANDING"),
    Runway("18C/36C", "Zwanenburgbaan",   3300, "BOTH"),
    Runway("18L/36R", "Aalsmeerbaan",     3400, "DEPARTURE"),
    Runway("06/24",   "Kaagbaan",         3500, "BOTH"),
    Runway("09/27",   "Buitenveldertbaan",3453, "BOTH"),
    Runway("04/22",   "Schiphol-Oost",    2014, "BOTH"),
]

# For storm scenario in the talk track:
# Storm closes 18C 15:00-17:00, forces single-runway departures off 18L


# STAR fixes - real EHAM Initial Approach Fixes
@dataclass
class Fix:
    name: str
    fix_type: str
    typical_landing_rwy: str


FIXES: list[Fix] = [
    Fix("ARTIP", "IAF", "27"),     # East, typically vectored to 27 or 18C
    Fix("SUGOL", "IAF", "18C"),    # North, to 18C or 06
    Fix("RIVER", "IAF", "18C"),    # NW, to 18C
    Fix("NIRSI", "IAF", "18R"),    # NW, used for Polderbaan
]


# Ground handlers at EHAM
@dataclass
class Handler:
    code: str
    name: str


HANDLERS: list[Handler] = [
    Handler("KLG",     "KLM Ground Services"),
    Handler("AGS",     "Aviapartner Ground Services"),
    Handler("DNATA",   "dnata Aviation Services Netherlands"),
    Handler("MENZIES", "Menzies Aviation"),
]


# Taxi-in time matrix: (fix, runway, pier) -> (mean, std) in minutes
# Polderbaan (18R via NIRSI) is famously long-taxi
TAXI_IN_MATRIX = {
    # (fix, runway, pier_or_R_for_remote): (mean, stdev)
    ("SUGOL", "18C", "B"): (8, 2),
    ("SUGOL", "18C", "C"): (7, 2),
    ("SUGOL", "18C", "D"): (7, 2),
    ("SUGOL", "18C", "E"): (6, 2),
    ("SUGOL", "18C", "F"): (6, 2),
    ("SUGOL", "18C", "G"): (7, 2),
    ("SUGOL", "18C", "H"): (8, 2),
    ("SUGOL", "18C", "M"): (7, 2),
    ("SUGOL", "18C", "R"): (10, 3),

    ("RIVER", "18C", "B"): (8, 2),
    ("RIVER", "18C", "C"): (7, 2),
    ("RIVER", "18C", "D"): (7, 2),
    ("RIVER", "18C", "E"): (6, 2),
    ("RIVER", "18C", "F"): (6, 2),
    ("RIVER", "18C", "G"): (7, 2),
    ("RIVER", "18C", "H"): (8, 2),
    ("RIVER", "18C", "M"): (7, 2),
    ("RIVER", "18C", "R"): (10, 3),

    ("ARTIP", "27", "B"): (7, 2),
    ("ARTIP", "27", "C"): (6, 2),
    ("ARTIP", "27", "D"): (6, 2),
    ("ARTIP", "27", "E"): (5, 2),
    ("ARTIP", "27", "F"): (5, 2),
    ("ARTIP", "27", "G"): (6, 2),
    ("ARTIP", "27", "H"): (7, 2),
    ("ARTIP", "27", "M"): (6, 2),
    ("ARTIP", "27", "R"): (9, 3),

    ("NIRSI", "18R", "B"): (12, 3),
    ("NIRSI", "18R", "C"): (11, 3),
    ("NIRSI", "18R", "D"): (11, 3),
    ("NIRSI", "18R", "E"): (11, 3),
    ("NIRSI", "18R", "F"): (10, 3),
    ("NIRSI", "18R", "G"): (10, 3),
    ("NIRSI", "18R", "H"): (12, 3),
    ("NIRSI", "18R", "M"): (10, 3),
    ("NIRSI", "18R", "R"): (5, 2),   # remote stands near 18R holding bay
}

# Taxi-out: (pier, runway) -> (mean, std)
TAXI_OUT_MATRIX = {
    ("B", "18L"): (5, 2),
    ("C", "18L"): (7, 2),
    ("D", "18L"): (8, 2),
    ("E", "18L"): (9, 2),
    ("F", "18L"): (10, 3),
    ("G", "18L"): (11, 3),
    ("H", "18L"): (6, 2),
    ("M", "18L"): (10, 3),
    ("R", "18L"): (7, 2),

    ("B", "24"): (10, 3),
    ("C", "24"): (11, 3),
    ("D", "24"): (12, 3),
    ("E", "24"): (13, 3),
    ("F", "24"): (14, 4),
    ("G", "24"): (15, 4),
    ("H", "24"): (10, 3),
    ("M", "24"): (14, 4),
    ("R", "24"): (11, 3),

    ("B", "09"): (8, 2),
    ("C", "09"): (9, 2),
    ("D", "09"): (10, 3),
    ("E", "09"): (11, 3),
    ("F", "09"): (12, 3),
    ("G", "09"): (13, 3),
    ("H", "09"): (8, 2),
    ("M", "09"): (12, 3),
    ("R", "09"): (9, 2),
}


# Common KL routes from EHAM with realistic SOBT clusters
KL_ROUTES = {
    # Asia long-haul (afternoon/evening dep from EHAM)
    "RJTT": ("HND Tokyo",        "H", "F", (12, 30)),  # KL861 area
    "VHHH": ("HKG Hong Kong",    "H", "F", (14, 0)),
    "RKSI": ("ICN Seoul",        "H", "F", (15, 30)),
    "ZSPD": ("PVG Shanghai",     "H", "F", (16, 0)),
    "WSSS": ("SIN Singapore",    "H", "F", (17, 30)),
    "VTBS": ("BKK Bangkok",      "H", "F", (15, 0)),
    "OMDB": ("DXB Dubai",        "H", "F", (10, 30)),
    "VABB": ("BOM Mumbai",       "H", "F", (11, 0)),
    "VIDP": ("DEL Delhi",        "H", "F", (12, 0)),
    # Americas (morning/midday)
    "KJFK": ("JFK New York",     "H", "F", (10, 30)),
    "KORD": ("ORD Chicago",      "H", "F", (11, 30)),
    "KATL": ("ATL Atlanta",      "H", "F", (10, 0)),
    "KIAD": ("IAD Washington",   "H", "F", (12, 0)),
    "KLAX": ("LAX Los Angeles",  "H", "F", (13, 0)),
    "KSFO": ("SFO San Francisco","H", "F", (12, 30)),
    "KSEA": ("SEA Seattle",      "H", "F", (13, 0)),
    "KIAH": ("IAH Houston",      "H", "F", (14, 30)),
    "MMUN": ("CUN Cancun",       "H", "F", (13, 0)),
    "SBGR": ("GRU Sao Paulo",    "H", "F", (20, 30)),
    "SAEZ": ("EZE Buenos Aires", "H", "F", (21, 0)),
    # Africa
    "HKJK": ("NBO Nairobi",      "H", "F", (20, 0)),
    "FACT": ("CPT Cape Town",    "H", "F", (19, 30)),
    "DNMM": ("LOS Lagos",        "H", "F", (21, 0)),
    "HAAB": ("ADD Addis Ababa",  "H", "F", (20, 30)),
    "DAAG": ("ALG Algiers",      "M", "C", (8, 30)),
    "GMMN": ("CMN Casablanca",   "M", "C", (8, 0)),
    # European hubs (short-haul, all day)
    "EGLL": ("LHR London",       "M", "C", None),
    "EGKK": ("LGW Gatwick",      "M", "C", None),
    "EDDF": ("FRA Frankfurt",    "M", "C", None),
    "EDDM": ("MUC Munich",       "M", "C", None),
    "LFPG": ("CDG Paris",        "M", "C", None),
    "LEMD": ("MAD Madrid",       "M", "C", None),
    "LEBL": ("BCN Barcelona",    "M", "B", None),
    "LIRF": ("FCO Rome",         "M", "C", None),
    "LIMC": ("MXP Milan",        "M", "C", None),
    "LSZH": ("ZRH Zurich",       "M", "C", None),
    "EKCH": ("CPH Copenhagen",   "M", "C", None),
    "ESSA": ("ARN Stockholm",    "M", "C", None),
    "ENGM": ("OSL Oslo",         "M", "C", None),
    "EFHK": ("HEL Helsinki",     "M", "C", None),
    "EPWA": ("WAW Warsaw",       "M", "C", None),
    "LKPR": ("PRG Prague",       "M", "C", None),
    "LOWW": ("VIE Vienna",       "M", "C", None),
    "LHBP": ("BUD Budapest",     "M", "C", None),
    "EIDW": ("DUB Dublin",       "M", "C", None),
    "LGAV": ("ATH Athens",       "M", "C", None),
    "LTBA": ("IST Istanbul",     "M", "C", None),
    "GCLP": ("LPA Las Palmas",   "M", "C", None),
}


# ---------------------------------------------------------------------------
# 2. Helpers
# ---------------------------------------------------------------------------

def fmt_ts(dt: Optional[datetime]) -> str:
    if dt is None:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def normal_clamped(rng: random.Random, mu: float, sigma: float,
                   lo: float, hi: float) -> float:
    v = rng.gauss(mu, sigma)
    return max(lo, min(hi, v))


def add_min(t: datetime, m: float) -> datetime:
    return t + timedelta(minutes=round(m))


# ---------------------------------------------------------------------------
# 3. Flight model
# ---------------------------------------------------------------------------

@dataclass
class Flight:
    callsign: str
    sobt: datetime
    operator_iata: str
    aircraft_registration: str
    icao_type: str
    wtc: str
    flight_type: str    # ARRIVAL, DEPARTURE
    origin_icao: str
    destination_icao: str
    stand_code: str
    runway_designator: str
    entry_fix: Optional[str]
    handler_code: str
    pax_connections: int
    atfm_penalty: float

    # 16 milestones
    eobt: Optional[datetime] = None
    ctot: Optional[datetime] = None
    atot_upstation: Optional[datetime] = None
    fir_entry_time: Optional[datetime] = None
    tldt: Optional[datetime] = None
    eldt: Optional[datetime] = None
    aldt: Optional[datetime] = None
    aibt: Optional[datetime] = None
    acgt: Optional[datetime] = None
    tobt: Optional[datetime] = None
    tsat: Optional[datetime] = None
    abdt: Optional[datetime] = None
    ardt: Optional[datetime] = None
    asrt: Optional[datetime] = None
    asat: Optional[datetime] = None
    ttot: Optional[datetime] = None
    aobt: Optional[datetime] = None
    atot: Optional[datetime] = None

    feeds_callsign: Optional[str] = None
    feeds_sobt: Optional[datetime] = None
    is_eligible_acdm: bool = True

    def csv_row(self) -> list[str]:
        return [
            self.callsign, fmt_ts(self.sobt),
            self.operator_iata, self.aircraft_registration,
            self.icao_type, self.wtc, self.flight_type,
            self.origin_icao, self.destination_icao,
            self.stand_code, self.runway_designator, self.entry_fix or "",
            self.handler_code, str(self.pax_connections), f"{self.atfm_penalty:.2f}",
            fmt_ts(self.eobt),
            fmt_ts(self.ctot),
            fmt_ts(self.atot_upstation),
            fmt_ts(self.fir_entry_time),
            fmt_ts(self.tldt),
            fmt_ts(self.eldt),
            fmt_ts(self.aldt),
            fmt_ts(self.aibt),
            fmt_ts(self.acgt),
            fmt_ts(self.tobt),
            fmt_ts(self.tsat),
            fmt_ts(self.abdt),
            fmt_ts(self.ardt),
            fmt_ts(self.asrt),
            fmt_ts(self.asat),
            fmt_ts(self.ttot),
            fmt_ts(self.aobt),
            fmt_ts(self.atot),
            self.feeds_callsign or "",
            fmt_ts(self.feeds_sobt),
            "TRUE" if self.is_eligible_acdm else "FALSE",
        ]


# ---------------------------------------------------------------------------
# 4. Milestone synthesis
# ---------------------------------------------------------------------------

def synthesize_arrival(f: Flight, rng: random.Random,
                       lateness_offset_min: float = 0.0,
                       stop_at_ms5: bool = False) -> None:
    """Populate milestones for an inbound flight.

    Convention: f.sobt represents the Scheduled Time of Arrival (STA) at EHAM,
    i.e. the scheduled in-block time at the destination. This matches the AODB
    convention where every flight's SOBT is in the local destination/origin
    time at EHAM, regardless of direction.

    lateness_offset_min: minutes of delay vs scheduled in-block.
    stop_at_ms5: if True, the flight is still en route at "demo_now" and is at
                 MS5 final approach. MS6 (ALDT) and downstream are left as None.
    """
    cruise_table = {
        # to EHAM, in minutes
        "KJFK": 425, "KORD": 480, "KATL": 510, "KIAD": 430,
        "KLAX": 605, "KSFO": 620, "KSEA": 575, "KIAH": 565,
        "MMUN": 595, "SBGR": 690, "SAEZ": 750,
        "RJTT": 695, "VHHH": 705, "RKSI": 660, "ZSPD": 670,
        "WSSS": 770, "VTBS": 660, "OMDB": 385, "VABB": 470, "VIDP": 460,
        "HKJK": 540, "FACT": 700, "DNMM": 410, "HAAB": 470,
        "DAAG": 165, "GMMN": 215,
        "EGLL": 75, "EGKK": 75, "EDDF": 65, "EDDM": 90, "LFPG": 75,
        "LEMD": 145, "LEBL": 125, "LIRF": 145, "LIMC": 110, "LSZH": 95,
        "EKCH": 80, "ESSA": 125, "ENGM": 100, "EFHK": 140, "EPWA": 110,
        "LKPR": 90, "LOWW": 110, "LHBP": 130, "EIDW": 95, "LGAV": 195,
        "LTBA": 215, "GCLP": 270, "KMSP": 530, "KDTW": 535,
    }
    cruise_min = cruise_table.get(f.origin_icao, 120)
    cruise_min += rng.gauss(0, 5)  # noise

    # Working backward from SOBT (= STA = scheduled in-block at EHAM)
    target_aibt = f.sobt + timedelta(minutes=lateness_offset_min)

    pier = STAND_BY_CODE[f.stand_code].pier
    rwy = f.runway_designator.split("/")[0]
    key = (f.entry_fix, rwy, pier)
    if key in TAXI_IN_MATRIX:
        mean, sd = TAXI_IN_MATRIX[key]
    else:
        mean, sd = 8, 2
    taxi_in = max(1, round(rng.gauss(mean, sd)))
    target_aldt = target_aibt - timedelta(minutes=taxi_in)

    # MS5 ELDT/TLDT: AMAN refines close to landing
    f.tldt = target_aldt - timedelta(minutes=2)
    f.eldt = target_aldt - timedelta(minutes=2)

    # MS4 FIR entry: EHAA FIR ~25 min before landing for short/medium-haul,
    # 35 min for long-haul
    fir_offset = 25 + rng.gauss(0, 3) if cruise_min < 240 else 35 + rng.gauss(0, 5)
    f.fir_entry_time = target_aldt - timedelta(minutes=fir_offset)

    # MS3 ATOT upstation = ALDT - cruise
    f.atot_upstation = target_aldt - timedelta(minutes=cruise_min)

    if not stop_at_ms5:
        # Flight has landed - populate MS6+
        f.aldt = target_aldt
        f.aibt = target_aibt
        f.acgt = f.aibt    # normal turnaround
    # Else: ALDT/AIBT/ACGT remain None (flight still en route at demo_now)


def synthesize_departure(f: Flight, rng: random.Random,
                         tobt_dev_min: Optional[float] = None,
                         ardt_dev_min: Optional[float] = None,
                         force_compliant: bool = False) -> None:
    """Populate MS9-MS16 for an outbound flight.

    tobt_dev_min: TOBT - EOBT in minutes (None = sample from carrier dist)
    ardt_dev_min: ARDT - TOBT in minutes (None = sample from compliance dist)
    """
    # MS1: EOBT - usually = SOBT for KL mainline, slight drift for LCC
    if f.operator_iata in ("KL", "DL", "AF", "KQ"):
        eobt_drift = rng.gauss(0, 1)
    else:
        eobt_drift = rng.gauss(2, 4)  # LCC drift
    f.eobt = add_min(f.sobt, eobt_drift)

    # MS9 TOBT
    if tobt_dev_min is None:
        if f.operator_iata == "KL":
            tobt_dev_min = rng.gauss(2, 4)
        elif f.operator_iata in ("DL", "AF", "KQ"):
            tobt_dev_min = rng.gauss(-1, 3)
        else:
            tobt_dev_min = rng.gauss(6, 8)
    f.tobt = add_min(f.eobt, tobt_dev_min)

    # MS10 TSAT
    tsat_delay = 0
    if 7 <= f.sobt.hour <= 10 or 16 <= f.sobt.hour <= 19:
        # peak bank - sequencing delay
        tsat_delay = rng.uniform(0, 10)
    f.tsat = add_min(f.tobt, tsat_delay)

    # MS11 ABDT - boarding usually 25-35 min before TOBT
    f.abdt = add_min(f.tobt, -rng.uniform(25, 35))

    # MS12 ARDT
    if ardt_dev_min is None:
        if force_compliant:
            # Clamp to ensure |ARDT - TOBT| <= 5min (talk-track-safe)
            ardt_dev_min = rng.gauss(0, 2.5)
            ardt_dev_min = max(-4.5, min(4.5, ardt_dev_min))
        else:
            # 75% compliant: N(0, 5)
            # 15% late: mean +8, sigma 4
            # 10% early: mean -3, sigma 2
            r = rng.random()
            if r < 0.75:
                ardt_dev_min = rng.gauss(0, 5)
            elif r < 0.90:
                ardt_dev_min = rng.gauss(8, 4)
            else:
                ardt_dev_min = rng.gauss(-3, 2)
    f.ardt = add_min(f.tobt, ardt_dev_min)

    # MS13 ASRT - shortly after ARDT
    f.asrt = add_min(f.ardt, rng.uniform(0, 2))

    # MS14 ASAT
    f.asat = add_min(f.tsat, rng.gauss(0, 2))

    # MS15 AOBT - off block
    f.aobt = add_min(max(f.asat, f.ardt), rng.uniform(1, 3))

    # Taxi out
    pier = STAND_BY_CODE[f.stand_code].pier
    rwy = f.runway_designator.split("/")[0] if "/" in f.runway_designator else f.runway_designator
    key = (pier, rwy)
    if key in TAXI_OUT_MATRIX:
        mean, sd = TAXI_OUT_MATRIX[key]
    else:
        mean, sd = 9, 3
    taxi_out = max(2, round(rng.gauss(mean, sd)))
    f.ttot = add_min(f.aobt, taxi_out)
    # ATOT slight queue noise
    f.atot = add_min(f.ttot, rng.uniform(0, 3))

    # MS2 CTOT for ~22% of flights (Eurocontrol regulation rate)
    if rng.random() < 0.22:
        # CTOT compliance: 78% within [-5, +10] min of TTOT
        if rng.random() < 0.78:
            f.ctot = add_min(f.ttot, rng.uniform(-5, 10))
        else:
            f.ctot = add_min(f.ttot, rng.uniform(-30, -5))
        # ATFM penalty weight
        f.atfm_penalty = rng.uniform(1, 5)


# ---------------------------------------------------------------------------
# 5. Curated narrative flights
# ---------------------------------------------------------------------------

def build_curated_flights(rng: random.Random) -> list[Flight]:
    """The flights that must exist for the talk track to land.

    These are hand-positioned to produce the expected query outputs:
      - Act 1 (rules): per-handler TOBT violations 7/5/3/2
      - Act 2 (graph): KL1234 cascade chain
      - Act 3 (predictive): 4 MS5 forecast conflicts
      - Act 4 (prescriptive): 47 flights in 15:00-17:00 TSAT window
      - Act 5 (superalignment): KL691 high-connector preserved flight
    """
    flights: list[Flight] = []

    # ----- The KL1234 cascade scenario -----------------------------------
    # KL1234: inbound from KJFK, 35 min late, currently at MS5 final approach
    # SOBT = STA at EHAM (scheduled in-block) = 14:06
    # Lateness 35 min -> actual AIBT would be 14:41; ALDT 14:35; TLDT 14:33
    kl1234 = Flight(
        callsign="KL1234", sobt=datetime(2026, 10, 14, 14, 6),
        operator_iata="KL",
        aircraft_registration="PH-BVA",
        icao_type="B77W", wtc="H",
        flight_type="ARRIVAL",
        origin_icao="KJFK", destination_icao="EHAM",
        stand_code="E18", runway_designator="18C/36C",
        entry_fix="SUGOL", handler_code="KLG",
        pax_connections=124, atfm_penalty=0.0,
    )
    # KL1234 is still en route at demo_now=14:30. Stop at MS5 (no ALDT/AIBT).
    synthesize_arrival(kl1234, rng, lateness_offset_min=35.0, stop_at_ms5=True)
    flights.append(kl1234)

    # KL1235: outbound, same aircraft as KL1234 (rotation)
    # Originally scheduled SOBT 14:50, now TOBT becomes infeasible
    kl1235 = Flight(
        callsign="KL1235", sobt=datetime(2026, 10, 14, 14, 50),
        operator_iata="KL",
        aircraft_registration="PH-BVA",   # same tail as KL1234
        icao_type="B77W", wtc="H",
        flight_type="DEPARTURE",
        origin_icao="EHAM", destination_icao="VTBS",  # to Bangkok
        stand_code="E18", runway_designator="18L/36R",
        entry_fix=None, handler_code="KLG",
        pax_connections=98, atfm_penalty=2.5,
    )
    synthesize_departure(kl1235, rng)
    # Link rotation: KL1234 feeds KL1235
    kl1234.feeds_callsign = "KL1235"
    kl1234.feeds_sobt = kl1235.sobt
    flights.append(kl1235)

    # KL1402: 2nd-hop conflict on stand E18 - was scheduled to use E18 next
    # Different aircraft, different rotation, but shares stand window
    kl1402 = Flight(
        callsign="KL1402", sobt=datetime(2026, 10, 14, 15, 20),
        operator_iata="KL",
        aircraft_registration="PH-BXM",
        icao_type="B738", wtc="M",
        flight_type="DEPARTURE",
        origin_icao="EHAM", destination_icao="LEMD",  # Madrid
        stand_code="E18", runway_designator="18L/36R",
        entry_fix=None, handler_code="KLG",
        pax_connections=42, atfm_penalty=1.0,
    )
    synthesize_departure(kl1402, rng)
    flights.append(kl1402)

    # HV5821: stand D54 conflict (different stand, different operator,
    # demonstrates cross-operator cascade)
    # The cascade reaches HV5821 via a chain: KL1234 occupies E18 longer,
    # E18 widebody overflow takes a D-stand normally used by HV.
    # For demo simplicity, we wire HV5821 to D54 conflict with an upstream KL flight.
    hv5821 = Flight(
        callsign="HV5821", sobt=datetime(2026, 10, 14, 14, 35),
        operator_iata="HV",
        aircraft_registration="PH-HSI",
        icao_type="B738", wtc="M",
        flight_type="DEPARTURE",
        origin_icao="EHAM", destination_icao="LEBL",  # Barcelona
        stand_code="D54", runway_designator="18L/36R",
        entry_fix=None, handler_code="AGS",
        pax_connections=18, atfm_penalty=0.5,
    )
    # Force compliant: HV5821 is a stand-conflict victim, not a TOBT violator.
    synthesize_departure(hv5821, rng, force_compliant=True)
    flights.append(hv5821)

    # An upstream KL inbound that creates the D54 conflict
    # SOBT = STA at EHAM (scheduled in-block). 40 min late. Already landed,
    # parked at D54, AOBT pushed back to 14:50 so window overlaps HV5821 14:35.
    kl0641 = Flight(
        callsign="KL0641", sobt=datetime(2026, 10, 14, 12, 30),
        operator_iata="KL",
        aircraft_registration="PH-BHF",
        icao_type="B789", wtc="H",
        flight_type="ARRIVAL",
        origin_icao="KIAH", destination_icao="EHAM",
        stand_code="D54", runway_designator="18C/36C",
        entry_fix="SUGOL", handler_code="KLG",
        pax_connections=87, atfm_penalty=0.0,
    )
    synthesize_arrival(kl0641, rng, lateness_offset_min=40.0)  # actual AIBT 13:10
    # KL0641 will park at D54 until its onward outbound pushes (not modeled
    # here as an outbound, but the stand occupancy window extends via the
    # cascade graph using the aircraft rotation).
    flights.append(kl0641)

    # AF1241: 2nd-hop conflict, stand F08 (non-Schengen)
    af1241 = Flight(
        callsign="AF1241", sobt=datetime(2026, 10, 14, 16, 0),
        operator_iata="AF",
        aircraft_registration="F-GUGA",
        icao_type="A20N", wtc="M",
        flight_type="DEPARTURE",
        origin_icao="EHAM", destination_icao="LFPG",  # Paris CDG
        stand_code="F08", runway_designator="18L/36R",
        entry_fix=None, handler_code="DNATA",
        pax_connections=66, atfm_penalty=2.0,
    )
    synthesize_departure(af1241, rng)
    flights.append(af1241)

    # An upstream KL widebody that creates the F08 conflict
    # Different callsign to avoid clashing with KL0691 MS5 forecast flight below.
    # KL0712 inbound from SIN, parks at F08, overstays - conflicts with AF1241.
    kl0712 = Flight(
        callsign="KL0712", sobt=datetime(2026, 10, 14, 13, 45),
        operator_iata="KL",
        aircraft_registration="PH-BVN",
        icao_type="B77W", wtc="H",
        flight_type="ARRIVAL",
        origin_icao="WSSS", destination_icao="EHAM",
        stand_code="F08", runway_designator="18C/36C",
        entry_fix="RIVER", handler_code="KLG",
        pax_connections=156, atfm_penalty=0.0,
    )
    synthesize_arrival(kl0712, rng, lateness_offset_min=30.0)  # AIBT 14:15
    flights.append(kl0712)

    # KL1601: 3rd-hop in the chain via KL1402's aircraft rotation
    # PH-BXM aircraft from KL1402 was supposed to do KL1601 to FRA next
    kl1601 = Flight(
        callsign="KL1601", sobt=datetime(2026, 10, 14, 17, 10),
        operator_iata="KL",
        aircraft_registration="PH-BXM",  # same as KL1402
        icao_type="B738", wtc="M",
        flight_type="DEPARTURE",
        origin_icao="EHAM", destination_icao="EDDF",  # Frankfurt
        stand_code="C08", runway_designator="18L/36R",
        entry_fix=None, handler_code="KLG",
        pax_connections=51, atfm_penalty=1.5,
    )
    synthesize_departure(kl1601, rng)
    kl1402.feeds_callsign = "KL1601"
    kl1402.feeds_sobt = kl1601.sobt
    flights.append(kl1601)

    # ----- 4 MS5 forecast conflicts (Act 3 - predictive) ----------------
    # These flights are at MS5 (TLDT set, ALDT not yet) at the demo "now" 14:30
    # The talk-track output shows:
    #   DL0036 / E18 / predicted AIBT 14:42 / 0.73
    #   KL0691 / F04 / predicted AIBT 14:51 / 0.58   (a 2nd KL0691 - inbound!)
    #   AF1641 / D88 / predicted AIBT 15:07 / 0.41
    #   BA0432 / B26 / predicted AIBT 14:59 / 0.22
    # For the demo, we set TLDT close to "now" so they appear in the forecast
    dl0036 = Flight(
        callsign="DL0036", sobt=datetime(2026, 10, 14, 7, 30),
        operator_iata="DL",
        aircraft_registration="N810NW",
        icao_type="A339", wtc="H",
        flight_type="ARRIVAL",
        origin_icao="KATL", destination_icao="EHAM",
        stand_code="E18", runway_designator="18C/36C",
        entry_fix="SUGOL", handler_code="KLG",
        pax_connections=72, atfm_penalty=0.0,
    )
    # Tweak so TLDT is ~14:35 (5 min from "now"), AIBT forecast ~14:42
    dl0036.atot_upstation = datetime(2026, 10, 14, 5, 50)
    dl0036.fir_entry_time = datetime(2026, 10, 14, 14, 10)
    dl0036.tldt = datetime(2026, 10, 14, 14, 35)
    dl0036.eldt = datetime(2026, 10, 14, 14, 35)
    # ALDT not set (not yet landed)
    flights.append(dl0036)

    # NOTE: KL0691 callsign reuse: the inbound from VHHH at 08:00 is a different
    # operational day rotation; the MS5 conflict flight is a 2nd KL flight using
    # the same call number on a different SOBT (rare but possible for split
    # services). We disambiguate by SOBT in the PK.
    kl0691_ms5 = Flight(
        callsign="KL0691", sobt=datetime(2026, 10, 14, 8, 15),  # different SOBT
        operator_iata="KL",
        aircraft_registration="PH-BVF",
        icao_type="B772", wtc="H",
        flight_type="ARRIVAL",
        origin_icao="ZSPD", destination_icao="EHAM",
        stand_code="F04", runway_designator="18C/36C",
        entry_fix="RIVER", handler_code="KLG",
        pax_connections=94, atfm_penalty=0.0,
    )
    kl0691_ms5.atot_upstation = datetime(2026, 10, 13, 22, 5)
    kl0691_ms5.fir_entry_time = datetime(2026, 10, 14, 14, 20)
    kl0691_ms5.tldt = datetime(2026, 10, 14, 14, 44)
    kl0691_ms5.eldt = datetime(2026, 10, 14, 14, 44)
    flights.append(kl0691_ms5)

    af1641 = Flight(
        callsign="AF1641", sobt=datetime(2026, 10, 14, 13, 0),
        operator_iata="AF",
        aircraft_registration="F-GUGB",
        icao_type="A320", wtc="M",
        flight_type="ARRIVAL",
        origin_icao="LFPG", destination_icao="EHAM",
        stand_code="D88", runway_designator="18C/36C",
        entry_fix="SUGOL", handler_code="DNATA",
        pax_connections=22, atfm_penalty=0.0,
    )
    af1641.atot_upstation = datetime(2026, 10, 14, 13, 17)
    af1641.fir_entry_time = datetime(2026, 10, 14, 14, 30)
    af1641.tldt = datetime(2026, 10, 14, 15, 0)
    af1641.eldt = datetime(2026, 10, 14, 15, 0)
    flights.append(af1641)

    ba0432 = Flight(
        callsign="BA0432", sobt=datetime(2026, 10, 14, 13, 30),
        operator_iata="BA",
        aircraft_registration="G-EUYZ",
        icao_type="A320", wtc="M",
        flight_type="ARRIVAL",
        origin_icao="EGLL", destination_icao="EHAM",
        stand_code="B26", runway_designator="18C/36C",
        entry_fix="ARTIP", handler_code="MENZIES",
        pax_connections=14, atfm_penalty=0.0,
    )
    ba0432.atot_upstation = datetime(2026, 10, 14, 13, 50)
    ba0432.fir_entry_time = datetime(2026, 10, 14, 14, 35)
    ba0432.tldt = datetime(2026, 10, 14, 14, 52)
    ba0432.eldt = datetime(2026, 10, 14, 14, 52)
    flights.append(ba0432)

    # ----- TOBT violations for Act 1 (per-handler bins 7/5/3/2) ----------
    # These are DEPARTURE flights with ARDT in last 4h (10:30-14:30)
    # and |ARDT - TOBT| > 5min, distributed across handlers
    violation_specs = (
        # (handler, count, sign of deviation)
        ("KLG",     7, +1),  # 7 KLG violations, mostly late ready
        ("AGS",     5, +1),  # 5 AGS
        ("DNATA",   3, -1),  # 3 DNATA early-ready
        ("MENZIES", 2, +1),  # 2 MENZIES
    )
    callsign_idx = 7000
    for handler, count, sign in violation_specs:
        for i in range(count):
            op = "KL" if handler == "KLG" else \
                 "HV" if handler == "AGS" else \
                 "AF" if handler == "DNATA" else "BA"
            atype, awtc, _ = AIRCRAFT_TYPES[op][0]
            # SOBT in 11:00-14:00 ensures ARDT stays inside the 10:30-14:30
            # audit window even with +/-12 min deviation.
            sobt_h = rng.randint(11, 13)
            sobt_m = rng.choice([0, 15, 30, 45])
            cs_prefix = {"KL": "KL", "HV": "HV", "AF": "AF", "BA": "BA"}[op]
            cs = f"{cs_prefix}{callsign_idx + i:04d}"
            stand = rng.choice([s.code for s in STANDS
                                if s.pier in ("B", "C", "D", "E") and s.max_wtc != "L"])
            dest = rng.choice(list(KL_ROUTES.keys()))
            f_v = Flight(
                callsign=cs,
                sobt=datetime(2026, 10, 14, sobt_h, sobt_m),
                operator_iata=op,
                aircraft_registration=gen_reg(op, rng),
                icao_type=atype, wtc=awtc,
                flight_type="DEPARTURE",
                origin_icao="EHAM", destination_icao=dest,
                stand_code=stand, runway_designator="18L/36R",
                entry_fix=None, handler_code=handler,
                pax_connections=rng.randint(0, 60),
                atfm_penalty=0.0,
            )
            # Force the violation: ARDT deviates from TOBT by 6-12 minutes,
            # signed by handler convention
            dev = sign * rng.uniform(6, 12)
            synthesize_departure(f_v, rng, ardt_dev_min=dev)
            flights.append(f_v)
        callsign_idx += 100

    # ----- KL691: high-connector preserved flight (Act 5) ----------------
    # Outbound to RJTT (Tokyo Haneda), >80 pax connections, TSAT in window
    kl691 = Flight(
        callsign="KL691", sobt=datetime(2026, 10, 14, 15, 25),
        operator_iata="KL",
        aircraft_registration="PH-BHG",
        icao_type="B789", wtc="H",
        flight_type="DEPARTURE",
        origin_icao="EHAM", destination_icao="RJTT",
        stand_code="F02", runway_designator="18L/36R",
        entry_fix=None, handler_code="KLG",
        pax_connections=137, atfm_penalty=4.0,
    )
    synthesize_departure(kl691, rng)
    flights.append(kl691)

    return flights


# ---------------------------------------------------------------------------
# 6. Bulk background flights
# ---------------------------------------------------------------------------

# Carrier daily share (rough proportions matching EHAM)
CARRIER_SHARE = [
    ("KL",  52),
    ("HV",  8),
    ("AF",  4),
    ("DL",  3),
    ("BA",  2),
    ("LH",  1.5),
    ("EZY", 3),
    ("FR",  1),
    ("W6",  1),
    ("TK",  1.5),
    ("EK",  1),
    ("SQ",  0.7),
    ("KQ",  0.5),
    ("5X",  0.5),
]


def pick_carrier(rng: random.Random) -> str:
    total = sum(s for _, s in CARRIER_SHARE)
    r = rng.uniform(0, total)
    acc = 0.0
    for op, s in CARRIER_SHARE:
        acc += s
        if r < acc:
            return op
    return "KL"


def pick_stand_for(op: str, wtc: str, schengen_dest: bool,
                   rng: random.Random) -> str:
    candidates = []
    for st in STANDS:
        # Pier eligibility
        if st.max_wtc == "L" and wtc != "L":
            continue
        if st.max_wtc == "M" and wtc in ("H", "J"):
            continue
        # Schengen rules
        if st.schengen != schengen_dest:
            continue
        # Operator preference
        if op == "KL" and st.pier in ("B", "C", "D", "E", "F"):
            candidates.append(st.code)
        elif op == "HV" and st.pier in ("B", "H"):
            candidates.append(st.code)
        elif op in ("EZY", "FR", "W6") and st.pier in ("B", "H", "R"):
            candidates.append(st.code)
        elif op in ("DL", "EK", "SQ", "TK", "KQ") and st.pier in ("F", "G", "M"):
            candidates.append(st.code)
        elif op == "5X" and st.pier == "R":
            candidates.append(st.code)
        else:
            candidates.append(st.code)  # fallback
    if not candidates:
        candidates = [s.code for s in STANDS if s.max_wtc != "L"]
    return rng.choice(candidates)


def pick_destination(op: str, rng: random.Random) -> tuple[str, str, bool]:
    """Return (icao, pier_hint, schengen). Pier hint is informational."""
    # KL hits the full network
    if op == "KL":
        dest = rng.choice(list(KL_ROUTES.keys()))
    elif op == "HV":
        dest = rng.choice(["LEBL", "LEMD", "LIRF", "LIMC", "LGAV", "GCLP",
                           "GMMN", "DAAG", "EGKK", "LFPG"])
    elif op == "AF":
        dest = rng.choice(["LFPG", "LFML", "LFLL"])
    elif op == "DL":
        dest = rng.choice(["KATL", "KJFK", "KMSP", "KSEA", "KDTW"])
    elif op == "BA":
        dest = "EGLL"
    elif op == "LH":
        dest = rng.choice(["EDDF", "EDDM"])
    elif op == "EZY":
        dest = rng.choice(["EGGW", "EGKK", "LFPG", "LIMC", "LEMD"])
    elif op == "FR":
        dest = rng.choice(["EIDW", "EGSS", "LEMD"])
    elif op == "W6":
        dest = rng.choice(["LHBP", "EPWA", "LROP"])
    elif op == "TK":
        dest = "LTBA"
    elif op == "EK":
        dest = "OMDB"
    elif op == "SQ":
        dest = "WSSS"
    elif op == "KQ":
        dest = "HKJK"
    elif op == "5X":
        dest = rng.choice(["EDDL", "KSDF"])
    else:
        dest = "EGLL"
    # Schengen lookup (a simplification)
    schengen = dest.startswith(("E", "L")) and dest not in (
        "EGLL", "EGKK", "EGGW", "EGSS", "EICK", "EIDW",  # UK and IE in pre-Brexit was Schengen-ish; treat as non-Schengen for demo
    )
    pier_hint = "F" if not schengen else "C"
    return dest, pier_hint, schengen


def build_bulk_flights(rng: random.Random, target_count: int,
                       existing: list[Flight]) -> list[Flight]:
    """Fill in background flights to reach target_count for the day."""
    out: list[Flight] = []
    existing_callsigns = {(f.callsign, f.sobt) for f in existing}
    # Reserve curated callsigns: bulk must never reuse these to avoid the
    # narrative flights being shadowed by collisions.
    reserved_callsigns = {f.callsign for f in existing}
    callsign_counter = 100

    # Distribute SOBTs across the day in the bank pattern
    # Banks: 06-08 (arr), 07-10 (dep), 10-13 (LH dep), 13-15 (arr), 16-19 (mixed)
    # 19-22 (Asia/Africa LH dep)
    while len(out) < target_count:
        op = pick_carrier(rng)
        types = AIRCRAFT_TYPES[op]
        atype, awtc, _ = rng.choice(types)

        # 50/50 ARR/DEP
        ftype = rng.choice(["ARRIVAL", "DEPARTURE"])
        is_arr = ftype == "ARRIVAL"

        dest_icao, pier_hint, schengen = pick_destination(op, rng)
        if is_arr:
            origin_icao, destination_icao = dest_icao, "EHAM"
        else:
            origin_icao, destination_icao = "EHAM", dest_icao

        stand_code = pick_stand_for(op, awtc, schengen, rng)

        # SOBT bank distribution
        r = rng.random()
        if is_arr:
            if r < 0.20:
                h = rng.randint(6, 8)   # morning US/Asia arr wave
            elif r < 0.55:
                h = rng.randint(13, 15)  # afternoon arr wave
            elif r < 0.85:
                h = rng.randint(16, 19)
            else:
                h = rng.choice([9, 10, 11, 12, 20, 21])
        else:
            if r < 0.20:
                h = rng.randint(7, 9)
            elif r < 0.50:
                h = rng.randint(10, 13)  # long-haul outbound bank
            elif r < 0.80:
                h = rng.randint(16, 19)
            else:
                h = rng.choice([6, 14, 15, 20, 21])
        m = rng.choice([0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55])

        sobt = datetime(2026, 10, 14, h, m)

        # callsign
        prefix = op
        if op in ("EZY",):
            prefix = "EZY"
        callsign = f"{prefix}{callsign_counter:04d}"
        callsign_counter += rng.randint(1, 7)
        # Skip if collides with curated callsign or exact (callsign,sobt) dup
        if callsign in reserved_callsigns:
            continue
        if (callsign, sobt) in existing_callsigns:
            continue

        # Runway: choose by direction and traffic flow (north flow)
        if is_arr:
            # Map fix -> rwy
            if awtc in ("H", "J"):
                fix = rng.choice(["RIVER", "SUGOL"])
            else:
                fix = rng.choice(["ARTIP", "SUGOL", "RIVER", "NIRSI"])
            if fix == "NIRSI":
                rwy = "18R/36L"
            elif fix == "ARTIP":
                rwy = "09/27" if rng.random() < 0.3 else "18C/36C"
            else:
                rwy = "18C/36C"
        else:
            fix = None
            rwy = "18L/36R" if rng.random() < 0.8 else "06/24"

        # Handler assignment by operator
        if op == "KL":
            handler = "KLG"
        elif op == "HV":
            handler = "AGS"
        elif op in ("AF", "DL", "KQ"):
            handler = "DNATA"
        elif op == "BA":
            handler = "MENZIES"
        else:
            handler = rng.choice(["AGS", "DNATA", "MENZIES"])

        # Pax connections
        if op == "KL":
            pax_conn = rng.randint(20, 180)
        elif op in ("DL", "AF", "KQ", "SQ", "EK", "TK", "KQ"):
            pax_conn = rng.randint(30, 120)
        else:
            pax_conn = rng.randint(0, 40)

        f = Flight(
            callsign=callsign, sobt=sobt,
            operator_iata=op,
            aircraft_registration=gen_reg(op, rng),
            icao_type=atype, wtc=awtc,
            flight_type=ftype,
            origin_icao=origin_icao, destination_icao=destination_icao,
            stand_code=stand_code, runway_designator=rwy,
            entry_fix=fix, handler_code=handler,
            pax_connections=pax_conn,
            atfm_penalty=0.0,
        )
        if is_arr:
            synthesize_arrival(f, rng)
        else:
            # Talk-track guardrail: any bulk departure whose ARDT would fall in
            # the last-4h audit window (10:30-14:30) is force-compliant so the
            # curated violations dominate the Act 1 query.
            # We probe by tentatively setting ARDT and checking the window.
            # Simpler: if SOBT puts the flight likely to ARDT in the window,
            # force compliance.
            sobt_in_window = (
                datetime(2026, 10, 14, 10, 0) <= sobt
                <= datetime(2026, 10, 14, 14, 30)
            )
            synthesize_departure(f, rng, force_compliant=sobt_in_window)
        out.append(f)
        existing_callsigns.add((callsign, sobt))
    return out


def ensure_tsat_window_count(flights: list[Flight], rng: random.Random,
                             target: int = 47) -> list[Flight]:
    """Ensure exactly `target` flights have TSAT in [15:00, 17:00)."""
    window_start = datetime(2026, 10, 14, 15, 0)
    window_end = datetime(2026, 10, 14, 17, 0)

    in_window = [f for f in flights
                 if f.flight_type == "DEPARTURE"
                 and f.tsat is not None
                 and window_start <= f.tsat < window_end]
    deficit = target - len(in_window)
    if deficit > 0:
        # Convert some out-of-window departures by shifting their SOBT/TSAT.
        # Guardrail: do NOT shift flights whose ARDT is in the Act-1 audit
        # window [10:30, 14:30], otherwise we lose curated TOBT violations.
        audit_lo = DEMO_NOW - timedelta(hours=4)
        audit_hi = DEMO_NOW
        candidates = [f for f in flights
                      if f.flight_type == "DEPARTURE"
                      and f.tsat is not None
                      and (f.tsat < window_start or f.tsat >= window_end)
                      and not (f.ardt is not None
                               and audit_lo <= f.ardt <= audit_hi)]
        rng.shuffle(candidates)
        for f in candidates[:deficit]:
            # Shift entire timeline by a delta that puts TSAT into the window
            target_tsat = datetime(2026, 10, 14,
                                   rng.randint(15, 16),
                                   rng.choice([0, 5, 10, 15, 20, 25, 30, 35,
                                               40, 45, 50, 55]))
            delta = target_tsat - f.tsat
            for attr in ("sobt", "eobt", "tobt", "tsat", "abdt", "ardt",
                         "asrt", "asat", "aobt", "ttot", "atot"):
                v = getattr(f, attr)
                if v is not None:
                    setattr(f, attr, v + delta)
    return flights


# ---------------------------------------------------------------------------
# 7. SQL emission
# ---------------------------------------------------------------------------

DDL_TEMPLATE = """\
-- =====================================================================
-- EHAM A-CDM Demo - Snowflake DDL
-- Generated: {now}
-- Seed: {seed}
-- =====================================================================

CREATE DATABASE IF NOT EXISTS {db};
USE DATABASE {db};

CREATE SCHEMA IF NOT EXISTS {schema};
USE SCHEMA {schema};

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
"""


def sql_escape(s: Optional[str]) -> str:
    if s is None or s == "":
        return "NULL"
    return "'" + str(s).replace("'", "''") + "'"


def sql_ts(dt: Optional[datetime]) -> str:
    if dt is None:
        return "NULL"
    return "TO_TIMESTAMP_NTZ('" + dt.strftime("%Y-%m-%d %H:%M:%S") + "')"


def emit_ddl(now: str, seed: int) -> str:
    return DDL_TEMPLATE.format(now=now, seed=seed, db=DB_NAME, schema=SCHEMA_NAME)


def emit_reference_sql() -> str:
    parts = [
        f"USE DATABASE {DB_NAME};",
        f"USE SCHEMA {SCHEMA_NAME};",
        "",
        "-- ----- Operators -----",
    ]
    for o in OPERATORS:
        parts.append(
            f"INSERT INTO dim_operator VALUES ("
            f"{sql_escape(o.iata)}, {sql_escape(o.icao)}, {sql_escape(o.name)}, "
            f"{sql_escape(o.alliance)}, {o.min_turn_narrowbody_min}, {o.min_turn_widebody_min});"
        )
    parts.append("")
    parts.append("-- ----- Runways -----")
    for r in RUNWAYS:
        parts.append(
            f"INSERT INTO dim_runway VALUES ("
            f"{sql_escape(r.designator)}, {sql_escape(r.name)}, "
            f"{r.length_m}, {sql_escape(r.used_for)});"
        )
    parts.append("")
    parts.append("-- ----- Fixes -----")
    for fx in FIXES:
        parts.append(
            f"INSERT INTO dim_fix VALUES ("
            f"{sql_escape(fx.name)}, {sql_escape(fx.fix_type)}, "
            f"{sql_escape(fx.typical_landing_rwy)});"
        )
    parts.append("")
    parts.append("-- ----- Ground handlers -----")
    for h in HANDLERS:
        parts.append(
            f"INSERT INTO dim_ground_handler VALUES ("
            f"{sql_escape(h.code)}, {sql_escape(h.name)});"
        )
    parts.append("")
    parts.append("-- ----- Stands -----")
    for s in STANDS:
        parts.append(
            f"INSERT INTO dim_stand VALUES ("
            f"{sql_escape(s.code)}, {sql_escape(s.pier)}, "
            f"{'TRUE' if s.is_contact else 'FALSE'}, "
            f"{sql_escape(s.max_wtc)}, "
            f"{'TRUE' if s.schengen else 'FALSE'});"
        )
    parts.append("")
    parts.append("-- ----- Taxi-in matrix -----")
    for (fix, rwy, pier), (mean, sd) in TAXI_IN_MATRIX.items():
        parts.append(
            f"INSERT INTO taxi_time_in VALUES ("
            f"{sql_escape(fix)}, {sql_escape(rwy)}, {sql_escape(pier)}, "
            f"{mean}, {sd});"
        )
    parts.append("")
    parts.append("-- ----- Taxi-out matrix -----")
    for (pier, rwy), (mean, sd) in TAXI_OUT_MATRIX.items():
        parts.append(
            f"INSERT INTO taxi_time_out VALUES ("
            f"{sql_escape(pier)}, {sql_escape(rwy)}, {mean}, {sd});"
        )
    parts.append("")
    parts.append("-- ----- Weather event (storm scenario for Act 4) -----")
    parts.append(
        f"INSERT INTO weather_event VALUES ("
        f"'WX_2026101415', "
        f"{sql_ts(datetime(2026, 10, 14, 15, 0))}, "
        f"{sql_ts(datetime(2026, 10, 14, 17, 0))}, "
        f"'Convective cell over 18C, 40% arrival capacity reduction, "
        f"forces single-runway departures off 18L', "
        f"'18C/36C,27');"
    )
    parts.append("")
    return "\n".join(parts) + "\n"


def emit_aircraft_inserts(flights: list[Flight]) -> str:
    """Emit dim_aircraft INSERTs derived from the flights actually in use."""
    seen: dict[str, tuple[str, str, str, int]] = {}
    for f in flights:
        if f.aircraft_registration in seen:
            continue
        # Find seats from AIRCRAFT_TYPES
        seats = 0
        for t, w, s in AIRCRAFT_TYPES.get(f.operator_iata, []):
            if t == f.icao_type:
                seats = s
                break
        seen[f.aircraft_registration] = (f.icao_type, f.wtc, f.operator_iata, seats)
    parts = [f"USE DATABASE {DB_NAME};",
             f"USE SCHEMA {SCHEMA_NAME};",
             "",
             "-- ----- Aircraft (auto-derived from flight roster) -----"]
    for reg, (t, w, op, seats) in sorted(seen.items()):
        parts.append(
            f"INSERT INTO dim_aircraft VALUES ("
            f"{sql_escape(reg)}, {sql_escape(t)}, {sql_escape(w)}, "
            f"{sql_escape(op)}, {seats});"
        )
    return "\n".join(parts) + "\n"


# ---------------------------------------------------------------------------
# 8. CSV emission for flight rows
# ---------------------------------------------------------------------------

FLIGHT_COLUMNS = [
    "CALLSIGN", "SOBT",
    "OPERATOR_IATA", "AIRCRAFT_REGISTRATION",
    "ICAO_TYPE", "WTC", "FLIGHT_TYPE",
    "ORIGIN_ICAO", "DESTINATION_ICAO",
    "STAND_CODE", "RUNWAY_DESIGNATOR", "ENTRY_FIX",
    "HANDLER_CODE", "PAX_CONNECTIONS", "ATFM_PENALTY",
    "EOBT", "CTOT", "ATOT_UPSTATION", "FIR_ENTRY_TIME",
    "TLDT", "ELDT", "ALDT", "AIBT", "ACGT",
    "TOBT", "TSAT", "ABDT", "ARDT", "ASRT", "ASAT",
    "TTOT", "AOBT", "ATOT",
    "FEEDS_CALLSIGN", "FEEDS_SOBT", "IS_ELIGIBLE_ACDM",
]


def write_csv(flights: list[Flight], path: Path) -> None:
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(FLIGHT_COLUMNS)
        for f in flights:
            w.writerow(f.csv_row())


# ---------------------------------------------------------------------------
# 9. Load + validation SQL
# ---------------------------------------------------------------------------

LOAD_TEMPLATE = """\
-- =====================================================================
-- EHAM A-CDM Demo - Load script
-- =====================================================================

USE DATABASE {db};
USE SCHEMA {schema};

-- 1) Create internal stage
CREATE OR REPLACE STAGE eham_demo_stage
    FILE_FORMAT = (
        TYPE = CSV
        SKIP_HEADER = 1
        FIELD_OPTIONALLY_ENCLOSED_BY = '"'
        NULL_IF = ('', 'NULL')
        EMPTY_FIELD_AS_NULL = TRUE
    );

-- 2) Upload the CSV using SnowSQL (run this from your local shell):
--    snowsql -q "PUT file://eham_demo_flights.csv @{db}.{schema}.eham_demo_stage AUTO_COMPRESS=TRUE"
--
--    Or in Snowsight, open the stage and use the GUI uploader.

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
"""


VALIDATION_TEMPLATE = """\
-- =====================================================================
-- EHAM A-CDM Demo - Validation queries
-- =====================================================================
-- These queries prove the synthetic data supports the talk track narrative.
-- Run them after loading and verify the expected counts.

USE DATABASE {db};
USE SCHEMA {schema};

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
"""


def emit_load_sql() -> str:
    return LOAD_TEMPLATE.format(db=DB_NAME, schema=SCHEMA_NAME)


def emit_validation_sql() -> str:
    return VALIDATION_TEMPLATE.format(db=DB_NAME, schema=SCHEMA_NAME)


# ---------------------------------------------------------------------------
# 10. Main
# ---------------------------------------------------------------------------

def main() -> None:
    rng = random.Random(SEED)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"[gen] Seed = {SEED}")
    print(f"[gen] Building curated narrative flights...")
    curated = build_curated_flights(rng)
    print(f"[gen]   curated: {len(curated)}")

    print(f"[gen] Building bulk background flights...")
    target_total = 320
    bulk = build_bulk_flights(rng, target_total - len(curated), curated)
    print(f"[gen]   bulk:    {len(bulk)}")

    flights = curated + bulk
    print(f"[gen]   total:   {len(flights)}")

    # Make sure we have 47 in the TSAT window
    print(f"[gen] Tuning TSAT window to ~47 flights...")
    flights = ensure_tsat_window_count(flights, rng, target=47)

    # Write outputs
    ddl_path  = OUT_DIR / "eham_demo_ddl.sql"
    ref_path  = OUT_DIR / "eham_demo_reference.sql"
    air_path  = OUT_DIR / "eham_demo_aircraft.sql"
    csv_path  = OUT_DIR / "eham_demo_flights.csv"
    load_path = OUT_DIR / "eham_demo_load.sql"
    val_path  = OUT_DIR / "eham_demo_validation.sql"

    ddl_path.write_text(emit_ddl(now_str, SEED))
    ref_path.write_text(emit_reference_sql())
    air_path.write_text(emit_aircraft_inserts(flights))
    write_csv(flights, csv_path)
    load_path.write_text(emit_load_sql())
    val_path.write_text(emit_validation_sql())

    print(f"[gen] Wrote:")
    for p in (ddl_path, ref_path, air_path, csv_path, load_path, val_path):
        print(f"  - {p}  ({p.stat().st_size:>8,} bytes)")

    # Quick self-validation
    print(f"\n[gen] Quick self-validation:")
    arrivals = sum(1 for f in flights if f.flight_type == "ARRIVAL")
    departures = sum(1 for f in flights if f.flight_type == "DEPARTURE")
    tsat_window = sum(1 for f in flights
                      if f.flight_type == "DEPARTURE"
                      and f.tsat is not None
                      and datetime(2026, 10, 14, 15, 0) <= f.tsat
                                                       < datetime(2026, 10, 14, 17, 0))
    print(f"  arrivals:                {arrivals}")
    print(f"  departures:              {departures}")
    print(f"  in TSAT 15:00-17:00:     {tsat_window}")

    # TOBT violation counts by handler in last 4h
    cutoff_lo = DEMO_NOW - timedelta(hours=4)
    by_handler: dict[str, int] = {}
    for f in flights:
        if f.flight_type != "DEPARTURE" or f.ardt is None or f.tobt is None:
            continue
        if not (cutoff_lo <= f.ardt <= DEMO_NOW):
            continue
        if abs((f.ardt - f.tobt).total_seconds() / 60) > 5:
            by_handler[f.handler_code] = by_handler.get(f.handler_code, 0) + 1
    print(f"  TOBT violations by handler (last 4h, expect KLG~7, AGS~5, DNATA~3, MENZIES~2):")
    for h in ("KLG", "AGS", "DNATA", "MENZIES"):
        print(f"    {h:<8} {by_handler.get(h, 0)}")

    # MS5 candidates
    ms5 = [f for f in flights
           if f.flight_type == "ARRIVAL"
           and f.tldt is not None and f.aldt is None
           and DEMO_NOW <= f.tldt <= DEMO_NOW + timedelta(minutes=30)]
    print(f"  MS5 forecast candidates ({len(ms5)}, expect at least 4):")
    for f in sorted(ms5, key=lambda x: x.tldt)[:6]:
        print(f"    {f.callsign:<8} stand={f.stand_code:<5} tldt={f.tldt.strftime('%H:%M')}")

    # Rotation chain
    kl_chain = [f for f in flights if f.callsign in
                ("KL1234", "KL1235", "KL1402", "KL1601", "HV5821", "AF1241")]
    print(f"  Cascade chain flights: {len(kl_chain)} (expect 6)")


if __name__ == "__main__":
    main()
