"""Network flow problem: lane flows and fulfillment center openings at minimum total cost."""

from relationalai.semantics import Float, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

from .schema import Demand, Lane, Site, model

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

# Decision variables on the model itself.
Lane.x_flow = model.Property(f"{Lane} carries {Float:flow}")
Site.x_open = model.Property(f"{Site} is open {Float:open}")

problem = Problem(model, Float, name="network_flow_planning")

# Variable: flow on each lane (continuous, bounded by lane capacity).
problem.solve_for(
    Lane.x_flow,
    lower=0,
    upper=Lane.capacity,
    name=["flow", Lane.id],
)

# Variable: open/close decision per fulfillment center (binary).
# Restricted to sites with positive fixed_cost — i.e., the FC sites.
problem.solve_for(
    Site.x_open,
    type="bin",
    name=["open", Site.name],
    where=[Site.fixed_cost > 0],
)

# Constraint: source supply — outflow from each warehouse cannot exceed its
# inventory.
out_lane = Lane.ref()
problem.satisfy(model.where(
    Site.inventory > 0,
).require(
    sum(out_lane.x_flow).where(out_lane.source == Site).per(Site) <= Site.inventory
))

# Constraint: flow conservation at hubs — inflow equals outflow.
in_lane = Lane.ref()
out_lane = Lane.ref()
problem.satisfy(model.where(
    Site.type == "HUB",
).require(
    sum(in_lane.x_flow).where(in_lane.dest == Site).per(Site)
    == sum(out_lane.x_flow).where(out_lane.source == Site).per(Site)
))

# Constraint: flow conservation at fulfillment centers — inflow equals outflow.
in_lane = Lane.ref()
out_lane = Lane.ref()
problem.satisfy(model.where(
    Site.type == "FULFILLMENT_CENTER",
).require(
    sum(in_lane.x_flow).where(in_lane.dest == Site).per(Site)
    == sum(out_lane.x_flow).where(out_lane.source == Site).per(Site)
))

# Constraint: FC capacity gated by open decision — total inflow at an FC cannot
# exceed its capacity unless x_open == 1.
in_lane = Lane.ref()
problem.satisfy(model.where(
    Site.fixed_cost > 0,
).require(
    sum(in_lane.x_flow).where(in_lane.dest == Site).per(Site)
    <= Site.capacity * Site.x_open
))

# Constraint: demand satisfaction — total inflow at each customer site must
# meet aggregate demand at that site.
in_lane = Lane.ref()
demand_ref = Demand.ref()
problem.satisfy(model.where(
    Site.type == "CUSTOMER",
).require(
    sum(in_lane.x_flow).where(in_lane.dest == Site).per(Site)
    >= sum(demand_ref.quantity).where(demand_ref.site == Site).per(Site)
))

# Objective: minimize transport cost + fixed cost of opened fulfillment centers.
# With no site that has a fixed cost the second sum is empty; `| 0.0` makes it zero.
problem.minimize(
    sum(Lane.cost_per_unit * Lane.x_flow) + (sum(Site.fixed_cost * Site.x_open) | 0.0)
)

# --------------------------------------------------
# Solve
# --------------------------------------------------

# Each refresh of the deployed model runs this solve.
problem.configure("highs", time_limit_sec=60)

# The solve's status and objective, which the deployed model publishes for the queries.
SolveStatus = model.Relationship(f"network flow solve status is {String:status}")
TotalCost = model.Relationship(f"network flow total cost is {Float:cost}")
model.define(SolveStatus(problem.termination_status()), TotalCost(problem.objective_value()))
