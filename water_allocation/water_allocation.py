# Water Allocation:
# Minimize cost of distributing water from sources to users

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Model, data, require, select, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

model = Model("water_allocation", config=globals().get("config", None), use_lqp=False)

# --------------------------------------------------
# Load Data and Define Ontology
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Water sources with capacity and cost
Source = model.Concept("Source")
Source.id = model.Property("{Source} has {id:int}")
Source.name = model.Property("{Source} has {name:string}")
Source.capacity = model.Property("{Source} has {capacity:float}")
Source.cost_per_unit = model.Property("{Source} has {cost_per_unit:float}")
data(read_csv(data_dir / "sources.csv")).into(Source, keys=["id"])

# Users with demand and priority
User = model.Concept("User")
User.id = model.Property("{User} has {id:int}")
User.name = model.Property("{User} has {name:string}")
User.demand = model.Property("{User} has {demand:float}")
User.priority = model.Property("{User} has {priority:int}")
data(read_csv(data_dir / "users.csv")).into(User, keys=["id"])

# Connections between sources and users with flow limits and loss rates
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
# Define Optimization Problem
# --------------------------------------------------

Conn = Connection.ref()

# Constraint: total outflow from each source <= capacity
outflow = sum(Conn.flow).where(Conn.source == Source).per(Source)
source_limit = require(outflow <= Source.capacity)

# Constraint: effective inflow to each user >= demand (accounting for losses)
effective_inflow = sum(Conn.flow * (1 - Conn.loss_rate)).where(Conn.user == User).per(User)
meet_demand = require(effective_inflow >= User.demand)

# Objective: minimize total cost
total_cost = sum(Connection.flow * Connection.source.cost_per_unit)

# --------------------------------------------------
# Set Up Solver Model
# --------------------------------------------------

s = SolverModel(model, "cont")
s.solve_for(
    Connection.flow,
    name=["flow", Connection.source.name, Connection.user.name],
    lower=0,
    upper=Connection.max_flow
)
s.minimize(total_cost)
s.satisfy(source_limit)
s.satisfy(meet_demand)

# --------------------------------------------------
# Solve and Display Results
# --------------------------------------------------

solver = Solver("highs")
s.solve(solver, time_limit_sec=60)

print(f"Status: {s.termination_status}")
print(f"Total cost: ${s.objective_value:.2f}")

# Access solution via populated relations
allocations = select(
    Connection.source.name.alias("source"),
    Connection.user.name.alias("user"),
    Connection.flow
).where(Connection.flow > 0.001).to_df()

print("\nFlow allocations:")
print(allocations.to_string(index=False))
