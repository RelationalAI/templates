---
title: "Hospital Staffing"
description: "Assign nurses to shifts to ensure adequate coverage while minimizing staffing cost."
featured: false
experience_level: intermediate
industry: "Healthcare"
reasoning_types:
  - Prescriptive
tags:
  - Allocation
  - MILP
  - Staffing
---

# Hospital Staffing

> [!WARNING]
> This template uses the early access `relational.semantics` API in version `0.13` of the `relationalai` Python package.

## What this template is for

Hospitals need to schedule nurses across shifts while meeting patient safety requirements, regulatory rules, and budget constraints.
This template models a simple nurse-to-shift assignment problem where:

- Each shift needs a minimum number of nurses.
- Each shift requires at least one nurse at or above a minimum skill level.
- Nurses can only be assigned to shifts they’re available for.
- Each nurse can work at most one shift.

The goal is to produce a feasible schedule that **minimizes total staffing cost**.

## Who this is for

- You want an end-to-end example of **prescriptive reasoning (optimization)** with RelationalAI Semantics.
- You’re comfortable with basic Python and understand the idea of constraints + objectives.

## What you’ll build

- A semantic model of nurses, shifts, and nurse–shift availability.
- A mixed-integer linear program (MILP) with one binary decision variable per feasible nurse–shift pair.
- Coverage and skill constraints per shift.
- A solver run using the **HiGHS** backend that prints the assignments and total cost.

## What’s included

- **Model + solve script**: `hospital_staffing.py`
- **Sample data**: `data/nurses.csv`, `data/shifts.csv`, `data/availability.csv`
- **Outputs**: printed termination status, objective value, and a small assignment table

## Prerequisites

### Access

- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools

- Python >= 3.10

## Quickstart

Follow these steps to run the template with the included sample data.

1. **Create and activate a virtual environment**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install -U pip
   ```

2. **Install dependencies**

   From this folder:

   ```bash
   python -m pip install .
   ```

3. **Configure Snowflake connection and RAI profile**

   ```bash
   rai init
   ```

4. **Run the template**

   ```bash
   python hospital_staffing.py
   ```

5. **Expected output**

   ```text
   Status: OPTIMAL
   Total staffing cost: $1792.00

   Staff assignments:
     nurse     shift
   Nurse_A   Morning
   Nurse_B     Night
   Nurse_C     Night
   Nurse_D Afternoon
   Nurse_E   Morning
   Nurse_F Afternoon
   ```

> [!NOTE]
> Alternative optimal solutions may assign different nurses to shifts at the same total cost,
> as long as coverage, availability, and skill requirements are satisfied.

## Template structure

```text
.
├─ README.md
├─ pyproject.toml
├─ hospital_staffing.py       # main runner / entrypoint
└─ data/                      # sample input data
   ├─ nurses.csv
   ├─ shifts.csv
   └─ availability.csv
```

**Start here**: `hospital_staffing.py`

## Sample data

Data files are in `data/`.

### `nurses.csv`

Defines the available nurses, their skill level, and hourly cost.

| Column | Meaning |
| --- | --- |
| `id` | Unique nurse identifier |
| `name` | Nurse name (used for output labeling) |
| `skill_level` | Skill rating (1=basic, 2=intermediate, 3=advanced) |
| `hourly_cost` | Cost per hour ($) |

### `shifts.csv`

Defines each shift and its coverage and skill requirements.

| Column | Meaning |
| --- | --- |
| `id` | Unique shift identifier |
| `name` | Shift name (Morning, Afternoon, Night) |
| `start_hour` | Start time (24-hour clock) |
| `duration` | Shift length in hours |
| `min_nurses` | Minimum nurses required |
| `min_skill` | Minimum skill level required for at least one nurse on the shift |

### `availability.csv`

Indicates whether each nurse can work each shift.

| Column | Meaning |
| --- | --- |
| `nurse_id` | References `nurses.csv.id` |
| `shift_id` | References `shifts.csv.id` |
| `available` | 1 if the nurse can work the shift; 0 otherwise |

## Model overview

The optimization model is built around four concepts.

### `Nurse`

Represents a nurse with a skill level and hourly cost.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `id` | int | Yes | Primary key loaded from `data/nurses.csv` |
| `name` | string | No | Used for output labels |
| `skill_level` | int | No | Used to satisfy the per-shift skill requirement |
| `hourly_cost` | float | No | Used in the cost-minimization objective |

### `Shift`

Represents a shift, including coverage requirements.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `id` | int | Yes | Primary key loaded from `data/shifts.csv` |
| `name` | string | No | Used for output labels |
| `start_hour` | int | No | Metadata (not used by the solver in this template) |
| `duration` | int | No | Multiplies hourly cost to compute total cost |
| `min_nurses` | int | No | Minimum staffing constraint |
| `min_skill` | int | No | Minimum skill threshold for at least one assigned nurse |

### `Availability`

Links nurses to shifts they are eligible to work.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `nurse` | `Nurse` | No | Joined from `data/availability.csv.nurse_id` |
| `shift` | `Shift` | No | Joined from `data/availability.csv.shift_id` |
| `available` | int | No | 0/1 flag used to enforce valid assignments |

### `Assignment` (decision concept)

One binary variable per availability row.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `availability` | `Availability` | Yes | One variable per nurse–shift candidate |
| `assigned` | float | No | Binary decision variable (0/1) |

## How it works

This section walks through the highlights in `hospital_staffing.py`.

### Import libraries and configure inputs

```python
from pathlib import Path

