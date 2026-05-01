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

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

model = Model("tsp")

# Edge concept: directed edges with distances between nodes.
Edge = model.Concept("Edge", identify_by={"i": Integer, "j": Integer})
Edge.dist = model.Property(f"{Edge} has {Float:dist}")

# Load edges from CSV.
edge_csv = read_csv(DATA_DIR / "edges.csv")
model.define(Edge.new(model.data(edge_csv).to_schema()))

# Node concept: derived from edge endpoints.
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

problem = Problem(model, Float)

# Variable: x[i,j] = 1 if edge (i,j) is in the tour, else 0
Edge.x = model.Property(f"{Edge} is selected if {Float:x}")
problem.solve_for(Edge.x, type="bin", name=["x", Edge.i, Edge.j])

# Variable: u[v] = MTZ auxiliary ordering value for subtour elimination
Node.u = model.Property(f"{Node} has auxiliary value {Float:u}")
problem.solve_for(Node.u, name=["u", Node.v], type="int", lower=1, upper=node_count)

# Objective: minimize total tour distance
total_dist = sum(Edge.dist * Edge.x)
problem.minimize(total_dist)

# Constraint: fix u[1] = 1 as symmetry-breaking anchor
problem.satisfy(model.require(Node.u == 1).where(Node.v(1)))

# Constraint: degree constraints (exactly one in-edge and one out-edge per node)
node_flow = sum(Edge.x).per(Node)
problem.satisfy(model.require(
    node_flow.where(Edge.j == Node.v) == 1,
    node_flow.where(Edge.i == Node.v) == 1
))

# Constraint: MTZ subtour elimination
# If edge (i,j) is in tour (x=1), then u[j] >= u[i]+1.
# Big-M form: u[i] - u[j] + n*x <= n-1
problem.satisfy(model.where(
    Ni := Node, Nj := Node.ref(),
    Edge.i > 1, Edge.j > 1,
    Ni.v(Edge.i), Nj.v(Edge.j),
).require(
    Ni.u - Nj.u + node_count * Edge.x <= node_count - 1
))

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

# Check model structure — engine-side ICs avoid querying data to the client.
model.require(problem.num_variables() == count(Edge) + count(Node))
model.require(problem.num_min_objectives() == 1)
problem.display()

# Solve with HiGHS (MILP branch-and-bound)
problem.solve("highs", time_limit_sec=60)
si_highs = problem.solve_info()
si_highs.display()
print(f"HiGHS: {si_highs.termination_status}, tour distance={si_highs.objective_value:.1f}")

# Extract solution
model.require(count(Edge).where(Edge.x > 0.5) == count(Node))
print("\nTour edges:")
model.select(Edge.i.alias("from"), Edge.j.alias("to")).where(Edge.x > 0.5).inspect()
