"""Water Allocation - Minimize cost of distributing water from sources to users."""

from pathlib import Path
from time import time_ns

from pandas import read_csv
from relationalai.semantics import Model, data, require, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel


def define_model(config=None):
    """Define base model with Source, User, and Connection concepts."""
    model = Model(f"water_allocation_{time_ns()}", config=config, use_lqp=False)

    Concept, Property = model.Concept, model.Property

    # Concepts
    Source = Concept("Source")
    Source.id = Property("{Source} has {id:int}")
    Source.name = Property("{Source} has {name:string}")
    Source.capacity = Property("{Source} has {capacity:float}")
    Source.cost_per_unit = Property("{Source} has {cost_per_unit:float}")

    User = Concept("User")
    User.id = Property("{User} has {id:int}")
    User.name = Property("{User} has {name:string}")
    User.demand = Property("{User} has {demand:float}")
    User.priority = Property("{User} has {priority:int}")

    Connection = Concept("Connection")
    Connection.source = Property("{Connection} from {source:Source}")
    Connection.user = Property("{Connection} to {user:User}")
    Connection.max_flow = Property("{Connection} has {max_flow:float}")
    Connection.loss_rate = Property("{Connection} has {loss_rate:float}")

    # Load data from CSVs
    data_dir = Path(__file__).parent / "data"

    sources_df = read_csv(data_dir / "sources.csv")
    data(sources_df).into(Source, keys=["id"])

    users_df = read_csv(data_dir / "users.csv")
    data(users_df).into(User, keys=["id"])

    # Load connections with references
    conn_df = read_csv(data_dir / "connections.csv")
    conn_data = data(conn_df)
    where(Source.id(conn_data.source_id), User.id(conn_data.user_id)).define(
        Connection.source(Connection, Source),
        Connection.user(Connection, User),
        Connection.max_flow(Connection, conn_data.max_flow),
        Connection.loss_rate(Connection, conn_data.loss_rate),
    )

    # Store references
    model.Source = Source
    model.User = User
    model.Connection = Connection

    return model


def define_problem(model):
    """Define decision variables, constraints, and objective."""
    Source = model.Source
    User = model.User
    Connection = model.Connection

    # Decision variable: flow on each connection
    Connection.flow = model.Property("{Connection} has {flow:float}")

    s = SolverModel(model, "cont")

    # Variable: flow >= 0, <= max_flow
    s.solve_for(
        Connection.flow,
        name=["flow", Connection.source.id, Connection.user.id],
        lower=0,
        upper=Connection.max_flow
    )

    # Constraint: total outflow from each source <= capacity
    s.satisfy(require(
        sum(Connection.flow).where(Connection.source == Source) <= Source.capacity
    ))

    # Constraint: effective inflow to each user >= demand
    # effective_inflow = flow * (1 - loss_rate)
    effective_inflow = sum(Connection.flow * (1 - Connection.loss_rate)).where(
        Connection.user == User
    )
    s.satisfy(require(effective_inflow >= User.demand))

    # Objective: minimize total cost (source cost * flow)
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
