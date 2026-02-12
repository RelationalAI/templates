---
title: "Water Allocation"
description: "Allocate water from sources to users at minimum cost while meeting demand, subject to connection limits and transmission losses."
featured: false
experience_level: beginner
industry: "Utilities"
reasoning_types:
  - prescriptive reasoning (optimization)
tags:
  - Allocation
  - LP
  - Network Flow
---

# Water Allocation

> [!WARNING]
> This template uses the early access `relationalai.semantics` API in version `0.13.3` of the `relationalai` Python package.

## What this template is for

Water utilities (and any operator of a distribution network) must decide how to route limited supply to satisfy demand at the lowest possible cost.
This template models a small water distribution network: sources (e.g., reservoirs and groundwater) send water to users (municipal, industrial, agricultural) over a set of connections with capacity limits and transmission losses.

This template uses RelationalAI's **prescriptive reasoning (optimization)** capabilities to choose flows on each connection that meet all user demands while minimizing total sourcing cost.

## Who this is for

- You want a small, end-to-end example of **prescriptive reasoning (optimization)** with RelationalAI.
- You’re comfortable with basic Python and the idea of constraints + objectives.

## What you’ll build

- A semantic model of water `Source`, demand `User`, and `Connection` entities using concepts and typed properties.
- A linear program (LP) that chooses a non-negative flow on each source-to-user connection.
- Constraints for source capacity, per-connection max flow, and demand satisfaction after accounting for loss rates.
- A solver run (HiGHS backend) that prints a readable table of non-trivial flow allocations.

## What’s included

- **Model + solve script**: `water_allocation.py`
- **Sample data**: `data/sources.csv`, `data/users.csv`, `data/connections.csv`
- **Outputs**: Printed termination status, objective value, and a flow allocation table

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
   curl -O https://private.relational.ai/templates/zips/v0.13/water_allocation.zip
   unzip water_allocation.zip
   cd water_allocation
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
   python water_allocation.py
   ```

6. **Expected output**

   ```text
   Status: OPTIMAL
   Total cost: $874.28

   Flow allocations:
         source        user       flow
    Reservoir_A   Municipal 317.934783
    Reservoir_A  Industrial 182.065217
    Reservoir_A Agricultural 500.000000
    Reservoir_B   Municipal 316.980758
    Reservoir_B  Industrial 250.000000
    Reservoir_B Agricultural  56.818182
   ```

## Template structure

```text
.
├─ README.md
├─ pyproject.toml
├─ water_allocation.py         # main runner / entrypoint
└─ data/                       # sample input data
   ├─ sources.csv
   ├─ users.csv
   └─ connections.csv
```

**Start here**: `water_allocation.py`

## Sample data

Data files are in `data/`.

### `sources.csv`

Defines water sources, each with a capacity (maximum total outflow) and a per-unit cost.

| Column | Meaning |
| --- | --- |
| `id` | Unique source identifier |
| `name` | Source name (e.g., `Reservoir_A`) |
| `capacity` | Maximum total flow out of the source |
| `cost_per_unit` | Cost per unit of water sourced |

### `users.csv`

Defines demand points (users). The `priority` column is included in the sample data but is not used in the optimization model in this template.

| Column | Meaning |
| --- | --- |
| `id` | Unique user identifier |
| `name` | User name (e.g., `Municipal`) |
| `demand` | Required delivered volume (after losses) |
| `priority` | Integer priority (not used in the model) |

### `connections.csv`

Defines feasible source-to-user connections with a maximum allowed flow and a fractional loss rate.

| Column | Meaning |
| --- | --- |
| `source_id` | Foreign key to `sources.csv.id` |
| `user_id` | Foreign key to `users.csv.id` |
| `max_flow` | Upper bound on flow along this connection |
| `loss_rate` | Fraction of flow lost in transmission (e.g., `0.08` means 8% loss) |

## Model overview

The semantic model for this template is built around three concepts.

### `Source`

A water supply point with limited capacity and a per-unit sourcing cost.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `id` | int | Yes | Loaded as the key from `data/sources.csv` |
| `name` | string | No | Human-readable label used in output |
| `capacity` | float | No | Upper bound on total outflow |
| `cost_per_unit` | float | No | Multiplies flow in the objective |

### `User`

A demand point that must receive enough *effective* inflow (flow adjusted for losses).

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `id` | int | Yes | Loaded as the key from `data/users.csv` |
| `name` | string | No | Human-readable label used in output |
| `demand` | float | No | Required delivered volume |
| `priority` | int | No | Included in sample data; not used in this model |

### `Connection`

A feasible link from a `Source` to a `User` that can carry flow up to `max_flow` and loses a fraction `loss_rate` in transit.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `source` | `Source` | Part of compound key | Joined from `data/connections.csv.source_id` |
| `user` | `User` | Part of compound key | Joined from `data/connections.csv.user_id` |
| `max_flow` | float | No | Upper bound on the decision variable |
| `loss_rate` | float | No | Used to compute delivered inflow: `flow * (1 - loss_rate)` |
| `flow` | float | No | Continuous decision variable ($\ge 0$) |

## How it works

This section walks through the highlights in `water_allocation.py`.

### Import libraries and configure inputs

First, the script imports the Semantics APIs (`Model`, `data`, `where`, `require`, `sum`, `select`) and configures the local `DATA_DIR` it will read CSVs from:

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

Next, it declares `Source` and `User` concepts and loads `sources.csv` and `users.csv` into those concepts with `data(...).into(...)`:

```python
# Create a Semantics model container.
model = Model("water_allocation", config=globals().get("config", None), use_lqp=False)

