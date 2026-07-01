---
title: "Traveling Salesman"
description: "Find the shortest route that visits every city exactly once and returns home. Solves the traveling salesman problem with the Miller-Tucker-Zemlin subtour-elimination formulation as a mixed-integer program."
featured: false
experience_level: intermediate
industry: "Supply Chain & Logistics"
reasoning_types:
  - Prescriptive
tags:
  - Routing
  - Mixed-Integer Programming (MIP)
  - Combinatorial Optimization
  - Miller-Tucker-Zemlin (MTZ)
---

## What this template is for

A delivery driver, a service technician, or a drilling head has a list of stops and needs the cheapest way to visit them all and come back. The traveling salesman problem (TSP) captures exactly this: given a set of locations and the distances between them, find the shortest tour that visits every location once and returns to the start. It is one of the most studied problems in optimization and shows up across route planning, delivery logistics, circuit-board drilling, and scheduling.

This template solves a small TSP instance end to end and gives you a clear, self-contained starting point for building route optimization on RelationalAI.

**Reasoning approach:** the tour is found with prescriptive reasoning — a mixed-integer program (MIP) whose binary variables choose which edges are on the route and whose Miller-Tucker-Zemlin (MTZ) auxiliary variables rule out disconnected subtours.

## Who this is for

- Operations researchers learning TSP formulations
- Logistics planners building route optimization prototypes
- Students studying combinatorial optimization
- Developers exploring mixed-integer programming with RelationalAI

## What you'll build

- An optimal tour visiting every node exactly once, returned as the set of selected edges with a total distance.
- A prescriptive MIP formulation with binary edge decisions and integer ordering variables, expressed directly on the ontology.
- Degree constraints guaranteeing exactly one in-edge and one out-edge per node.
- Miller-Tucker-Zemlin subtour elimination that keeps the solution a single connected cycle.

Built using **prescriptive reasoning** (mixed-integer programming with the HiGHS solver).

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
- RelationalAI Python SDK (`relationalai == 1.0.14`)

## Quickstart

1. Download ZIP:
   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/traveling_salesman.zip
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
traveling_salesman/
├── README.md            # this file
├── pyproject.toml       # dependencies
├── traveling_salesman.py # main script (ontology, MTZ formulation, solve)
└── data/
    └── edges.csv        # 12 directed edges between 4 nodes, with distances
```

**Start here:** `traveling_salesman.py` runs the whole template end to end.

## Sample data

`data/edges.csv` is a directed distance matrix with the columns `i`, `j`, and `dist`: a distance `dist` for traveling from node `i` to node `j`. The bundled instance has 12 directed edges connecting 4 nodes, with an edge in both directions between every pair, so the graph is strongly connected and a tour always exists. Nodes are not listed in their own file; the model derives them from the edge endpoints.

## Model overview

The model has two concepts: the `Edge` rows loaded from CSV, and the `Node` set derived from edge endpoints. The optimizer adds one decision per edge and one ordering value per node.

- **Key entities**: `Edge` (a directed leg with a distance), `Node` (a location to visit).
- **Primary identifiers**: an `Edge` is identified by its endpoint pair `(i, j)`; a `Node` is identified by its index `v`.
- **Important invariants**: distances are non-negative; every node needs exactly one in-edge and one out-edge; the selected edges must form a single cycle (no subtours).

### Edge

A directed leg from one node to another with an associated distance. Loaded from `data/edges.csv`; the `x` property is filled in by the solver.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `i` | Integer | Yes | Source node index |
| `j` | Integer | Yes | Destination node index |
| `dist` | Float | No | Distance from `i` to `j` |
| `x` | Float | No | Binary decision (0/1): 1 if the edge is on the tour |

### Node

A location to visit, derived from the `i` endpoints of the edges. The `u` property is the MTZ ordering value the solver assigns for subtour elimination.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `v` | Integer | Yes | Node index, derived from `Edge.i` |
| `u` | Float | No | Integer MTZ ordering value in `[1, node_count]`, assigned by the solver |

### Relationships

The model defines one standalone relationship beyond the concept properties.

| Relationship | Reads as | Notes |
|---|---|---|
| `node count is <n>` | the number of nodes in the instance | Stored so the solver can reference it in the ordering-variable bounds |

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
problem.solve_for(Edge.x, type="bin", name=["x", Edge.i, Edge.j])

Node.u = model.Property(f"{Node} has auxiliary value {Float:u}")
problem.solve_for(Node.u, name=["u", Node.v], type="int", lower=1, upper=node_count)
```

**3. Add degree constraints.** Every node must have exactly one incoming and one outgoing edge:

```python
node_flow = sum(Edge.x).per(Node)
problem.satisfy(model.require(
    node_flow.where(Edge.j == Node.v) == 1,
    node_flow.where(Edge.i == Node.v) == 1
))
```

**4. Add MTZ subtour elimination.** If edge (i,j) is in the tour, then the ordering of j must be at least one more than i. This prevents disconnected subtours:

```python
problem.satisfy(model.where(
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
problem.minimize(total_dist)
```

## Customize this template

### Use your own data

- Replace `data/edges.csv` with your own city-to-city distance matrix, as a list of directed edges with the columns `i`, `j`, and `dist`, or change the `read_csv(...)` path in the script.
- Provide an edge in both directions for every pair of nodes so the graph stays strongly connected. Asymmetric costs are supported: give the forward and reverse edges different `dist` values.

### Tune parameters

- The solve time cap is `time_limit_sec` (default 60) in the `problem.solve("highs", ...)` call. Lower it to accept a near-optimal tour sooner on larger instances.

### Extend the model

- Add time windows by introducing per-node arrival-time variables and constraints.
- Visualize the result by plotting the nodes and the selected edges with a plotting library such as matplotlib.

### Scale up / productionize

- The MTZ formulation is compact and works well for small to medium instances (up to roughly 50 nodes). Its subtour-elimination constraints grow with the square of the node count, so solves slow down as instances grow.
- For production-scale routing (100+ stops), move to specialized TSP solvers or cutting-plane / branch-and-cut formulations.

## Learn more

### Core concepts

- [Prescriptive reasoning](https://docs.relational.ai/) — the `Problem` API, decision variables, constraints, and objectives used here.
- [PyRel v1 modeling](https://docs.relational.ai/) — concepts, properties, and deriving one concept from another (nodes from edges).

### Language / modeling reference

- [Constraints and objectives](https://docs.relational.ai/) — `satisfy()`, `require()`, `minimize()`, and per-group aggregation with `.per(...)`.

### CLI / SDK guides

- [RelationalAI Python SDK](https://docs.relational.ai/) — installing and configuring the `relationalai` package and connecting to Snowflake.

## Support

- File issues at the RelationalAI templates repository.

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
