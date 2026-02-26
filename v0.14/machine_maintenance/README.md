---
title: "Machine Maintenance"
description: "Schedule preventive maintenance across time slots to minimize cost while respecting crew-hour capacity and machine conflicts."
featured: false
experience_level: intermediate
industry: "Manufacturing"
reasoning_types:
  - Prescriptive
tags:
  - Scheduling
  - MILP
---

# Machine Maintenance

> [!WARNING]
> This template uses the early access `relationalai.semantics` API in version `0.14.2` of the `relationalai` Python package.

## What this template is for

Preventive maintenance reduces unplanned downtime, but scheduling it can be tricky.
You typically have limited crew capacity per shift/day, some equipment can’t be serviced at the same time (shared tooling, access constraints, or specialist technicians), and some maintenance windows are more expensive (overtime/weekends).

This template shows how to build a small **maintenance scheduling** optimizer with RelationalAI.
It schedules each machine into exactly one time slot, respects crew-hour limits, avoids conflicting machine pairs in the same slot, and minimizes total expected maintenance cost.

## Who this is for

- You want an end-to-end example of **prescriptive reasoning (optimization)** using RelationalAI Semantics.
- You’re comfortable with basic Python and the idea of decision variables, constraints, and an objective.

## What you’ll build

- A semantic model for machines, time slots, and conflicts (concepts + properties).
- A MILP scheduling model with one binary assignment variable per machine–slot pair.
- Constraints for exactly-once scheduling, crew-hour capacity, and conflict exclusions.
- A cost-minimizing solve using the **HiGHS** backend and a readable printed schedule.

## What’s included

- **Model + solve script**: `machine_maintenance.py`
- **Sample data**: `data/machines.csv`, `data/time_slots.csv`, `data/conflicts.csv`
- **Outputs**: solver status + objective value + a machine-to-day schedule printed to stdout

## Prerequisites

### Access

- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools

- Python >= 3.10

## Quickstart

Follow these steps to run the template with the included sample data.

1. Download the ZIP file for this template and extract it:

   ```bash
   curl -O https://private.relational.ai/templates/zips/v0.14/machine_maintenance.zip
   unzip machine_maintenance.zip
   cd machine_maintenance
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
   python machine_maintenance.py
   ```

6. **Expected output**

   ```text
   Status: OPTIMAL
   Total maintenance cost: $19500.00

   Maintenance schedule:
    machine      day
   CNC_Mill  Tuesday
      Drill  Tuesday
      Lathe   Monday
      Press   Monday
     Welder Thursday
   ```

## Template structure

```text
.
├─ README.md
├─ pyproject.toml
├─ machine_maintenance.py      # main runner / entrypoint
└─ data/                       # sample input data
   ├─ machines.csv
   ├─ time_slots.csv
   └─ conflicts.csv
```

**Start here**: `machine_maintenance.py`

## Sample data

Data files are in `data/`.

### `machines.csv`

Defines the machines to schedule, the effort required, and the relative cost of delaying maintenance.

| Column | Meaning |
| --- | --- |
| `id` | Unique machine identifier |
| `name` | Machine name |
| `maintenance_hours` | Crew-hours required to complete maintenance |
| `failure_cost` | Weight/cost used in the objective (higher means “more expensive to schedule into costly slots”) |
| `importance` | Priority level (loaded for convenience; not used in the objective in this template) |

### `time_slots.csv`

Defines available maintenance time slots.

| Column | Meaning |
| --- | --- |
| `id` | Unique slot identifier |
| `day` | Slot label used in output (e.g., Monday, Tuesday) |
| `crew_hours` | Total crew-hours available in the slot |
| `cost_multiplier` | Cost multiplier for scheduling into the slot (e.g., overtime) |

### `conflicts.csv`

Defines machine pairs that cannot be maintained in the same time slot.

| Column | Meaning |
| --- | --- |
| `machine1_id` | First machine in a conflicting pair |
| `machine2_id` | Second machine in a conflicting pair |

## Model overview

The semantic model for this template is built around four concepts.

### `Machine`

A machine that requires preventive maintenance.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `id` | int | Yes | Loaded as the key from `data/machines.csv` |
| `name` | string | No | Used for output labeling |
| `maintenance_hours` | int | No | Consumed against slot capacity |
| `failure_cost` | float | No | Scales assignment cost in the objective |
| `importance` | int | No | Included as an extension hook |

### `TimeSlot`

