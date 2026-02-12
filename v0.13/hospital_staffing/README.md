---
title: "Hospital Staffing"
description: "Assign nurses to shifts to minimize overtime cost and overflow penalties from unmet patient demand."
featured: false
experience_level: intermediate
industry: "Healthcare"
reasoning_types:
  - Prescriptive
tags:
  - Allocation
  - MILP
  - Staffing
  - Multi-objective
---

# Hospital Staffing

> [!WARNING]
> This template uses the early access `relationalai.semantics` API in version `0.13.3` of the `relationalai` Python package.

## What this template is for

Hospitals must schedule nurses across shifts while keeping overtime costs low and ensuring patients receive care.
This template models assigning 6 nurses to 3 shifts (Morning, Afternoon, Night), where each shift has patient demand that depends on staffing levels.

Nurses can work extra shifts beyond their regular hours, but at a premium rate (1.5x).
When staffing falls short and patient demand goes unmet, the hospital incurs an overflow penalty reflecting missed care ratios, throughput shortfalls, and regulatory risk.
This template uses RelationalAI's **prescriptive reasoner** to find the assignment of nurses to shifts that minimizes the combined cost of overtime and overflow, while respecting availability, safety limits, and skill requirements.

Prescriptive reasoning helps you:

- **Control overtime cost**: Identify the lowest-cost overtime assignments when extra coverage is needed.
- **Avoid costly overflow**: Ensure high-demand shifts get additional staff to prevent unmet patient demand.
- **Quantify trade-offs**: Determine whether overtime cost is justified by the overflow penalty it avoids.
- **Enforce safety limits**: Guarantee no nurse works more than 2 shifts (16 hours).

## Who this is for

- You want an end-to-end example of **prescriptive reasoning (optimization)** with RelationalAI.
- You're comfortable with basic Python and mixed-integer optimization concepts.

## What you'll build

- A semantic model of nurses, shifts, and availability using concepts and properties.
- A MILP model with binary assignment variables, continuous overtime hours, patient throughput, and unmet demand variables.
- Nine constraints covering availability, coverage, skill requirements, overtime, demand, capacity, and overflow.
- An objective that minimizes overtime cost plus an overflow penalty for unserved patients.
- A solver that uses the **HiGHS** backend and prints overtime assignments, patient throughput, and staff schedules.

## What's included

- **Model + solve script**: `hospital_staffing.py`
- **Sample data**: `data/nurses.csv`, `data/shifts.csv`, `data/availability.csv`

## Prerequisites

### Access

- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools

- Python >= 3.10

## Quickstart

Follow these steps to run the template with the included sample data.
You can customize the data and model as needed after you have it running end-to-end.

1. Download the ZIP file for this template and extract it:

   ```bash
   curl -O https://private.relational.ai/templates/zips/v0.13/hospital_staffing.zip
   unzip hospital_staffing.zip
   cd hospital_staffing
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
   python hospital_staffing.py
   ```

6. **Expected output**

   ```text
   Status: OPTIMAL
   Total cost: $616.00

   Overtime assignments:
     nurse  overtime_hours
   Nurse_B             8.0
   Nurse_C             8.0

   Patient throughput by shift:
        shift  patients_served  patient_demand  unmet_demand
      Morning             32.0              45          13.0
    Afternoon             60.0              60           0.0
        Night             24.0              25           1.0

   Total patients served: 116 / 130
   Total unmet demand: 14 patients

   Staff assignments:
     nurse      shift
   Nurse_A    Morning
   Nurse_A  Afternoon
   Nurse_B    Morning
   Nurse_B  Afternoon
   Nurse_C  Afternoon
   Nurse_C      Night
   Nurse_D    Morning
   Nurse_E    Morning
   Nurse_E      Night
   Nurse_F      Night
   ```

## Template structure

