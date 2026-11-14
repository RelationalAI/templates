"""Water allocation decision problem: least-cost flow on each connection, with nonlinear losses."""

from relationalai.semantics import Float, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

from .schema import Connection, Property, Source, User, model

ConnectionRef = Connection.ref()

Connection.x_flow = Property(f"{Connection} has {Float:flow}")

problem = Problem(model, Float, name="water_allocation")

# Variable: flow on each connection
problem.solve_for(
    Connection.x_flow,
    name=["flow", Connection.source.name, Connection.user.name],
    lower=0,
    upper=Connection.max_flow
)

# Constraint: total outflow from each connected source <= capacity
outflow = sum(ConnectionRef.x_flow).where(ConnectionRef.source == Source).per(Source)
source_limit = model.where(ConnectionRef.source == Source).require(outflow <= Source.capacity)
problem.satisfy(source_limit)

# Constraint: effective inflow to each user >= demand (nonlinear losses)
# Transmission loss increases with utilization: effective delivery per connection
# = flow * (1 - loss_rate * flow / max_flow). At low flow the loss is small;
# at max flow the full loss_rate applies. This makes the constraint quadratic.
effective_inflow = (
    sum(ConnectionRef.x_flow * (1 - ConnectionRef.loss_rate * ConnectionRef.x_flow / ConnectionRef.max_flow))
    .where(ConnectionRef.user == User)
    .per(User)
)
meet_demand = model.where(ConnectionRef.user == User).require(effective_inflow >= User.demand)
problem.satisfy(meet_demand)

# Objective: minimize total cost
total_cost = sum(Connection.x_flow * Connection.source.cost_per_unit)
problem.minimize(total_cost)

# Each refresh of the deployed model runs this solve.
problem.configure("ipopt", time_limit_sec=60)

# The solve's status and objective, which the deployed model publishes for the queries.
SolveStatus = model.Relationship(f"water allocation solve status is {String:status}")
TotalCost = model.Relationship(f"water allocation total cost is {Float:cost}")
model.define(SolveStatus(problem.termination_status()), TotalCost(problem.objective_value()))