import pandas
from pandas import read_csv

from relationalai.semantics import Model, data, define, require, select, sum, where
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

```python
# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

model = Model("hospital_staffing", config=globals().get("config", None), use_lqp=False)

# Concept: nurses with skill level and hourly cost
Nurse = model.Concept("Nurse")
Nurse.id = model.Property("{Nurse} has {id:int}")
Nurse.name = model.Property("{Nurse} has {name:string}")
Nurse.skill_level = model.Property("{Nurse} has {skill_level:int}")
Nurse.hourly_cost = model.Property("{Nurse} has {hourly_cost:float}")

# Load nurse data from CSV and create Nurse entities.
data(read_csv(DATA_DIR / "nurses.csv")).into(Nurse, keys=["id"])

# Concept: shifts with coverage requirements
Shift = model.Concept("Shift")
Shift.id = model.Property("{Shift} has {id:int}")
Shift.name = model.Property("{Shift} has {name:string}")
Shift.start_hour = model.Property("{Shift} has {start_hour:int}")
Shift.duration = model.Property("{Shift} has {duration:int}")
Shift.min_nurses = model.Property("{Shift} has {min_nurses:int}")
Shift.min_skill = model.Property("{Shift} has {min_skill:int}")

# Load shift data from CSV and create Shift entities.
data(read_csv(DATA_DIR / "shifts.csv")).into(Shift, keys=["id"])

# Relationship: availability linking nurses to shifts
Availability = model.Concept("Availability")
Availability.nurse = model.Property("{Availability} for {nurse:Nurse}")
Availability.shift = model.Property("{Availability} in {shift:Shift}")
Availability.available = model.Property("{Availability} is {available:int}")

# Load availability data from CSV.
avail_data = data(read_csv(DATA_DIR / "availability.csv"))

# Define Availability entities by joining nurse/shift IDs from the CSV with the
# Nurse and Shift concepts.
where(
    Nurse.id == avail_data.nurse_id,
    Shift.id == avail_data.shift_id
).define(
    Availability.new(nurse=Nurse, shift=Shift, available=avail_data.available)
)
```

### Define decision variables, constraints, and objective

