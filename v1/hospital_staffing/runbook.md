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
   • frontier runs from (130 unmet, $0 overtime) to (0 unmet, full overtime)
   • knee at ~43 unmet still costs $0; past it cost climbs steeply (~$15.51/patient, then steeper)
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

**Response:** All solves OPTIMAL (HiGHS). The anchors bound the frontier: the minimum-overtime schedule costs **$0** but leaves **130 patients unmet**, while the best-service schedule reaches **0 unmet** only by taking on substantial overtime. The five epsilon caps step across the [0, 130] unmet range, each giving the cheapest schedule that meets that service level.

## 4. Find the knee

**Prompt:** /rai-prescriptive-results-interpretation Where's the knee of the cost-vs-service frontier — the best-value operating point — and how fast does overtime cost rise as we push toward full service?

**Response:** Overtime stays at **$0 all the way down to about 43 unmet patients** — service improves for free until then, which is the knee. Past it, cost climbs steeply: roughly **$15.51 per additional patient** served in the next segment, and steeper still on the final push to zero unmet (the cost-per-patient accelerates as the frontier turns convex). The recommended operating point is the knee at ~43 unmet with $0 overtime; closing the last gap to full service is disproportionately expensive.

## Data

Bundled CSVs in `data/`: 6 nurses, 3 shifts, 18 availability pairs. The epsilon sweep (5 interior points across the unmet range) is built into the script. Full model in `hospital_staffing.py`.
