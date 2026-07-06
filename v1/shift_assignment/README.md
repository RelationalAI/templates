---
title: "Shift Assignment"
description: "Assign workers to shifts based on availability to meet coverage requirements."
featured: false
experience_level: beginner
industry: "Cross-Industry"
reasoning_types:
  - Prescriptive
tags:
  - scheduling
  - constraint-programming
  - workforce
  - what-if-analysis
---

## What this template is for

Workforce scheduling is a common operational challenge: given a set of workers, each with their own availability windows, you need to assign them to shifts so that every shift meets its minimum staffing requirements. Doing this manually becomes impractical as the number of workers, shifts, and constraints grows.

This template uses **Prescriptive** reasoning to formulate the shift assignment problem as a constraint satisfaction model. Workers are assigned to shifts they are available for, subject to minimum coverage requirements per shift and a limit on how many shifts each worker can take. The solver (MiniZinc) finds feasible assignments that satisfy all constraints simultaneously.

The template also demonstrates scenario analysis by sweeping over different minimum coverage levels. This lets you quickly see which staffing targets are achievable with your current workforce and availability data, and where you might need to hire or adjust schedules.

## Who this is for

- Operations managers building shift schedules for teams
- Analysts exploring feasibility of different staffing levels
- Developers learning constraint programming with RelationalAI
- Anyone new to prescriptive reasoning who wants a simple, intuitive example

## What you'll build

- A constraint model that assigns workers to shifts respecting availability and capacity limits
- Scenario analysis across multiple minimum-coverage levels (1, 2, 3 workers per shift)
- Post-solve verification via `problem.verify()` to confirm constraint satisfaction across all scenarios

## What's included

- `shift_assignment.py` -- main script with ontology, constraints, and scenario analysis
- **Runbook**: `runbook.md` — a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the script itself.
- `data/workers.csv` -- 10 workers with IDs and names
- `data/shifts.csv` -- 3 shifts (Morning, Afternoon, Night) with capacity limits
- `data/availability.csv` -- worker-to-shift availability mappings
- `pyproject.toml` -- Python package configuration

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools
- Python >= 3.10
- RelationalAI Python SDK (`relationalai == 1.0.14`)

## Quickstart

1. Download ZIP:
   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/shift_assignment.zip
   unzip shift_assignment.zip
   cd shift_assignment
   ```
   > [!TIP]
   > You can also download the template ZIP using the "Download ZIP" button at the top of this page.

2. Create venv:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   ```

3. Install:
   ```bash
   python -m pip install .
   ```

4. Configure:
   ```bash
   rai init
   ```

5. Run:
   ```bash
   python shift_assignment.py
   ```

6. Expected output (a few representative rows confirm a successful run):
   ```text
   Assignments per scenario:
       scenario  worker      shift
     coverage_1   Alice    Morning
     coverage_1     Bob      Night
     coverage_1  Carlos  Afternoon
     ...
     coverage_2   Alice  Afternoon
     coverage_2     Bob    Morning
     ...
     coverage_3   Alice    Morning
     coverage_3     Bob    Morning
     ...
   ```

   The three scenarios sweep `min_coverage` from 1 to 3 workers per shift. This
   is a feasibility problem with no objective, so the solver returns *any*
   assignment that satisfies the constraints — the specific worker-to-shift
   roster varies run to run. What is stable is feasibility: each scenario returns
   an `OPTIMAL` status with every shift meeting its minimum coverage and no worker
   over their shift limit.

## Template structure

```text
.
├── README.md            # this file
├── pyproject.toml       # dependencies
├── shift_assignment.py  # main script: ontology, constraints, scenario sweep
└── data/
    ├── workers.csv       # 10 workers (id, name)
    ├── shifts.csv        # 3 shifts (id, name, capacity)
    └── availability.csv  # worker-to-shift availability pairs
```

**Start here**: run `python shift_assignment.py` for the full scenario sweep end to end, or follow `runbook.md` to reproduce it step by step with the RAI skills.

## Sample data

The bundled data is a small, illustrative workforce — 10 workers, 3 shifts, and their availability pairs — sized to make the constraint interactions easy to read.

- **`workers.csv`** (10 rows) — one row per worker (`id`, `name`).
- **`shifts.csv`** (3 rows) — the Morning, Afternoon, and Night shifts, each with a `capacity` (the maximum number of workers it can hold).
- **`availability.csv`** — `(worker_id, shift_id)` pairs listing which shifts each worker can take. A worker can only be assigned to a shift that appears here.

## Model overview

The model has three concepts plus a `Scenario` concept that parameterizes the coverage sweep. Availability is a standalone relationship, and the assignment decision is a per-scenario decision variable.

- **Key entities**: `Worker` — a person who can be assigned to shifts; `Shift` — a shift that needs to be staffed; `Scenario` — one coverage level in the sweep, solved simultaneously with the others.
- **Primary identifiers**: `Worker.id` and `Shift.id` are integers; `Scenario.name` is a string.
- **Important invariants**: `Shift.capacity` is a positive integer; each scenario's `min_coverage` must be no larger than the smallest shift capacity or that scenario is infeasible; each worker takes at most `max_shifts` shifts (default 1); a worker can only be assigned to a shift they are available for.

