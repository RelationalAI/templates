"""Traveling salesman (prescriptive optimization) template.

This script demonstrates a mixed-integer linear optimization (MILP) problem
in RelationalAI:

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

from pandas import read_csv

from relationalai.semantics import Float, Integer, Model, count, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("tsp")

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Concept: directed edges with distances between nodes
Edge = model.Concept("Edge", identify_by={"i": Integer, "j": Integer})
Edge.dist = model.Property(f"{Edge} has {Float:dist}")
edge_csv = read_csv(data_dir / "edges.csv")
model.define(Edge.new(model.data(edge_csv).to_schema()))

# Rule: nodes derived from edge endpoints
Node = model.Concept("Node", identify_by={"v": Integer})
model.define(Node.new(v=Edge.i))

# Rule: node count stored as a relationship
# WORKAROUND: direct count(Node.ref()) in solver bounds is broken (pending pyrel compiler fix).
# Store count as a Relationship and reference it in solve_for(upper=node_count).
node_count = model.Relationship(f"node count is {Integer}")
model.define(node_count(count(Node)))

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

s = Problem(model, Float)

# Variable: x[i,j] = 1 if edge (i,j) is in the tour, else 0
Edge.x = model.Property(f"{Edge} is selected if {Float:x}")
s.solve_for(Edge.x, type="bin", name=["x", Edge.i, Edge.j])

# Variable: u[v] = MTZ auxiliary ordering value for subtour elimination
Node.u = model.Property(f"{Node} has auxiliary value {Float:u}")
s.solve_for(Node.u, name=["u", Node.v], type="int", lower=1, upper=node_count)

# Objective: minimize total tour distance
total_dist = sum(Edge.dist * Edge.x)
s.minimize(total_dist)

# Constraint: fix u[1] = 1 as symmetry-breaking anchor
s.satisfy(model.require(Node.u == 1).where(Node.v(1)))

# Constraint: degree constraints (exactly one in-edge and one out-edge per node)
node_flow = sum(Edge.x).per(Node)
s.satisfy(model.require(
    node_flow.where(Edge.j == Node.v) == 1,
    node_flow.where(Edge.i == Node.v) == 1
))

# Constraint: MTZ subtour elimination
# If edge (i,j) is in tour (x=1), then u[j] >= u[i]+1.
# Big-M form: u[i] - u[j] + n*x <= n-1
s.satisfy(model.where(
    Ni := Node, Nj := Node.ref(),
    Edge.i > 1, Edge.j > 1,
    Ni.v(Edge.i), Nj.v(Edge.j),
).require(
    Ni.u - Nj.u + node_count * Edge.x <= node_count - 1
))

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

s.display()
s.solve("highs", time_limit_sec=60, _server_side_import=False)
s.display_solve_info()

print(f"Status: {s.termination_status}")
print(f"Tour distance: {s.objective_value:.2f}")

# Extract solution via model.select() — properties are populated after solve
tour = model.select(
    Edge.i.alias("from"), Edge.j.alias("to"),
).where(Edge.x > 0.5).to_df()
print(f"\nTour edges:\n{tour.to_string(index=False)}")
