"""Water allocation (prescriptive optimization) template.

This script demonstrates a simple network flow optimization model in RelationalAI:

- Load sample CSVs describing water sources, users (demand points), and connections.
- Model those entities as *concepts* with typed properties.
- Choose a non-negative flow on each connection to meet all user demands.
- Minimize total sourcing cost subject to source capacities, connection limits,
  and transmission losses.

Run:
    `python water_allocation.py`

Output:
    Prints the solver termination status, objective value, and a table of
    non-trivial flow allocations.
"""

from pathlib import Path

import pandas
from pandas import read_csv

from relationalai.semantics import Model, Relationship, data, require, select, sum, where
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
model = Model("water_allocation", config=globals().get("config", None))

# Source concept: water supply points with capacity and per-unit cost.
Source = model.Concept("Source")
Source.id = model.Property("{Source} has {id:int}")
Source.name = model.Property("{Source} has {name:string}")
Source.capacity = model.Property("{Source} has {capacity:float}")
Source.cost_per_unit = model.Property("{Source} has {cost_per_unit:float}")

# Load source data from CSV.
source_csv = read_csv(DATA_DIR / "sources.csv")
data(source_csv).into(Source, keys=["id"])

# User concept: demand points with required volume (and a priority field).
User = model.Concept("User")
User.id = model.Property("{User} has {id:int}")
User.name = model.Property("{User} has {name:string}")
User.demand = model.Property("{User} has {demand:float}")
User.priority = model.Property("{User} has {priority:int}")

# Load user data from CSV.
user_csv = read_csv(DATA_DIR / "users.csv")
data(user_csv).into(User, keys=["id"])

# Connection concept: links a Source to a User with transmission parameters.
Connection = model.Concept("Connection")
Connection.source = model.Relationship("{Connection} from {source:Source}")
Connection.user = model.Relationship("{Connection} to {user:User}")
Connection.max_flow = model.Property("{Connection} has {max_flow:float}")
Connection.loss_rate = model.Property("{Connection} has {loss_rate:float}")
Connection.x_flow = model.Property("{Connection} has {flow:float}")

# Load connection data from CSV.
conn_data = data(read_csv(DATA_DIR / "connections.csv"))

# Define Connection entities by joining the CSV data with Source and User.
where(
    Source.id == conn_data.source_id,
    User.id == conn_data.user_id
).define(
    Connection.new(
        source=Source,
        user=User,
        max_flow=conn_data.max_flow,
        loss_rate=conn_data.loss_rate,
    )
)

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

Conn = Connection.ref()

# Create a continuous optimization model.
s = SolverModel(model, "cont")

# Decision variable: flow on each connection (continuous, non-negative).
s.solve_for(
    Connection.x_flow,
    name=["flow", Connection.source.name, Connection.user.name],
    lower=0,
    upper=Connection.max_flow,
)

# Constraint: total outflow from each source must not exceed its capacity.
outflow = sum(Conn.x_flow).where(Conn.source == Source).per(Source)
source_limit = require(outflow <= Source.capacity)
s.satisfy(source_limit)

# Constraint: effective inflow to each user must meet demand (accounting for losses).
effective_inflow = (
    sum(Conn.x_flow * (1 - Conn.loss_rate)).where(Conn.user == User).per(User)
)
meet_demand = require(effective_inflow >= User.demand)
s.satisfy(meet_demand)

# Objective: minimize total cost.
total_cost = sum(Connection.x_flow * Connection.source.cost_per_unit)
s.minimize(total_cost)

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

solver = Solver("highs")
s.solve(solver, time_limit_sec=60)

print(f"Status: {s.termination_status}")
print(f"Total cost: ${s.objective_value:.2f}")

allocations = select(
    Connection.source.name.alias("source"),
    Connection.user.name.alias("user"),
    Connection.x_flow,
).where(
    Connection.x_flow > 0.001
).to_df()

print("\nFlow allocations:")
print(allocations.to_string(index=False))
