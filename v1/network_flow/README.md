---
title: "Network Flow"
description: "Find maximum flow from source to sink in a capacitated network."
featured: false
experience_level: beginner
industry: "Logistics & Transportation"
reasoning_types:
  - Prescriptive
tags:
  - Linear Programming
  - Network Optimization
  - Maximum Flow
---

# Network Flow

## What this template is for

The maximum flow problem is a fundamental network optimization problem: given a directed graph with edge capacities, find the maximum amount of flow that can be sent from a source node to a sink node without exceeding any edge's capacity. This problem appears in transportation networks, communication routing, supply chain logistics, and many other domains.

This template models the max-flow problem using prescriptive reasoning. Each edge in the network has a continuous decision variable representing the flow on that edge. Flow conservation constraints ensure that at every interior node, inflow equals outflow. Capacity constraints bound each edge's flow. The objective maximizes total flow leaving the source.

The template uses a 6-node directed graph with 9 edges, where node 1 is the source and node 6 is the sink. The network structure and capacities are loaded from a CSV file, making it straightforward to swap in your own network topology.

## Who this is for

- Operations researchers working with network optimization problems
- Logistics and transportation planners analyzing capacity bottlenecks
- Students learning max-flow formulations and LP duality
- Data scientists exploring graph-based optimization with RelationalAI

## What you'll build

- A linear programming model that finds maximum flow through a directed network
- Flow conservation constraints at every interior node
- Capacity constraints on every edge
- A solution showing active flows and the maximum achievable throughput

## What's included

- `network_flow.py` -- Main script defining the network flow model, constraints, and solution extraction
- `data/edges.csv` -- Directed edges with source node, destination node, and capacity
- `pyproject.toml` -- Python package configuration with dependencies

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools
- Python >= 3.10

## Quickstart

1. Download ZIP:
   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/network_flow.zip
   unzip network_flow.zip
   cd network_flow
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
   python network_flow.py
   ```

6. Expected output:
   ```text
   Status: OPTIMAL
   Maximum flow: 14.00

   Active flows:
    from  to  flow  capacity
       1   2   9.0       9.0
       1   3   5.0       8.0
       2   4   4.0       4.0
       2   5   4.0       4.0
       3   2   0.0       2.0
       3   5   2.0       5.0
       3   6   3.0       3.0
       4   6   4.0       5.0
       5   6   6.0       6.0
   ```

## Template structure

```text
.
├── README.md
├── pyproject.toml
├── network_flow.py
└── data/
    └── edges.csv
```

## How it works

### 1. Define concepts and load data

The model defines an `Edge` concept identified by source and destination node indices, with a capacity property:

```python
Edge = model.Concept("Edge", identify_by={"i": Integer, "j": Integer})
Edge.cap = model.Property(f"{Edge} has {Float:cap}")
edge_csv = read_csv(data_dir / "edges.csv")
model.define(Edge.new(model.data(edge_csv).to_schema()))
```

### 2. Decision variables

Each edge gets a continuous flow variable bounded between 0 and the edge's capacity:

```python
Edge.x_flow = model.Property(f"{Edge} has {Float:flow}")
s.solve_for(Edge.x_flow, name=["x", Edge.i, Edge.j], lower=0, upper=Edge.cap)
```

### 3. Flow conservation constraints

At every interior node, total inflow must equal total outflow. This is expressed using reference variables and per-node aggregation:

```python
Ei, Ej = Edge.ref(), Edge.ref()
flow_out = per(Ei.i).sum(Ei.x_flow)
flow_in = per(Ej.j).sum(Ej.x_flow)
balance = model.require(flow_in == flow_out).where(Ei.i == Ej.j)
s.satisfy(balance)
```

### 4. Objective and solution

The objective maximizes total flow leaving the source node (node 1). After solving, active flows are extracted via `model.select()`:

```python
total_flow = sum(Edge.x_flow).where(Edge.i(1))
s.maximize(total_flow)
```

## Customize this template

- **Change the network topology**: Edit `edges.csv` to add or remove edges, change capacities, or model a different graph.
- **Minimum cost flow**: Add cost-per-unit-flow on each edge and change the objective from maximizing flow to minimizing total cost while meeting a flow requirement.
- **Multi-commodity flow**: Introduce multiple commodities sharing the same network, each with its own source, sink, and demand.
- **Add node capacities**: Split each node into an in-node and out-node connected by an edge with the node's capacity.

## Troubleshooting

<details>
<summary>Maximum flow is zero</summary>

Check that there is a directed path from the source node (node 1) to the sink node in `edges.csv`. If the graph is disconnected, no flow can reach the sink.
</details>

<details>
<summary>rai init fails or connection errors</summary>

Ensure your Snowflake credentials are configured correctly and that the RAI Native App is installed on your account. Run `rai init` again and verify the connection settings.
</details>

<details>
<summary>ModuleNotFoundError for relationalai</summary>

Make sure you activated the virtual environment and ran `python -m pip install .` from the template directory. The `pyproject.toml` declares the required dependencies.
</details>

<details>
<summary>Flow conservation appears violated</summary>

The source and sink nodes are not subject to flow conservation -- only interior nodes are. This is by design: the source generates flow and the sink absorbs it. Check the constraint's `where` clause if you modified the formulation.
</details>
