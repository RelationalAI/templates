"""Network Flow (prescriptive optimization) template.

This script demonstrates a classic maximum-flow linear optimization model in RelationalAI:

- Load a capacitated directed network from CSV.
- Choose a non-negative flow on each edge.
- Enforce capacity bounds and flow conservation.
- Maximize total flow out of the source node.

Run:
    `python network_flow.py`

Output:
    Prints the solver termination status, maximum flow value, and a table of
    edges with non-trivial flow.
"""

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
