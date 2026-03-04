"""Water Allocation (prescriptive optimization) template.

This script demonstrates a network flow optimization model in RelationalAI:

- Load sample CSVs describing water sources, users (demand points), and connections.
- Model those entities as *concepts* with typed properties.
- Choose a non-negative flow on each connection to meet all user demands.
- Enforce source capacity limits, connection flow limits, and transmission losses.
- Minimize total sourcing cost.

Run:
    `python water_allocation.py`

Output:
    Prints the solver termination status, objective value, and a table of
    non-trivial flow allocations.
"""

from pathlib import Path

from pandas import read_csv

from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("water_allocation")
Concept, Property = model.Concept, model.Property

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Concept: water sources with capacity and cost
Source = Concept("Source", identify_by={"id": Integer})
Source.name = Property(f"{Source} has {String:name}")
Source.capacity = Property(f"{Source} has {Float:capacity}")
Source.cost_per_unit = Property(f"{Source} has {Float:cost_per_unit}")
source_csv = read_csv(data_dir / "sources.csv")
model.define(Source.new(model.data(source_csv).to_schema()))

# Concept: users with demand and priority
User = Concept("User", identify_by={"id": Integer})
User.name = Property(f"{User} has {String:name}")
User.demand = Property(f"{User} has {Float:demand}")
User.priority = Property(f"{User} has {Integer:priority}")
user_csv = read_csv(data_dir / "users.csv")
model.define(User.new(model.data(user_csv).to_schema()))

# Relationship: connections between sources and users
Connection = Concept("Connection")
Connection.source = Property(f"{Connection} from {Source}", short_name="source")
Connection.user = Property(f"{Connection} to {User}", short_name="user")
Connection.max_flow = Property(f"{Connection} has {Float:max_flow}")
Connection.loss_rate = Property(f"{Connection} has {Float:loss_rate}")
Connection.x_flow = Property(f"{Connection} has {Float:flow}")

conn_csv = read_csv(data_dir / "connections.csv")
conn_data = model.data(conn_csv)
model.define(
    Connection.new(source=Source, user=User, max_flow=conn_data.max_flow, loss_rate=conn_data.loss_rate)
).where(Source.id == conn_data.source_id, User.id == conn_data.user_id)

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

ConnectionRef = Connection.ref()

s = Problem(model, Float)

# Variable: flow on each connection
s.solve_for(
    Connection.x_flow,
    name=["flow", Connection.source.name, Connection.user.name],
    lower=0,
    upper=Connection.max_flow
)

# Constraint: total outflow from each source <= capacity
outflow = sum(ConnectionRef.x_flow).where(ConnectionRef.source == Source).per(Source)
source_limit = model.require(outflow <= Source.capacity)
s.satisfy(source_limit)

# Constraint: effective inflow to each user >= demand (accounting for losses)
effective_inflow = sum(ConnectionRef.x_flow * (1 - ConnectionRef.loss_rate)).where(ConnectionRef.user == User).per(User)
meet_demand = model.require(effective_inflow >= User.demand)
s.satisfy(meet_demand)

# Objective: minimize total cost
total_cost = sum(Connection.x_flow * Connection.source.cost_per_unit)
s.minimize(total_cost)

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

s.display()
s.solve("highs", time_limit_sec=60, _server_side_import=False)
s.display_solve_info()

print(f"Status: {s.termination_status}")
print(f"Total cost: ${s.objective_value:.2f}")

allocations = model.select(
    Connection.source.name.alias("source"),
    Connection.user.name.alias("user"),
    Connection.x_flow
).where(Connection.x_flow > 0.001).to_df()

print("\nFlow allocations:")
print(allocations.to_string(index=False))
