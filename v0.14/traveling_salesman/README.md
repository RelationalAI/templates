---
title: "Traveling Salesman"
description: "Find the shortest route visiting all cities exactly once and returning to the start."
featured: false
experience_level: intermediate
industry: "Supply Chain"
reasoning_types:
  - Prescriptive
tags:
  - Routing
  - MILP
---

# Traveling Salesman

> [!WARNING]
> This template uses the early access `relationalai.semantics` API in version `0.13.3` of the `relationalai` Python package.

## What this template is for

The traveling salesman problem (TSP) asks for the shortest closed route that visits every location exactly once.
It shows up in real-world settings like routing a delivery vehicle, ordering inspection stops, or sequencing tool paths.

The challenge is combinatorial: as the number of locations grows, the number of possible tours explodes, so “try all routes” quickly becomes impractical.
This template uses RelationalAI's **prescriptive reasoning (optimization)** capabilities to model the TSP as a mixed-integer linear program (MILP) and solve for the shortest tour.

## Who this is for

- You want an end-to-end example of **prescriptive reasoning (optimization)** with RelationalAI.
- You’re comfortable with basic Python and the idea of constraints + an objective.
- You want to see a standard TSP MILP formulation (MTZ subtour elimination).

## What you’ll build

- A small semantic model of nodes and directed edges loaded from CSV.
- A MILP with a binary decision variable for selecting edges in the tour.
- Subtour elimination constraints using the Miller–Tucker–Zemlin (MTZ) ordering formulation.
- A solver run using the **HiGHS** backend that prints the selected tour edges.

## What’s included

- **Model + solve script**: `traveling_salesman.py`
- **Sample data**: `data/distances.csv`
- **Dependencies**: `pyproject.toml`

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
   curl -O https://private.relational.ai/templates/zips/v0.13/traveling_salesman.zip
   unzip traveling_salesman.zip
   cd traveling_salesman
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
   python traveling_salesman.py
   ```

6. **Expected output**

   The exact tour may differ based on the data, but you should see a feasible solver status, the tour distance (objective), and a table of selected edges:

   ```text
   Status: OPTIMAL
   Shortest tour distance: 8.50

   Selected edges (tour):
    i  j  dist
    1  3   2.5
    2  1   2.0
    3  4   2.5
    4  2   1.5
   ```

## Template structure

```text
.
├─ README.md
├─ pyproject.toml
├─ traveling_salesman.py      # main runner / entrypoint
└─ data/
   └─ distances.csv           # directed edge distances
```

**Start here**: `traveling_salesman.py`

## Sample data

Data files are in `data/`.

### `distances.csv`

Defines the directed distance (travel cost) for each edge $(i \to j)$.
For an undirected instance, you typically include both directions as separate rows.

| Column | Meaning |
| --- | --- |
| `i` | Origin node identifier (integer) |
| `j` | Destination node identifier (integer) |
| `dist` | Distance/cost for traveling from `i` to `j` (float) |

## Model overview

The optimization model is built around two concepts.

### `Edge`

A directed edge $(i \to j)$ with a distance and a binary decision variable indicating whether the edge is selected in the tour.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `i` | int | Part of compound key | Loaded as the key from `data/distances.csv.i` |
| `j` | int | Part of compound key | Loaded as the key from `data/distances.csv.j` |
| `dist` | float | No | Loaded from `data/distances.csv.dist` |
| `x_edge` | float | No | Binary decision variable (0/1) indicating if edge $(i \to j)$ is used |

### `Node`

A node (city/location) derived from the edge endpoints, with an integer “order” variable used by MTZ subtour elimination.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `v` | int | Yes | Derived from `Edge.i` to create the node set |
| `u_node` | float | No | Integer decision variable used to prevent subtours |

## How it works

This section walks through the highlights in `traveling_salesman.py`.

### Import libraries and configure inputs

First, the script imports the Semantics APIs (`Model`, `data`, `define`, `require`, `sum`, `where`) and sets up `DATA_DIR` for local CSV loading:

```python
from pathlib import Path

import pandas
from pandas import read_csv

from relationalai.semantics import (
    Model,
    count,
    data,
    define,
    require,
    select,
    sum,
    where,
)
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

Next, it defines an `Edge` concept keyed by `(i, j)`, loads `distances.csv` via `data(...).into(...)`, and derives the `Node` set from edge start nodes:

```python
# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

# Create a Semantics model container.
model = Model("tsp", config=globals().get("config", None), use_lqp=False)

# Edge concept: directed edge (i -> j) with an associated distance.
Edge = model.Concept("Edge")
Edge.dist = model.Property("{Edge} has {dist:float}")

# Load edge distance data from CSV.
distances_csv = read_csv(DATA_DIR / "distances.csv")
data(distances_csv).into(Edge, keys=["i", "j"])

# Node concept: node identifiers derived from edge start nodes.
Node = model.Concept("Node")
define(Node.new(v=Edge.i))
```