# Source concept: water supply points with capacity and per-unit cost.
Source = model.Concept("Source")
Source.id = model.Property("{Source} has {id:int}")
Source.name = model.Property("{Source} has {name:string}")
Source.capacity = model.Property("{Source} has {capacity:float}")
Source.cost_per_unit = model.Property("{Source} has {cost_per_unit:float}")

# Load source data from CSV.
source_csv = read_csv(DATA_DIR / "sources.csv")
data(source_csv).into(Source, keys=["id"])

# User concept: demand points with required volume (and a priority field).
User = model.Concept("User")
User.id = model.Property("{User} has {id:int}")
User.name = model.Property("{User} has {name:string}")
User.demand = model.Property("{User} has {demand:float}")
User.priority = model.Property("{User} has {priority:int}")

# Load user data from CSV.
user_csv = read_csv(DATA_DIR / "users.csv")
data(user_csv).into(User, keys=["id"])
```

Then it declares a `Connection` concept and uses `where(...).define(...)` to join each `connections.csv` row to the corresponding `Source` and `User`:

```python
# Connection concept: links a Source to a User with transmission parameters.
Connection = model.Concept("Connection")
Connection.source = model.Property("{Connection} from {source:Source}")
Connection.user = model.Property("{Connection} to {user:User}")
Connection.max_flow = model.Property("{Connection} has {max_flow:float}")
Connection.loss_rate = model.Property("{Connection} has {loss_rate:float}")
Connection.flow = model.Property("{Connection} has {flow:float}")

# Load connection data from CSV.
conn_data = data(read_csv(DATA_DIR / "connections.csv"))

# Define Connection entities by joining the CSV data with Source and User.
where(
    Source.id == conn_data.source_id,
    User.id == conn_data.user_id
).define(
    Connection.new(
        source=Source,
        user=User,
        max_flow=conn_data.max_flow,
        loss_rate=conn_data.loss_rate,
    )
)
```

### Define decision variables, constraints, and objective

With the network data in place, the script creates a continuous `SolverModel` and declares `Connection.flow` as a non-negative decision variable with an upper bound from `Connection.max_flow`:

```python
Conn = Connection.ref()

# Create a continuous optimization model.
s = SolverModel(model, "cont")

# Decision variable: flow on each connection (continuous, non-negative).
s.solve_for(
    Connection.flow,
    name=["flow", Connection.source.name, Connection.user.name],
    lower=0,
    upper=Connection.max_flow,
)
```

Next, it adds two constraints with `require(...)` and `s.satisfy(...)`: source capacity (total outflow per source) and demand satisfaction (effective inflow per user, accounting for losses):

```python
# Constraint: total outflow from each source must not exceed its capacity.
outflow = sum(Conn.flow).where(Conn.source == Source).per(Source)
source_limit = require(outflow <= Source.capacity)
s.satisfy(source_limit)

