---
title: "Shift Assignment"
description: "Assign workers to shifts based on availability while meeting minimum coverage and per-worker capacity constraints."
featured: true
experience_level: beginner
industry: "Workforce Management"
reasoning_types:
  - Prescriptive
tags:
  - Scheduling
  - CSP
  - Allocation
---

# Shift Assignment

> [!WARNING]
> This template uses the early access `relationalai.semantics` API in version `0.13.3` of the `relationalai` Python package.

## What this template is for

Workforce planners often need to staff multiple shifts while respecting who is available and how much each person can work.
This template models a small shift assignment problem where:

- Workers can only be assigned to shifts they’re available for.
- Each shift must meet a minimum coverage requirement.
- Each worker can work at most a limited number of shifts.

This template uses RelationalAI's **prescriptive reasoning (optimization)** capabilities to find a feasible assignment that satisfies all constraints.
Because this is a feasibility / constraint satisfaction problem, there is no objective value—any schedule that meets the rules is acceptable.

## Who this is for

- You want an end-to-end example of **prescriptive reasoning (optimization)** with RelationalAI where the goal is feasibility.
- You’re comfortable with basic Python and the idea of decision variables and constraints.

## What you’ll build

- A semantic model of workers, shifts, and worker–shift availability.
- A binary decision variable `Assignment.x_assigned` for each available worker–shift pair.
- Constraints that enforce minimum shift coverage and per-worker assignment limits.
- A solve step that uses the `minizinc` backend and prints an assignment table.

## What’s included

- **Model + solve script**: `shift_assignment.py`
- **Sample data**: `data/workers.csv`, `data/shifts.csv`, `data/availability.csv`
- **Outputs**: solver termination status, an assignments table, and a per-shift coverage summary

## Prerequisites

### Access

- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools

- Python >= 3.10
- RelationalAI CLI (`rai`) for setting up your profile

## Quickstart

Follow these steps to run the template with the included sample data.

1. Download the ZIP file for this template and extract it:

   ```bash
   curl -O https://private.relational.ai/templates/zips/v0.13/shift_assignment.zip
   unzip shift_assignment.zip
   cd shift_assignment
   ```

   > [!TIP]
   > You can also download the template ZIP using the "Download ZIP" button at the top of this page.

2. **Create and activate a virtual environment**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install -U pip
   ```

3. **Install dependencies**

   From this folder:

   ```bash
   python -m pip install .
   ```

4. **Configure Snowflake connection and RAI profile**

   ```bash
   rai init
   ```

5. **Run the template**

   ```bash
   python shift_assignment.py
   ```

6. **Expected output**

   Your exact assignments may vary between runs, but you should see a feasible status plus an assignments table and coverage summary:

   ```text
   Status: OPTIMAL

   Assignments:
    worker     shift
     Alice  Morning
       Bob    Night
     Diana Afternoon

   Coverage per shift:
        shift  workers
   Afternoon        2
     Morning        2
       Night        2
   ```

## Template structure

```text
.
├─ README.md
├─ pyproject.toml
├─ shift_assignment.py      # main runner / entrypoint
└─ data/                    # sample input data
   ├─ workers.csv
   ├─ shifts.csv
   └─ availability.csv
```

**Start here**: `shift_assignment.py`

## Sample data

Data files are in `data/`.

### `workers.csv`

| Column | Meaning |
| --- | --- |
| `id` | Unique worker identifier |
| `name` | Worker name (used for output labeling) |

### `shifts.csv`

| Column | Meaning |
| --- | --- |
| `id` | Unique shift identifier |
| `name` | Shift name (e.g., Morning, Afternoon, Night) |
| `capacity` | Sample data field (not enforced by this template as written) |

### `availability.csv`

| Column | Meaning |
| --- | --- |
| `worker_id` | Foreign key to `workers.csv.id` |
| `shift_id` | Foreign key to `shifts.csv.id` |

Each row declares one allowed worker–shift pairing.
The script only creates `Assignment` entities for these rows, so unlisted pairings are impossible by construction.

## Model overview

The semantic model for this template is built around three concepts.

### `Worker`

A worker who may be assigned to at most a limited number of shifts.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `id` | int | Yes | Loaded as the key from `data/workers.csv` |
| `name` | string | No | Used for output labeling |

### `Shift`

A shift that must be staffed with at least `min_coverage` workers.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `id` | int | Yes | Loaded as the key from `data/shifts.csv` |
| `name` | string | No | Used for output labeling |

### `Assignment` (decision concept)

One entity per available worker–shift pair, created by joining `availability.csv` to `Worker` and `Shift`.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `worker` | `Worker` | Part of compound key | Joined via `availability.csv.worker_id` |
| `shift` | `Shift` | Part of compound key | Joined via `availability.csv.shift_id` |
| `assigned` | int | No | Binary decision variable (0/1) |

## How it works

This section walks through the highlights in `shift_assignment.py`.

### Import libraries and configure inputs

First, the script imports the Semantics APIs and configures local inputs like `DATA_DIR`:

```python
from pathlib import Path

import pandas
from pandas import read_csv

from relationalai.semantics import Model, data, require, select, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"

# Disable pandas inference of string types. This ensures that string columns
# in the CSVs are loaded as object dtype. This is only required when using
# relationalai versions prior to v1.0.
pandas.options.future.infer_string = False
```

### Define concepts and load CSV data

Next, it creates a `Model`, defines `Worker` and `Shift` concepts, and loads the corresponding CSVs using `data(...).into(...)`:

```python
# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

# Create a Semantics model container.
model = Model("shift_assignment", config=globals().get("config", None), use_lqp=False)

