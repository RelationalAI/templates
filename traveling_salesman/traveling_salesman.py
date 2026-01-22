# Traveling Salesman:
# Find shortest route visiting all cities exactly once (MTZ formulation)

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Model, count, data, define, require, select, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

model = Model("tsp", config=globals().get("config", None), use_lqp=False)

# --------------------------------------------------
# Load Data and Define Ontology
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Edges with distances between nodes
Edge = model.Concept("Edge")
Edge.dist = model.Property("{Edge} has {dist:float}")
data(read_csv(data_dir / "distances.csv")).into(Edge, keys=["i", "j"])

# Create nodes from edge endpoints
Node = model.Concept("Node")
define(Node.new(v=Edge.i))

# Store node count for MTZ constraints
node_count = count(Node.ref())

# --------------------------------------------------
# Define Optimization Problem
# --------------------------------------------------

# Decision variable: binary edge selection
Edge.x_edge = model.Property("{Edge} is selected if {x:float}")

# Auxiliary variable: node ordering (for subtour elimination)
Node.u_node = model.Property("{Node} has auxiliary value {u:float}")

# Objective: minimize total distance
total_dist = sum(Edge.dist * Edge.x_edge)

# Constraint: fix u=1 for node 1 (symmetry breaking)
start_node = require(Node.u_node == 1).where(Node.v(1))

# Constraint: exactly one incoming and one outgoing edge per node
node_flow = sum(Edge.x_edge).per(Node)
flow_balance = require(
    node_flow.where(Edge.j(Node.v)) == 1,
    node_flow.where(Edge.i(Node.v)) == 1
)

# Constraint: MTZ subtour elimination
Ni = Node
Nj = Node.ref()
mtz = where(
    Edge.i > 1, Edge.j > 1,
    Ni.v(Edge.i), Nj.v(Edge.j),
).require(
    Ni.u_node - Nj.u_node + node_count * Edge.x_edge <= node_count - 1
)

# --------------------------------------------------
# Set Up Solver Model
# --------------------------------------------------

s = SolverModel(model, "cont")
s.solve_for(Edge.x_edge, type="bin", name=["x", Edge.i, Edge.j])
s.solve_for(Node.u_node, type="int", name=["u", Node.v], lower=1, upper=node_count)
s.minimize(total_dist)
s.satisfy(start_node)
s.satisfy(flow_balance)
s.satisfy(mtz)

# --------------------------------------------------
# Solve and Display Results
# --------------------------------------------------

solver = Solver("highs")
s.solve(solver, time_limit_sec=60)

print(f"Status: {s.termination_status}")
print(f"Shortest tour distance: {s.objective_value:.2f}")

# Access solution via populated relations
tour = select(Edge.i, Edge.j, Edge.dist).where(Edge.x_edge > 0.5).to_df()

print("\nSelected edges (tour):")
print(tour.to_string(index=False))
