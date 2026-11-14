"""Traveling salesman decision problem: the shortest tour, with MTZ subtour elimination."""

from relationalai.semantics import Float, Integer, String, count, sum
from relationalai.semantics.reasoners.prescriptive import Problem

from .schema import Edge, Node, model

# Rule: node count stored as a relationship
# WORKAROUND: direct count(Node.ref()) in solver bounds is broken (pending pyrel compiler fix).
# Store count as a Relationship and reference it in solve_for(upper=node_count).
node_count = model.Relationship(f"node count is {Integer}")
model.define(node_count(count(Node)))

problem = Problem(model, Float, name="traveling_salesman")

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
problem.satisfy(model.where(Edge.j == Node.v).require(node_flow.where(Edge.j == Node.v) == 1))
problem.satisfy(model.where(Edge.i == Node.v).require(node_flow.where(Edge.i == Node.v) == 1))

# Constraint: MTZ subtour elimination
# If edge (i,j) is in tour (x=1), then u[j] >= u[i]+1.
# Big-M form: u[i] - u[j] + n*x <= n-1
problem.satisfy(model.where(
    Ni := Node, Nj := Node.ref(),
    Edge.i > 1, Edge.j > 1,
    Ni.v(Edge.i), Nj.v(Edge.j),
    node_count,
).require(
    Ni.u - Nj.u + node_count * Edge.x <= node_count - 1
))

# Each refresh of the deployed model runs this solve (HiGHS MILP branch-and-bound).
problem.configure("highs", time_limit_sec=60)

# The solve's status and objective, which the deployed model publishes for the queries.
SolveStatus = model.Relationship(f"tsp solve status is {String:status}")
TourDistance = model.Relationship(f"tsp tour distance is {Float:distance}")
model.define(SolveStatus(problem.termination_status()), TourDistance(problem.objective_value()))
