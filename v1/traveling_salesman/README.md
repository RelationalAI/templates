---
title: "Traveling Salesman"
description: "Find the shortest route visiting all cities exactly once using the MTZ formulation."
featured: false
experience_level: intermediate
industry: "Logistics"
reasoning_types:
  - Prescriptive
tags:
  - routing
  - mixed-integer-programming
  - combinatorial-optimization
  - graph
---

# Traveling Salesman

## What this template is for

The traveling salesman problem (TSP) is one of the most studied problems in combinatorial optimization: given a set of cities and the distances between them, find the shortest tour that visits every city exactly once and returns to the starting city. TSP has practical applications in route planning, circuit board drilling, delivery logistics, and many other domains.

This template solves a small TSP instance using the Miller-Tucker-Zemlin (MTZ) formulation, which eliminates subtours through auxiliary ordering variables rather than exponentially many subtour-elimination constraints. The model uses binary decision variables for edge selection and integer auxiliary variables for node ordering, solved as a mixed-integer program with HiGHS.

The MTZ formulation is compact and well-suited for small to medium instances. For larger problems, more sophisticated formulations (cutting planes, branch-and-cut) would be needed, but this template provides a clear, self-contained starting point for understanding TSP modeling with RelationalAI.

## Who this is for

- Operations researchers learning TSP formulations
- Logistics planners building route optimization prototypes
- Students studying combinatorial optimization
- Developers exploring mixed-integer programming with RelationalAI

## What you'll build

- An MTZ-based TSP formulation with binary edge variables and integer ordering variables
- Degree constraints ensuring exactly one in-edge and one out-edge per node
- Subtour elimination via MTZ auxiliary variables
- Optimal tour extraction from solver results

## What's included

- `traveling_salesman.py` -- main script with ontology, MTZ formulation, and solver call
- `data/edges.csv` -- 12 directed edges between 4 nodes with distances
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
   curl -L -O https://docs.relational.ai/templates/zips/v1/traveling_salesman.zip
   unzip traveling_salesman.zip
   cd traveling_salesman
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
   python traveling_salesman.py
   ```

6. Expected output:
   ```text
   Status: OPTIMAL
   Tour distance: 8.50

   Tour edges:
    from  to
       1   2
       2   4
       4   3
       3   1
   ```

## Template structure
```text
.
├── README.md
├── pyproject.toml
├── traveling_salesman.py
└── data/
    └── edges.csv
```

## How it works

**1. Load the edge data and derive nodes.** Edges with distances are loaded from CSV. Nodes are derived from edge endpoints:

```python
Edge = model.Concept("Edge", identify_by={"i": Integer, "j": Integer})
Edge.dist = model.Property(f"{Edge} has {Float:dist}")

Node = model.Concept("Node", identify_by={"v": Integer})
model.define(Node.new(v=Edge.i))
```

**2. Define decision variables.** Binary variables `x[i,j]` select edges in the tour. Integer auxiliary variables `u[v]` enforce node ordering for subtour elimination:

```python
Edge.x = model.Property(f"{Edge} is selected if {Float:x}")
s.solve_for(Edge.x, type="bin", name=["x", Edge.i, Edge.j])

Node.u = model.Property(f"{Node} has auxiliary value {Float:u}")
s.solve_for(Node.u, name=["u", Node.v], type="int", lower=1, upper=node_count)
```

**3. Add degree constraints.** Every node must have exactly one incoming and one outgoing edge:

```python
node_flow = sum(Edge.x).per(Node)
s.satisfy(model.require(
    node_flow.where(Edge.j == Node.v) == 1,
    node_flow.where(Edge.i == Node.v) == 1
))
```

**4. Add MTZ subtour elimination.** If edge (i,j) is in the tour, then the ordering of j must be at least one more than i. This prevents disconnected subtours:

```python
s.satisfy(model.where(
    Ni := Node, Nj := Node.ref(),
    Edge.i > 1, Edge.j > 1,
    Ni.v(Edge.i), Nj.v(Edge.j),
).require(
    Ni.u - Nj.u + node_count * Edge.x <= node_count - 1
))
```

**5. Minimize total tour distance:**

```python
total_dist = sum(Edge.dist * Edge.x)
s.minimize(total_dist)
```

## Customize this template

- **Use your own distance data** by replacing `edges.csv` with your city-to-city distance matrix (as a list of directed edges).
- **Scale to more cities** by adding nodes and edges. The MTZ formulation works well for up to ~50 nodes.
- **Add asymmetric costs** -- the formulation already supports directed edges with different forward/reverse distances.
- **Add time windows** by introducing arrival time variables and constraints per node.
- **Visualize the tour** by plotting nodes and selected edges with matplotlib.

## Troubleshooting

<details>
  <summary>Solver returns INFEASIBLE</summary>

- Ensure `edges.csv` contains edges in both directions for every pair of nodes (the graph must be strongly connected).
- Verify that node indices are consistent: every node referenced in an edge must appear as both a source and a destination.

</details>

<details>
  <summary>Import error for <code>relationalai</code></summary>

- Confirm your virtual environment is active: `which python` should point to `.venv`.
- Reinstall dependencies: `python -m pip install .`.

</details>

<details>
  <summary>Authentication or configuration errors</summary>

- Run `rai init` to create or update your RelationalAI/Snowflake configuration.
- If you have multiple profiles, set `export RAI_PROFILE=<your_profile>`.

</details>

<details>
  <summary>Slow solve times for larger instances</summary>

- The MTZ formulation has O(n^2) subtour elimination constraints, which can be slow for large n.
- Consider reducing the `time_limit_sec` parameter and accepting near-optimal solutions.
- For production-scale TSP (100+ cities), consider specialized TSP solvers or cutting-plane approaches.

</details>
