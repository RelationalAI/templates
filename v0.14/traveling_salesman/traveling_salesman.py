"""Traveling salesman (prescriptive optimization) template.

- Load a directed distance matrix from CSV.
- Model the traveling salesman problem (TSP) as a MILP using the MTZ subtour
  elimination formulation.
- Solve for the shortest Hamiltonian cycle and print the selected edges.

Run:
    `python traveling_salesman.py`

Output:
    Prints the solver termination status, objective value (shortest tour
    distance), and a table of selected edges.
"""

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

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

# Create a Semantics model container.
model = Model("tsp", config=globals().get("config", None))

# Edge concept: directed edge (i -> j) with an associated distance.
Edge = model.Concept("Edge")
Edge.dist = model.Property("{Edge} has {dist:float}")

# Load edge distance data from CSV.
distances_csv = read_csv(DATA_DIR / "distances.csv")
data(distances_csv).into(Edge, keys=["i", "j"])

# Node concept: node identifiers derived from edge start nodes.
Node = model.Concept("Node")
define(Node.new(v=Edge.i))

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

# Pre-compute the number of nodes (used by the MTZ formulation).
node_count = count(Node.ref())

NodeFrom = Node
NodeTo = Node.ref()

s = SolverModel(model, "cont")

# Edge.x_edge decision variable: 1 if the edge is selected, 0 otherwise.
Edge.x_edge = model.Property("{Edge} is selected if {x:float}")
s.solve_for(Edge.x_edge, type="bin", name=["x", Edge.i, Edge.j])

# Node.x_u_node decision variable: ordering variable used for MTZ subtour elimination.
Node.x_u_node = model.Property("{Node} has auxiliary value {u:float}")
s.solve_for(Node.x_u_node, type="int", name=["u", Node.v], lower=1, upper=node_count)

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
    NodeFrom.v == Edge.i,
    NodeTo.v == Edge.j
).require(
    NodeFrom.x_u_node - NodeTo.x_u_node + node_count * Edge.x_edge <= node_count - 1
)
s.satisfy(mtz)

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