For the full concept and property definitions, see `shift_assignment.py`; `runbook.md` builds them step by step with the RAI skills.

## How it works

The pipeline loads workers, shifts, and availability pairs, adds a `Scenario` concept for the coverage sweep, then hands a single constraint-satisfaction problem to the MiniZinc solver that finds a feasible roster for every scenario at once.

```text
CSV inputs → load Worker / Shift / availability → add Scenario coverage levels
  → binary assignment variable (per worker-shift-scenario, scoped to availability)
  → coverage + workload + capacity constraints → solve → verify → per-scenario roster
```

1. **Load the data.** Workers and shifts come from their CSVs; availability pairs become a `Worker.available_for(Shift)` relationship that scopes which assignments are even possible.
2. **Set up the decision.** A binary `x_assign` variable indicates whether a worker takes a given shift in a given scenario. Each coverage level (`coverage_1` / `_2` / `_3`) is a `Scenario` with a `min_coverage`, and the variable is scoped to the availability relationship so unavailable pairs are never considered.
3. **Constrain the roster.** Three constraints govern every scenario: each shift meets its `min_coverage`, each worker takes no more than `max_shifts` shifts (default 1), and no shift exceeds its `capacity`. The constraints are named so they can be re-checked after solving.
4. **Solve and verify.** A single solve handles all scenarios simultaneously; this is a feasibility problem with no objective, so the solver returns any assignment satisfying every constraint. `problem.verify()` then re-fires the named constraints as integrity checks to confirm the solution holds.

See `shift_assignment.py` for the implementation and `runbook.md` for the skill-driven reproduction.

## Customize this template

### Use your own data

- Replace the CSVs in `data/` with your own; keep the column names (`workers.csv`: `id`, `name`; `shifts.csv`: `id`, `name`, `capacity`; `availability.csv`: `worker_id`, `shift_id`). The model scales automatically to more workers, shifts, and availability pairs.
- Every `worker_id` and `shift_id` in `availability.csv` must match an `id` in the other two files, or those pairs silently drop out of the available-for relationship.

### Tune parameters

- **Max shifts per worker** — adjust the `max_shifts` parameter (default `1`) near the top of the decision-problem section.
- **Coverage levels** — edit the `scenario_data` list to sweep different `min_coverage` values, or add more scenarios.

### Extend the model

- **Add shift preferences** by introducing a preference score and converting from feasibility to optimization (minimize total dissatisfaction).
- **Add skills or qualifications** by introducing a skill-matching relationship between workers and shifts.
- **Switch to optimization** by adding an objective (e.g., maximize total coverage or minimize cost) with `problem.minimize()` or `problem.maximize()`.

### Scale up / productionize

- For Snowflake-backed runs, swap the `read_csv(...)` calls for `model.data(snowflake_table)` and adjust the loaders accordingly.
- The feasibility CSP scales to whatever fits the solver's time budget (`time_limit_sec`, default 60). For a scheduled pipeline, pin the `relationalai` version and add an objective so results are reproducible rather than any-feasible.

## Troubleshooting

<details>
  <summary>Solver returns INFEASIBLE</summary>

- With the single-solve approach, if any scenario's constraints are unsatisfiable, the entire problem is infeasible.
- Verify that the `capacity` in `shifts.csv` is at least as large as the highest `min_coverage` scenario. If capacity < min_coverage for any shift, the problem is infeasible.
- Check that `availability.csv` has enough worker-shift pairs to cover every shift at the highest `min_coverage` level.
- Ensure worker IDs and shift IDs in `availability.csv` match those in the other CSV files.

</details>

<details>
  <summary>Import error for <code>relationalai</code></summary>

- Confirm your virtual environment is active: `which python` should point to `.venv`.
- Reinstall dependencies: `python -m pip install .`.

</details>

<details>
  <summary>Authentication or configuration errors</summary>

- Run `rai init` to create or update your RelationalAI/Snowflake configuration.
- If you have multiple profiles, set `export RAI_PROFILE=<your_profile>`.

</details>

<details>
  <summary>MiniZinc solver not available</summary>

- This template uses the MiniZinc constraint solver. Ensure the RAI Native App version supports MiniZinc.
- As an alternative, you can try switching to `"highs"` in the `problem.solve()` call, though HiGHS is designed for linear/MIP problems.

</details>

## Learn more

### Core concepts

- [Prescriptive reasoning](https://docs.relational.ai/) — constraint satisfaction and optimization: decision variables, constraints, objectives.
- [PyRel v1 query language](https://docs.relational.ai/) — `model.select(...)` / `model.where(...)` / aggregations, used to extract the assignments after solving.

### Reasoner reference

- [Solver management](https://docs.relational.ai/) — problem types, solver selection (MiniZinc, HiGHS), and solve execution.
- [Scenario modeling](https://docs.relational.ai/) — parameterizing a single solve across multiple scenarios.

## Support

- File issues at the RelationalAI templates repository.
