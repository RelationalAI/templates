"""Network Flow - Find maximum flow through a capacitated network."""

from pathlib import Path
from time import time_ns

from pandas import read_csv
from relationalai.semantics import Model, data, per, require, select, sum
from relationalai.semantics.reasoners.optimization import Solver, SolverModel


def define_model(config=None):
    """Define base model with Edge concept and capacities."""
    model = Model(f"network_flow_{time_ns()}", config=config, use_lqp=False)

    # Concept: directed edge with capacity
    Edge = model.Concept("Edge")

    # Load edges from CSV (source i, target j, capacity cap)
    data_dir = Path(__file__).parent / "data"
    csv = read_csv(data_dir / "edges.csv")
    data(csv).into(Edge, keys=["i", "j"])

    model.Edge = Edge
    return model


def define_problem(model):
    """Define decision variables, constraints, and objective."""
    Edge = model.Edge

    # Decision variable: flow on each edge
    Edge.flow = model.Property("{Edge} has {flow:float}")

    # Objective: maximize total flow out of source node (node 1)
    total_flow = sum(Edge.flow).where(Edge.i(1))

    # Constraint: flow between 0 and capacity
    bounds = require(Edge.flow >= 0, Edge.flow <= Edge.cap)

    # Constraint: flow conservation at intermediate nodes
    Ei = Edge
    Ej = Edge.ref()
    flow_out = per(Ei.i).sum(Ei.flow)
    flow_in = per(Ej.j).sum(Ej.flow)
    balance = require(flow_in == flow_out).where(Ei.i == Ej.j)

    # Build solver model
    s = SolverModel(model, "cont")
    s.solve_for(Edge.flow, name=["flow", Edge.i, Edge.j])
    s.maximize(total_flow)
    s.satisfy(bounds)
    s.satisfy(balance)

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
    print(f"Maximum flow: {sol['objective']:.0f}")
    print("\nEdge flows:")
    df = sol["variables"]
    active = df[df["float"] > 0] if "float" in df.columns else df
    print(active.to_string(index=False))