A maintenance window with limited crew capacity and a relative cost.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `id` | int | Yes | Loaded as the key from `data/time_slots.csv` |
| `day` | string | No | Used for output labeling |
| `crew_hours` | int | No | Capacity per slot |
| `cost_multiplier` | float | No | Increases cost for expensive slots |

### `Conflict`

A pair of machines that cannot be scheduled in the same slot.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `machine1` | `Machine` | Part of compound key | Joined from `conflicts.csv.machine1_id` |
| `machine2` | `Machine` | Part of compound key | Joined from `conflicts.csv.machine2_id` |

### `Schedule` (decision concept)

A decision entity that assigns a machine to a slot.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `machine` | `Machine` | Part of compound key | One dimension of the assignment |
| `slot` | `TimeSlot` | Part of compound key | One dimension of the assignment |
| `assigned` | float | No | Binary decision variable (0/1) |

## How it works

This section walks through the highlights in `machine_maintenance.py`.

### Import libraries and configure inputs

First, the script imports the Semantics APIs, sets `DATA_DIR`, and creates a Semantics `Model` container:

```python
from pathlib import Path

import pandas
from pandas import read_csv

from relationalai.semantics import Model, Relationship, data, define, require, select, sum, where
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

# Create a Semantics model container.
model = Model("machine_maintenance", config=globals().get("config", None))
```

### Define concepts and load CSV data

Next, it defines `Machine` and `TimeSlot` concepts and loads the corresponding CSVs using `data(...).into(...)`:

```python
# Machine concept: represents a machine with maintenance hours, failure cost, and importance level.
Machine = model.Concept("Machine")
Machine.id = model.Property("{Machine} has {id:int}")
Machine.name = model.Property("{Machine} has {name:string}")
Machine.maintenance_hours = model.Property("{Machine} has {maintenance_hours:int}")
Machine.failure_cost = model.Property("{Machine} has {failure_cost:float}")
Machine.importance = model.Property("{Machine} has {importance:int}")

# Load machine data from CSV.
data(read_csv(DATA_DIR / "machines.csv")).into(Machine, keys=["id"])

# TimeSlot concept: represents a maintenance time slot with crew hour capacity and cost multiplier.
TimeSlot = model.Concept("TimeSlot")
TimeSlot.id = model.Property("{TimeSlot} has {id:int}")
TimeSlot.day = model.Property("{TimeSlot} on {day:string}")
TimeSlot.crew_hours = model.Property("{TimeSlot} has {crew_hours:int}")
TimeSlot.cost_multiplier = model.Property("{TimeSlot} has {cost_multiplier:float}")

# Load time slot data from CSV.
data(read_csv(DATA_DIR / "time_slots.csv")).into(TimeSlot, keys=["id"])
```

Then, it loads conflict pairs from `conflicts.csv` and resolves machine IDs into `Machine` instances with `where(...).define(...)`:

```python
# Conflict concept: represents conflicts between machines that cannot be maintained at the same time
Conflict = model.Concept("Conflict")
Conflict.machine1 = model.Relationship("{Conflict} between {machine1:Machine}")
Conflict.machine2 = model.Relationship("{Conflict} and {machine2:Machine}")

# Load machine conflict pairs from CSV.
conflicts_data = data(read_csv(DATA_DIR / "conflicts.csv"))
OtherMachine = Machine.ref()
where(
    Machine.id == conflicts_data.machine1_id,
    OtherMachine.id == conflicts_data.machine2_id
).define(
    Conflict.new(machine1=Machine, machine2=OtherMachine)
)
```

### Define decision variables, constraints, and objective

With the input concepts in place, the script creates a `Schedule` decision concept and uses `solve_for(..., type="bin")` to create one binary assignment variable per machine–slot pair:

```python
# Schedule decision concept: represents the assignment of machines to time slots.
# The "assigned" property is a binary variable indicating whether a machine is scheduled in a slot.
Schedule = model.Concept("Schedule")
Schedule.machine = model.Relationship("{Schedule} for {machine:Machine}")
Schedule.slot = model.Relationship("{Schedule} in {slot:TimeSlot}")
Schedule.x_assigned = model.Property("{Schedule} is {assigned:float}")
define(Schedule.new(machine=Machine, slot=TimeSlot))

ScheduleRef = Schedule.ref()
ScheduleA = Schedule.ref()
ScheduleB = Schedule.ref()

s = SolverModel(model, "cont")

# Variable: binary assignment
s.solve_for(Schedule.x_assigned, type="bin", name=["x", Schedule.machine.name, Schedule.slot.day])
```

