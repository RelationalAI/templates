# water allocation problem:
# minimize cost of distributing water from sources to users

from pathlib import Path

from pandas import read_csv

from relationalai.semantics import Model, data, require, select, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

model = Model("water_allocation", config=globals().get("config", None), use_lqp=False)

# --------------------------------------------------
# Define ontology & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Concept: water sources with capacity and cost
Source = model.Concept("Source")
Source.id = model.Property("{Source} has {id:int}")
Source.name = model.Property("{Source} has {name:string}")
Source.capacity = model.Property("{Source} has {capacity:float}")
Source.cost_per_unit = model.Property("{Source} has {cost_per_unit:float}")
data(read_csv(data_dir / "sources.csv")).into(Source, keys=["id"])

# Concept: users with demand and priority
User = model.Concept("User")
User.id = model.Property("{User} has {id:int}")
User.name = model.Property("{User} has {name:string}")
User.demand = model.Property("{User} has {demand:float}")
User.priority = model.Property("{User} has {priority:int}")
data(read_csv(data_dir / "users.csv")).into(User, keys=["id"])

# Relationship: connections between sources and users
Connection = model.Concept("Connection")
Connection.source = model.Property("{Connection} from {source:Source}")
Connection.user = model.Property("{Connection} to {user:User}")
Connection.max_flow = model.Property("{Connection} has {max_flow:float}")
Connection.loss_rate = model.Property("{Connection} has {loss_rate:float}")
Connection.flow = model.Property("{Connection} has {flow:float}")

conn_data = data(read_csv(data_dir / "connections.csv"))
where(Source.id(conn_data.source_id), User.id(conn_data.user_id)).define(
    Connection.new(source=Source, user=User, max_flow=conn_data.max_flow, loss_rate=conn_data.loss_rate)
)

# --------------------------------------------------
# Model the problem
# --------------------------------------------------

Conn = Connection.ref()

s = SolverModel(model, "cont")

# Variable: flow on each connection
s.solve_for(
    Connection.flow,
    name=["flow", Connection.source.name, Connection.user.name],
    lower=0,
    upper=Connection.max_flow
)

# Constraint: total outflow from each source <= capacity
outflow = sum(Conn.flow).where(Conn.source == Source).per(Source)
source_limit = require(outflow <= Source.capacity)
s.satisfy(source_limit)

# Constraint: effective inflow to each user >= demand (accounting for losses)
effective_inflow = sum(Conn.flow * (1 - Conn.loss_rate)).where(Conn.user == User).per(User)
meet_demand = require(effective_inflow >= User.demand)
s.satisfy(meet_demand)

# Objective: minimize total cost
total_cost = sum(Connection.flow * Connection.source.cost_per_unit)
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
    Connection.flow
).where(Connection.flow > 0.001).to_df()

print("\nFlow allocations:")
print(allocations.to_string(index=False))