```text
.
├─ README.md
├─ pyproject.toml
├─ hospital_staffing.py      # main runner / entrypoint
└─ data/                     # sample input data
   ├─ nurses.csv
   ├─ shifts.csv
   └─ availability.csv
```

**Start here**: `hospital_staffing.py`

## Sample data

Data files are in `data/`.

### `nurses.csv`

Staff members with skill ratings, pay rates, and overtime parameters.

| Column | Meaning |
| --- | --- |
| `id` | Unique nurse identifier |
| `name` | Nurse name |
| `skill_level` | Skill rating (1=basic, 2=intermediate, 3=advanced) |
| `hourly_cost` | Cost per hour ($) |
| `regular_hours` | Standard hours before overtime kicks in (8) |
| `overtime_multiplier` | Overtime pay rate multiplier (1.5x) |

### `shifts.csv`

Time periods with staffing requirements and patient demand.

| Column | Meaning |
| --- | --- |
| `id` | Unique shift identifier |
| `name` | Shift name (Morning, Afternoon, Night) |
| `start_hour` | Shift start time (24-hour format) |
| `duration` | Shift length in hours |
| `min_nurses` | Minimum nurses required per shift |
| `min_skill` | Minimum skill level required for at least one nurse |
| `patient_demand` | Total patients needing care during this shift |
| `patients_per_nurse_hour` | Patients one nurse can serve per hour |

### `availability.csv`

Links nurses to shifts, indicating which assignments are feasible.

| Column | Meaning |
| --- | --- |
| `nurse_id` | Foreign key to `nurses.csv.id` |
| `shift_id` | Foreign key to `shifts.csv.id` |
| `available` | 1 if the nurse can work this shift, 0 otherwise |

## Model overview

The semantic model for this template is built around four concepts.

### `Nurse`

A staff member with a skill level, hourly cost, and overtime parameters.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `id` | int | Yes | Loaded as the key from `data/nurses.csv` |
| `name` | string | No | Human-readable nurse name |
| `skill_level` | int | No | Used in skill-requirement constraints |
| `hourly_cost` | float | No | Cost per hour, used in overtime cost calculation |
| `regular_hours` | int | No | Hours before overtime applies (8) |
| `overtime_multiplier` | float | No | Overtime pay multiplier (1.5x) |
| `overtime_hours` | float | No | Continuous decision variable ($\ge 0$) |

### `Shift`

A time period with coverage requirements and patient demand.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `id` | int | Yes | Loaded as the key from `data/shifts.csv` |
| `name` | string | No | Human-readable shift name |
| `start_hour` | int | No | Shift start time (24-hour format) |
| `duration` | int | No | Shift length in hours |
| `min_nurses` | int | No | Minimum nurses required |
| `min_skill` | int | No | Minimum skill level for at least one assigned nurse |
| `patient_demand` | int | No | Total patients needing care |
| `patients_per_nurse_hour` | float | No | Patients one nurse can serve per hour |
| `patients_served` | float | No | Continuous decision variable ($\ge 0$) |
| `unmet_demand` | float | No | Continuous decision variable ($\ge 0$); overflow |

### `Availability`

A nurse-shift pair indicating whether the nurse can work that shift.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `nurse` | `Nurse` | Part of compound key | Joined via `data/availability.csv.nurse_id` |
| `shift` | `Shift` | Part of compound key | Joined via `data/availability.csv.shift_id` |
| `available` | int | No | 1 if available, 0 otherwise |

### `Assignment`

A decision concept created for each `Availability` row; the solver chooses whether to assign.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `availability` | `Availability` | Yes | One assignment per nurse-shift pair |
| `assigned` | float | No | Binary decision variable (0/1) |

## How it works

This section walks through the highlights in `hospital_staffing.py`.

### Import libraries and configure inputs

First, the script imports the Semantics APIs (`Model`, `data`, `define`, `where`, `require`, `sum`) and configures local inputs like `DATA_DIR`:

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

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