# Constraint: effective inflow to each user must meet demand (accounting for losses).
effective_inflow = (
    sum(Conn.flow * (1 - Conn.loss_rate)).where(Conn.user == User).per(User)
)
meet_demand = require(effective_inflow >= User.demand)
s.satisfy(meet_demand)
```

Finally, it minimizes total sourcing cost by summing flow times the per-unit cost of the corresponding source:

```python
# Objective: minimize total cost.
total_cost = sum(Connection.flow * Connection.source.cost_per_unit)
s.minimize(total_cost)
```

### Solve and print results

The script solves with the HiGHS backend, prints status and objective value, and then uses `select(...).where(...).to_df()` to display only non-trivial flows (`> 0.001`):

```python
solver = Solver("highs")
s.solve(solver, time_limit_sec=60)

print(f"Status: {s.termination_status}")
print(f"Total cost: ${s.objective_value:.2f}")

allocations = select(
    Connection.source.name.alias("source"),
    Connection.user.name.alias("user"),
    Connection.flow,
).where(
    Connection.flow > 0.001
).to_df()

print("\nFlow allocations:")
print(allocations.to_string(index=False))
```

## Customize this template

### Use your own data

- Replace the CSVs in `data/` with your own, keeping the same column names (or update the loading logic in `water_allocation.py`).
- Make sure your `connections.csv` only references valid `source_id` and `user_id` values that exist in `sources.csv` and `users.csv`.
- Remember that `users.csv.demand` is the *delivered* requirement; because of losses, the required flow may be higher than demand.

### Tune parameters

- Adjust cost tradeoffs by changing `sources.csv.cost_per_unit`.
- Model higher leakage/evaporation by changing `connections.csv.loss_rate`.
- Tighten or relax infrastructure constraints by changing `connections.csv.max_flow` and `sources.csv.capacity`.

### Extend the model

- Add intermediate transfer nodes (source → junction → user) by introducing a node concept and splitting `Connection` into edge-to-edge connections.
- Incorporate user priorities (currently loaded but unused) by changing the objective to penalize unmet demand with priority weights, or by adding staged solves.

## Troubleshooting

<details>
<summary><code>rai init</code> fails or the script cannot authenticate</summary>

- Run <code>rai init</code> again and confirm you can see/select the right Snowflake account, role, warehouse, and the RAI Native App.
- If you use multiple profiles, set <code>RAI_PROFILE</code> to the intended profile before running the script.
- Ensure your Snowflake user has privileges to use the RAI Native App in the selected context.

</details>

<details>
<summary><code>ModuleNotFoundError</code> for <code>relationalai</code> or <code>pandas</code></summary>

- Confirm your virtual environment is active (<code>source .venv/bin/activate</code>).
- From the template folder, reinstall dependencies with <code>python -m pip install .</code>.
- Verify you’re using Python 3.10+ with <code>python --version</code>.

</details>

<details>
<summary>Missing or incorrect CSV columns (for example: <code>KeyError</code> or <code>AttributeError</code>)</summary>

- Verify the CSV headers match the expected schemas:
  - <code>sources.csv</code>: <code>id</code>, <code>name</code>, <code>capacity</code>, <code>cost_per_unit</code>
  - <code>users.csv</code>: <code>id</code>, <code>name</code>, <code>demand</code>, <code>priority</code>
  - <code>connections.csv</code>: <code>source_id</code>, <code>user_id</code>, <code>max_flow</code>, <code>loss_rate</code>
- Ensure numeric columns parse as numbers (no stray text like <code>"800 gallons"</code>).

</details>

<details>
<summary><code>Status: INFEASIBLE</code></summary>

- Check feasibility limits: for each user, the sum of <code>max_flow * (1 - loss_rate)</code> across incoming connections must be at least <code>demand</code>.
- Check that total source capacity is sufficient (and remember that losses may require total flow to exceed total delivered demand).
- If you increased <code>loss_rate</code>, you may need to increase <code>max_flow</code> or <code>capacity</code> to compensate.

</details>

<details>
<summary>Flow allocation table is empty</summary>

- The output filters out very small flows with <code>Connection.flow &gt; 0.001</code>. If your solution uses tiny flows, lower the threshold.
- If the model is infeasible, no decision variables will have meaningful values; check the printed termination status first.

</details>
