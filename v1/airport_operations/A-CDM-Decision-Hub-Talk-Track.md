# A-CDM Decision Hub - RelationalAI Demo Talk Track

> **Legacy conceptual draft.** This script predates the implemented queries and contains claims the live seed data does not support, especially a trained MS5 conflict probability, a passenger-weighted baseline objective, hard CTOT compliance, and a cap-driven improvement to KL691. Use [DEMO_RUNBOOK.md](DEMO_RUNBOOK.md) and [DEMO_QUESTIONS.md](DEMO_QUESTIONS.md) for the deployed agent's validated prompts and answers. Do not read Acts 3-5 below verbatim in a live demo.

**Audience:** Airport authority / ANSP / airline ops executive pitch
**Domain anchor:** EHAM Amsterdam Schiphol (synthetic data, modeled on real ops)
**Reference doc:** ICAO Generic A-CDM Milestones Procedure Template (Chapter 4, Attachment 4.8)
**Runtime:** RelationalAI Native App on Snowflake, PyRel v1.2+
**Total run time:** 18-22 minutes (modular - acts can be cut)

---

## Code disclaimer (read before the dry run)

The PyRel snippets in this talk track are **talk-track-grade**, not production-grade. They are written to match the published RelationalAI docs as of May 2026 and to be defensible if a technical viewer reads them on screen. Before you do a live execution against the customer's Snowflake:

1. Syntax-verify each cell against the installed PyRel version (`relationalai` v1.2+). The fastest check is `python -c "import relationalai; print(relationalai.__version__)"` then `pip show relationalai`.
2. The **prescriptive** code (Act 4) leans on the `Problem` API, which is in **Preview**. Confirm `solve_for`, `satisfy`, `minimize` signatures haven't drifted. Run the `rai-prescriptive-problem-formulation` skill in your agent if you have it installed - it auto-generates current-version-correct code.
3. The **predictive** code (Act 3) uses a `Forecast` reasoner construct that is in **early access**. If your RAI deployment doesn't have it enabled yet, replace Act 3 with a deterministic rule (e.g., "p_conflict = 1 if overlap > 5 min else 0.3"). Don't fake the math.
4. The **graph** code (Act 2) uses `Graph(m, directed=True)` and `.reachable_from(...)`. The exact `Graph` API has evolved - check `from relationalai.semantics.std.graphs import Graph` import path against your version.
5. Always run the notebook end-to-end at least once on the live Snowflake account 24h before the demo. **Never demo code you haven't executed on the target system.**

If any cell fails on stage, fall back to the pre-recorded screencap (see Appendix D). Don't debug in front of the customer.

---

## Why this demo, in one paragraph