model = Model("hospital_staffing", config=globals().get("config", None), use_lqp=False)
```

### Define concepts and load CSV data

Next, it declares the `Nurse` and `Shift` concepts and loads `nurses.csv` and `shifts.csv` via `data(...).into(...)`:

```python
# Nurse concept: staff members with skill level, cost, and overtime parameters.
Nurse = model.Concept("Nurse")
Nurse.id = model.Property("{Nurse} has {id:int}")
Nurse.name = model.Property("{Nurse} has {name:string}")
Nurse.skill_level = model.Property("{Nurse} has {skill_level:int}")
Nurse.hourly_cost = model.Property("{Nurse} has {hourly_cost:float}")
Nurse.regular_hours = model.Property("{Nurse} has {regular_hours:int}")
Nurse.overtime_multiplier = model.Property("{Nurse} has {overtime_multiplier:float}")
Nurse.overtime_hours = model.Property("{Nurse} has {overtime_hours:float}")

# Load nurse data from CSV and create Nurse entities.
data(read_csv(DATA_DIR / "nurses.csv")).into(Nurse, keys=["id"])

# Shift concept: time periods with coverage requirements and patient demand.
Shift = model.Concept("Shift")
Shift.id = model.Property("{Shift} has {id:int}")
Shift.name = model.Property("{Shift} has {name:string}")
Shift.start_hour = model.Property("{Shift} has {start_hour:int}")
Shift.duration = model.Property("{Shift} has {duration:int}")
Shift.min_nurses = model.Property("{Shift} has {min_nurses:int}")
Shift.min_skill = model.Property("{Shift} has {min_skill:int}")
Shift.patient_demand = model.Property("{Shift} has {patient_demand:int}")
Shift.patients_per_nurse_hour = model.Property("{Shift} has {patients_per_nurse_hour:float}")
Shift.patients_served = model.Property("{Shift} has {patients_served:float}")
Shift.unmet_demand = model.Property("{Shift} has {unmet_demand:float}")

# Load shift data from CSV and create Shift entities.
data(read_csv(DATA_DIR / "shifts.csv")).into(Shift, keys=["id"])
```

`availability.csv` contains foreign keys (`nurse_id`, `shift_id`). The template resolves them into `Nurse` and `Shift` instances and creates an `Availability` concept per row using `where(...).define(...)`:

```python
# Availability concept: links nurses to shifts they can work.
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
    Shift.id == avail_data.shift_id,
).define(
    Availability.new(nurse=Nurse, shift=Shift, available=avail_data.available)
)
```

### Define decision variables, constraints, and objective

An `Assignment` decision concept is created for every `Availability` row. The script then declares four decision variables on a `SolverModel`: binary assignment flags, continuous overtime hours, patients served per shift, and unmet demand per shift:

```python
# Assignment decision concept: represents the decision variables for assigning
# nurses to shifts. Each Assignment is linked to an Availability entity, which
# indicates whether the nurse can work that shift.
Assignment = model.Concept("Assignment")
Assignment.availability = model.Property("{Assignment} uses {availability:Availability}")
Assignment.assigned = model.Property("{Assignment} is {assigned:float}")
define(Assignment.new(availability=Availability))

Asn = Assignment.ref()

s = SolverModel(model, "cont")

# Variable: binary assignment (nurse to shift)
s.solve_for(
    Assignment.assigned,
    type="bin",
    name=[
        "x",
        Assignment.availability.nurse.name,
        Assignment.availability.shift.name,
    ],
)

# Variable: overtime hours per nurse (continuous >= 0)
s.solve_for(Nurse.overtime_hours, type="cont", name=["ot", Nurse.name], lower=0)

# Variable: patients served per shift (continuous >= 0)
s.solve_for(Shift.patients_served, type="cont", name=["pt", Shift.name], lower=0)

