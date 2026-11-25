"""Campaign budget plan: the reallocation problem that maximizes expected conversions under floors
and caps, and how the optimized plan compares with the current budgets."""

from relationalai.semantics import Float, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.std import aggregates as aggs

from .schema import Campaign, model

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

TOTAL_BUDGET = 1130.0  # $K — same as current total; pure reallocation, no budget cut
FLOOR_FRACTION = 0.1   # no campaign drops below 10% of current spend
CAP_MULTIPLIER = 3.0   # no campaign exceeds 3x current spend
PAUSED_REGION = "WEST"
PAUSED_CAP_FRACTION = 0.5  # paused-region total cannot exceed 50% of TOTAL_BUDGET
PAUSED_CAP = PAUSED_CAP_FRACTION * TOTAL_BUDGET  # $K cap on the paused region's total spend

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

# Decision variable: optimized budget per campaign (continuous, $K).
Campaign.x_budget = model.Property(f"{Campaign} has new budget {Float:budget}")

problem = Problem(model, Float, name="campaign_roi")

problem.solve_for(
    Campaign.x_budget,
    lower=0,
    name=["budget", Campaign.name],
)

# Constraint: per-campaign floor and cap, derived from each campaign's
# current spend.
problem.satisfy(model.where(Campaign).require(
    Campaign.x_budget >= FLOOR_FRACTION * Campaign.current_budget,
    Campaign.x_budget <= CAP_MULTIPLIER * Campaign.current_budget,
))

# Constraint: total spend across all campaigns cannot exceed TOTAL_BUDGET.
problem.satisfy(model.require(sum(Campaign.x_budget) <= TOTAL_BUDGET))

# Constraint: paused-region total spend cannot exceed PAUSED_CAP. Without this
# constraint the optimizer would pour budget into the paused region whenever its
# conversion rates are competitive.
problem.satisfy(model.require(
    sum(Campaign.x_budget).where(Campaign.region == PAUSED_REGION) <= PAUSED_CAP
))

# Objective: maximize total expected conversions.
problem.maximize(sum(Campaign.x_budget * Campaign.conversion_rate))

# --------------------------------------------------
# Solve
# --------------------------------------------------

# Each refresh of the deployed model runs this solve.
problem.configure("highs", time_limit_sec=60)

# The solve's status and objective, which the deployed model publishes for the queries.
SolveStatus = model.Relationship(f"campaign roi solve status is {String:status}")
TotalConversions = model.Relationship(f"campaign roi total conversions is {Float:conversions}")
model.define(SolveStatus(problem.termination_status()), TotalConversions(problem.objective_value()))

# --------------------------------------------------
# Compare the optimized plan with the current budgets
# --------------------------------------------------

# Expected conversions at the current budgets, and the optimized plan's lift over
# them as a fraction of the current figure.
CurrentConversions = model.Relationship(
    f"campaign roi current conversions is {Float:current_conversions}"
)
ConversionLift = model.Relationship(f"campaign roi conversion lift is {Float:lift}")
model.define(CurrentConversions(sum(Campaign, Campaign.current_budget * Campaign.conversion_rate)))
_optimized, _current = Float.ref(), Float.ref()
model.where(TotalConversions(_optimized), CurrentConversions(_current)).define(
    ConversionLift((_optimized - _current) / _current)
)

# Each campaign's change from its current budget. These values are computed from the
# solution, so they live on CampaignPlan, not Campaign: such a property on the concept
# the solve reads fails the deploy.
CampaignPlan = model.Concept("CampaignPlan", identify_by={"campaign": Campaign})
CampaignPlan.delta = model.Property(f"{CampaignPlan} changes its budget by {Float:delta}")
CampaignPlan.multiple = model.Property(
    f"{CampaignPlan} has {Float:multiple} times its current budget"
)
model.define(CampaignPlan.new(campaign=Campaign))
model.where(CampaignPlan.campaign == Campaign).define(
    CampaignPlan.delta(Campaign.x_budget - Campaign.current_budget),
    CampaignPlan.multiple(Campaign.x_budget / Campaign.current_budget),
)

# Spend per region: current, optimized, and the optimized share of TOTAL_BUDGET.
RegionSpend = model.Concept("RegionSpend", identify_by={"region": String})
RegionSpend.current_spend = model.Property(f"{RegionSpend} has current spend {Float:current_spend}")
RegionSpend.optimized_spend = model.Property(
    f"{RegionSpend} has optimized spend {Float:optimized_spend}"
)
RegionSpend.share_of_total = model.Property(
    f"{RegionSpend} has {Float:share_of_total} of the total budget"
)
model.define(RegionSpend.new(region=Campaign.region))
_in_region = Campaign.region == RegionSpend.region
model.define(
    RegionSpend.current_spend(
        aggs.sum(Campaign, Campaign.current_budget).per(RegionSpend).where(_in_region)
    ),
    RegionSpend.optimized_spend(
        aggs.sum(Campaign, Campaign.x_budget).per(RegionSpend).where(_in_region)
    ),
)
model.define(RegionSpend.share_of_total(RegionSpend.optimized_spend / TOTAL_BUDGET))