Next, it adds three families of constraints using `require(...)` and `s.satisfy(...)`: schedule each machine exactly once, enforce per-slot crew-hour capacity, and prevent conflicting pairs from being scheduled in the same slot:

```python
# Constraint: each machine scheduled exactly once
machine_scheduled = sum(ScheduleRef.x_assigned).where(ScheduleRef.machine == Machine).per(Machine)
exactly_once = require(machine_scheduled == 1)
s.satisfy(exactly_once)

# Constraint: crew hours per slot not exceeded
slot_hours = sum(ScheduleRef.x_assigned * ScheduleRef.machine.maintenance_hours).where(ScheduleRef.slot == TimeSlot).per(TimeSlot)
crew_limit = require(slot_hours <= TimeSlot.crew_hours)
s.satisfy(crew_limit)

# Constraint: conflicting machines cannot be scheduled in same slot
no_conflicts = require(ScheduleA.x_assigned + ScheduleB.x_assigned <= 1).where(
    ScheduleA.machine == Conflict.machine1,
    ScheduleB.machine == Conflict.machine2,
    ScheduleA.slot == ScheduleB.slot
)
s.satisfy(no_conflicts)
```

Then, it minimizes total cost, computed as `failure_cost * cost_multiplier` for the chosen assignments:

```python
# Objective: minimize total maintenance cost (base cost * slot multiplier)
total_cost = sum(Schedule.x_assigned * Schedule.machine.failure_cost * Schedule.slot.cost_multiplier)
s.minimize(total_cost)
```

### Solve and print results

Finally, it solves using the HiGHS backend (with a 60s time limit), prints the status/objective, and selects only assignments with `Schedule.x_assigned > 0.5` for the output table:

```python
solver = Solver("highs")
s.solve(solver, time_limit_sec=60)

print(f"Status: {s.termination_status}")
print(f"Total maintenance cost: ${s.objective_value:.2f}")

schedule = select(
    Schedule.machine.name.alias("machine"),
    Schedule.slot.day.alias("day")
).where(Schedule.x_assigned > 0.5).to_df()

print("\nMaintenance schedule:")
print(schedule.to_string(index=False))
```

## Customize this template

### Use your own data

- Replace the CSVs under `data/` with your own data, keeping the same headers (or update the loading logic in `machine_maintenance.py`).
- Ensure `conflicts.csv` only references valid machine IDs from `machines.csv`.
- Make sure total crew capacity across slots is sufficient for the total required maintenance hours (and that conflicts don’t force impossible packings).

### Tune parameters

- To make certain days more expensive, edit `time_slots.csv.cost_multiplier`.
- To reflect staffing changes, edit `time_slots.csv.crew_hours`.
- To change the solve time budget, edit the call `s.solve(solver, time_limit_sec=60)`.

### Extend the model

- Use `Machine.importance` in the objective (for example, multiply it into the cost) if you want a second, coarse priority signal.
- Add “must-schedule-by” deadlines by restricting which slots certain machines are allowed to use.
- Add technician skills or machine-type requirements by introducing additional concepts and capacity constraints.

### Scale up and productionize

- Replace CSV ingestion with Snowflake sources.
- Write the chosen schedule back to Snowflake after solving.

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
- Install dependencies from this folder with `python -m pip install .`.

</details>

<details>
  <summary>Why does CSV loading fail (missing file or column)?</summary>


- Confirm the CSVs exist under `data/` and the filenames match.
- Ensure the headers match the expected schema:
  - `machines.csv`: `id`, `name`, `maintenance_hours`, `failure_cost`, `importance`
  - `time_slots.csv`: `id`, `day`, `crew_hours`, `cost_multiplier`
  - `conflicts.csv`: `machine1_id`, `machine2_id`

</details>

<details>
  <summary>Why do I get <code>Status: INFEASIBLE</code>?</summary>


- Check that total required hours can fit into the available `crew_hours` across slots.
- Conflicts can force additional separation: ensure conflicting machines have enough remaining capacity across distinct slots.
- Confirm every machine has at least one feasible slot (in this template, all machines can use all slots; if you extend the model with eligibility rules, this becomes a common cause).

</details>

<details>
  <summary>Why is the printed schedule empty?</summary>


- The output filters on `Schedule.x_assigned > 0.5`. If the solve did not succeed, no assignments may satisfy that.
- Print `s.termination_status` and inspect whether the solve completed successfully.

</details>