# Variable: unmet patient demand per shift (continuous >= 0)
s.solve_for(Shift.unmet_demand, type="cont", name=["ud", Shift.name], lower=0)
```

Then it adds nine constraints using `require(...)` and `s.satisfy(...)`. The constraints enforce availability, minimum and maximum shifts per nurse, coverage and skill requirements, overtime accounting, demand and capacity caps, and the definition of unmet demand:

```python
# Constraint: can only assign if available
must_be_available = require(Assignment.assigned <= Assignment.availability.available)
s.satisfy(must_be_available)

# Constraint: every nurse works at least one shift
nurse_shift_count = sum(Asn.assigned).where(Asn.availability.nurse == Nurse).per(Nurse)
min_one_shift = require(nurse_shift_count >= 1)
s.satisfy(min_one_shift)

# Constraint: max 2 shifts per nurse (safety limit: 16 hours max)
max_two_shifts = require(nurse_shift_count <= 2)
s.satisfy(max_two_shifts)

# Constraint: minimum nurses per shift
shift_staff_count = sum(Asn.assigned).where(Asn.availability.shift == Shift).per(Shift)
min_coverage = require(shift_staff_count >= Shift.min_nurses)
s.satisfy(min_coverage)

# Constraint: at least one nurse with required skill level per shift
skilled_coverage = sum(Asn.assigned).where(
    Asn.availability.shift == Shift,
    Asn.availability.nurse.skill_level >= Shift.min_skill,
).per(Shift)
min_skilled = require(skilled_coverage >= 1)
s.satisfy(min_skilled)

# Constraint: overtime >= total hours worked - regular hours
total_hours_worked = sum(Asn.assigned * Asn.availability.shift.duration).where(
    Asn.availability.nurse == Nurse
).per(Nurse)
overtime_def = require(Nurse.overtime_hours >= total_hours_worked - Nurse.regular_hours)
s.satisfy(overtime_def)

# Constraint: patients served <= patient demand per shift
demand_cap = require(Shift.patients_served <= Shift.patient_demand)
s.satisfy(demand_cap)

# Constraint: patients served <= nursing capacity per shift
shift_nursing_capacity = shift_staff_count * Shift.patients_per_nurse_hour * Shift.duration
capacity_cap = require(Shift.patients_served <= shift_nursing_capacity)
s.satisfy(capacity_cap)

# Constraint: unmet demand >= patient demand - patients served
unmet_def = require(Shift.unmet_demand >= Shift.patient_demand - Shift.patients_served)
s.satisfy(unmet_def)
```

With the feasible region defined, the objective minimizes overtime cost plus an overflow penalty for unmet patient demand. The `overflow_penalty_per_patient` parameter ($20/patient) represents the cost of failing to serve a patient:

```python
# Objective: minimize overtime cost + overflow penalty for unmet patient demand.
# overflow_penalty_per_patient represents the cost of failing to serve a patient
# (missed care ratios, throughput shortfall, regulatory risk).
overflow_penalty_per_patient = 20
overtime_cost = sum(Nurse.overtime_hours * Nurse.hourly_cost * Nurse.overtime_multiplier)
total_overflow_penalty = overflow_penalty_per_patient * sum(Shift.unmet_demand)
s.minimize(overtime_cost + total_overflow_penalty)
```

### Solve and print results

Finally, the script solves with the HiGHS backend and prints overtime assignments (nurses with more than 0.5 overtime hours), patient throughput by shift, and the staff assignment schedule:

```python
solver = Solver("highs")
s.solve(solver, time_limit_sec=60)

print(f"Status: {s.termination_status}")
print(f"Total cost: ${s.objective_value:.2f}")

# Overtime summary
overtime = select(
    Nurse.name.alias("nurse"),
    Nurse.overtime_hours.alias("overtime_hours"),
).where(Nurse.overtime_hours > 0.5).to_df()

if not overtime.empty:
    print("\nOvertime assignments:")
    print(overtime.to_string(index=False))
