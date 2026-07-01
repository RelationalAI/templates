# Hospital Staffing — Analyst Runbook

A nurse manager faces a real tradeoff: minimize overtime cost, or minimize unmet patient demand — the two pull against each other. Rather than collapse them into one weighted penalty, this template traces the whole cost-vs-service Pareto frontier with the epsilon-constraint method, then flags the knee — the best-value operating point. The dataset is 6 nurses (each with a skill level and cost), 3 shifts (each with a patient demand and staffing minimums), and an availability matrix. The analysis solves a series of staffing programs to map the frontier.

```text
6 nurses (cost, skill) · 3 shifts (demand 45/60/25, min staff & skill) · 18 availability pairs
      │
      ▼
/rai-prescriptive-problem-formulation + /rai-prescriptive-solver-management
   • decision: binary nurse-shift assignment + overtime hours + unmet demand per shift
   • constraints: availability; each nurse 1–2 shifts; min staff & skill per shift;
     patients served capped by demand and nursing capacity; unmet = demand − served
   • objective: minimize overtime cost subject to a tightening cap on total unmet (epsilon-constraint)
   • HiGHS — two anchors + 5 epsilon points      -> Pareto frontier, all OPTIMAL
      │
      ▼
/rai-prescriptive-results-interpretation
   • frontier from a cheapest-overtime anchor (most unmet) to a full-service anchor (most overtime)
   • a knee: service improves cheaply, then overtime climbs steeply to reach zero unmet
```

Each prompt is pasted into a fresh agent session loaded with the named `/rai-*` skill (named at the start of each prompt). They run in order in a single session — the formulate step reads the `Nurse`/`Shift` concepts and availability the build step created, and the interpret step reads the frontier the sweep produced.

---

## 1. Build the ontology

**Prompt:** /rai-build-starter-ontology Build an ontology from `data/nurses.csv` (each nurse has a skill level, an hourly cost, regular hours, and an overtime multiplier), `data/shifts.csv` (each shift has a patient demand, a minimum nurse count, a minimum skill, and a patients-per-nurse-hour rate), and `data/availability.csv` (which nurses are available for which shifts). Model availability as a relationship from nurse to shift.

**Response:** Loads `Nurse` (6, with `skill_level`, `hourly_cost`, `regular_hours`, `overtime_multiplier`), `Shift` (3: Morning demand 45, Afternoon 60, Night 25, each with `min_nurses` and `min_skill`), and a `Nurse.available_for(Shift)` relationship from the 18 availability rows.

## 2. Examine the ontology

**Prompt:** /rai-querying What concepts and relationships does the ontology have, and how many rows are in each?

**Response:** Two concepts — 6 `Nurse` (cost, skill) and 3 `Shift` (patient demand 45/60/25, staffing minimums) — linked by `available_for` with 18 nurse-shift availability pairs.

## 3. Trace the cost-vs-service frontier

**Prompt:** /rai-prescriptive-problem-formulation + /rai-prescriptive-solver-management Trace the tradeoff between overtime cost and unmet patient demand. Assign nurses to shifts (binary, only where available; each nurse works 1 or 2 shifts; each shift meets its minimum staff and skill), track overtime hours beyond regular hours, and let patients served be capped by both demand and nursing capacity, with unmet demand the shortfall. First find the two anchors — the minimum-overtime schedule and the minimum-unmet schedule — then sweep five intermediate caps on total unmet demand, each minimizing overtime cost (the epsilon-constraint method). Report each point on the frontier.

**Response:** All solves OPTIMAL (HiGHS). The anchors bound the frontier: the minimum-overtime schedule keeps overtime cost lowest while leaving the most patient demand unmet, and the best-service schedule drives unmet demand to zero by taking on the most overtime. The epsilon caps step between them, each the cheapest schedule that meets its service level. (The exact unmet counts and overtime dollars depend on how nurse capacity, patient demand, and overtime are modeled, so the frontier's shape — not specific figures — is the reproducible result.)

## 4. Find the knee

**Prompt:** /rai-prescriptive-results-interpretation Where's the knee of the cost-vs-service frontier — the best-value operating point — and how fast does overtime cost rise as we push toward full service?

**Response:** The frontier has a clear knee: overtime stays flat (the cheapest schedules) across a range of service levels, then rises steeply as you push toward serving every patient — the last increments of service are the most expensive, so the cost-per-patient accelerates as the frontier turns convex. The recommended operating point is the knee, capturing most of the achievable service before overtime cost takes off; closing the final gap to zero unmet is disproportionately expensive.

## Data

Bundled CSVs in `data/`: 6 nurses, 3 shifts, 18 availability pairs. The epsilon sweep (5 interior points across the unmet range) is built into the script. Full model in `hospital_staffing.py`.
