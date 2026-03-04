---
title: "Shift Assignment"
description: "Assign workers to shifts based on availability to meet coverage requirements."
featured: false
experience_level: beginner
industry: "Operations"
reasoning_types:
  - Prescriptive
tags:
  - scheduling
  - constraint-programming
  - workforce
  - what-if-analysis
---

# Shift Assignment

## What this template is for

Workforce scheduling is a common operational challenge: given a set of workers, each with their own availability windows, you need to assign them to shifts so that every shift meets its minimum staffing requirements. Doing this manually becomes impractical as the number of workers, shifts, and constraints grows.

This template formulates the shift assignment problem as a constraint satisfaction model using RelationalAI's prescriptive reasoning. Workers are assigned to shifts they are available for, subject to minimum coverage requirements per shift and a limit on how many shifts each worker can take. The solver (MiniZinc) finds feasible assignments that satisfy all constraints simultaneously.

The template also demonstrates scenario analysis by sweeping over different minimum coverage levels. This lets you quickly see which staffing targets are achievable with your current workforce and availability data, and where you might need to hire or adjust schedules.

## Who this is for

- Operations managers building shift schedules for teams
- Analysts exploring feasibility of different staffing levels
- Developers learning constraint programming with RelationalAI
- Anyone new to prescriptive reasoning who wants a simple, intuitive example

## What you'll build

- A constraint model that assigns workers to shifts respecting availability and capacity
- Scenario analysis across multiple minimum-coverage levels (1, 2, 3 workers per shift)
- Feasibility checks that reveal when staffing targets become infeasible

## What's included

- `shift_assignment.py` -- main script with ontology, constraints, and scenario loop
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

6. Expected output:
   ```text
   Running scenario: min_coverage = 1
     Status: OPTIMAL
     Assignments:
              name            value
    x_Alice_Morning            1.0
    x_Carlos_Afternoon         1.0
    x_Bob_Night                1.0

   Running scenario: min_coverage = 2
     Status: OPTIMAL
     Assignments:
              name            value
    x_Alice_Morning            1.0
    x_Diana_Morning            1.0
    x_Carlos_Afternoon         1.0
    x_Grace_Afternoon          1.0
    x_Bob_Night                1.0
    x_Ethan_Night              1.0

   Running scenario: min_coverage = 3
     Status: INFEASIBLE

   ==================================================
   Scenario Analysis Summary
   ==================================================
     min_coverage=1: OPTIMAL
     min_coverage=2: OPTIMAL
     min_coverage=3: INFEASIBLE
   ```

## Template structure
```text
.
├── README.md
├── pyproject.toml
├── shift_assignment.py
└── data/
    ├── workers.csv
    ├── shifts.csv
    └── availability.csv
```

## How it works

**1. Define the ontology and load data.** Workers, shifts, and availability are modeled as concepts and relationships:

```python
Worker = model.Concept("Worker", identify_by={"id": Integer})
Worker.name = model.Property(f"{Worker} has {String:name}")

Shift = model.Concept("Shift", identify_by={"id": Integer})
Shift.name = model.Property(f"{Shift} has {String:name}")
Shift.capacity = model.Property(f"{Shift} has {Integer:capacity}")

Worker.available_for = model.Relationship(f"{Worker} is available for {Shift}")
```

**2. Define decision variables.** A binary variable `x_assign` indicates whether a worker is assigned to a given shift:

```python
Worker.x_assign = model.Property(f"{Worker} has {Shift} if {Integer:assigned}")
s.solve_for(
    Worker.x_assign(Shift, x),
    type="bin",
    name=["x", Worker.name, Shift.name],
    where=[Worker.available_for(Shift)],
    populate=False,
)
```

**3. Add constraints.** Each shift must meet the minimum coverage, and each worker works at most one shift:

```python
s.satisfy(model.where(Worker.x_assign(Shift, x)).require(
    sum(Worker, x).per(Shift) >= min_coverage
))
s.satisfy(model.where(Worker.x_assign(Shift, x)).require(
    sum(Shift, x).per(Worker) <= max_shifts
))
```

**4. Solve across scenarios.** The loop varies `min_coverage` from 1 to 3, creating a fresh Problem each iteration and reporting whether a feasible assignment exists.

## Customize this template

- **Add more shifts or workers** by editing the CSV files. The model scales automatically.
- **Change the max shifts per worker** by adjusting the `max_shifts` parameter.
- **Add shift preferences** by introducing a preference score and converting from feasibility to optimization (minimize total dissatisfaction).
- **Add skills or qualifications** by introducing a skill-matching relationship between workers and shifts.
- **Switch to optimization** by adding an objective (e.g., maximize total coverage or minimize cost) with `s.minimize()` or `s.maximize()`.

## Troubleshooting

<details>
  <summary>Solver returns INFEASIBLE for all scenarios</summary>

- Check that `availability.csv` has enough worker-shift pairs to cover every shift.
- Verify that `shifts.csv` capacity values are reasonable given the number of available workers.
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
- As an alternative, you can try switching to `"highs"` in the `s.solve()` call, though HiGHS is designed for linear/MIP problems.

</details>
