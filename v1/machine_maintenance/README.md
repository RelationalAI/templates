---
title: "Machine Maintenance"
description: "A multi-reasoner template that chains graph analysis, rules-based classification, and prescriptive optimization to schedule preventive maintenance across machines and technicians."
featured: false
experience_level: intermediate
industry: "Manufacturing"
reasoning_types:
  - Graph
  - Rules
  - Prescriptive
tags:
  - Multi-Reasoner
  - Chained Reasoning
  - Scheduling
  - Maintenance
  - Manufacturing
  - Assignment
---

# Machine Maintenance

## What this template is for

Manufacturing facilities must schedule preventive maintenance for machines with ML-predicted failure probabilities. This requires understanding which machines compete for the same technicians, flagging compliance risks, and then optimizing the schedule subject to all of these signals.

This template uses RelationalAI's **graph analysis**, **rules-based classification**, and **prescriptive reasoning (optimization)** capabilities in a chained multi-reasoner workflow:

1. **Graph analysis** builds a machine dependency graph from shared-technician qualifications, identifies dependency clusters via weakly connected components, and computes betweenness centrality to find bottleneck machines.
2. **Rules** derive compliance flags: overdue maintenance, high-risk machines, parts reorder triggers, and expiring technician certifications.
3. **Prescriptive optimization** schedules maintenance across a multi-period horizon, assigning qualified technicians to machines. The optimizer consumes outputs from both earlier stages: betweenness centrality weights the failure cost (bottleneck machines are more expensive to leave vulnerable), and overdue-maintenance flags add hard scheduling constraints (overdue machines must be serviced early).

This demonstrates how multiple reasoning types compose naturally in a single RelationalAI model, where each stage enriches the shared ontology and downstream stages consume those enrichments.

## Who this is for

- Manufacturing and plant managers scheduling preventive maintenance
- Operations researchers exploring multi-reasoner pipelines in RelationalAI
- Developers learning how to chain graph, rules, and optimization in a single model

## What you'll build

- A machine dependency graph with cluster detection and centrality scoring
- Four compliance rules as derived Relationships (boolean flags)
- Binary decision variables for maintenance timing, vulnerability tracking, and technician assignment
- Cumulative coverage, capacity, and overdue-deadline constraints
- A cost minimization objective that incorporates graph centrality as a risk multiplier

## What's included

- `machine_maintenance.py` -- Main script with three chained reasoning stages
- `data/machines.csv` -- 30 machines with failure probability, criticality (1-5), duration, and parts cost
- `data/technicians.csv` -- 10 technicians with skill levels, certifications, hourly rates, and locations
- `data/availability.csv` -- Technician availability across the 4-period planning horizon
- `data/qualifications.csv` -- Mapping of which technicians can service which machine types
- `data/parts_inventory.csv` -- Spare parts stock levels at each facility
- `data/certification_expiry.csv` -- Days remaining on technician certifications per machine type
- `pyproject.toml` -- Python project configuration with dependencies

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools
- Python >= 3.10

## Quickstart

1. Download the ZIP file for this template and extract it:

   ```bash
   curl -O https://private.relational.ai/templates/zips/v1/machine_maintenance.zip
   unzip machine_maintenance.zip
   cd machine_maintenance
   ```

   > [!TIP]
   > You can also download the template ZIP using the "Download ZIP" button at the top of this page.

