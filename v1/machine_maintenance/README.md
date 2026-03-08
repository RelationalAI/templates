---
title: "Machine Maintenance"
description: "Schedule preventive maintenance across a planning horizon, assigning qualified technicians to machines, minimizing expected failure cost plus labor and travel costs."
featured: false
experience_level: intermediate
industry: "Manufacturing"
reasoning_types:
  - Prescriptive
tags:
  - Scheduling
  - Maintenance
  - Manufacturing
  - Assignment
---

# Machine Maintenance

## What this template is for

Manufacturing facilities must schedule preventive maintenance for machines with ML-predicted failure probabilities. Each machine either receives maintenance by a given period or remains vulnerable to failure. When maintenance is scheduled, a qualified technician must be assigned, subject to hours-based capacity constraints and per-period parts/bay limits.

This template uses prescriptive reasoning to decide when each machine is maintained and which technician performs it, minimizing the combined cost of expected failures (weighted by criticality and parts cost), technician labor (duration times hourly rate), and travel penalties for cross-location assignments.

The model demonstrates a multi-period scheduling problem with skill-based assignment, hours-based capacity, location-aware costing, and a multi-component objective -- a practical pattern for any maintenance planning scenario.

## Who this is for

- Manufacturing and plant managers scheduling preventive maintenance
- Operations researchers modeling multi-period scheduling with skill-constrained assignment
- Developers learning binary optimization with cross-product decision spaces in RelationalAI

## What you'll build

- Binary decision variables for maintenance timing, vulnerability tracking, and technician assignment
- Cumulative coverage constraints (each machine maintained or vulnerable per period)
- Assignment-maintenance linkage (exactly one qualified technician per maintenance action)
- Hours-based technician capacity constraints (duration-aware, not just count-based)
- Parts/bay capacity limits per period
- A cost minimization objective with three components: failure risk, labor cost, and travel cost

## What's included

- `machine_maintenance.py` -- Main script that defines the model, solves it, and prints results
- `data/machines.csv` -- 30 machines with failure probability, criticality (1-5), duration, and parts cost
- `data/technicians.csv` -- 10 technicians with skill levels, certifications, hourly rates, and locations
- `data/availability.csv` -- Technician availability across the 4-period planning horizon
- `data/qualifications.csv` -- Pre-computed mapping of which technicians can service which machine types
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
   curl -O https://docs.relational.ai/templates/zips/v1/machine_maintenance.zip
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
   Objective value: 274798.50

   Maintenance schedule (20 jobs):
     Period 1:
       M002 (Compressor, Plant_B, crit=5)
       M006 (Turbine, Plant_C, crit=5)
       M013 (Pump, Plant_A, crit=4)
       M014 (Generator, Plant_B, crit=5)
       M018 (Pump, Plant_C, crit=5)
     Period 2:
       M005 (Motor, Plant_B, crit=4)
       M007 (Compressor, Plant_A, crit=4)
       M028 (Pump, Plant_A, crit=4)
       ...
     Period 3: ...
     Period 4: ...

   Technician assignments (20):
     Period 1:
       M002: T001 (6h x $95/h = $570)
       M006: T009 (8h x $72/h = $576) [TRAVEL]
       M013: T002 (4h x $90/h = $360)
       ...
   ```

## Template structure
```text
.
├── README.md
├── pyproject.toml
├── machine_maintenance.py
└── data/
    ├── machines.csv
    ├── technicians.csv
    ├── availability.csv
    └── qualifications.csv
```

## How it works

### 1. Define the ontology and load data

The model defines seven concepts: machines with ML-predicted failure probability and numeric criticality, technicians with skills and hourly rates, a qualification mapping linking technicians to machine types, discrete planning periods, and three cross-product concepts for the scheduling decision space.

```python
Machine = model.Concept("Machine", identify_by={"machine_id": String})
Machine.failure_probability = model.Property(
    f"{Machine} has failure probability {Float:failure_probability}")
Machine.criticality = model.Property(f"{Machine} has criticality {Integer:criticality}")
Machine.maintenance_duration_hours = model.Property(
    f"{Machine} requires {Integer:maintenance_duration_hours} hours")

Technician = model.Concept("Technician", identify_by={"technician_id": String})
Technician.hourly_rate = model.Property(f"{Technician} has hourly rate {Float:hourly_rate}")

Qualification = model.Concept("Qualification",
    identify_by={"technician_id": String, "machine_type": String})

Period = model.Concept("Period", identify_by={"pid": Integer})

MachinePeriod = model.Concept("MachinePeriod",
    identify_by={"machine": Machine, "period": Period})
TechnicianMachinePeriod = model.Concept("TechnicianMachinePeriod",
    identify_by={"technician": Technician, "machine": Machine, "period": Period})
