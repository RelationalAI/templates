---
title: "Network Flow"
description: "Maximize flow through a capacitated network from a source node."
featured: false
experience_level: beginner
industry: "Supply Chain"
reasoning_types:
  - Prescriptive
tags:
  - Allocation
  - LP
  - Network Flow
---

# Network Flow

> [!WARNING]
> This template uses the early access `relational.semantics` API in version `0.14.2` of the `relationalai` Python package.

## What this template is for

Maximum flow is a classic optimization problem: given a directed network with capacities, find how much material (or traffic, bandwidth, product, etc.) you can push through the network.
This template builds a simple max-flow linear program using **prescriptive reasoning (optimization)** that chooses a non-negative flow on each edge, respects edge capacities, and enforces flow conservation.

Prescriptive reasoning helps you:

- **Estimate throughput** of a constrained network.
- **Identify bottlenecks** by inspecting which edges saturate.
- **Compare designs** by editing capacities and re-solving.

## Who this is for

- You want a small, end-to-end example of **prescriptive reasoning (optimization)** with RelationalAI.
- You’re comfortable with basic Python and linear optimization concepts.

## What you’ll build

- A semantic model with an `Edge` concept loaded from CSV.
- A continuous decision variable `Edge.x_flow` on each edge.
- Capacity and conservation constraints defined with `require(...)`.
- A max-flow objective solved with the **HiGHS** backend.

## What’s included

- **Model + solve script**: `network_flow.py`
- **Sample data**: `data/edges.csv`

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
curl -O https://private.relational.ai/templates/zips/v0.14/network_flow.zip
unzip network_flow.zip
cd network_flow
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

  ```bash
  python -m pip install .
  ```

4. **Configure Snowflake connection and RAI profile**

  ```bash
  rai init
  ```

5. **Run the template**

  ```bash
  python network_flow.py
  ```

6. **Expected output**

  ```text
  Status: OPTIMAL
  Maximum flow: 13

  Edge flows:
   i  j  flow
   1  2   8.0
   1  3   5.0
   2  4   4.0
   2  5   4.0
   3  5   2.0
   3  6   3.0
   4  6   4.0
   5  6   6.0
  ```

> [!NOTE]
> Alternative optimal solutions may route flow along different edges with the same maximum flow value.

## Template structure

```text
.
├─ README.md
├─ pyproject.toml
├─ network_flow.py     # main runner / entrypoint
└─ data/               # sample input data
  └─ edges.csv
```

**Start here**: `network_flow.py`

## Sample data

Data files are in `data/`.

### `edges.csv`

Each row represents a directed edge from node `i` to node `j` with capacity `cap`.

| Column | Meaning |
| --- | --- |
| `i` | Source node ID |
| `j` | Target node ID |
| `cap` | Maximum flow capacity |

> [!NOTE]
> The template’s objective uses `SOURCE_NODE = 1` (node 1 is treated as the source).

## Model overview

The model defines one concept (`Edge`) and one decision variable (`Edge.x_flow`).

### `Edge`

Represents a directed, capacitated edge.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `i` | int | Yes | Loaded from `data/edges.csv` |
| `j` | int | Yes | Loaded from `data/edges.csv` |
| `cap` | float | No | Capacity for the edge |
| `x_flow` | float | No | Decision variable (continuous) |

## How it works

This section walks through the highlights in `network_flow.py`.

### Import libraries and configure inputs

First, the script imports the Semantics and optimization APIs, configures the data directory, and sets a constant source node:

```python
from pathlib import Path

import pandas
from pandas import read_csv

from relationalai.semantics import Model, data, per, require, select, sum
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"

# Disable pandas inference of string types. This ensures that string columns
# in the CSVs are loaded as object dtype. This is only required when using
# relationalai versions prior to v1.0.
pandas.options.future.infer_string = False

# Source node for the max-flow objective.
SOURCE_NODE = 1
```

### Define concepts and load CSV data

Next, it creates a `Model`, defines the `Edge` concept, and loads `data/edges.csv` into that concept using `data(...).into(...)`:

```python
# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

# Create a Semantics model container.
model = Model("network_flow", config=globals().get("config", None))

# Edge concept: directed edges with endpoints (i, j) and capacity (cap).
Edge = model.Concept("Edge")

# Load edge data from CSV.
edges_csv = read_csv(DATA_DIR / "edges.csv")
data(edges_csv).into(Edge, keys=["i", "j"])
```

### Define decision variables, constraints, and objective

Then it creates a `SolverModel`, declares `Edge.x_flow` and marks it as a decision variable with `solve_for(...)`, and models the bounds and conservation constraints with `require(...)`:

```python
# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

EdgeSrc = Edge
EdgeRef = Edge.ref()

# Create a continuous optimization model.
s = SolverModel(model, "cont")

# Edge.x_flow decision variable: flow on each edge.
Edge.x_flow = model.Property("{Edge} has {flow:float}")
s.solve_for(Edge.x_flow, name=["flow", Edge.i, Edge.j])

# Constraint: flow must be non-negative and cannot exceed edge capacity.
bounds = require(
    Edge.x_flow >= 0,
    Edge.x_flow <= Edge.cap
)
s.satisfy(bounds)

# Constraint: flow conservation at each node (inflow equals outflow).
flow_out = per(EdgeSrc.i).sum(EdgeSrc.x_flow)
flow_in = per(EdgeRef.j).sum(EdgeRef.x_flow)
balance = require(flow_in == flow_out).where(
    EdgeSrc.i == EdgeRef.j
)
s.satisfy(balance)

# Objective: maximize total flow out of the source node.
total_flow = sum(Edge.x_flow).where(
    Edge.i == SOURCE_NODE
)
s.maximize(total_flow)
```

### Solve and print results

Finally, it solves with `Solver("highs")` and prints the termination status, objective value, and a filtered flow table (only edges with `Edge.x_flow > 0.001`):

```python
# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

solver = Solver("highs")
s.solve(solver, time_limit_sec=60)

print(f"Status: {s.termination_status}")
print(f"Maximum flow: {s.objective_value:.0f}")

flows = select(Edge.i, Edge.j, Edge.x_flow).where(Edge.x_flow > 0.001).to_df()

print("\nEdge flows:")
print(flows.to_string(index=False))
```

## Troubleshooting

<details>
  <summary>I get <code>ModuleNotFoundError</code> when running the script</summary>

  - Confirm you created and activated the virtual environment from the Quickstart.
  - Reinstall dependencies with `python -m pip install .`.
  - Verify you are running `python network_flow.py` from the `network_flow/` folder.
</details>

<details>
  <summary>The script fails while reading <code>data/edges.csv</code></summary>

  - Confirm the file exists at `data/edges.csv`.
  - Verify the CSV includes headers `i`, `j`, and `cap`.
  - Check that `cap` values are numeric and non-negative.
</details>

<details>
  <summary>My <code>Edge flows</code> table is empty</summary>

  - The output is filtered to `Edge.x_flow > 0.001`; small flows will not display.
  - If the maximum flow is 0, check that there are edges leaving `SOURCE_NODE = 1` and that their capacities are positive.
</details>

<details>
  <summary>I see an unexpected termination status (not <code>OPTIMAL</code>)</summary>

  - Try re-running; if you hit a time limit, consider increasing `time_limit_sec`.
  - Sanity-check the data for missing values (especially capacities).
  - If you modified the model, revert to the sample data to confirm the baseline still solves.
</details>