### Define decision variables

With the base entities in place, the template creates a `SolverModel` and registers two decision variables: `Edge.x_edge` to choose edges in the tour, and `Node.x_u_node` as an MTZ ordering variable:

```python
# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

# Pre-compute the number of nodes (used by the MTZ formulation).

node_count = count(Node.ref())

Node_i = Node
Node_j = Node.ref()

s = SolverModel(model, "cont")

# Edge.x_edge decision variable: 1 if the edge is selected, 0 otherwise.
Edge.x_edge = model.Property("{Edge} is selected if {x:float}")
s.solve_for(Edge.x_edge, type="bin", name=["x", Edge.i, Edge.j])

# Node.x_u_node decision variable: ordering variable used for MTZ subtour elimination.
Node.x_u_node = model.Property("{Node} has auxiliary value {u:float}")
s.solve_for(Node.x_u_node, type="int", name=["u", Node.v], lower=1, upper=node_count)
```

### Add constraints (degree constraints + MTZ subtour elimination)

Then it adds the standard TSP constraints: (1) symmetry breaking by fixing the start node’s order, (2) one incoming and one outgoing selected edge per node, and (3) MTZ subtour elimination to prevent disconnected cycles:

```python
# Constraint: fix u=1 for node 1 (symmetry breaking).
start_node = require(Node.x_u_node == 1).where(Node.v == 1)
s.satisfy(start_node)

# Constraint: exactly one incoming and one outgoing edge per node.
incoming_flow = sum(Edge.x_edge).where(Edge.j == Node.v).per(Node)
outgoing_flow = sum(Edge.x_edge).where(Edge.i == Node.v).per(Node)
flow_balance = require(incoming_flow == 1, outgoing_flow == 1)
s.satisfy(flow_balance)

# Constraint: MTZ subtour elimination.
mtz = where(
    Edge.i > 1,
    Edge.j > 1,
  Node_i.v == Edge.i,
  Node_j.v == Edge.j
).require(
  Node_i.u_node - Node_j.u_node + node_count * Edge.x_edge <= node_count - 1
)
s.satisfy(mtz)
```

### Minimize total distance and print the selected tour

Finally, it minimizes total distance, solves with HiGHS, and filters the selected edges with `Edge.x_edge > 0.5` for printing:

```python
# Objective: minimize total distance.
total_dist = sum(Edge.dist * Edge.x_edge)
s.minimize(total_dist)

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

solver = Solver("highs")
s.solve(solver, time_limit_sec=60)

print(f"Status: {s.termination_status}")
print(f"Shortest tour distance: {s.objective_value:.2f}")

tour = select(Edge.i, Edge.j, Edge.dist).where(Edge.x_edge > 0.5).to_df()

print("\nSelected edges (tour):")
print(tour.to_string(index=False))
```

## Customize this template

### Use your own data

- Replace `data/distances.csv` with your own edge list.
- Ensure the file includes columns `i`, `j`, and `dist`.
- For an undirected graph, include both directions (both $(i, j)$ and $(j, i)$).
- Make sure every node appears at least once in the `i` column. (In this template, nodes are derived from `Edge.i`.)

### Tune parameters

- Increase the solver time limit by changing `time_limit_sec=60` in `traveling_salesman.py`.
- Change the symmetry-breaking start node by editing the constraint `where(Node.v == 1)`.

### Extend the model

- Add rules to forbid certain edges (road closures) by requiring `Edge.x_edge == 0` for those pairs.
- Add additional objective terms (e.g., time, tolls) by extending the `dist` field or adding new edge attributes.

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

- Confirm your virtual environment is active (`source .venv/bin/activate`).
- Reinstall dependencies from this folder: `python -m pip install .`.
- Verify you’re using Python >= 3.10.

</details>

<details>
<summary>Why does reading <code>data/distances.csv</code> fail?</summary>

- Confirm the file exists at `data/distances.csv`.
- Verify the CSV has headers `i`, `j`, `dist`.
- Ensure `i` and `j` are integers and `dist` is numeric.

</details>

<details>
<summary>Why do I get <code>Status: INFEASIBLE</code> or no tour?</summary>

- Check that each node has at least one outgoing edge and at least one incoming edge in `distances.csv`.
- For undirected instances, ensure you included both directions for each pair.
- Start by testing a small, fully connected instance to validate the pipeline.

</details>

<details>
<summary>Why is the selected edge table empty?</summary>

- The script prints edges with `Edge.x_edge > 0.5`. If the solve did not reach a feasible solution, the filter may remove everything.
- Check the printed status and consider increasing `time_limit_sec`.

</details>
