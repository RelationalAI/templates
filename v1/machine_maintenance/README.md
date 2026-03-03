---
title: "Machine Maintenance"
description: "Schedule preventive maintenance for factory machines across time slots to minimize downtime cost."
featured: false
experience_level: beginner
industry: "Manufacturing"
reasoning_types:
  - Prescriptive
tags:
  - Scheduling
  - Maintenance
  - Manufacturing
---

# Machine Maintenance

## What this template is for

Manufacturing facilities must schedule preventive maintenance for their machines to avoid costly breakdowns. Each machine requires a specific number of crew hours, and maintenance crews have limited availability across the week. Some machines share resources or physical space and cannot be serviced at the same time.

This template uses prescriptive reasoning to assign each machine to exactly one maintenance time slot while respecting crew hour limits and machine conflict constraints. The objective minimizes total maintenance cost, which varies by time slot due to cost multipliers (such as premium rates for end-of-week scheduling).

The model demonstrates a classic assignment problem with side constraints, making it a practical starting point for any scheduling scenario where items must be allocated to time periods with resource limits and mutual exclusions.

## Who this is for

- Manufacturing and plant managers scheduling preventive maintenance
- Operations researchers modeling assignment problems with conflict constraints
- Developers learning binary optimization with RelationalAI
- Anyone building maintenance planning or resource scheduling tools

## What you'll build

- A machine-to-time-slot assignment model with binary decision variables
- Crew hour capacity constraints per time slot
- Conflict constraints preventing specific machine pairs from sharing a slot
- A cost minimization objective with time-slot-dependent multipliers

## What's included

- `machine_maintenance.py` -- Main script that defines the model, solves it, and prints results
- `data/machines.csv` -- Machines with maintenance hours, failure costs, and importance ratings
- `data/time_slots.csv` -- Weekly time slots with crew hour budgets and cost multipliers
- `data/conflicts.csv` -- Pairs of machines that cannot be maintained simultaneously
- `pyproject.toml` -- Python project configuration with dependencies

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools
- Python >= 3.10

## Quickstart

1. Download ZIP:
   ```bash
   curl -L -O https://docs.relational.ai/templates/zips/v1/machine_maintenance.zip
   unzip machine_maintenance.zip
   cd machine_maintenance
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
   python machine_maintenance.py
   ```

6. Expected output:
   ```text
   Status: OPTIMAL
   Total maintenance cost: $19500.00

   Maintenance schedule:
     machine       day
    CNC_Mill    Monday
       Lathe   Tuesday
       Press   Tuesday
      Welder    Monday
       Drill    Monday
   ```

## Template structure
```text
.
├── README.md
├── pyproject.toml
├── machine_maintenance.py
└── data/
    ├── machines.csv
    ├── time_slots.csv
    └── conflicts.csv
```

## How it works

### 1. Define the ontology and load data

The model defines three concepts: machines with maintenance requirements and failure costs, time slots with crew availability and cost multipliers, and conflict pairs indicating machines that cannot share a slot.

```python
Machine = Concept("Machine", identify_by={"id": Integer})
Machine.name = Property(f"{Machine} has {String:name}")
Machine.maintenance_hours = Property(f"{Machine} has {Integer:maintenance_hours}")
Machine.failure_cost = Property(f"{Machine} has {Float:failure_cost}")

TimeSlot = Concept("TimeSlot", identify_by={"id": Integer})
TimeSlot.day = Property(f"{TimeSlot} on {String:day}")
TimeSlot.crew_hours = Property(f"{TimeSlot} has {Integer:crew_hours}")
TimeSlot.cost_multiplier = Property(f"{TimeSlot} has {Float:cost_multiplier}")
```

### 2. Set up decision variables

A binary variable for every machine-slot combination indicates whether a machine is scheduled in that slot.

```python
Schedule = Concept("Schedule")
Schedule.machine = Property(f"{Schedule} for {Machine}", short_name="machine")
Schedule.slot = Property(f"{Schedule} in {TimeSlot}", short_name="slot")
Schedule.x_assigned = Property(f"{Schedule} is {Float:assigned}")
model.define(Schedule.new(machine=Machine, slot=TimeSlot))

s.solve_for(Schedule.x_assigned, type="bin",
    name=["sched", Schedule.machine.name, Schedule.slot.day])
```

### 3. Add constraints

Each machine must be scheduled exactly once, crew hours per slot must not be exceeded, and conflicting machines cannot share a slot.

```python
# Each machine scheduled exactly once
machine_scheduled = sum(ScheduleRef.x_assigned).where(
    ScheduleRef.machine == Machine).per(Machine)
s.satisfy(model.require(machine_scheduled == 1))

# Crew hour limits
slot_hours = sum(ScheduleRef.x_assigned * ScheduleRef.machine.maintenance_hours).where(
    ScheduleRef.slot == TimeSlot).per(TimeSlot)
s.satisfy(model.require(slot_hours <= TimeSlot.crew_hours))

# No conflicts in same slot
no_conflicts = model.require(ScheduleA.x_assigned + ScheduleB.x_assigned <= 1).where(
    ScheduleA.machine == Conflict.machine1,
    ScheduleB.machine == Conflict.machine2,
    ScheduleA.slot == ScheduleB.slot,
)
s.satisfy(no_conflicts)
```

### 4. Minimize total cost

The objective minimizes the sum of each machine's failure cost weighted by the slot's cost multiplier.

```python
total_cost = sum(Schedule.x_assigned * Schedule.machine.failure_cost * Schedule.slot.cost_multiplier)
s.minimize(total_cost)
```

## Customize this template

- **Add more machines or time slots** by extending the CSV files to model a larger facility.
- **Add machine priorities** to the objective so high-importance machines get preferred (cheaper) slots.
- **Introduce maintenance windows** where certain machines can only be serviced on specific days.
- **Model multi-day maintenance** for machines that require more hours than a single slot provides.
- **Add crew skill requirements** so only qualified crews can service certain machines.

## Troubleshooting

<details>
<summary>Solver returns INFEASIBLE</summary>

Check that the total crew hours across all slots can accommodate all machines. The current data has 5 machines requiring 4+3+5+2+2 = 16 hours, and 5 slots offering 8+8+6+8+6 = 36 hours. Also check that conflict constraints do not make it impossible to assign all machines.
</details>

<details>
<summary>Machines not spreading across slots as expected</summary>

The solver minimizes cost, so it will pack machines into the cheapest slots (lowest cost_multiplier) as long as crew hours allow. If you want to spread work more evenly, add a load-balancing term to the objective or tighten crew hour limits.
</details>

<details>
<summary>Connection or authentication errors</summary>

Run `rai init` to configure your Snowflake connection. Verify that the RAI Native App is installed and your user has the required permissions.
</details>

<details>
<summary>ModuleNotFoundError for relationalai</summary>

Ensure you activated the virtual environment and ran `python -m pip install .` to install all dependencies listed in `pyproject.toml`.
</details>
