# Network Flow:
# Find maximum flow through a capacitated network

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Model, data, per, require, select, sum
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

model = Model("network_flow", config=globals().get("config", None), use_lqp=False)

# --------------------------------------------------
# Load Data and Define Ontology
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Edges with source (i), target (j), and capacity (cap)
Edge = model.Concept("Edge")
data(read_csv(data_dir / "edges.csv")).into(Edge, keys=["i", "j"])

# --------------------------------------------------
# Define Optimization Problem
# --------------------------------------------------

source_node = 1  # node ID where flow originates

# Decision variable: flow on each edge
Edge.flow = model.Property("{Edge} has {flow:float}")

# Objective: maximize total flow out of source node
total_flow = sum(Edge.flow).where(Edge.i(source_node))

# Constraint: flow between 0 and capacity
bounds = require(Edge.flow >= 0, Edge.flow <= Edge.cap)

# Constraint: flow conservation at intermediate nodes
Ei = Edge
Ej = Edge.ref()
flow_out = per(Ei.i).sum(Ei.flow)
flow_in = per(Ej.j).sum(Ej.flow)
balance = require(flow_in == flow_out).where(Ei.i == Ej.j)

# --------------------------------------------------
# Set Up Solver Model
# --------------------------------------------------

s = SolverModel(model, "cont")
s.solve_for(Edge.flow, name=["flow", Edge.i, Edge.j])
s.maximize(total_flow)
s.satisfy(bounds)
s.satisfy(balance)

# --------------------------------------------------
# Solve and Display Results
# --------------------------------------------------

solver = Solver("highs")
s.solve(solver, time_limit_sec=60)

print(f"Status: {s.termination_status}")
print(f"Maximum flow: {s.objective_value:.0f}")

# Access solution via populated relations
flows = select(Edge.i, Edge.j, Edge.flow).where(Edge.flow > 0.001).to_df()

print("\nEdge flows:")
print(flows.to_string(index=False))