```

The `TechnicianMachinePeriod` cross-product is restricted to qualified pairs only -- technicians can only be assigned to machine types they are certified for. A derived `same_location` flag tracks whether the technician is co-located with the machine.

### 2. Set up decision variables

Three binary variables control the schedule: maintain a machine in a period, track vulnerability, and assign a technician.

```python
s.solve_for(MachinePeriod.x_maintain, type="bin")
s.solve_for(MachinePeriod.x_vulnerable, type="bin")
s.solve_for(TechnicianMachinePeriod.x_assigned, type="bin")
```

### 3. Add constraints

Cumulative coverage ensures each machine is either maintained by period tau or remains vulnerable. Assignment linkage requires exactly one qualified technician per maintenance action. Hours-based technician capacity accounts for maintenance duration (not just job count). Parts/bay limits cap concurrent maintenance per period.

```python
# C1: Cumulative maintenance coverage
maintained_until_tau = sum(MachinePeriod_inner.x_maintain).where(
    MachinePeriod_outer.machine(Machine_ref), MachinePeriod_outer.period(Period_outer),
    MachinePeriod_inner.machine(Machine_ref), MachinePeriod_inner.period(Period_inner),
    Period_inner.pid >= 1, Period_inner.pid <= Period_outer.pid
).per(Machine_ref, Period_outer)

coverage_constraint = model.require(
    maintained_until_tau + MachinePeriod_outer.x_vulnerable == 1
).where(MachinePeriod_outer.machine(Machine_ref), MachinePeriod_outer.period(Period_outer))

# C3: Technician hours capacity
assigned_hours = sum(
    TechnicianMachinePeriod_ref.x_assigned
    * TechnicianMachinePeriod_ref.machine.maintenance_duration_hours
).where(...).per(Technician_ref, Period_tc)

hours_constraint = model.require(assigned_hours <= avail_hours)
```

### 4. Minimize expected total cost

The objective has three components: failure risk for vulnerable machines (weighted by probability, parts cost, and criticality), labor cost for maintenance actions (duration times hourly rate), and a travel penalty when technicians work at a different location.

```python
failure_cost = sum(
    MachinePeriod_outer.x_vulnerable
    * MachinePeriod_outer.machine.failure_probability
    * MachinePeriod_outer.machine.estimated_parts_cost
    * MachinePeriod_outer.machine.criticality
).where(MachinePeriod_outer.machine(Machine_ref), MachinePeriod_outer.period(Period_outer))

labor_cost = sum(
    TechnicianMachinePeriod_ref.x_assigned
    * TechnicianMachinePeriod_ref.machine.maintenance_duration_hours
    * TechnicianMachinePeriod_ref.technician.hourly_rate
).where(...)

travel_cost = sum(
    TechnicianMachinePeriod_ref.x_assigned
    * (1 - TechnicianMachinePeriod_ref.same_location)
    * TechnicianMachinePeriod_ref.machine.maintenance_duration_hours
    * TRAVEL_COST_PER_HOUR
).where(...)

s.minimize(failure_cost + labor_cost + travel_cost)
```

## Customize this template

- **Extend the planning horizon** by adding more periods to the availability data and increasing `PERIOD_HORIZON`.
- **Adjust capacity limits** via `PARTS_CAPACITY_PER_PERIOD` to see how tighter constraints shift scheduling priorities.
- **Tune travel cost** via `TRAVEL_COST_PER_HOUR` to control preference for local vs. cross-facility assignments.
- **Add skill-level constraints** requiring senior technicians for critical machines.
- **Model multi-period maintenance** for machines requiring more than one period of work.

## Troubleshooting

<details>
<summary>Solver returns INFEASIBLE</summary>

Check that technician hours capacity across all periods can accommodate all machines. With 30 machines and 10 technicians over 4 periods, capacity is tight. If you reduce `PARTS_CAPACITY_PER_PERIOD` below the minimum needed, infeasibility may occur.
</details>

<details>
<summary>All machines maintained in period 1</summary>

The solver minimizes total cost. If capacity allows, it may schedule all maintenance early to avoid vulnerability costs. Tighten `PARTS_CAPACITY_PER_PERIOD` to spread maintenance across periods.
</details>

<details>
<summary>Query fails with "input definition is too large"</summary>

This occurs with large cross-products. The qualification-filtered assignment space (1,032 variables for 30 machines) avoids this issue. If you scale up significantly, consider reducing data size or using `variable_values()` instead of `model.select()`.
</details>

<details>
<summary>Connection or authentication errors</summary>

Run `rai init` to configure your Snowflake connection. Verify that the RAI Native App is installed and your user has the required permissions.
</details>
