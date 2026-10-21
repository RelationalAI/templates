# SNOWSIGHT_DEMO.md - 3-question Snowflake Intelligence talk track

This is the 5-minute version of the demo, delivered directly inside
Snowflake Intelligence. After `agent/deploy.py deploy`, an `airport_operations` agent
appears in the SI picker. Three questions land the value:

> **One-click visualisation.** Each agent response that returns tabular
> data shows a small chart icon next to the result. Click it and Snowsight
> auto-picks a chart type from the table shape. For this demo the agent
> also includes an `chart_hint` field (`{type, x, y, title}`) in its tool
> response and mentions the suggested chart in its text reply — that's the
> cue for the speaker to click the chart button and land the visual. The
> chart-friendly query variants (`*_chart` in `agent/queries.py`) return
> tighter 2-3 column DataFrames specifically shaped for Snowsight's auto
> charter.

> **Expected latency:** warm reasoner queries completed in seconds, but
> CoWork answers took longer because of agent orchestration and sproc setup.
> Cold engine provisioning took several minutes. Warm the queries before a
> live presentation; do not promise a fixed answer time.

---

## Question 1 - The rules layer

**Type:**
> Show TOBT violations by handler in the last four hours.

**Expected answer:** A table or chart with KLG (7), AGS (5), DNATA (3),
MENZIES (2). The agent will reach into `tobt_violations_by_handler` in
`agent/queries.py`, which delegates to the `TOBTViolation(Flight)` derived
concept in the ontology.

**Speaker beat (15 seconds):**
> "The rule is encoded once - 'ARDT deviates from TOBT by more than 5
> minutes' - and queryable for any time window. It composes with the next
> question."

---

## Question 2 - The graph layer

**Type:**
> Trace the rotation cascade if KL1234 is late.

**Expected answer:** A list of 6 downstream flights at risk: KL1235, KL0407,
KL1402, KL1601, HV5821, AF1241. The agent delegates to
`rotation_cascade_from_kl1234`, which runs the Graph reasoner over the
union of `feeds_callsign`, `slot_blocks`, and `shares_stand` edges.

**Speaker beat (20 seconds):**
> "Six downstream flights are reachable through three edge types. This is
> graph reachability, not a calculation of crew or ATFM-slot impact."

---

## Question 3 - The prescriptive layer

**Type:**
> Re-sequence the storm-window TSATs to minimize weighted delay.

**Expected answer:** A table of 47 (callsign, minute_offset, delay_min)
rows. KL691 stays at 0 delay in this baseline; passenger connections are
not part of the baseline objective. The
agent delegates to `tsat_resequence_under_storm`, which builds and
solves a MIP with HiGHS via the Prescriptive reasoner.

**Speaker beat (25 seconds):**
> "About 5,600 binary variables, with runway, pier, timing, and wake
> constraints. The objective minimizes delay weighted by ATFM penalty."

---

## (Optional) Question 4 - The persistent-rule moment

**Type:**
> Re-solve, but never delay KL flights with more than 80 connecting pax by
> more than 8 minutes from SOBT.

**Expected answer:** The agent delegates to `tsat_preservation_impact`.
Both solves are optimal at objective 1079.6, with zero baseline cap breaches.
KL691 stays at 0 delay; three slots differ across equal-objective solutions.
The cap is valid but did not bind on this seed data.

**Speaker beat (15 seconds):**
> "The rule is now explicit and auditable. In this scenario the baseline
> already satisfies it, so we should not claim a cap-driven improvement.
> That check is part of validating a decision, not just producing one."

---

## What to NOT say

- Don't say "this is just a database query." It is, and it isn't - the agent
  picks the right query from a catalog *and* the underlying queries
  compose graph + LP + rules across one model. The point isn't that any one
  of these is impossible. The point is that they all sit on one semantic
  layer.
- Don't say "the LP is the special part." The rules + graph + LP
  composition is the special part. Anyone with HiGHS can solve a MIP.
- Don't say "we replace your AODB." We don't. We sit on top of it as a
  decision layer.
