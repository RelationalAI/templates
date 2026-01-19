"""Water Allocation - Minimize cost of distributing water from sources to users."""

from pathlib import Path
from time import time_ns

from pandas import read_csv
from relationalai.semantics import Model, data, require, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel


def define_model(config=None):
    """Define base model with Source, User, and Connection concepts."""
    model = Model(f"water_allocation_{time_ns()}", config=config, use_lqp=False)

    # Concepts
    Source = model.Concept("Source")
    Source.id = model.Property("{Source} has {id:int}")
    Source.name = model.Property("{Source} has {name:string}")
    Source.capacity = model.Property("{Source} has {capacity:float}")
    Source.cost_per_unit = model.Property("{Source} has {cost_per_unit:float}")

    User = model.Concept("User")
    User.id = model.Property("{User} has {id:int}")
    User.name = model.Property("{User} has {name:string}")
    User.demand = model.Property("{User} has {demand:float}")
    User.priority = model.Property("{User} has {priority:int}")

    Connection = model.Concept("Connection")
    Connection.source = model.Property("{Connection} from {source:Source}")
    Connection.user = model.Property("{Connection} to {user:User}")
    Connection.max_flow = model.Property("{Connection} has {max_flow:float}")
    Connection.loss_rate = model.Property("{Connection} has {loss_rate:float}")
    Connection.flow = model.Property("{Connection} has {flow:float}")

    # Load data
    data_dir = Path(__file__).parent / "data"

    sources_df = read_csv(data_dir / "sources.csv")
    data(sources_df).into(Source, keys=["id"])

    users_df = read_csv(data_dir / "users.csv")
    data(users_df).into(User, keys=["id"])

    conn_df = read_csv(data_dir / "connections.csv")
    conn_data = data(conn_df)
    where(Source.id(conn_data.source_id), User.id(conn_data.user_id)).define(
        Connection.new(source=Source, user=User, max_flow=conn_data.max_flow, loss_rate=conn_data.loss_rate)
    )

    model.Source = Source
    model.User = User
    model.Connection = Connection

    return model


def define_problem(model):
    """Define decision variables, constraints, and objective."""
    Source = model.Source
    User = model.User
    Connection = model.Connection

    s = SolverModel(model, "cont")

    # Variable: flow >= 0
    s.solve_for(
        Connection.flow,
        name=["flow", Connection.source.id, Connection.user.id],
        lower=0,
        upper=Connection.max_flow
    )

    # Constraint: total outflow from each source <= capacity
    Conn = Connection.ref()
    outflow = sum(Conn.flow).where(Conn.source == Source).per(Source)
    s.satisfy(require(outflow <= Source.capacity))

    # Constraint: effective inflow to each user >= demand
    effective_inflow = sum(Conn.flow * (1 - Conn.loss_rate)).where(Conn.user == User).per(User)
    s.satisfy(require(effective_inflow >= User.demand))

    # Objective: minimize total cost
    total_cost = sum(Connection.flow * Connection.source.cost_per_unit)
    s.minimize(total_cost)

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
    print(f"Total cost: ${sol['objective']:.2f}")
    print("\nFlow allocations:")
    df = sol["variables"]
    active = df[df["float"] > 0] if "float" in df.columns else df
    print(active.to_string(index=False))
