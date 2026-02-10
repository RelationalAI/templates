# traveling salesman problem:
# find shortest route visiting all cities exactly once (MTZ formulation)

from pathlib import Path

import pandas; pandas.options.future.infer_string = False
from pandas import read_csv

from relationalai.semantics import Model, count, data, define, require, select, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

model = Model("tsp", config=globals().get("config", None), use_lqp=False)

# --------------------------------------------------
# Define ontology & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Concept: edges with distances between nodes
Edge = model.Concept("Edge")
Edge.dist = model.Property("{Edge} has {dist:float}")
data(read_csv(data_dir / "distances.csv")).into(Edge, keys=["i", "j"])

# Rule: nodes derived from edge endpoints
Node = model.Concept("Node")
define(Node.new(v=Edge.i))

# --------------------------------------------------
# Model the problem
# --------------------------------------------------

node_count = count(Node.ref())

Ni = Node
Nj = Node.ref()

s = SolverModel(model, "cont")

# Variable: binary edge selection
Edge.x_edge = model.Property("{Edge} is selected if {x:float}")
s.solve_for(Edge.x_edge, type="bin", name=["x", Edge.i, Edge.j])

# Variable: node ordering (for subtour elimination)
Node.u_node = model.Property("{Node} has auxiliary value {u:float}")
s.solve_for(Node.u_node, type="int", name=["u", Node.v], lower=1, upper=node_count)

# Constraint: fix u=1 for node 1 (symmetry breaking)
start_node = require(Node.u_node == 1).where(Node.v(1))
s.satisfy(start_node)

# Constraint: exactly one incoming and one outgoing edge per node
node_flow = sum(Edge.x_edge).per(Node)
flow_balance = require(
    node_flow.where(Edge.j(Node.v)) == 1,
    node_flow.where(Edge.i(Node.v)) == 1
)
s.satisfy(flow_balance)

# Constraint: MTZ subtour elimination
mtz = where(
    Edge.i > 1, Edge.j > 1,
    Ni.v(Edge.i), Nj.v(Edge.j),
).require(
    Ni.u_node - Nj.u_node + node_count * Edge.x_edge <= node_count - 1
)
s.satisfy(mtz)

# Objective: minimize total distance
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
