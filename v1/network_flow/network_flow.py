# network flow problem:
# find maximum flow from source to sink in a capacitated network

from pathlib import Path

from pandas import read_csv

from relationalai.semantics import Float, Integer, Model, per, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("network_flow")

# --------------------------------------------------
# Define ontology & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Concept: directed edges with integer node indices and capacity
Edge = model.Concept("Edge", identify_by={"i": Integer, "j": Integer})
Edge.cap = model.Property(f"{Edge} has {Float:cap}")
edge_csv = read_csv(data_dir / "edges.csv")
model.define(Edge.new(model.data(edge_csv).to_schema()))

# --------------------------------------------------
# Model the problem
# --------------------------------------------------

s = Problem(model, Float)

# Variable: flow on each edge (continuous, bounded by capacity)
Edge.x_flow = model.Property(f"{Edge} has {Float:flow}")
s.solve_for(Edge.x_flow, name=["x", Edge.i, Edge.j], lower=0, upper=Edge.cap)

# Constraint: flow conservation at interior nodes (inflow == outflow)
Ei, Ej = Edge.ref(), Edge.ref()
flow_out = per(Ei.i).sum(Ei.x_flow)
flow_in = per(Ej.j).sum(Ej.x_flow)
balance = model.require(flow_in == flow_out).where(Ei.i == Ej.j)
s.satisfy(balance)

# Objective: maximize total flow leaving source node (node 1)
total_flow = sum(Edge.x_flow).where(Edge.i(1))
s.maximize(total_flow)

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

s.display()
s.solve("highs", time_limit_sec=60, _server_side_import=False)
s.display_solve_info()

print(f"Status: {s.termination_status}")
print(f"Maximum flow: {s.objective_value:.2f}")

# Extract solution via model.select() — properties are populated after solve
flows = model.select(
    Edge.i.alias("from"), Edge.j.alias("to"),
    Edge.x_flow.alias("flow"), Edge.cap.alias("capacity"),
).where(Edge.x_flow > 0.001).to_df()
print(f"\nActive flows:\n{flows.to_string(index=False)}")
