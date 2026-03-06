---
title: "Machine Maintenance"
description: "Schedule preventive maintenance across a planning horizon, assigning technicians to machines, minimizing expected failure cost plus maintenance cost."
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

Manufacturing facilities must schedule preventive maintenance for machines with ML-predicted remaining useful life. Each machine either receives maintenance by a given period or remains vulnerable to failure. When maintenance is scheduled, exactly one technician must be assigned, subject to technician availability constraints and global capacity limits.

This template uses prescriptive reasoning to decide when each machine is maintained and which technician performs it, minimizing the combined cost of expected failures (for vulnerable machines) and maintenance actions.

The model demonstrates a multi-period scheduling problem with technician assignment, cumulative coverage constraints, and a risk-weighted objective -- a practical pattern for any maintenance planning scenario.

## Who this is for

- Manufacturing and plant managers scheduling preventive maintenance
- Operations researchers modeling multi-period scheduling with assignment
- Developers learning binary optimization with cross-product decision spaces in RelationalAI

## What you'll build

- Binary decision variables for maintenance timing, vulnerability tracking, and technician assignment
- Cumulative coverage constraints (each machine maintained or vulnerable per period)
- Assignment-maintenance linkage (exactly one technician per maintenance action)
- Technician availability and global capacity constraints
- A cost minimization objective balancing failure risk against maintenance cost

## What's included

- `machine_maintenance.py` -- Main script that defines the model, solves it, and prints results
- `data/machines.csv` -- 10 machines with remaining useful life, failure probability, criticality, and parts cost
- `data/technicians.csv` -- 10 technicians with skill levels, certifications, hourly rates, and specializations
- `data/availability.csv` -- Technician availability across the 4-period planning horizon
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
   Objective value: 11.0

   Maintenance schedule (10 assignments):
     Period 1: M005, M010
     Period 2: M001, M004, M007
     Period 3: M002, M003, M006, M008, M009
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
    └── availability.csv
```

## How it works

### 1. Define the ontology and load data

The model defines six concepts: machines with ML-predicted remaining useful life, technicians with skills and certifications, discrete planning periods, and three cross-product concepts for the scheduling decision space.

```python
Machine = model.Concept("Machine", identify_by={"machine_id": String})
Machine.remaining_useful_life = model.Property(
    f"{Machine} has remaining useful life {Float:remaining_useful_life}")
Machine.failure_probability = model.Property(
    f"{Machine} has failure probability {Float:failure_probability}")

Technician = model.Concept("Technician", identify_by={"technician_id": String})
Period = model.Concept("Period", identify_by={"pid": Integer})

MachinePeriod = model.Concept("MachinePeriod",
    identify_by={"machine": Machine, "period": Period})
TechnicianMachinePeriod = model.Concept("TechnicianMachinePeriod",
    identify_by={"technician": Technician, "machine": Machine, "period": Period})
```

### 2. Set up decision variables

Three binary variables control the schedule: maintain a machine in a period, track vulnerability, and assign a technician.

```python
s.solve_for(MachinePeriod.x_maintain, type="bin")
s.solve_for(MachinePeriod.x_vulnerable, type="bin")
s.solve_for(TechnicianMachinePeriod.x_assigned, type="bin")
```

### 3. Add constraints

Cumulative coverage ensures each machine is either maintained by period tau or remains vulnerable. Assignment linkage requires exactly one technician per maintenance action. Technician capacity and global parts/space limits bound the schedule.

```python
# C1: Cumulative maintenance coverage
maintained_until_tau = sum(MachinePeriod_inner.x_maintain).where(
    MachinePeriod_outer.machine(Machine_ref), MachinePeriod_outer.period(Period_outer),
    MachinePeriod_inner.machine(Machine_ref), MachinePeriod_inner.period(Period_inner),
    Period_inner.pid >= 1, Period_inner.pid <= Period_outer.pid
).per(Machine_ref, Period_outer)

s.satisfy(
    model.require(maintained_until_tau + MachinePeriod_outer.x_vulnerable == 1)
    .where(MachinePeriod_outer.machine(Machine_ref), MachinePeriod_outer.period(Period_outer))
)
```

### 4. Minimize expected total cost

The objective balances failure risk (vulnerable machines weighted by failure probability) against maintenance cost.

```python
expected_cost = sum(
    MachinePeriod_outer.x_vulnerable * MachinePeriod_outer.fail_prob * FAILURE_TO_MAINTENANCE_RATIO
    + MachinePeriod_outer.x_maintain
).where(MachinePeriod_outer.machine(Machine_ref), MachinePeriod_outer.period(Period_outer))

s.minimize(expected_cost)
```

## Customize this template

- **Extend the planning horizon** by adding more periods to the availability data and increasing `PERIOD_HORIZON`. Full-scale data (50 machines, 40 technicians, 12 periods) is available in `data/full_scale/`.
- **Add skill matching** so only certified technicians can service certain machine types.
- **Weight by criticality** to prioritize high-criticality machines for earlier maintenance.
- **Add travel costs** based on technician base location vs machine facility.
- **Model multi-period maintenance** for machines requiring more than one period of work.

## Troubleshooting

<details>
<summary>Solver returns INFEASIBLE</summary>

Check that technician availability across all periods can accommodate all machines. With 10 machines and 10 technicians over 4 periods, there is ample capacity. If you tighten constraints (e.g., reduce PARTS_CAPACITY_PER_PERIOD), infeasibility may occur.
</details>

<details>
<summary>All machines maintained in period 1</summary>

The solver minimizes total cost. If capacity allows, it may schedule all maintenance early to avoid vulnerability costs. To spread maintenance, tighten PARTS_CAPACITY_PER_PERIOD or SPACE_CAPACITY_PER_PERIOD.
</details>

<details>
<summary>Query fails with "input definition is too large"</summary>

This occurs with large cross-products (e.g., 50 machines x 40 technicians x 12 periods = 24,000 entities). The solver handles these fine, but post-solve queries may exceed RAI's AST size limit. Reduce the data size or use the default 10x10x4 configuration.
</details>

<details>
<summary>Connection or authentication errors</summary>

Run `rai init` to configure your Snowflake connection. Verify that the RAI Native App is installed and your user has the required permissions.
</details>
