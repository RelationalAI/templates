"""Ad spend decision problem: maximize expected conversions across budget scenarios."""

from relationalai.semantics import Float, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

from .schema import Allocation, Campaign, Effectiveness, Property, Scenario, model

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

model.define(Allocation.new(effectiveness=Effectiveness))

# Decision variables — indexed by Scenario (multi-argument Properties)
Allocation.x_spend = Property(f"{Allocation} in {Scenario} has {Float:spend}")
Allocation.x_active = Property(f"{Allocation} in {Scenario} is {Float:active}")

# Refs for binding multi-arg variables in constraints
x_spend = Float.ref()
x_active = Float.ref()

problem = Problem(model, Float, name="ad_spend_allocation")

# Variables
problem.solve_for(
    Allocation.x_spend(Scenario, x_spend),
    name=["spend", Scenario.name, Allocation.effectiveness.channel.name, Allocation.effectiveness.campaign.name],
    lower=0,
)
problem.solve_for(
    Allocation.x_active(Scenario, x_active),
    type="bin",
    name=["active", Scenario.name, Allocation.effectiveness.channel.name, Allocation.effectiveness.campaign.name],
)

# Constraint: minimum spend per channel when active
problem.satisfy(model.where(
    Allocation.x_spend(Scenario, x_spend),
    Allocation.x_active(Scenario, x_active),
).require(x_spend >= Allocation.effectiveness.channel.min_spend * x_active))

# Constraint: maximum spend per channel when active
problem.satisfy(model.where(
    Allocation.x_spend(Scenario, x_spend),
    Allocation.x_active(Scenario, x_active),
).require(x_spend <= Allocation.effectiveness.channel.max_spend * x_active))

# Constraint: per-campaign budget across all channels (per scenario)
problem.satisfy(model.where(
    Allocation.x_spend(Scenario, x_spend),
    Allocation.effectiveness.campaign(Campaign),
).require(
    sum(Allocation, x_spend).where(Allocation.effectiveness.campaign == Campaign).per(Campaign, Scenario)
    <= Campaign.budget
))

# Constraint: require at least one active channel per campaign (per scenario)
problem.satisfy(model.where(
    Allocation.x_active(Scenario, x_active),
    Allocation.effectiveness.campaign(Campaign),
).require(
    sum(Allocation, x_active).where(Allocation.effectiveness.campaign == Campaign).per(Campaign, Scenario)
    >= 1
))

# Constraint: total budget across all campaigns (per scenario)
problem.satisfy(model.where(
    Allocation.x_spend(Scenario, x_spend),
).require(sum(Allocation, x_spend).per(Scenario) <= Scenario.total_budget))

# Objective: maximize total expected conversions
problem.maximize(
    sum(Allocation, Scenario, x_spend * Allocation.effectiveness.conversion_rate)
    .where(Allocation.x_spend(Scenario, x_spend))
)

# --------------------------------------------------
# Solve (single solve for all scenarios)
# --------------------------------------------------

# Each refresh of the deployed model runs this solve.
problem.configure("highs", time_limit_sec=60)

# The solve's status and objective, which the deployed model publishes for the queries.
SolveStatus = model.Relationship(f"ad spend solve status is {String:status}")
TotalConversions = model.Relationship(f"ad spend total conversions is {Float:conversions}")
model.define(SolveStatus(problem.termination_status()), TotalConversions(problem.objective_value()))
