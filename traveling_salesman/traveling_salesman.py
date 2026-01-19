"""Traveling Salesman - Find shortest route visiting all cities exactly once."""

from pathlib import Path
from time import time_ns

from pandas import read_csv
from relationalai.semantics import Model, count, data, define, require, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel


def define_model(config=None):
    """Define base model with Edge and Node concepts."""
    model = Model(f"tsp_{time_ns()}", config=config, use_lqp=False)

    Edge = model.Concept("Edge")
    Node = model.Concept("Node")
    Edge.dist = model.Property("{Edge} has {dist:float}")

    # Load edges from CSV
    data_dir = Path(__file__).parent / "data"
    csv = read_csv(data_dir / "distances.csv")
    data(csv).into(Edge, keys=["i", "j"])

    # Create nodes from edge endpoints
    define(Node.new(v=Edge.i))

    # Store node count for MTZ constraints
    model.node_count = count(Node.ref())

    model.Edge = Edge
    model.Node = Node
    return model


def define_problem(model):
    """Define decision variables, constraints, and objective (MTZ formulation)."""
    Edge = model.Edge
    Node = model.Node
    node_count = model.node_count

    s = SolverModel(model, "cont")

    # Decision variable: binary edge selection
    Edge.x_edge = model.Property("{Edge} is selected if {x:float}")
    s.solve_for(Edge.x_edge, type="bin", name=["x", Edge.i, Edge.j])

    # Auxiliary variable: node ordering (for subtour elimination)
    Node.u_node = model.Property("{Node} has auxiliary value {u:float}")
    s.solve_for(Node.u_node, type="int", name=["u", Node.v], lower=1, upper=node_count)

    # Objective: minimize total distance
    total_dist = sum(Edge.dist * Edge.x_edge)
    s.minimize(total_dist)

    # Constraint: fix u=1 for node 1 (symmetry breaking)
    s.satisfy(require(Node.u_node == 1).where(Node.v(1)))

    # Constraint: exactly one incoming and one outgoing edge per node
    node_flow = sum(Edge.x_edge).per(Node)
    s.satisfy(require(
        node_flow.where(Edge.j(Node.v)) == 1,
        node_flow.where(Edge.i(Node.v)) == 1
    ))

    # Constraint: MTZ subtour elimination
    s.satisfy(where(
        Ni := Node, Nj := Node.ref(),
        Edge.i > 1, Edge.j > 1,
        Ni.v(Edge.i), Nj.v(Edge.j),
    ).require(
        Ni.u_node - Nj.u_node + node_count * Edge.x_edge <= node_count - 1
    ))

    return s


def solve(config=None, solver_name="highs"):
    """Orchestrate model, problem, and solver execution."""
    model = define_model(config)
    solver_model = define_problem(model)

    solver = Solver(solver_name)
    solver_model.solve(solver, time_limit_sec=60)

    return solver_model


def extract_solution(solver_model):
    """Extract solution as dict with metadata."""
    return {
        "status": solver_model.termination_status,
        "objective": solver_model.objective_value,
        "variables": solver_model.variable_values().to_df(),
    }


if __name__ == "__main__":
    sm = solve()
    sol = extract_solution(sm)

    print(f"Status: {sol['status']}")
    print(f"Shortest tour distance: {sol['objective']:.2f}")
    print("\nSelected edges (tour):")
    df = sol["variables"]
    active = df[df["float"] > 0.5] if "float" in df.columns else df
    print(active.to_string(index=False))