# Worker concept: employees available for scheduling.
Worker = model.Concept("Worker")
Worker.id = model.Property("{Worker} has {id:int}")
Worker.name = model.Property("{Worker} has {name:string}")

# Load worker data from CSV.
data(read_csv(DATA_DIR / "workers.csv")).into(Worker, keys=["id"])

# Shift concept: time periods that require staffing.
Shift = model.Concept("Shift")
Shift.id = model.Property("{Shift} has {id:int}")
Shift.name = model.Property("{Shift} has {name:string}")

# Load shift data from CSV.
data(read_csv(DATA_DIR / "shifts.csv")).into(Shift, keys=["id"])
```

### Create decision entities from availability

Then it defines an `Assignment` decision concept and uses `where(...).define(...)` to create one `Assignment` entity for each available worker–shift pair:

```python
# Assignment decision concept: a worker-shift pair that can potentially be staffed.
# The availability table determines which pairs exist.
Assignment = model.Concept("Assignment")
Assignment.worker = model.Property("{Assignment} has {worker:Worker}")
Assignment.shift = model.Property("{Assignment} has {shift:Shift}")
Assignment.x_assigned = model.Property("{Assignment} assigned {assigned:int}")

# Load availability data from CSV.
avail = data(read_csv(DATA_DIR / "availability.csv"))

# Define Assignment entities by joining availability rows to Worker and Shift.
where(
    Worker.id == avail.worker_id,
    Shift.id == avail.shift_id
).define(
    Assignment.new(worker=Worker, shift=Shift)
)
```

### Define decision variables and constraints

With the feasible worker–shift pairs defined, the template creates a `SolverModel`, declares a binary decision variable, and adds two constraints using `require(...)` and `sum(...).per(...)`:

```python
# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

# Parameters.
min_coverage = 2
max_shifts_per_worker = 1

Asn = Assignment.ref()

s = SolverModel(model, "int")

# Variable: binary assignment (0 or 1)
s.solve_for(
    Assignment.x_assigned,
    name=["x", Assignment.worker.name, Assignment.shift.name],
    type="bin",
)

# Constraint: each shift has minimum coverage
shift_coverage = where(
    Asn.shift == Shift
).require(
    sum(Asn.assigned).per(Shift) >= min_coverage
)
s.satisfy(shift_coverage)

# Constraint: each worker works at most max_shifts_per_worker shifts
worker_capacity = where(
    Asn.worker == Worker
).require(
    sum(Asn.assigned).per(Worker) <= max_shifts_per_worker
)
s.satisfy(worker_capacity)
```

### Solve and print results

Finally, it solves the model using the `minizinc` backend and prints the assignments and coverage summary:

```python
# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

solver = Solver("minizinc")
s.solve(solver, time_limit_sec=60)

print(f"Status: {s.termination_status}")

assignments = select(
    Assignment.worker.name.alias("worker"),
    Assignment.shift.name.alias("shift")
).where(Assignment.x_assigned >= 1).to_df()

print("\nAssignments:")
print(assignments.to_string(index=False))

print("\nCoverage per shift:")
print(assignments.groupby("shift").size().reset_index(name="workers").to_string(index=False))
```

## Customize this template

### Use your own data

- Replace the CSVs in `data/` with your own data.
- Keep the required headers:
  - `workers.csv`: `id`, `name`
  - `shifts.csv`: `id`, `name`
  - `availability.csv`: `worker_id`, `shift_id`
- Ensure `availability.csv.worker_id` values exist in `workers.csv.id` and `availability.csv.shift_id` values exist in `shifts.csv.id`.

### Tune parameters

Update the parameters in `shift_assignment.py`:

- `min_coverage`: minimum workers per shift
- `max_shifts_per_worker`: maximum shifts per worker

If you increase `min_coverage` or reduce availability, the problem may become infeasible.

### Extend the model

Common extensions include:

- **Max coverage (capacity)**: If you want to enforce a maximum number of workers per shift, add a `Shift.capacity` property, load it from `shifts.csv`, and require `sum(Asn.assigned).per(Shift) <= Shift.capacity`.
- **Preferences or costs**: Add a weight per worker–shift pair and switch from pure feasibility to minimizing total cost.

## Troubleshooting

<details>
<summary>I got <code>ModuleNotFoundError</code> when running the script</summary>

- Confirm your virtual environment is active.
- Reinstall dependencies from the template folder: <code>python -m pip install .</code>
- Confirm you’re using Python 3.10+.

</details>

<details>
<summary>I can’t authenticate / the script can’t connect to Snowflake</summary>

- Re-run <code>rai init</code> and confirm your profile is set up.
- If you use multiple profiles, set <code>RAI_PROFILE</code> and retry.
- Confirm your Snowflake user has access to the RelationalAI Native App.

</details>

<details>
<summary>I got a CSV error (missing file or missing columns)</summary>

- Confirm these files exist in <code>data/</code>: <code>workers.csv</code>, <code>shifts.csv</code>, <code>availability.csv</code>.
- Confirm required headers:
- <code>workers.csv</code>: <code>id</code>, <code>name</code>
- <code>shifts.csv</code>: <code>id</code>, <code>name</code>
- <code>availability.csv</code>: <code>worker_id</code>, <code>shift_id</code>
- Make sure IDs are consistent across files (foreign keys actually match).

</details>

<details>
<summary>The solver returns <code>Status: INFEASIBLE</code></summary>

- Lower <code>min_coverage</code> or increase worker availability in <code>availability.csv</code>.
- Increase <code>max_shifts_per_worker</code> if you have too few workers to cover all shifts.
- Sanity-check that every shift appears in <code>availability.csv</code> at least <code>min_coverage</code> times.

</details>