2. Create a virtual environment and activate it:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   ```

3. Install dependencies:

   ```bash
   python -m pip install .
   ```

4. Configure your RAI connection:

   ```bash
   rai init
   ```

5. Run the template:

   ```bash
   python machine_maintenance.py
   ```

6. Expected output:
   ```text
   ======================================================================
   STAGE 1: Graph Analysis -- Dependency Clusters & Centrality
   ======================================================================
   Dependency clusters found: 1

   Top bottleneck machines (betweenness centrality):
     M003 (Pump, Plant_C): betweenness=24.0000, failure_prob=0.089
     M008 (Pump, Plant_B): betweenness=24.0000, failure_prob=0.076
     M013 (Pump, Plant_A): betweenness=24.0000, failure_prob=0.435
     M002 (Compressor, Plant_B): betweenness=18.0000, failure_prob=0.270
     ...

   ======================================================================
   STAGE 2: Rules -- Compliance Flags
   ======================================================================

   Overdue maintenance (6 machines):
     M002 (Compressor_Beta_1): RUL=3.7h < duration=6h
     M006 (Turbine_Alpha_2): RUL=3.4h < duration=8h
     M013 (Pump_Gamma_3): RUL=2.3h < duration=4h
     ...

   High-risk machines (1):
     M013 (Pump_Gamma_3): prob=0.435, crit=4

   Parts needing reorder (4):
     P001 (Spindle Bearings, Plant_A): stock=25 <= min_order=50
     ...

   Expiring certifications (5):
     T001 (Alice_Johnson): Compressor -- 22 days remaining
     T004 (Diana_Chen): Pump -- 8 days remaining
     ...

   ======================================================================
   STAGE 3: Prescriptive -- Maintenance Scheduling
   ======================================================================

   Status: OPTIMAL
   Objective value: 510549.59

   Maintenance schedule (20 jobs):
     Period 1:
       M002 (Compressor, Plant_B, crit=5)
       M006 (Turbine, Plant_C, crit=5)
       M013 (Pump, Plant_A, crit=4)
       M014 (Generator, Plant_B, crit=5)
       ...
     Period 2: ...
     Period 3: ...
     Period 4: ...

   Technician assignments (20):
     Period 1:
       M002: T003 (6h x $65/h = $390) [TRAVEL]
       M013: T006 (4h x $88/h = $352) [TRAVEL]
       M014: T005 (12h x $92/h = $1104)
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
    ├── qualifications.csv
    ├── parts_inventory.csv
    └── certification_expiry.csv
```

## How it works

This section walks through the highlights in `machine_maintenance.py`.

### Define concepts and load CSV data

First, the model defines concepts for machines (with ML-predicted failure probability and numeric criticality), technicians (with skills and hourly rates), qualifications linking technicians to machine types, parts inventory, and certification expiry data. All data is loaded from CSV files:

```python
Machine = model.Concept("Machine", identify_by={"machine_id": String})
Machine.failure_probability = model.Property(
    f"{Machine} has failure probability {Float:failure_probability}")
Machine.criticality = model.Property(f"{Machine} has criticality {Integer:criticality}")

Technician = model.Concept("Technician", identify_by={"technician_id": String})
Qualification = model.Concept(
    "Qualification", identify_by={"technician_id": String, "machine_type": String})

PartsInventory = model.Concept("PartsInventory", identify_by={"part_id": String})
CertificationExpiry = model.Concept(
    "CertificationExpiry",
    identify_by={"technician_id": String, "machine_type": String})
```

Cross-product concepts define the scheduling decision space. `MachinePeriod` pairs each machine with each planning period. `TechnicianMachinePeriod` is restricted to qualified pairs -- technicians can only be assigned to machine types they are certified for.

### Stage 1: Graph -- dependency clusters and centrality

An undirected graph is built where machine nodes are connected when they share a qualified technician. Two machines share an edge if any technician is qualified for both their `machine_type` values (a self-join on qualifications):

```python
dep_graph = Graph(
    model, directed=False, weighted=False, node_concept=Machine, aggregator="sum"
)

model.where(
    q1.technician(tech),
    q2.technician(tech),
    q1.machine_type_str == m1.machine_type,
    q2.machine_type_str == m2.machine_type,
    m1.machine_id < m2.machine_id,
).define(dep_graph.Edge.new(src=m1, dst=m2))
```

Weakly connected components identify dependency clusters (groups of machines that compete for the same technicians). Betweenness centrality scores bottleneck machines -- those whose maintenance blocks the most scheduling options. These scores are stored as a `Machine.betweenness` property for use in Stage 3.

### Stage 2: Rules -- compliance flags

Four derived Relationships flag compliance issues. Each rule is a pure logic derivation using `model.where(...).define(...)`:

```python
Machine.is_overdue_maintenance = model.Relationship(
    f"{Machine} is overdue maintenance"
)
model.where(
    Machine.remaining_useful_life < Machine.maintenance_duration_hours
).define(Machine.is_overdue_maintenance())