```python
# --------------------------------------------------
# Model the problem
# --------------------------------------------------

# Decision concept: assignments of nurses to shifts
Assignment = model.Concept("Assignment")
Assignment.availability = model.Property("{Assignment} uses {availability:Availability}")
Assignment.assigned = model.Property("{Assignment} is {assigned:float}")
define(Assignment.new(availability=Availability))

Asn = Assignment.ref()

s = SolverModel(model, "cont")

# Variable: binary assignment
s.solve_for(
    Assignment.assigned,
    type="bin",
    name=[
        "x",
        Assignment.availability.nurse.name,
        Assignment.availability.shift.name,
    ],
)

# Constraint: can only assign if available
must_be_available = require(Assignment.assigned <= Assignment.availability.available)
s.satisfy(must_be_available)

# Constraint: each nurse works at most one shift
nurse_shifts = sum(Asn.assigned).where(Asn.availability.nurse == Nurse).per(Nurse)
one_shift_max = require(nurse_shifts <= 1)
s.satisfy(one_shift_max)

# Constraint: minimum nurses per shift
shift_coverage = sum(Asn.assigned).where(Asn.availability.shift == Shift).per(Shift)
min_coverage = require(shift_coverage >= Shift.min_nurses)
s.satisfy(min_coverage)

# Constraint: at least one nurse with required skill level per shift
skilled_coverage = sum(Asn.assigned).where(
    Asn.availability.shift == Shift,
    Asn.availability.nurse.skill_level >= Shift.min_skill,
).per(Shift)
min_skilled = require(skilled_coverage >= 1)
s.satisfy(min_skilled)

# Objective: minimize total staffing cost
total_cost = sum(
    Assignment.assigned
    * Assignment.availability.shift.duration
    * Assignment.availability.nurse.hourly_cost
)
s.minimize(total_cost)
```

### Solve and print results

```python
# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

solver = Solver("highs")
s.solve(solver, time_limit_sec=60)

print(f"Status: {s.termination_status}")
print(f"Total staffing cost: ${s.objective_value:.2f}")

assignments = select(
    Assignment.availability.nurse.name.alias("nurse"),
    Assignment.availability.shift.name.alias("shift")
).where(Assignment.assigned > 0.5).to_df()

print("\nStaff assignments:")
print(assignments.to_string(index=False))
```

## Customize this template

### Use your own data

- Replace the CSVs in `data/` with your own `nurses`, `shifts`, and `availability` tables.
- Keep the same column names, or update the CSV column references in `hospital_staffing.py`.

> [!TIP]
> Start by swapping in your own `availability.csv` first.
> In many real staffing problems, feasibility issues come from availability gaps that make shift coverage impossible.

### Tune parameters

- Adjust per-shift requirements in `data/shifts.csv` (`min_nurses`, `min_skill`).
- Adjust costs in `data/nurses.csv` (`hourly_cost`) to see how assignments change.

### Extend the model

Common next steps:

- Add maximum consecutive nights, rest-time rules, or day-of-week constraints.
- Add preferences (soft constraints) with penalty terms in the objective.
- Add different shift lengths or roles (e.g., RN vs. charge nurse).

## Troubleshooting

<details>
    <summary>Why does authentication/configuration fail?</summary>


- Run `rai init` to create/update `raiconfig.toml`.
- If you have multiple profiles, set `RAI_PROFILE` or switch profiles in your config.

</details>

<details>
    <summary>Why does the script fail to connect to the RAI Native App?</summary>


- Verify the Snowflake account/role/warehouse and `rai_app_name` are correct in `raiconfig.toml`.
- Ensure the RAI Native App is installed and you have access.

</details>

<details>
    <summary><code>ModuleNotFoundError</code> when running the script</summary>

- Confirm your virtual environment is activated.
- Install the template dependencies from this folder: `python -m pip install .`

</details>

<details>
    <summary>CSV loading fails (missing file or column)</summary>

- Confirm the CSVs exist under `data/` and the filenames match.
- Ensure the headers match the expected schema:
    - `nurses.csv`: `id`, `name`, `skill_level`, `hourly_cost`
    - `shifts.csv`: `id`, `name`, `start_hour`, `duration`, `min_nurses`, `min_skill`
    - `availability.csv`: `nurse_id`, `shift_id`, `available`

</details>

<details>
    <summary>Why do I get <code>Status: INFEASIBLE</code>?</summary>


- Check `data/availability.csv` to ensure each shift has enough available nurses to satisfy `min_nurses`.
- Ensure each shift has at least one available nurse with `skill_level >= min_skill`.

</details>

<details>
    <summary>Why is the assignment table empty?</summary>


- The script filters assignments with `Assignment.assigned > 0.5`. If nothing prints, inspect feasibility and input data.
- Confirm the CSVs were read correctly and contain rows.

</details>

<details>
    <summary>Solver fails or returns an unexpected termination status</summary>


- Try re-running; transient connectivity issues can affect the solve step.
- If the solve is slow, increase the time limit in `hospital_staffing.py`.

</details>
