---
title: "Water Allocation"
description: "Minimize the cost of distributing water from sources to users with nonlinear transmission losses."
featured: false
experience_level: intermediate
industry: "Utilities & Resources"
reasoning_types:
  - Prescriptive
tags:
  - Resource Allocation
  - Network Flow
  - Nonlinear Programming
  - Ipopt
---

# Water Allocation

## What this template is for

This template uses **prescriptive reasoning (optimization)** to minimize the cost of distributing water from sources to users with nonlinear transmission losses.

Water utilities must distribute water from multiple sources (reservoirs, groundwater) to multiple user groups (municipal, industrial, agricultural). Each source has a limited capacity and a different extraction cost. Each connection in the distribution network has a maximum flow rate and a transmission loss rate that reduces the effective amount delivered.

This template uses prescriptive reasoning to find the minimum-cost allocation that satisfies every user's demand. It models the distribution network as a flow problem with source capacity constraints, demand satisfaction constraints with nonlinear transmission losses, and connection flow limits.

The key feature is nonlinear loss modeling: transmission losses increase with utilization (effective delivery = flow * (1 - loss_rate * flow / max_flow)), creating a quadratic constraint that requires the Ipopt nonlinear solver. This is more realistic than constant-rate losses -- at low flow the loss is small, but at capacity the full loss rate applies.

## Who this is for

- Water resource planners and utility operations analysts
- Engineers modeling distribution networks with capacity and loss
- Developers learning network flow optimization with RelationalAI

## What you'll build

- A nonlinear optimization model for minimum-cost water distribution solved with Ipopt
- Source capacity constraints limiting total outflow per source
- Demand constraints with nonlinear (utilization-dependent) transmission losses
- Flow upper bounds on individual connections

## What's included

- `water_allocation.py` -- Main script defining the network model, constraints, and solver call
- `data/sources.csv` -- Water sources with capacity and cost per unit
- `data/users.csv` -- User groups with demand and priority
- `data/connections.csv` -- Network connections with max flow and loss rate
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
   curl -O https://private.relational.ai/templates/zips/v1/water_allocation.zip
   unzip water_allocation.zip
   cd water_allocation
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
   python water_allocation.py
   ```

6. Expected output:
   ```text
   Status: LOCALLY_SOLVED
   Total cost: $853.39

   Flow allocations:
     Reservoir_A  Agricultural  352.77
     Reservoir_A    Industrial  247.23
     Reservoir_A     Municipal  400.00
     Reservoir_B  Agricultural  182.06
     Reservoir_B    Industrial  177.93
     Reservoir_B     Municipal  228.99
   ```

   Groundwater is not used — the solver routes all flow through the cheaper
   reservoirs. Reservoir A supplies its full municipal capacity (400 units) while
   splitting the remainder between agricultural and industrial users. Reservoir B
   covers the remaining demand.

## Template structure
```text
.
├── README.md
├── pyproject.toml
├── water_allocation.py
└── data/
    ├── connections.csv
    ├── sources.csv
    └── users.csv
```

## How it works

### 1. Define sources, users, and connections

The model loads three concepts from CSV. Sources have capacity and cost. Users have demand and priority. Connections link sources to users with max flow and loss rate:

```python
Source = Concept("Source", identify_by={"id": Integer})
Source.capacity = Property(f"{Source} has {Float:capacity}")
Source.cost_per_unit = Property(f"{Source} has {Float:cost_per_unit}")

User = Concept("User", identify_by={"id": Integer})
User.demand = Property(f"{User} has {Float:demand}")

Connection = Concept("Connection")
Connection.source = Property(f"{Connection} from {Source}", short_name="source")
Connection.user = Property(f"{Connection} to {User}", short_name="user")
Connection.max_flow = Property(f"{Connection} has {Float:max_flow}")
Connection.loss_rate = Property(f"{Connection} has {Float:loss_rate}")
```

### 2. Define the flow variable

Each connection gets a continuous flow variable bounded between zero and its maximum flow:

```python
problem.solve_for(
    Connection.x_flow,
    name=["flow", Connection.source.name, Connection.user.name],
    lower=0,
    upper=Connection.max_flow
)
```

### 3. Add capacity and demand constraints

Source capacity limits total outflow. Demand constraints use nonlinear losses -- loss increases with utilization, so effective delivery per connection is `flow * (1 - loss_rate * flow / max_flow)`:

```python
outflow = sum(ConnectionRef.x_flow).where(ConnectionRef.source == Source).per(Source)
problem.satisfy(model.require(outflow <= Source.capacity))

effective_inflow = sum(
    ConnectionRef.x_flow * (1 - ConnectionRef.loss_rate * ConnectionRef.x_flow / ConnectionRef.max_flow)
).where(ConnectionRef.user == User).per(User)
problem.satisfy(model.require(effective_inflow >= User.demand))
```

This quadratic constraint makes the problem nonlinear, requiring the Ipopt solver.

### 4. Minimize cost

The objective minimizes total extraction cost across all active flows:

```python
total_cost = sum(Connection.x_flow * Connection.source.cost_per_unit)
problem.minimize(total_cost)
```

## Customize this template

- **Add seasonal variation** by introducing time periods with different source capacities and user demands.
- **Include priority-based allocation** using the priority field to penalize unmet demand differently for each user group.
- **Add minimum flow requirements** on certain connections to model contractual obligations.
- **Extend the network** with intermediate nodes (pumping stations, treatment plants) that add processing costs or additional capacity constraints.

## Troubleshooting

<details>
<summary><code>Status: INFEASIBLE</code></summary>

Total source capacity (after losses) is insufficient to meet all user demands. Check that the sum of source capacities minus worst-case losses covers total demand. You can increase source capacity in `sources.csv`, reduce demands in `users.csv`, or add new connections in `connections.csv`.
</details>

<details>
<summary>Some connections show zero flow</summary>

The solver avoids expensive routes when cheaper alternatives exist. If a source has a high cost per unit, its connections may carry zero flow. This is expected behavior for a cost-minimizing solution.
</details>

<details>
<summary><code>ModuleNotFoundError</code></summary>

Make sure you activated the virtual environment and ran `python -m pip install .` to install all dependencies listed in `pyproject.toml`.
</details>

<details>
<summary>Connection or authentication errors</summary>

Run `rai init` to configure your Snowflake connection. Verify that your account has the RAI Native App installed and that your user has the required permissions.
</details>