else:
    print("\nNo overtime assigned.")

# Throughput and overflow summary
throughput = select(
    Shift.name.alias("shift"),
    Shift.patients_served.alias("patients_served"),
    Shift.patient_demand.alias("patient_demand"),
    Shift.unmet_demand.alias("unmet_demand"),
).to_df()

print("\nPatient throughput by shift:")
print(throughput.to_string(index=False))
print(f"Total patients served: {throughput['patients_served'].sum():.0f} / {throughput['patient_demand'].sum()}")
print(f"Total unmet demand: {throughput['unmet_demand'].sum():.0f} patients")

# Staff assignments
assignments = select(
    Assignment.availability.nurse.name.alias("nurse"),
    Assignment.availability.shift.name.alias("shift"),
).where(Assignment.assigned > 0.5).to_df()

print("\nStaff assignments:")
print(assignments.to_string(index=False))
```

## Customize this template

Here are some ideas for how to customize and extend this template to fit your specific use case.

### Tune parameters

The `overflow_penalty_per_patient` parameter controls the trade-off between overtime cost and unmet patient demand.

| Parameter | Default | Effect |
| --- | --- | --- |
| `overflow_penalty_per_patient` | 20 | Higher values push the optimizer to staff up at overtime cost; lower values tolerate more unmet demand |

### Use your own data

- Replace the CSVs in `data/` with your own, keeping the same column names (or update the loading logic in `hospital_staffing.py`).
- Ensure that `availability.csv` only references valid `nurse_id` and `shift_id` values.
- Each nurse needs a `regular_hours` value (standard hours before overtime) and an `overtime_multiplier`.
- Each shift needs `patient_demand` and `patients_per_nurse_hour` values for throughput modeling.

### Extend the model

- Add shift preferences or fairness constraints (e.g., balanced workload across nurses).
- Add per-shift overtime caps or total overtime budget limits.
- Model multi-day scheduling by adding a date dimension to shifts.
- Add break/rest constraints between consecutive shifts.

### Scale up and productionize

- Replace CSV ingestion with Snowflake sources.
- Write staff assignments and overtime plans back to Snowflake after solving.

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
  <summary>Why do I get <code>ModuleNotFoundError</code>?</summary>

- Confirm your virtual environment is activated.
- Install the template dependencies from this folder: `python -m pip install .`

</details>

<details>
  <summary>Why do I get <code>Status: INFEASIBLE</code>?</summary>

- Check that the combination of nurse availability and shift requirements is feasible. Every shift needs `min_nurses` available nurses, and every nurse must have at least one available shift.
- Confirm that at least one nurse with the required `min_skill` level is available for each shift.
- If you modified the data, ensure `regular_hours` and `overtime_multiplier` are positive.

</details>

<details>
  <summary>Why is the overtime summary empty?</summary>

- The script filters nurses with `Nurse.overtime_hours > 0.5`. If no nurse works beyond their regular hours, the "No overtime assigned" message is printed instead.
- This is expected when staffing requirements can be met without overtime.

</details>

<details>
  <summary>Why are staff assignments missing or incomplete?</summary>

- The output filters on `Assignment.assigned > 0.5` (binary threshold). If values are near zero, inspect the availability data and constraints.
- Confirm `availability.csv` was read correctly and contains rows with `available = 1`.

</details>

<details>
  <summary>CSV loading fails (missing file or column)</summary>

- Confirm the CSVs exist under `data/` and the filenames match.
- Ensure the headers match the expected schema:
  - `nurses.csv`: `id`, `name`, `skill_level`, `hourly_cost`, `regular_hours`, `overtime_multiplier`
  - `shifts.csv`: `id`, `name`, `start_hour`, `duration`, `min_nurses`, `min_skill`, `patient_demand`, `patients_per_nurse_hour`
  - `availability.csv`: `nurse_id`, `shift_id`, `available`

</details>
