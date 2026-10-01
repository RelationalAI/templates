# Shift Assignment — Analyst Runbook

A scheduling manager wants to staff every shift from a small hourly workforce without violating anyone's availability, without overstaffing past capacity, and without overloading any worker — then see which minimum-coverage targets the current team can actually sustain. The dataset is 10 workers, 3 daily shifts (Morning, Afternoon, Night) with capacities, and 22 worker-shift availability pairs. The analysis solves a constraint-satisfaction problem and sweeps three minimum-coverage targets (1, 2, 3 workers per shift) in a single solve.

```text
10 workers, 3 shifts (capacity), 22 availability pairs
      │
      ▼
/rai-prescriptive-problem
   • decision: binary assign per (worker, shift, scenario), only over available pairs
   • constraints: each shift staffed ≥ min_coverage and ≤ capacity; each worker ≤ 1 shift
   • feasibility (no objective); coverage scenarios swept 1 / 2 / 3 in one solve
   • solved as a CSP                             -> OPTIMAL (satisfiable) at all 3 levels
      │
      ▼
/rai-prescriptive-results
   • feasible at all three targets; minimum staffing 3 / 6 / 9 across the shifts
   • triple coverage needs 9 of the 10 workers — the roster's sustainable ceiling
```

Each prompt is pasted into a fresh agent session loaded with the named `/rai-*` skill (named at the start of each prompt). They run in order in a single session — the formulate step reads the `Worker`/`Shift` concepts and the availability relationship the build step created, and the interpret step reads the `Worker.x_assign` decisions the solve wrote back.

---

## 1. Build the ontology

**Prompt:** /rai-ontology Build an ontology from `data/workers.csv`, `data/shifts.csv` (each shift has a capacity), and `data/availability.csv` (worker-shift pairs the worker is available for). Model availability as a relationship from worker to the shifts they can work.

**Response:** Loads `Worker` (10), `Shift` (3: Morning capacity 3, Afternoon 4, Night 3), and a `Worker.available_for(Shift)` relationship populated from the 22 availability pairs.

## 2. Examine the ontology

**Prompt:** /rai-pyrel What concepts and relationships does the ontology have, and how many rows are in each?

**Response:** Two concepts — 10 `Worker` and 3 `Shift` (with `capacity`) — linked by `available_for` with 22 worker-shift availability pairs.

## 3. Staff the shifts across coverage targets

**Prompt:** /rai-prescriptive-problem Is there a feasible assignment of workers to shifts where each shift has at least its minimum coverage and no more than its capacity, each worker works at most one shift, and no one is assigned to a shift they're unavailable for? Solve it for three minimum-coverage targets — 1, 2, and 3 workers per shift — in a single solve, with the coverage target as a first-class scenario concept and the assignment decision indexed by (worker, shift, scenario). Persist the assignments to the ontology.

**Response:** OPTIMAL (satisfiable) at all three coverage levels — 66 binary variables (22 availability pairs x 3 scenarios), 48 constraints. The assignment is written back as `Worker.x_assign(Shift, Scenario)`. This is a feasibility problem with no objective, so the solver returns one valid assignment per level — an alternative valid assignment may differ run to run.

## 4. Read the staffing levels

**Prompt:** /rai-prescriptive-results For each coverage target, what's the minimum staffing the team needs, and how much coverage can the current roster sustain?

**Response:** All three targets are satisfiable. Meeting 1, 2, and 3 workers per shift requires at minimum **3, 6, and 9 staffed slots** across the three shifts. With 10 workers each capped at one shift, even triple coverage (9 slots) fits — with one worker to spare — so **3-per-shift is the sustainable ceiling** for this roster; any higher target, or losing availability, would risk infeasibility. (Because there's no objective, the solver may return any assignment meeting these minimums, so the exact roster varies.)

## Data

Bundled CSVs in `data/`: 10 workers, 3 shifts with capacities, 22 availability pairs. The three coverage scenarios (1, 2, 3) are defined in the script. Full model in `shift_assignment.py`.
