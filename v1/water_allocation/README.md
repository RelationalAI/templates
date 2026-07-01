---
title: "Water Allocation"
description: "Minimize the cost of distributing water from sources to users with nonlinear transmission losses."
featured: false
experience_level: intermediate
industry: "Energy & Utilities"
reasoning_types:
  - Prescriptive
tags:
  - Resource Allocation
  - Network Flow
  - Nonlinear Programming
  - Ipopt
---

## What this template is for

Water utilities must distribute water from multiple sources — reservoirs, groundwater — to multiple user groups such as municipal, industrial, and agricultural demand. Each source has a limited capacity and a different extraction cost, and every connection in the distribution network has a maximum flow rate and a transmission loss that reduces the amount actually delivered. Losses grow as a pipe runs closer to capacity, so a plan that ignores that effect over-promises delivery on its busiest routes.

The goal is the minimum-cost allocation that still meets every user's demand once realistic, utilization-dependent losses are accounted for.

**A prescriptive reasoner finds the least-cost allocation that meets every demand while honoring source capacities and utilization-dependent transmission losses.**

## Who this is for

- Water resource planners and utility operations analysts
- Engineers modeling distribution networks with capacity and loss
- Developers learning network flow optimization with RelationalAI

## What you'll build

- A minimum-cost water-distribution plan — a flow allocation across every source-to-user connection — solved with the Ipopt nonlinear solver.
- Source-capacity constraints limiting total outflow per source, and per-connection flow upper bounds.
- Demand constraints that model utilization-dependent transmission losses, so delivered volume reflects how hard each route is being pushed.

Built using **prescriptive reasoning** (nonlinear program over continuous flow variables, with a quadratic loss term).

## What's included

- **Model**: a single-stage nonlinear optimization on a shared ontology — `Source`, `User`, and `Connection` concepts wired to the bundled CSVs.
- **Runner**: `water_allocation.py` — a single Python script that builds the model, constraints, and objective and calls the solver against a Snowflake-connected RAI account.
- **Sample data**: a small water-distribution network of sources, user groups, and the connections between them. See *Sample data* below.
- **Outputs**: solver status, total cost, and the per-connection flow allocations.

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools
- Python >= 3.10.
- RelationalAI Python SDK (`relationalai == 1.0.14`).

## Quickstart

1. Download ZIP:
   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/water_allocation.zip
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

6. Expected output (a few lines confirm a successful run):
   ```text
   Status: LOCALLY_SOLVED
   Total cost: $853.39

   Flow allocations:
     Reservoir_A     Municipal  400.00
     Reservoir_B  Agricultural  182.06
     ...
   ```

   The full printout and a step-by-step walkthrough are in `runbook.md`.

## Template structure

```text
water_allocation/
  water_allocation.py   # Main script (network model, constraints, solver call)
  data/
    sources.csv         # Water sources with capacity and cost per unit
    users.csv           # User groups with demand and priority
    connections.csv     # Network connections with max flow and loss rate
  README.md             # this file
  runbook.md            # analyst-facing paste-testable walkthrough
  pyproject.toml        # dependencies
```

**Start here**: run `python water_allocation.py` for the full solve end to end, or follow `runbook.md` to rebuild it step by step.

## Sample data

The bundled data is a small, illustrative water-distribution network — designed to teach the nonlinear flow formulation on a Snowflake-connected RAI account, not to match a specific utility's system.

- **`sources.csv`** — water sources, each with a `capacity` and a `cost_per_unit`.
- **`users.csv`** — user groups, each with a `demand` and a `priority`.
- **`connections.csv`** — source-to-user links, each with a `max_flow` and a `loss_rate` (the fraction lost at full utilization).

## Model overview

A single shared ontology holds the network. The `Connection` concept carries the flow decision variable the solver assigns.

- **Key entities**: `Source` (reservoirs, groundwater), `User` (demand groups), `Connection` (source-to-user links).
- **Primary identifiers**: integer `id` on `Source` and `User`; `Connection` is identified by its `source` and `user` endpoints.
- **Important invariants**: `capacity`, `demand`, `max_flow`, and `cost_per_unit` are non-negative; `loss_rate` is a fraction in `[0, 1]`; each connection's flow is continuous and bounded between 0 and its `max_flow`.

### Concepts

**`Source`** — a water source with a capacity ceiling and an extraction cost.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | Integer | Yes | Loaded from `data/sources.csv` |
| `name` | String | No | e.g. `Reservoir_A` |
| `capacity` | Float | No | Maximum total outflow |
| `cost_per_unit` | Float | No | Extraction cost per unit of flow |

**`User`** — a demand group that must be served.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | Integer | Yes | Loaded from `data/users.csv` |
| `name` | String | No | e.g. `Municipal` |
| `demand` | Float | No | Required delivered volume |
| `priority` | Integer | No | Group priority (available for priority-based extensions) |

**`Connection`** — a link from a source to a user; the flow decision lives here.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `source` | Relationship | Yes | Endpoint on `Source` |
| `user` | Relationship | Yes | Endpoint on `User` |
| `max_flow` | Float | No | Upper bound on this connection's flow |
| `loss_rate` | Float | No | Fraction lost at full utilization |
| `x_flow` | Float | No | Flow allocated by the solver (decision variable) |

## How it works

This is a network-flow problem with source-capacity limits, per-connection flow bounds, and demand constraints whose nonlinear loss term makes it quadratic, solved with the Ipopt nonlinear solver.

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

Source capacity limits total outflow. Demand constraints use nonlinear losses that increase with utilization, so effective delivery per connection falls as a route approaches its `max_flow`, as encoded below:

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

Focus on the first changes most users will make.

### Use your own data

- Replace the CSVs in `data/` with your own; keep the column names shown in *Sample data* above (`sources.csv`, `users.csv`, `connections.csv`).
- For Snowflake-backed runs, swap the `read_csv(...)` calls for `model.data(snowflake_table)` calls.
- Confirm `source_id` and `user_id` in `connections.csv` match the `id` columns in `sources.csv` and `users.csv` — a mismatched key silently drops the connection.

### Tune parameters

- **Source capacity and cost** — edit `capacity` and `cost_per_unit` in `sources.csv` to change which sources the solver prefers.
- **Loss rate** — `loss_rate` in `connections.csv` controls how steeply delivery falls as a route approaches capacity.

### Extend the model

- **Add seasonal variation** by introducing time periods with different source capacities and user demands.
- **Include priority-based allocation** using the `priority` field to penalize unmet demand differently for each user group.
- **Add minimum flow requirements** on certain connections to model contractual obligations.
- **Extend the network** with intermediate nodes (pumping stations, treatment plants) that add processing costs or additional capacity constraints.

### Scale up / productionize

- Replace the `data/` CSV bundle with CDC ingestion from your upstream source and demand systems.
- The bundled network is small; the formulation scales to whatever the Ipopt solver can handle in your solve budget. Pin dependencies via `pyproject.toml` for reproducible runs.

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

## Learn more

### Core concepts

- [PyRel v1 query language](https://docs.relational.ai/) — `model.where(...)` / `model.select(...)` / `sum`.
- [Ontology modeling](https://docs.relational.ai/) — concepts, properties, and relationships that back this network model.

### Reasoner reference

- [Prescriptive reasoner](https://docs.relational.ai/) — `Problem` API, decision variables, constraints, objective.
- [Nonlinear solving with Ipopt](https://docs.relational.ai/) — when a quadratic or nonlinear constraint requires the nonlinear solver.

## Support

- File issues at the RelationalAI templates repository.
