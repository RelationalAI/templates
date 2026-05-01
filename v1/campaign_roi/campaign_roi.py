"""Campaign ROI (prescriptive optimization) template.

This script demonstrates a marketing budget reallocation LP in RelationalAI:

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
    `python campaign_roi.py`

Output:
    Prints solver termination status, total conversions vs current,
    optimized budget vs current per campaign, and regional spend summary
    against the paused-region cap.
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"

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
problem.satisfy(model.require(
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
# Solve and check solution
# --------------------------------------------------

problem.display()
problem.solve("highs", time_limit_sec=60)
model.require(problem.termination_status() == "OPTIMAL")
si = problem.solve_info()
si.display()

print(f"\nStatus: {si.termination_status}")
print(f"Total expected conversions (optimized): {si.objective_value:,.1f}")

current_total = (campaign_csv["current_budget"] * campaign_csv["conversion_rate"]).sum()
print(f"Total expected conversions (current):   {current_total:,.1f}")
print(f"Lift: {(si.objective_value - current_total) / current_total * 100:+.1f}%")

print("\nBudget reallocation per campaign (sorted by largest absolute change):")
results_df = model.select(
    Campaign.name.alias("campaign"),
    Campaign.region.alias("region"),
    Campaign.current_budget.alias("current"),
    Campaign.x_budget.alias("optimized"),
    Campaign.conversion_rate.alias("rate"),
).to_df()
results_df["delta"] = results_df["optimized"] - results_df["current"]
results_df["multiple"] = results_df["optimized"] / results_df["current"]
results_df = results_df.sort_values("delta", key=abs, ascending=False).reset_index(drop=True)
print(results_df.to_string(index=False))

print("\nRegional spend (optimized):")
regional = (
    results_df.groupby("region")[["current", "optimized"]]
    .sum()
    .reset_index()
    .sort_values("optimized", ascending=False)
)
regional["share_of_total"] = regional["optimized"] / TOTAL_BUDGET
print(regional.to_string(index=False))
print(
    f"\nPaused region '{PAUSED_REGION}' cap: "
    f"{PAUSED_CAP_FRACTION * TOTAL_BUDGET:.1f} ({PAUSED_CAP_FRACTION:.0%} of ${TOTAL_BUDGET:,.0f}K total)"
)