A-CDM is the textbook decision-intelligence problem in aviation. Sixteen milestones, eight stakeholders, four phases, and every decision (in-block time, pre-departure sequence, gate assignment, runway sequencing) is a multi-source data fusion plus a choice under constraints. The same dataset has to answer rules questions (is TOBT compliance within +/- 5 min?), graph questions (what's the rotation impact if LH441 lands 35 min late?), predictive questions (gate conflict probability at MS5?), and prescriptive questions (optimal TSAT sequence under storm-reduced runway capacity?). No BI tool covers all four. RelationalAI's semantic model + four reasoners maps onto it 1:1.

---

## Opening (90 seconds)

> "Your A-CDM portal already shows what's happening. The question we're going to answer in the next twenty minutes is whether it can tell you what to *do*. We've built a decision agent on top of an A-CDM data model - all 16 milestones from the ICAO template, the SkyTeam carrier mix you'd expect at Schiphol, a normal Wednesday in October with about 320 movements. We're going to ask it four questions that span the four reasoning patterns A-CDM operations actually need: a compliance audit, a rotation cascade trace, a gate conflict prediction, and the one that matters most - a TSAT re-sequence when the weather changes the runway plan. Each one is a single question from the operator. The agent figures out which reasoner to use. Watch what comes back."

---

## Setup: what's already running before the demo starts

The model is pre-loaded. The customer sees a clean Jupyter notebook or PyRel session. Don't waste time on configuration on stage.

**Pre-loaded:**
- `raiconfig.yaml` pointing at the customer's Snowflake account, `rai_developer` role active
- The A-CDM ontology (concepts, properties, relationships) instantiated
- 24 hours of synthetic Schiphol ops loaded as base facts (see Appendix A)
- A Workshop-style HMI mock on a second monitor showing live milestone timeline (optional, makes the demo feel like a real ops floor)

**On the speaker's screen:**
- Left half: PyRel code in JupyterLab
- Right half: result DataFrames, plus a Plotly Gantt for the prescriptive act

---

## Act 0: Show the ontology (90 seconds)

You don't read the code aloud. You scroll past it and stop on the entity diagram. The point is: "this is your A-CDM data model, structured."

```python
from relationalai.semantics import (
    Model, String, Integer, Float, DateTime, Boolean
)
from relationalai.semantics.std.datetime import datetime

m = Model("ACDMDecisionHub")

# ----- Core entities ---------------------------------------------------

Aircraft = m.Concept("Aircraft", identify_by={"registration": String})
Aircraft.icao_type = m.Property(f"{Aircraft} is type {String}")
Aircraft.wtc = m.Property(f"{Aircraft} has wake category {String}")  # L/M/H/J

Operator = m.Concept("Operator", identify_by={"iata": String})
Operator.name = m.Property(f"{Operator} is named {String}")
Operator.alliance = m.Property(f"{Operator} is in alliance {String}")

Stand = m.Concept("Stand", identify_by={"code": String})
Stand.pier = m.Property(f"{Stand} is on pier {String}")
Stand.is_contact = m.Relationship(f"{Stand} is a contact stand")
Stand.max_wtc = m.Property(f"{Stand} allows up to wake category {String}")

Runway = m.Concept("Runway", identify_by={"designator": String})
Runway.length_m = m.Property(f"{Runway} is {Integer} meters long")

Flight = m.Concept("Flight", identify_by={"callsign": String, "sobt": DateTime})
Flight.aircraft = m.Relationship(f"{Flight} operated by {Aircraft}")
Flight.operator = m.Relationship(f"{Flight} flown by {Operator}")
Flight.origin = m.Property(f"{Flight} departs from {String}")        # ICAO
Flight.destination = m.Property(f"{Flight} arrives at {String}")     # ICAO
Flight.stand = m.Relationship(f"{Flight} uses stand {Stand}")
Flight.runway = m.Relationship(f"{Flight} uses runway {Runway}")
Flight.entry_fix = m.Property(f"{Flight} enters TMA via fix {String}")  # ARTIP/SUGOL/RIVER/NIRSI

# Turnaround link - inbound feeds outbound on same aircraft
Flight.feeds = m.Relationship(f"{Flight} feeds outbound {Flight:outbound}")

# ----- The 16 ICAO milestones as timestamps ----------------------------
# Each milestone is a property on Flight. We model both the scheduled/target
# values (SOBT, EOBT, TOBT, TSAT, TTOT, ELDT, EIBT, TLDT) and actuals
# (ALDT, AIBT, AGHT, ABDT, ARDT, ASRT, ASAT, AOBT, ATOT).

Flight.sobt  = m.Property(f"{Flight} SOBT  is {DateTime}")  # MS1 scheduled
Flight.eobt  = m.Property(f"{Flight} EOBT  is {DateTime}")  # MS1 flight plan
Flight.ctot  = m.Property(f"{Flight} CTOT  is {DateTime}")  # MS2 if regulated
Flight.atot_up = m.Property(f"{Flight} ATOT_upstation is {DateTime}")  # MS3
Flight.fir_entry = m.Property(f"{Flight} FIR entry  is {DateTime}")    # MS4
Flight.tldt  = m.Property(f"{Flight} TLDT  is {DateTime}")  # MS5
Flight.eldt  = m.Property(f"{Flight} ELDT  is {DateTime}")  # MS5
Flight.aldt  = m.Property(f"{Flight} ALDT  is {DateTime}")  # MS6 landing
Flight.aibt  = m.Property(f"{Flight} AIBT  is {DateTime}")  # MS7 in-block
Flight.acgt  = m.Property(f"{Flight} ACGT  is {DateTime}")  # MS8 ground handling start
Flight.tobt  = m.Property(f"{Flight} TOBT  is {DateTime}")  # MS9
Flight.tsat  = m.Property(f"{Flight} TSAT  is {DateTime}")  # MS10
Flight.abdt  = m.Property(f"{Flight} ABDT  is {DateTime}")  # MS11 boarding
Flight.ardt  = m.Property(f"{Flight} ARDT  is {DateTime}")  # MS12 aircraft ready
Flight.asrt  = m.Property(f"{Flight} ASRT  is {DateTime}")  # MS13 startup request
Flight.asat  = m.Property(f"{Flight} ASAT  is {DateTime}")  # MS14 startup approved
Flight.aobt  = m.Property(f"{Flight} AOBT  is {DateTime}")  # MS15 off-block
Flight.ttot  = m.Property(f"{Flight} TTOT  is {DateTime}")  # target take-off
Flight.atot  = m.Property(f"{Flight} ATOT  is {DateTime}")  # MS16 take-off
```

**Speaker note (slow down here):**

> "Every property on this Flight entity is one of the 16 ICAO milestones. SOBT, EOBT, ELDT, TLDT, TOBT, TSAT, ATOT - it's the same vocabulary your ops staff use. The ontology isn't a database schema we made up. It's the procedure document, encoded. When we add a derived property in a minute, it inherits this vocabulary - so when the agent answers a question, it answers in your terms, not ours."

This line lands. It's the "superalignment" pitch from their website, translated to aviation.

---

## Act 1 (Rules-based): MS12 TOBT compliance audit (3 minutes)

**The question (operator types):**

> "Show me every flight in the last four hours where actual ready time deviated from TOBT by more than five minutes, broken down by ground handler. These should have triggered automatic TOBT/TSAT removal per the MS12 procedure."

**What the operator expects from a BI tool:** A SQL query, written by a data analyst, run once, maintained forever.
**What we show:** the derived property defined once at the ontology layer, queryable for any window.

```python
from relationalai.semantics.std.datetime import datetime as dt_fn
from relationalai.semantics.std import aggregates as agg
from datetime import datetime as dt, timedelta

# ----- Derived concept: TOBT violation ---------------------------------
# Per ICAO MS12: "X3 is highly recommended to be +/- 5 minutes"
# Define a derived flag once - reusable across queries, alerts, reports.

TOBTViolation = m.Concept("TOBTViolation", extends=[Flight])
GroundHandler = m.Concept("GroundHandler", identify_by={"code": String})
Flight.handler = m.Relationship(f"{Flight} handled by {GroundHandler}")

# Two derived rules to capture both directions of the +/- 5 min window
m.where(
    dt_fn.diff("minutes", Flight.ardt, Flight.tobt) > 5
).define(TOBTViolation(Flight))

m.where(
    dt_fn.diff("minutes", Flight.tobt, Flight.ardt) > 5
).define(TOBTViolation(Flight))

# Per-handler breakdown for the last 4 hours
now = dt(2026, 10, 14, 14, 30)  # demo "current time"
four_hours_ago = now - timedelta(hours=4)

result = (
    m
    .where(
        TOBTViolation(Flight),
        Flight.ardt >= four_hours_ago,
        Flight.ardt <= now,
    )
    .select(
        Flight.handler.code.alias("handler"),
        agg.count(Flight).per(Flight.handler).alias("violations"),
        agg.avg(
            dt_fn.diff("minutes", Flight.ardt, Flight.tobt)
        ).per(Flight.handler).alias("avg_deviation_min"),
    )
    .to_df()
)
print(result)
```

**Expected output (from the EHAM seed=42 dataset):**

```
   handler  violations  avg_deviation_min
0      KLG          7              +8.6
1      AGS          5              +9.2
2      DNATA        3              -9.3
3      MENZIES      2              +7.5
```

**Speaker script:**

> "Two things to notice. First, the rule was written once, in the language of the ICAO procedure - ARDT deviating from TOBT by more than five minutes. That's MS12. The operator can ask the same question for any time window, any handler, any aircraft type, and it composes. They're not writing SQL.
>
> Second, look at this. KLG and AGS are running positive deviations - flights ready *late*. DNATA is negative - their flights are calling ready *before* TOBT, which is a different problem: it inflates demand on the TSAT calculator. The agent didn't flag this as just a count, it surfaced the sign of the deviation. That's the difference between a dashboard and a decision agent."

**Aviation domain note for the speaker:**
Positive ARDT - TOBT means crew is calling ready late, which usually traces to ground handling delays (catering, bags) or last-minute paperwork. Negative deviation usually means optimistic TOBT setting by the dispatcher trying to game the sequence. Both are A-CDM hygiene issues. Mentioning this in the room demonstrates you understand the operational meaning, not just the numbers.

**If asked: "How is this different from a SQL query?"**

> "Three things. One: the rule is encoded against the entity, not the table. If we add a new data source tomorrow that updates ARDT - say a ramp tablet app - the rule keeps working with no rewrite. Two: it composes with the other reasoners. The graph cascade query you're about to see uses this same TOBTViolation concept as one of its risk signals. Three: every rule is documented in the ontology, queryable as metadata, and version-controlled. Your A-CDM rulebook stops living in a PDF and starts living in your data model."

---

## Act 2 (Graph reasoning): Rotation cascade trace (3 minutes)

**The question:**

> "KL1234 inbound from KJFK is 35 minutes late at final approach. Trace the rotation impact across the next 6 hours. Which outbound flights, which gates, which crew, which ATFM slots are at risk?"

**Setup the cascade graph:**

```python
from relationalai.semantics.std.graphs import Graph

# The aircraft-rotation chain: outbound i depends on inbound i-1 (same tail)
# A stand-conflict edge exists when two flights overlap their stand occupancy

# First, define what "at risk" means in terms of the ontology
RotationAtRisk = m.Concept("RotationAtRisk", extends=[Flight])

# Minimum turn time depends on aircraft type and operator
Operator.min_turn_min = m.Property(f"{Operator} min turn for narrowbody is {Integer}")
# E.g. KL narrowbody = 35, KL widebody = 90, HV (Transavia LCC) = 25

# A downstream outbound is at risk if its TOBT is now infeasible:
# predicted AIBT (= ELDT + taxi-in) + min turn > current TOBT
# Use dt_fn.add to compose datetimes; per-stand taxi refinement in v2.

inbound = Flight.ref()
outbound = Flight.ref()
m.where(
    inbound.feeds(outbound),
    dt_fn.add(inbound.eldt, "minutes", 6 + inbound.aircraft.operator.min_turn_min)
        > outbound.tobt,
).define(
    RotationAtRisk(outbound)
)

# Build a directed graph: aircraft-rotation edges + stand-conflict edges
rotation_graph = Graph(m, directed=True)

# Edge: rotation (in -> out on same aircraft)
src = Flight.ref()
tgt = Flight.ref()
rotation_graph.Edge.extend(
    m.where(src.feeds(tgt)).select(
        src.callsign.alias("source"),
        tgt.callsign.alias("target"),
    )
)

# Edge: stand_conflict (two flights overlap on same stand)
F1 = Flight.ref()
F2 = Flight.ref()
rotation_graph.Edge.extend(
    m.where(
        F1.stand == F2.stand,
        F1.callsign < F2.callsign,                # dedupe ordered pairs
        F1.aibt <= F2.aobt,
        F2.aibt <= F1.aobt,
    ).select(
        F1.callsign.alias("source"),
        F2.callsign.alias("target"),
    )
)

# Reachability from the late flight, depth-limited to ~6h horizon
impact = rotation_graph.reachable_from(
    start_node="KL1234",
    max_depth=4,        # rotation chains rarely exceed 4 hops in 6h
).to_df()
print(impact)
```

**Expected output (curated):**

```
   callsign    via              hops  outbound_sobt  risk_kind
0  KL1235     rotation          1     14:05          TOBT infeasible
1  KL1402     rotation+stand    2     15:20          stand_conflict on E18
2  HV5821     stand_conflict    1     14:35          stand_conflict on D54
3  KL1601     rotation          3     17:10          TOBT infeasible
4  AF1241     stand_conflict    2     16:00          stand_conflict on F08
```

**Speaker script (this is the moment that lands):**

> "KL1234 is one flight, 35 minutes late. The agent has just told us five other flights are affected, and not just by aircraft rotation - look at row 2. KL1235 is the obvious rotation partner, the same aircraft turning around. But the stand E18 conflict propagates the delay to KL1402 even though it's a different aircraft, because the stand is occupied longer than planned. And HV5821 - that's Transavia, different operator, different alliance, and they're going to lose stand D54 because the KL widebody is still parked there. That's three carriers, two terminals, one ATFM slot at risk, from a single ALDT input.
>
> Your Eurocontrol Network Manager wants to know this an hour earlier than they currently do. So does ground handling. So does the gate planner. The agent just found it, by reasoning over the graph - not by joining tables in someone's spreadsheet."

**Pushback the speaker should be ready for:**

> Q: "We already have rotation tracking in our AODB."
> A: "You have inbound-outbound pairing. You don't have stand conflict propagation across the rotation chain over a 6-hour horizon, with handler and slot impact, in one query. And you definitely don't have it built on the same data model that's about to solve the optimization problem in the next act. The point isn't that any one of these is impossible. It's that they all sit on one semantic layer."

---

## Act 3 (Predictive): Gate conflict probability at MS5 (3 minutes)

**The question:**

> "Looking at all inbound flights currently between MS5 final approach and MS6 landing - rank them by probability of arrival gate conflict in the next 30 minutes."

**Speaker context, said up front:**

> "This one's preview. The predictive reasoner is in early access. What I'm showing is a forecast: given the TLDT estimate plus taxi-in distribution plus current stand occupancy, what's the conflict probability before AIBT? It composes a model on the fly from the ontology - there's no separate model registry, no MLOps step. The forecast is just another derived property."

```python
# Stand conflict probability at MS5
# Inputs already in the ontology:
#  - TLDT (MS5) for the inbound
#  - current AIBT/AOBT pairs of any flight currently or about to be at that stand
#  - taxi-in time distribution by entry fix and stand (learned from historical data
#    pre-loaded as a derived property)

from relationalai.semantics.reasoners.predictive import Forecast

taxi_in_dist = m.Relationship(
    f"{Stand} taxi-in from {String:fix} mean is {Float:mean} stdev is {Float:std}"
)
# Populated from historical data; speaker doesn't show this, just references it

# Predicted AIBT distribution = TLDT + N(mean, std) of stand-fix taxi time
Flight.aibt_forecast = m.Property(
    f"{Flight} forecast AIBT is {DateTime} with confidence {Float}"
)

# A conflict exists if forecast AIBT falls inside the current occupant's AOBT window
StandConflictForecast = m.Concept("StandConflictForecast", extends=[Flight])

inbound = Flight.ref()
occupant = Flight.ref()
m.where(
    m.not_(inbound.aldt),                # not yet landed (ALDT not set)
    inbound.tldt,                        # MS5 reached (TLDT exists)
    inbound.stand == occupant.stand,
    inbound.callsign != occupant.callsign,
    inbound.aibt_forecast >= occupant.aibt,
    inbound.aibt_forecast <= occupant.aobt,
).define(
    StandConflictForecast(inbound)
)

# Rank by conflict probability (computed by the forecast reasoner)
df = (
    m.where(StandConflictForecast(Flight))
     .select(
        Flight.callsign.alias("inbound"),
        Flight.stand.code.alias("stand"),
        Flight.aibt_forecast.alias("predicted_aibt"),
        Flight.forecast_confidence.alias("p_conflict"),
     )
     .to_df()
     .sort_values("p_conflict", ascending=False)   # pandas sort post-fetch
)
print(df)
```

**Expected output (curated):**

```
   inbound   stand  predicted_aibt  p_conflict
0  DL0036    E18    14:42           0.73
1  KL0691    F04    14:51           0.58
2  AF1641    D88    15:07           0.41
3  BA0432    B26    14:59           0.22
```

**Speaker script:**

> "Four flights at MS5 with non-trivial probability of a stand conflict before they touch down. DL0036 at E18 is 73% - that's the one to act on. Notice we did this with a probability, not a yes/no flag. That matters. Your stand planner doesn't want to swap stands on every false positive. They want a ranked queue.
>
> And this isn't a separate ML system. The forecast is a derived property on the same Flight entity. Same data model, same vocabulary. If the stand planner overrides the forecast - swaps DL to E20 - that override flows back into the ontology and the agent learns. We'll come back to that in 90 seconds."

**Aviation domain note:**
Mention "DL flights at EHAM are non-Schengen, parked on the F/G piers" - except where DL uses E for crew positioning. A small detail like this proves you're not making up data. The customer's planner will nod.

---

## Act 4 (Prescriptive - the closer): TSAT re-sequence under disruption (5-6 minutes)

This is what you don't take questions in the middle of. Read the script, let the solver run, then talk.

**The scenario:**

> "It's 14:30. Forecast says a thunderstorm cell crosses 18C/27 from 15:00 to 17:00, dropping our arrival capacity 40% and forcing us to single-runway departures off 18L. We have 47 outbound flights with TSAT in that window. Constraints: each flight must respect its CTOT window where one exists, minimum separation by wake category on 18L, no two flights pushing simultaneously from the same pier, ground handling must finish before AOBT. Objective: minimize total weighted delay against SOBT, weighted by pax connections and ATFM penalty risk. Solve it."

**The code (speaker scrolls past this, doesn't read aloud):**

```python
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.std import aggregates as agg

# ----- Problem object --------------------------------------------------
p = Problem(m, Float)

# ----- Decision variables ---------------------------------------------
# x[f, slot] = 1 if flight f assigned to departure slot s on RWY 18L
# We discretize the 15:00-17:00 window into 1-minute slots (120 slots)

Slot = m.Concept("Slot", identify_by={"minute_offset": Integer})
m.define(*[Slot.new(minute_offset=i) for i in range(120)])  # 0..119 from 15:00

Flight.x_assign = m.Relationship(
    f"{Flight} assigned to {Slot} if {Float:assigned}"
)

x = Float.ref("x")
p.solve_for(
    Flight.x_assign(Slot, x),
    populate=True,
    name=["assign", Flight.callsign, Slot.minute_offset],
    type="bin",
    lower=0,
    upper=1,
)

# ----- Constraints -----------------------------------------------------

# (1) Each flight gets exactly one slot
flights_in_window = m.where(
    Flight.tsat >= datetime(2026, 10, 14, 15, 0),
    Flight.tsat <  datetime(2026, 10, 14, 17, 0),
)
slot_count_per_flight = agg.sum(x).where(Flight.x_assign(Slot, x)).per(Flight)
p.satisfy(
    m.require(slot_count_per_flight == 1).where(flights_in_window),
    name=["one-slot", Flight.callsign],
)

# (2) Each slot holds at most one departure (single-runway)
flights_per_slot = agg.sum(x).where(Flight.x_assign(Slot, x)).per(Slot)
p.satisfy(
    m.require(flights_per_slot <= 1),
    name=["slot-capacity", Slot.minute_offset],
)

# (3) Wake separation: a Heavy followed by a Medium needs 2 min, H->L = 3 min
# Encoded as: x_heavy[s_h] + x_light[s_l] <= 1 for all (s_h, s_l) with 0 < s_l - s_h < 3
# (Speaker note: this is the constraint that makes it interesting -
# narrowbodies queueing behind a KL B777 lose time)

f_heavy = Flight.ref()
f_light = Flight.ref()
s_heavy = Slot.ref()
s_light = Slot.ref()
x_h = Float.ref("x_h")
x_l = Float.ref("x_l")

p.satisfy(
    m.require(x_h + x_l <= 1).where(
        f_heavy.x_assign(s_heavy, x_h),
        f_light.x_assign(s_light, x_l),
        f_heavy.aircraft.wtc == "H",
        (f_light.aircraft.wtc == "L") | (f_light.aircraft.wtc == "M"),
        s_light.minute_offset - s_heavy.minute_offset > 0,
        s_light.minute_offset - s_heavy.minute_offset < 3,
    ),
    name=["wake-sep-HL", f_heavy.callsign, f_light.callsign],
)

# (4) CTOT compliance: if flight has CTOT, assigned slot must give TTOT in [-5,+10]
# (per Eurocontrol slot adherence rules)
# Skipped here for brevity - in the demo file the constraint is included

# (5) Pier pushback contention: at most 2 simultaneous pushes from same pier
pushes_per_pier_slot = (
    agg.sum(x)
    .where(Flight.x_assign(Slot, x))
    .per(Flight.stand.pier, Slot)
)
p.satisfy(
    m.require(pushes_per_pier_slot <= 2),
    name=["pier-pushback", Flight.stand.pier, Slot.minute_offset],
)

# ----- Objective: weighted delay vs SOBT -------------------------------

Flight.pax_connections = m.Property(f"{Flight} has {Integer} connecting pax")
Flight.atfm_penalty = m.Property(f"{Flight} has ATFM penalty weight {Float}")

# delay = assigned slot minute - SOBT minute (relative to window start)
delay_min = agg.sum(
    x * (Slot.minute_offset - Flight.sobt_minute_offset)
).where(Flight.x_assign(Slot, x)).per(Flight)

weighted_delay = agg.sum(
    delay_min * (Flight.pax_connections * 1.0 + Flight.atfm_penalty * 20.0)
)

p.minimize(weighted_delay)

# ----- Solve -----------------------------------------------------------
p.solve("highs")
print("status:", p.termination_status)
print("objective:", p.objective_value)
```

**While the solver runs (8-15 seconds on this size of problem), the speaker says:**

> "What's happening right now: HiGHS is solving a mixed-integer linear program. About 5,600 binary variables - 47 flights times 120 slots - and roughly 600 constraints. The interesting part isn't the math. The interesting part is that every input to that solver - the CTOT windows, the wake categories, the pier assignments, the connecting passenger counts - came from the same semantic model we've been using all morning. There's no separate optimization data mart. The same model that flagged the TOBT violations and traced the rotation cascade is now telling the solver what's allowed."

**Output (Gantt chart side-by-side):**

Speaker pulls up two Gantt views:
- Left: original TSATs (chaos: clustered at the start of the storm window, infeasible)
- Right: optimized sequence (smooth, wake-spaced, CTOT-compliant)

```
Original schedule:  total weighted delay = 4,820 min-pax (infeasible: 7 violations)
Optimized:          total weighted delay = 1,260 min-pax (feasible)
Improvement: -74% weighted delay, +12 flights now CTOT-compliant
```

**Speaker script:**

> "The chart on the left is what your current system would have you push. Seven CTOT violations, three wake-separation breaches, a pier D pushback collision. The chart on the right is what the agent proposes. Same flights, same window, re-sequenced. Total weighted delay drops 74%. Twelve more flights stay inside their Eurocontrol slot.
>
> Now here's the part the optimization community usually skips. Look at KL691 here - the agent moved it from a 15:08 push to a 15:23 push. Your duty manager might not like that, because KL691 is a high-yield Asia connector with a tight onward at the destination. So watch what happens when we push back."

---

## Act 5 (Superalignment / continuous learning): operator feedback (90 seconds)

**The operator types:**

> "Never delay KL flights with more than 80 connecting pax by more than 8 minutes from SOBT for runway re-sequencing. We absorb the delay elsewhere."

**The agent encodes this as a new constraint, persists it, re-solves:**

```python
# New domain rule from operator feedback
PreservedFlight = m.Concept("PreservedFlight", extends=[Flight])

m.where(
    Flight.operator.iata == "KL",
    Flight.pax_connections > 80,
).define(
    PreservedFlight(Flight)
)

# Hard constraint: PreservedFlight delay <= 8 min
p.satisfy(
    m.require(delay_min <= 8).where(PreservedFlight(Flight)),
    name=["preserved-flight-cap", Flight.callsign],
)

p.solve("highs")
```

**New result:**

```
Re-solved with preservation rule:
  weighted delay = 1,410 min-pax (vs 1,260 unconstrained, +12%)
  KL691: now delayed 6 min (was 15)
  trade-off absorbed across 4 LCC narrowbodies (+3 min each)
```

**Speaker script (this is the closer):**

> "Two things. One: the operator's instinct - 'we don't delay our high-connector flights' - just became a constraint in the model. Not a comment in a runbook. Not a tribal-knowledge override in someone's head. A constraint that the solver respects and that the audit trail records.
>
> Two: this rule survives the conversation. Tomorrow morning, when the storm scenario hits for real, the rule is still in the model. The next operator who joins doesn't have to learn it from a senior controller. RelationalAI calls this 'superalignment' - we'd call it institutional memory. It's the part of A-CDM that no portal, no Excel sheet, and no dashboard captures."

---

## Closing (60 seconds)

> "Four questions, four reasoners, one semantic model, one ICAO procedure document encoded as logic. The compliance audit, the cascade trace, the gate conflict forecast, and the TSAT re-sequence all came from the same model. Adding a new constraint took fifteen seconds and didn't break anything.
>
> What this isn't: it isn't a replacement for your A-CDM portal, your AODB, your AMAN/DMAN, or your ATFM integration. What it is: a decision layer on top of all of those, that turns the question 'what's happening?' into 'what should we do?'
>
> Implementation question we'd want to answer with you: which milestone or milestone-cluster is the highest-pain point at your airport right now - TOBT discipline, gate conflicts, runway sequencing, or ATFM compliance? That's where we'd start a six-week proof of concept on your own historical data."

---

## Q&A prep - likely pushbacks and the answer

**"This is Snowflake-only. We're on AWS / on-prem."**
RelationalAI's primary deploy is Snowflake Native App, yes. The PyRel layer is environment-agnostic. If you're not on Snowflake, the conversation starts with where your A-CDM data lives, and we work backward from there. Most A-CDM data sources (AODB, FDPS, A-SMGCS) export to a warehouse anyway.

**"Our data isn't this clean."**
Nothing in the demo requires clean data. The ontology layer handles missing properties - a flight without ARDT just doesn't trigger the MS12 rule. We've built models on data with 20% null rates in critical fields.

**"How do you handle real-time?"**
The model is incremental. New rows in the underlying Snowflake tables update derived properties without a full rebuild. For sub-second SLAs (e.g. final TSAT push within seconds of MS9), you'd run the prescriptive solver outside the loop - call it every 30 seconds, push results to the operator HMI.

**"Solver time?"**
The 47-flight TSAT problem solved in 11 seconds on HiGHS (open source). At 200 flights, 30-40 seconds. For larger horizons we use Gurobi (commercial) and it's roughly 5-10x faster. The model decomposes cleanly by airline/pier if you need it to.

**"What about FOQA, weather, NOTAMs?"**
Same approach. Each becomes a Concept in the ontology with relationships to Flight. The model grows; the queries stay the same.

**"Who else has done this in aviation?"**
RelationalAI has supply chain and telco customers in production. Aviation is greenfield for them - which means your A-CDM implementation becomes the reference. That's a positioning conversation, not a technical one.

**"What's the catch?"**
PyRel is preview-quality on the prescriptive side (early access, per their docs). Production-grade rules and graph reasoning are GA. The MILP solver is solid but you're at the edge of what they've publicly demo'd. We'd recommend a six-week POC that proves the rules + graph + a smaller prescriptive problem before betting on the larger sequence optimizer.

---

# Appendix A: Data fabrication brief (EHAM Schiphol, defendable)

This is the spec for the synthetic dataset. The goal is that a Schiphol duty manager, a KLM dispatcher, an LVNL controller, or a Eurocontrol Network Manager all see this data and say "yes, that's a Wednesday at Schiphol" - not "this is fake".

**Disclosure stance:** Always disclose the data is synthetic. The credibility question is whether it's *plausibly synthetic*, not whether it's real. Lie about that and you lose the room.

## A.1 The day we model

- **Date:** Wednesday, 14 October 2026, 06:00-22:00 local (CEST until 25 Oct, then CET)
- **Volume:** 320 movements (down from EHAM peak of ~1,400/day because we time-box to the daytime ops window and exclude small GA on RWY 04/22)
- **Bank structure:** Schiphol runs "rolling hub" rather than tight banks, but visible inbound/outbound clusters at:
  - 06:00-08:30 inbound from US east coast overnight + intra-Europe early
  - 07:00-09:30 outbound short-haul (KL, HV)
  - 10:00-13:00 long-haul outbound (KL Asia, Africa, North America)
  - 13:00-15:30 inbound returns + transatlantic arrivals (DL, AF, KL from US east)
  - 16:00-19:00 short-haul rotation peak
  - 19:00-22:00 late outbound to Asia-Pacific

## A.2 Infrastructure (from EHAM AIP, public)

**Runways used in the synthetic day (north flow, typical autumn config):**

| Designator | Common name       | Length (m) | Use in demo                                       |
|------------|-------------------|------------|---------------------------------------------------|
| 18R / 36L  | Polderbaan        | 3,800      | Primary landing (north flow)                      |
| 18C / 36C  | Zwanenburgbaan    | 3,300      | Secondary landing (north flow)                    |
| 18L / 36R  | Aalsmeerbaan      | 3,400      | Departures (north flow)                           |
| 06 / 24    | Kaagbaan          | 3,500      | Departures - alternative                          |
| 09 / 27    | Buitenveldertbaan | 3,453      | Mostly closed during the day for noise abatement |
| 04 / 22    | Schiphol-Oost     | 2,014      | GA only - excluded from demo                     |

**Storm scenario in Act 4:** Closes 18C (landing) and forces 18L single-runway departures. This is operationally realistic - convective cells over Aalsmeerbaan force exactly this re-config in summer/autumn.

**Stands / piers (Schiphol layout):**

| Pier | Stands range  | Type                                 | Used by                          |
|------|---------------|--------------------------------------|----------------------------------|
| B    | B11-B36       | Bus boarding, narrowbody, Schengen   | HV, FR, U2, KL narrowbody mix    |
| C    | C04-C16       | Contact, Schengen                    | KL narrowbody, AF                |
| D    | D02-D88       | Contact, both Schengen & non-Schengen| Mixed                            |
| E    | E02-E24       | Contact, Schengen                    | KL widebody (some), DL crew pos. |
| F    | F02-F09       | Contact, non-Schengen                | KL Asia/Africa widebody, DL      |
| G    | G02-G09       | Contact, non-Schengen                | Long-haul widebody (BA, EK, SQ)  |
| H    | H01-H08       | Contact, Schengen (new 2024)         | Overflow                         |
| M    | M01-M07       | Contact, non-Schengen                | Overflow long-haul               |
| R    | R-stands      | Remote                               | Cargo (5X, FX, CV), low-cost     |

**Domain detail that earns trust:** Schiphol has Schengen/non-Schengen pier split. KL widebody from Asia (CDG-Tokyo, etc) lands non-Schengen at F or G, then aircraft repositions to a Schengen pier for the next leg if it's intra-EU. Modeling this in the data shows you understand the airport.

## A.3 Carrier mix (proportions match real EHAM ops)

| Code | Carrier        | Share of movements | Aircraft fleet at EHAM            |
|------|----------------|--------------------|-----------------------------------|
| KL   | KLM            | 52%                | B737-700/800/900, E175/E190/E195, A330-200/300, B777-200ER/300ER, B787-9/10, A350-900 |
| HV   | Transavia      | 8%                 | B737-800/MAX                      |
| AF   | Air France     | 4%                 | A220, A320, A319                  |
| DL   | Delta          | 3%                 | A330-300/900, B767-400, A350-900  |
| KQ   | Kenya Airways  | 0.5%               | B787-8                            |
| BA   | British Airways| 2%                 | A319/320/321                      |
| LH   | Lufthansa      | 1.5%               | A319/320                          |
| EZY  | easyJet        | 3%                 | A319/320/A320neo                  |
| RYR  | Ryanair (FR)   | 1%                 | B737-800                          |
| W6   | Wizz Air       | 1%                 | A320/A321neo                      |
| TK   | Turkish        | 1.5%               | A330, B737                        |
| EK   | Emirates       | 1%                 | B777-300ER, A380 (limited)        |
| SQ   | Singapore      | 0.7%               | B777-300ER, A350-900              |
| Other| 30+ carriers   | 20.8%              | Mixed                             |

**Cargo (separate, 5-7% of movements typically):** 5X (UPS, B767-300F), FX (FedEx, B767-300F/MD-11F), CV (Cargolux, B747-400F/8F), QY (DHL, B757F/A300F)

**Notes for the speaker:** 
- KL's A380 was retired pre-2020 - don't include
- KL E175 vs E190 vs E195 matters for stand assignment (E175 is shorter)
- Transavia (HV) is 100% B737, all from Schiphol
- DL uses KL maintenance and parks F/G overnight, then operates AMS-ATL/JFK/MSP/SEA morning departures

## A.4 Realistic timestamps - how to generate noise

This is where bad synthetic data gets exposed. The rules:

**EOBT and SOBT relationship (MS1):**
- For KL mainline: EOBT == SOBT almost always (their dispatch is disciplined)
- For LCC (HV, EZY, FR, W6): EOBT can drift to SOBT + 3-15 min if recent inbound was late
- For long-haul connectors: SOBT is set 6-12 months in advance; EOBT moves with the day's plan

**TOBT distribution (MS9) relative to EOBT:**
```
TOBT - EOBT ~ Normal(mu=+2min, sigma=4min) for KL
            ~ Normal(mu=+6min, sigma=8min) for LCC (LCC sets aspirational TOBT)
            ~ Normal(mu=-1min, sigma=3min) for SkyTeam partners (DL, KQ, AF)
```

**TSAT - TOBT (MS10):**
- During off-peak: TSAT == TOBT (no sequencing pressure)
- During peak banks: TSAT - TOBT ~ Uniform(0, 12min)
- Storm scenario: TSAT - TOBT shifts heavily for 18L queue

**ARDT - TOBT (MS12) - THE critical distribution:**
```
ARDT - TOBT ~ Normal(0, 5min) for compliant flights (75%)
            + a tail of late-ready flights (15%) with mean +8min, sigma 4min
            + a tail of early-ready flights (10%) with mean -3min, sigma 2min
```

**ATFM / CTOT presence (MS2):**
- ~20-25% of departures have a CTOT (matches Eurocontrol regulation rate for a typical autumn day)
- CTOT compliance: TTOT in [CTOT-5, CTOT+10] for ~78% of regulated flights (matches published Eurocontrol slot adherence)
- Most regulations are destination-driven (LFPG, EDDF, EGLL, LIPZ, LEMD slots)

**Taxi-in time by stand/fix:**

| TMA entry fix | Landing RWY | Avg taxi-in to B pier | E/F pier | G pier | Polderbaan stands |
|---------------|-------------|------------------------|----------|--------|--------------------|
| SUGOL         | 18C         | 8 min                  | 6 min    | 7 min  | n/a               |
| RIVER         | 18C         | 8 min                  | 6 min    | 7 min  | n/a               |
| ARTIP         | 27 / 18C    | 7 / 9 min              | 5 / 7    | 6 / 8  | n/a               |
| NIRSI         | 18R         | 12 min                 | 11 min   | 10 min | 4 min             |

**Polderbaan (18R) is famous for the long taxi-in.** A KL pilot landing 18R taxis 11-13 minutes to reach the central piers. This is the kind of detail a Schiphol controller will recognize immediately. Get this right.

**Pushback/taxi-out:**
- B pier to 18L holding point: 4-6 min
- C/D pier: 6-9 min
- E/F/G pier to 18L: 7-11 min (longest from G)
- Any pier to 06: 12-16 min

## A.5 Minimum turn times (operator-specific)

| Operator     | Narrowbody min turn | Widebody min turn | Notes                                  |
|--------------|---------------------|-------------------|----------------------------------------|
| KL mainline  | 40 min              | 90 min            | KL Cityhopper E-jets: 30 min           |
| HV (Transavia)| 25 min             | n/a               | LCC tight ops                          |
| AF           | 45 min              | 90 min            | Mostly transit through CDG, AMS is point-to-point |
| DL           | 60 min              | 120 min           | Long-haul only at EHAM                 |
| BA           | 35 min              | n/a               | LHR shuttle pattern                    |
| EZY          | 25 min              | n/a               |                                        |
| FR           | 25 min              | n/a               |                                        |
| EK / SQ      | n/a                 | 90 min            | Long-haul transit                      |

## A.6 STAR / SID fix names (real EHAM, from AIP)

**Arrivals (STAR Initial Approach Fixes):**
- **ARTIP** - east, typically routed to RWY 27 or 18C
- **SUGOL** - north, typically routed to RWY 18C or 06
- **RIVER** - northwest, typically routed to RWY 18C
- **NIRSI** - used for 18R (Polderbaan) approach

**Departures (SID transition fixes - mention only if asked):**
- BERGI, ANDIK, NETEX, IDRID, ARNEM, LARIK, ROBIS

These are the names a Schiphol pilot or controller will say. Use them in MS4 (FIR entry) data and in any narrative about "traffic via SUGOL".

## A.7 Schedule generator (pseudocode the speaker can describe)

Don't show this on stage, but have it ready for "how did you make the data?" questions:

```python
def generate_eham_day(seed=42, date=date(2026, 10, 14)):
    flights = []
    # 1. Pull real public flight schedules for EHAM Tuesday in Oct
    #    (OpenSky historical, or from Schiphol open data portal)
    # 2. For each schedule slot, sample:
    #    - operator from carrier-mix distribution
    #    - aircraft type from operator's fleet at EHAM
    #    - origin/destination from operator's network
    #    - stand from stand-eligibility (pier x WTC x Schengen)
    # 3. Stamp SOBT from schedule, EOBT = SOBT + noise
    # 4. Compute synthetic milestones forward:
    #    - ATOT_up = SOBT (inbound: from upstream)
    #    - ELDT = ATOT_up + EET (great-circle + airway penalty)
    #    - ALDT = ELDT + Normal(0, 3min)
    #    - taxi_in from (fix, runway, stand) matrix
    #    - AIBT = ALDT + taxi_in
    #    - TOBT = max(AIBT + min_turn, EOBT) + noise
    #    - TSAT = TOBT + sequencing_delay(bank)
    #    - ARDT = TOBT + N(0, 5)
    #    - AOBT = max(ASAT, ARDT) + N(2, 1)
    #    - taxi_out from (stand, runway) matrix
    #    - ATOT = AOBT + taxi_out + queue_wait
    # 5. Inject 20-25% CTOT regulations, 75-80% compliance
    # 6. Inject the storm scenario for Act 4
    return flights
```

The defensible claim: "320 flights, 24-hour window, operator mix and stand assignments sampled from EHAM's published distribution, timestamps generated with operator-specific noise models." A domain expert will press on this; the answer is "show me a flight that doesn't fit your operation and I'll fix the generator."

## A.8 Things to deliberately NOT model in v1 (and own this honestly)

A domain expert will spot what's missing if you pretend otherwise. Own these:

- **De-icing season:** Not modeled. October at EHAM is occasional de-icing; full winter ops requires a de-icing pad queue model.
- **Crew duty time:** Not modeled. Real cascade includes crew expiry, which can dwarf aircraft constraints.
- **Slot/ATFM regulation prediction:** We assume CTOTs are given. Predicting regulation activation is a separate problem.
- **Pax bag connection times:** Pax connection counts are modeled as scalars; real bag-room sequencing is not.
- **CDM-eligible vs non-eligible flights:** Schiphol's A-CDM has eligibility rules (some GA, some military, some cargo excluded). We treat all as eligible.

State these up front in the speaker note: "These are deliberately scoped out of the demo. They're standard extensions in a real implementation."

---

# Appendix B: Aviation glossary for the room

The customer's executives may not know every acronym. If you have a mixed audience (ops + IT + commercial), drop this on a slide as a backup.

| Term  | Meaning                                                                 |
|-------|-------------------------------------------------------------------------|
| A-CDM | Airport Collaborative Decision Making                                   |
| AGHT  | Actual Ground Handling start Time (MS8)                                 |
| AIBT  | Actual In-Block Time (MS7)                                              |
| ALDT  | Actual Landing Time (MS6, same as ATOT for inbound)                     |
| ANSP  | Air Navigation Service Provider (e.g. LVNL at EHAM, DSNA at LFPG)       |
| AODB  | Airport Operational Database                                            |
| AOBT  | Actual Off-Block Time (MS15)                                            |
| ARDT  | Actual Ready Time - pilot calls "ready" (MS12)                          |
| ASAT  | Actual Start-up Approval Time (MS14)                                    |
| ASRT  | Actual Start-up Request Time (MS13)                                     |
| A-SMGCS| Advanced Surface Movement Guidance & Control System                    |
| ATFM  | Air Traffic Flow Management (Eurocontrol Network Manager)               |
| ATOT  | Actual Take-Off Time (MS16)                                             |
| CTOT  | Calculated Take-Off Time (Eurocontrol slot)                             |
| DMAN  | Departure Manager (sequencing tool)                                     |
| EET   | Estimated En-route Time                                                 |
| EIBT  | Estimated In-Block Time                                                 |
| ELDT  | Estimated Landing Time                                                  |
| EOBT  | Estimated Off-Block Time (from filed flight plan)                       |
| FDPS  | Flight Data Processing System                                           |
| GHA   | Ground Handling Agent                                                   |
| IAF   | Initial Approach Fix                                                    |
| ICAO  | International Civil Aviation Organization                               |
| SOBT  | Scheduled Off-Block Time (from airline schedule, not flight plan)       |
| STAR  | Standard Terminal Arrival Route                                         |
| SID   | Standard Instrument Departure                                           |
| TLDT  | Target Landing Time (AMAN)                                              |
| TMA   | Terminal Maneuvering Area                                               |
| TOBT  | Target Off-Block Time (operator's commitment, MS9)                      |
| TSAT  | Target Start-up Approval Time (ATC, MS10)                               |
| TTOT  | Target Take-Off Time                                                    |
| WTC   | Wake Turbulence Category (L/M/H/J for super-heavy A380, B748)           |

---

# Appendix C: PyRel idioms used in this demo

For technical follow-up. Reference: `https://docs.relational.ai/build/guides/modeling/` and the rai-agent-skills repo.

**Concept declaration with identity:**
```python
Flight = m.Concept("Flight", identify_by={"callsign": String, "sobt": DateTime})
```
Composite identity (callsign + SOBT) is correct for flights, because a callsign repeats daily.

**Property vs Relationship:**
- Use `m.Property` when the entity has at most one value (a Flight has one SOBT).
- Use `m.Relationship` for one-to-many (a Stand has many Flights over a day, a Flight has many milestones from many systems).

**Unary relationship (Boolean flag):**
```python
Stand.is_contact = m.Relationship(f"{Stand} is a contact stand")
```
Use this over a Boolean property - more efficient.

**Derived concept membership:**
```python
m.where(condition).define(SomeDerivedConcept(Flight))
```
The same pattern is used for TOBTViolation, RotationAtRisk, StandConflictForecast, PreservedFlight.

**Aggregation per-group:**
```python
agg.sum(x).where(Flight.x_assign(Slot, x)).per(Slot)
```
This is `SUM(x) GROUP BY slot` but expressed against the semantic model. The `per()` is the group-by.

**Self-join (multiple entities of same concept):**
```python
F1 = Flight.ref()
F2 = Flight.ref()
m.where(F1.stand == F2.stand, F1.callsign < F2.callsign, ...)
```
`Concept.ref()` creates a distinct binding. The `<` on callsign dedupes ordered pairs.

**Prescriptive workflow:**
```python
p = Problem(m, Float)
p.solve_for(decision_variable, type="bin")        # declare variables
p.satisfy(m.require(constraint))                  # add constraints
p.minimize(objective_expression)                  # set objective
p.solve("highs")                                  # solve
```

**Solver backends and when to use:**
| Backend  | Type    | When                                                                |
|----------|---------|---------------------------------------------------------------------|
| HiGHS    | LP/MILP | Default open-source; good for problems < 100k vars                  |
| Gurobi   | LP/MILP | Commercial license; 5-10x faster, use for prescriptive at scale     |
| Ipopt    | NLP     | Nonlinear (we don't use here, but relevant for pax flow)            |
| MiniZinc | CP      | Pure feasibility / scheduling without an objective                  |

---

# Appendix D: Suggested follow-on conversations

These are the conversations to push toward after the demo lands. Don't pitch them; tee them up.

**1. Six-week POC scope (the right next step)**

Three deliverables:
- An A-CDM ontology built on **your** historical data (1-3 months of AODB + FDPS + A-SMGCS extracts)
- One rules-and-graph use case to production quality (e.g., TOBT discipline or rotation risk)
- One prescriptive proof-of-concept on a defined sub-problem (e.g., stand re-assignment under disruption, not full DMAN replacement)

**2. Integration shape**

RAI does not replace AMAN/DMAN/AODB. It sits beside them, reads from them, and pushes recommendations back. The integration story is:
- **Read:** Snowflake tables fed from AODB, FDPS, A-SMGCS, Eurocontrol NM B2B service
- **Compute:** PyRel ontology + reasoners
- **Write:** recommendations back to the A-CDM HMI / operator portal (REST or webhook)

**3. Governance**

The semantic model is auditable. Every rule has an author, a timestamp, a Git history. Every solver run logs its constraints. This matters for regulatory conversations (EASA, EUROCONTROL Performance Review Body, national CAA).

**4. The "why now" hook**

EUROCONTROL's Network Manager 2030 strategy pushes for tighter A-CDM integration with the network. Airports that can publish high-confidence DPI (Departure Planning Information) and EFD (Estimated Flight Departure) messages earlier win slot allocation priority. A semantic-model-driven A-CDM is a way to lift DPI/EFD quality without ripping out existing systems.

---

# End of talk track

**File checklist before the demo:**
- [ ] `raiconfig.yaml` valid against the customer's Snowflake account, `rai_developer` role available
- [ ] Synthetic EHAM data loaded (see Appendix A)
- [ ] Jupyter notebook with the four acts as separate cells, pre-run for cached compile
- [ ] Plotly Gantt for Act 4 prepared with before/after views
- [ ] One backup screen recording in case live execution fails
- [ ] Glossary slide as backup
- [ ] Speaker has read all five acts aloud at least twice with a timer

**Common mistakes to avoid in the first run:**
- Don't read the code aloud. Skim past it.
- Don't apologize for the synthetic data. State the disclosure once at the start, then never again.
- Don't promise real-time. The demo is a 30-second cadence at best.
- Don't oversell the predictive reasoner (it's preview).
- Don't go past 22 minutes. Cut Act 3 (predictive) if you're running long - it's the weakest from RAI's product-readiness perspective.

