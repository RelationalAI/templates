"""Water Allocation (nonlinear optimization) template.

This script demonstrates a nonlinear optimization model solved with Ipopt
in RelationalAI:

- Load sample CSVs describing water sources, users (demand points), and connections.
- Model those entities as *concepts* with typed properties.
- Choose a non-negative flow on each connection to meet all user demands.
- Enforce source capacity limits and connection flow limits.
- Account for nonlinear transmission losses: loss increases with utilization,
  so effective delivery = flow * (1 - loss_rate * flow / max_flow).
  This quadratic constraint requires a nonlinear solver.
- Minimize total sourcing cost.

Solver: Ipopt (interior-point for nonlinear programs). Ipopt finds locally
optimal solutions for smooth NLP problems with continuous variables.

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

DATA_DIR = Path(__file__).parent / "data"

# Source concept: water sources with capacity and cost.
Source = Concept("Source", identify_by={"id": Integer})
Source.name = Property(f"{Source} has {String:name}")
Source.capacity = Property(f"{Source} has {Float:capacity}")
Source.cost_per_unit = Property(f"{Source} has {Float:cost_per_unit}")
source_csv = read_csv(DATA_DIR / "sources.csv")
model.define(Source.new(model.data(source_csv).to_schema()))

# User concept: water demand points with priority levels.
User = Concept("User", identify_by={"id": Integer})
User.name = Property(f"{User} has {String:name}")
User.demand = Property(f"{User} has {Float:demand}")
User.priority = Property(f"{User} has {Integer:priority}")
user_csv = read_csv(DATA_DIR / "users.csv")
model.define(User.new(model.data(user_csv).to_schema()))

# Connection concept: links between sources and users.
Connection = Concept("Connection")
Connection.source = Property(f"{Connection} from {Source}", short_name="source")
Connection.user = Property(f"{Connection} to {User}", short_name="user")
Connection.max_flow = Property(f"{Connection} has {Float:max_flow}")
Connection.loss_rate = Property(f"{Connection} has {Float:loss_rate}")
Connection.x_flow = Property(f"{Connection} has {Float:flow}")

conn_csv = read_csv(DATA_DIR / "connections.csv")
conn_data = model.data(conn_csv)
model.define(
    Connection.new(source=Source, user=User, max_flow=conn_data.max_flow, loss_rate=conn_data.loss_rate)
).where(Source.id == conn_data.source_id, User.id == conn_data.user_id)

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

ConnectionRef = Connection.ref()

p = Problem(model, Float)

# Variable: flow on each connection
p.solve_for(
    Connection.x_flow,
    name=["flow", Connection.source.name, Connection.user.name],
    lower=0,
    upper=Connection.max_flow
)

# Constraint: total outflow from each source <= capacity
outflow = sum(ConnectionRef.x_flow).where(ConnectionRef.source == Source).per(Source)
source_limit = model.require(outflow <= Source.capacity)
p.satisfy(source_limit)

# Constraint: effective inflow to each user >= demand (nonlinear losses)
# Transmission loss increases with utilization: effective delivery per connection
# = flow * (1 - loss_rate * flow / max_flow). At low flow the loss is small;
# at max flow the full loss_rate applies. This makes the constraint quadratic.
effective_inflow = (
    sum(ConnectionRef.x_flow * (1 - ConnectionRef.loss_rate * ConnectionRef.x_flow / ConnectionRef.max_flow))
    .where(ConnectionRef.user == User)
    .per(User)
)
meet_demand = model.require(effective_inflow >= User.demand)
p.satisfy(meet_demand)

# Objective: minimize total cost
total_cost = sum(Connection.x_flow * Connection.source.cost_per_unit)
p.minimize(total_cost)

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

p.display()
p.solve("ipopt", time_limit_sec=60)
si = p.solve_info()
si.display()

print(f"Status: {si.termination_status}")  # Ipopt returns LOCALLY_SOLVED
print(f"Total cost: ${si.objective_value:.2f}")

print("\nFlow allocations:")
model.select(
    Connection.source.name.alias("source"),
    Connection.user.name.alias("user"),
    Connection.x_flow
).where(Connection.x_flow > 0.001).inspect()
