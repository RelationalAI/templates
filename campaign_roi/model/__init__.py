"""Campaign ROI (prescriptive optimization) template: the model.

This package demonstrates a marketing budget reallocation LP in RelationalAI:

- Load sample CSV describing marketing campaigns across regions, each with a
  current budget and a conversion rate.
- Choose a non-negative new budget per campaign (continuous decision variable).
- Enforce a per-campaign floor (no campaign can drop below FLOOR_FRACTION of
  current) and cap (no campaign can exceed CAP_MULTIPLIER * current).
- Enforce a regional cap on a paused region: total spend in PAUSED_REGION
  cannot exceed PAUSED_CAP_FRACTION of TOTAL_BUDGET.
- Enforce a total budget constraint.
- Maximize total expected conversions = sum(budget * conversion_rate).

Run:
    `rai models deploy --path model` deploys this model to the schema in
    raiconfig.yaml and waits for its first refresh, which runs the solve.
    `python -m queries.budget_reallocation` then prints the report from the deployed model.
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

TOTAL_BUDGET = 1130.0  # $K — same as current total; pure reallocation, no budget cut
FLOOR_FRACTION = 0.1   # no campaign drops below 10% of current spend
CAP_MULTIPLIER = 3.0   # no campaign exceeds 3x current spend
PAUSED_REGION = "WEST"
PAUSED_CAP_FRACTION = 0.5  # paused-region total cannot exceed 50% of TOTAL_BUDGET

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

model = Model("campaign_roi")

# Campaign concept: a marketing campaign with a current budget, region tag,
# and an empirical conversion rate (conversions per $K of spend).
Campaign = model.Concept("Campaign", identify_by={"id": Integer})
Campaign.name = model.Property(f"{Campaign} has {String:name}")
Campaign.region = model.Property(f"{Campaign} in {String:region}")
Campaign.current_budget = model.Property(f"{Campaign} has {Float:current_budget}")
Campaign.conversion_rate = model.Property(f"{Campaign} has {Float:conversion_rate}")

# Load campaigns from CSV.
campaign_csv = read_csv(DATA_DIR / "campaigns.csv")
model.define(Campaign.new(model.data(campaign_csv).to_schema()))

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

# Decision variable: optimized budget per campaign (continuous, $K).
Campaign.x_budget = model.Property(f"{Campaign} has new budget {Float:budget}")

problem = Problem(model, Float)

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

# Deploy the rules behind problem.display() with the model.
problem.install_display_strings()

# The solve's status and objective, published through the model's own relationships.
SolveStatus = model.Relationship(f"campaign roi solve status is {String:status}")
TotalConversions = model.Relationship(f"campaign roi total conversions is {Float:conversions}")
model.define(SolveStatus(problem.termination_status()), TotalConversions(problem.objective_value()))
