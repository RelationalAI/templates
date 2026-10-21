# DEMO_QUESTIONS.md - The 5 acts as plain-English questions

These are the questions an A-CDM operator would type into a Snowflake
Intelligence search box. They map 1:1 to the `agent/queries.py` functions
exposed to the Cortex agent.

---

## Q1. Act 1 (Rules) - TOBT compliance audit

**"Show TOBT violations by ground handler in the four hours before 14:30
on October 14, 2026. Give the counts and average ready-time deviation."**

| Why it matters | The derived rule flags departures whose ARDT differs from TOBT by more than five minutes. This query aggregates the violations by handler; it does not list every flight or prove any removal action occurred. |
|----------------|---|
| Reasoner       | Rules (logic). The `TOBTViolation(Flight)` derived concept defines the rule once at the ontology layer. The query reuses it under a 4-hour filter. |
| Expected shape | KLG dominates (7), AGS next (5), then DNATA (3, negative deviation = calling ready early), MENZIES (2). |

---

## Q2. Act 2 (Graph) - Rotation cascade

**"Which flights are reachable downstream from KL1234 through aircraft
rotation, slot-block, and stand-contention connections? List the six
other callsigns."**

| Why it matters | Existing AODBs do inbound-outbound pairing for one aircraft. They don't propagate the delay across stand conflicts to OTHER carriers' flights using the same gate area. |
|----------------|---|
| Reasoner       | Graph. The cascade is the union of three edge types over the same ontology: `feeds_callsign` (rotation), `slot_blocks` (pushback contention), and `shares_stand` (stand-occupancy overlap). RAI's Graph reasoner walks reachability. |
| Expected shape | Six other callsigns: AF1241, HV5821, KL0407, KL1235, KL1402, KL1601. The raw reachability table also contains KL1234 itself. This query does not calculate crew, gate, ATFM-slot, or time-bounded impacts. |

---

## Q3. Act 3 (Predictive heuristic) - MS5 gate-conflict ranking

**"Rank inbound flights landing between 14:30 and 15:00 on October 14
by the deterministic MS5 conflict-priority score. Show the top five."**

| Why it matters | Stand planners don't want a yes/no alarm on every false positive. They want a ranked queue so they can intervene on the top 1-2 only. |
|----------------|---|
| Reasoner       | Deterministic heuristic in PyRel (Predictive reasoner is preview). Score = time-pressure + pax-connection weight + pier-bonus - WTC-mismatch penalty. All weights are PyRel-derived properties; the ranking is `.select(...ms5_score...).sort_values()`. |
| Expected shape | Eleven candidates. Top five: KL0164 (0.675), KL1234 (0.649), KL0302 (0.519), KL0918 (0.508), DL0036 (0.501). This is a score, not a calibrated probability or proof of an actual gate conflict. |

---

## Q4. Act 4 (Prescriptive) - TSAT re-sequence under storm

**"Run the curated TSAT storm-window re-sequencing optimization for
October 14. How many flights are assigned, and what are the first five
callsigns with their slot offsets and delays?"**

| Why it matters | Manual re-sequencing of 47 flights with 5 constraints isn't tractable. The current handoff between AMAN/DMAN and the duty manager is "best effort". |
|----------------|---|
| Reasoner       | Prescriptive. Binary decision `FlightSlot.assign_base` over 47 flights x 120 one-minute slots. Constraints: one slot per flight, one flight per minute, no early push, at most one push per pier per minute, wake separation. Objective: minimize delay weighted by `1 + 20 * ATFM penalty`. CTOT is not a hard bound and connecting passengers are not in this baseline objective. |
| Expected shape | `OPTIMAL`, 47 flights, objective 1079.6. First five: KL0669 at offset 0 (8 min delay), KL0842 at 1 (5), KL0407 at 2 (2), KL0144 at 4 (7), KL0256 at 5 (1). |

---

## Q5. Act 5 (Persistent rule) - Operator-provided preservation rule

**"Apply an eight-minute maximum delay for KL flights with more than 80
connecting passengers. Compare the baseline and preserved solutions:
did the rule bind, did the objective change, and what happened to KL691?"**

| Why it matters | The operator rule is represented by the derived `PreservedFlight` concept and an eight-minute cap property, then applied as a solver constraint. The comparison also checks whether that rule was actually binding on this data. |
|----------------|---|
| Reasoner       | Rules + Prescriptive. The rule becomes a `PreservedFlight(Flight)` derived concept and an aggregate-delay constraint `sum(assign * delay) <= 8` per preserved flight. Re-solving picks up the constraint automatically because the constraint reads from the ontology. |
| Expected shape | Both solves are `OPTIMAL` at objective 1079.6. Baseline cap breaches: zero. KL691 is at zero delay in both. Three flight slots differ across alternative optimal solutions, but the cap did not force the change. |
