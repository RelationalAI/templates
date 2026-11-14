"""Campaign budget reallocation problem: maximize expected conversions under floors and caps."""

from relationalai.semantics import Float, sum
from relationalai.semantics.reasoners.prescriptive import Problem

from .schema import Campaign, model

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

TOTAL_BUDGET = 1130.0  # $K — same as current total; pure reallocation, no budget cut
FLOOR_FRACTION = 0.1   # no campaign drops below 10% of current spend
CAP_MULTIPLIER = 3.0   # no campaign exceeds 3x current spend
PAUSED_REGION = "WEST"
PAUSED_CAP_FRACTION = 0.5  # paused-region total cannot exceed 50% of TOTAL_BUDGET

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

# Constraint: paused-region total spend cannot exceed
# PAUSED_CAP_FRACTION * TOTAL_BUDGET. Without this constraint the optimizer
# would pour budget into the paused region whenever its conversion rates
# are competitive.
problem.satisfy(model.require(
    sum(Campaign.x_budget).where(Campaign.region == PAUSED_REGION)
    <= PAUSED_CAP_FRACTION * TOTAL_BUDGET
))

# Objective: maximize total expected conversions.
problem.maximize(sum(Campaign.x_budget * Campaign.conversion_rate))

# --------------------------------------------------
# Solve
# --------------------------------------------------

# Each refresh of the deployed model runs this solve.
problem.configure("highs", time_limit_sec=60)