PartsInventory.needs_reorder = model.Relationship(
    f"{PartsInventory} needs reorder"
)
model.where(
    PartsInventory.stock_level <= PartsInventory.min_order_qty
).define(PartsInventory.needs_reorder())
```

The overdue-maintenance flag feeds directly into the optimizer as a hard constraint, and the other flags surface actionable compliance information.

### Stage 3: Define decision variables, constraints, and objective

Three binary decision variables control the schedule: whether to maintain a machine in a period, whether it remains vulnerable, and whether a technician is assigned. The formulation includes four standard constraints (cumulative coverage, assignment linkage, technician capacity, parts/bay capacity) plus a new constraint from Stage 2:

```python
# Overdue machines must be maintained by OVERDUE_DEADLINE.
maintained_by_deadline = (
    sum(MachinePeriod_overdue.x_maintain)
    .where(
        MachinePeriod_overdue.machine(Machine_overdue),
        MachinePeriod_overdue.period(Period_overdue),
        Period_overdue.pid <= OVERDUE_DEADLINE,
    )
    .per(Machine_overdue)
)
p.satisfy(
    model.require(maintained_by_deadline >= 1).where(
        Machine_overdue.is_overdue_maintenance()
    )
)
```

The objective minimizes expected total cost with three components. The failure cost term incorporates betweenness centrality from Stage 1, making it more expensive to leave bottleneck machines vulnerable:

```python
Machine_obj = Machine.ref()
failure_cost = sum(
    MachinePeriod_outer.x_vulnerable
    * Machine_obj.failure_probability
    * Machine_obj.estimated_parts_cost
    * Machine_obj.criticality
    * (1 + CENTRALITY_WEIGHT * Machine_obj.betweenness)
).where(
    MachinePeriod_outer.machine(Machine_obj), MachinePeriod_outer.period(Period_outer)
)
```

### Solve and print results

The model is solved using the HiGHS solver with a two-minute time limit. After solving, the script prints the maintenance schedule grouped by period and technician assignments with cost breakdown:

```python
p.solve("highs", time_limit_sec=120)
si = p.solve_info()
assert si.termination_status == "OPTIMAL"
```

## Customize this template

- **Adjust centrality weight** via `CENTRALITY_WEIGHT` to control how strongly graph bottleneck scores influence scheduling priority.
- **Change the overdue deadline** via `OVERDUE_DEADLINE` to give more or fewer periods for overdue machines.
- **Extend the planning horizon** by adding more periods to the availability data and increasing `PERIOD_HORIZON`.
- **Adjust capacity limits** via `PARTS_CAPACITY_PER_PERIOD` to see how tighter constraints shift scheduling priorities.
- **Tune travel cost** via `TRAVEL_COST_PER_HOUR` to control preference for local vs. cross-facility assignments.
- **Add rule thresholds** -- adjust `failure_probability > 0.3` or `criticality >= 4` in the high-risk rule to match your risk tolerance.

## Troubleshooting

<details>
<summary><code>Status: INFEASIBLE</code></summary>

- The overdue-maintenance constraint requires certain machines to be scheduled in early periods. If technician capacity is too tight, this can cause infeasibility.
- Try increasing `OVERDUE_DEADLINE` from 2 to 3, or increase `PARTS_CAPACITY_PER_PERIOD`.
- Check that technician hours capacity across all periods can accommodate all machines.
</details>

<details>
<summary>All machines maintained in period 1</summary>

- The solver minimizes total cost. If capacity allows, it may schedule all maintenance early to avoid vulnerability costs.
- Tighten `PARTS_CAPACITY_PER_PERIOD` to spread maintenance across periods.
</details>

<details>
<summary>Graph shows 0 edges</summary>

- This means no two machines share a qualified technician. Check that `qualifications.csv` has overlapping machine types across technicians.
- The graph edge construction uses type-based joins: two machines connect if any technician is qualified for both their `machine_type` values.
</details>

<details>
<summary><code>input definition is too large</code></summary>

- This occurs with large cross-products. The qualification-filtered assignment space avoids this issue for the default 30-machine dataset.
- If you scale up significantly, consider reducing data size or using `variable_values()` instead of `model.select()`.
</details>

<details>
<summary><code>ModuleNotFoundError</code></summary>

- Make sure you activated the virtual environment and ran `python -m pip install .` from the template directory.
- The `pyproject.toml` declares the required dependencies.
</details>

<details>
<summary>Connection or authentication errors</summary>

- Run `rai init` to configure your Snowflake connection.
- Verify that the RAI Native App is installed and your user has the required permissions.
</details>
