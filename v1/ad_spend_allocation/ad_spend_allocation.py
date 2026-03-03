# ad spend allocation problem:
# allocate budget across channels and campaigns to maximize conversions

from pathlib import Path

from pandas import read_csv

from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("ad_spend")
Concept, Property = model.Concept, model.Property

# --------------------------------------------------
# Define ontology & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Concept: marketing channels with spend bounds
Channel = Concept("Channel", identify_by={"id": Integer})
Channel.name = Property(f"{Channel} has {String:name}")
Channel.min_spend = Property(f"{Channel} has {Float:min_spend}")
Channel.max_spend = Property(f"{Channel} has {Float:max_spend}")
Channel.roi_coefficient = Property(f"{Channel} has {Float:roi_coefficient}")
channel_csv = read_csv(data_dir / "channels.csv")
model.define(Channel.new(model.data(channel_csv).to_schema()))

# Concept: campaigns with budgets
Campaign = Concept("Campaign", identify_by={"id": Integer})
Campaign.name = Property(f"{Campaign} has {String:name}")
Campaign.budget = Property(f"{Campaign} has {Float:budget}")
Campaign.target_conversions = Property(f"{Campaign} has {Integer:target_conversions}")
campaign_csv = read_csv(data_dir / "campaigns.csv")
model.define(Campaign.new(model.data(campaign_csv).to_schema()))

# Relationship: conversion rate for each channel-campaign pair
Effectiveness = Concept("Effectiveness", identify_by={"channel_id": Integer, "campaign_id": Integer})
Effectiveness.channel = Property(f"{Effectiveness} via {Channel}")
Effectiveness.campaign = Property(f"{Effectiveness} for {Campaign}")
Effectiveness.conversion_rate = Property(f"{Effectiveness} has {Float:conversion_rate}")

eff_csv = read_csv(data_dir / "effectiveness.csv")
eff_data = model.data(eff_csv)
model.define(
    e := Effectiveness.new(channel_id=eff_data.channel_id, campaign_id=eff_data.campaign_id),
    e.conversion_rate(eff_data.conversion_rate),
)
model.define(Effectiveness.channel(Channel)).where(Effectiveness.channel_id == Channel.id)
model.define(Effectiveness.campaign(Campaign)).where(Effectiveness.campaign_id == Campaign.id)

# --------------------------------------------------
# Model the problem
# --------------------------------------------------

# Decision concept: spend allocation per channel-campaign pair
Allocation = Concept("Allocation", identify_by={"effectiveness": Effectiveness})
Allocation.x_spend = Property(f"{Allocation} has {Float:spend}")
Allocation.x_active = Property(f"{Allocation} is {Float:active}")
model.define(Allocation.new(effectiveness=Effectiveness))

# Parameters
total_budget = 45000

def build_formulation(s):
    """Register variables, constraints, and objective on the problem."""
    # Variables
    s.solve_for(Allocation.x_spend, name=["spend", Allocation.effectiveness.channel.name, Allocation.effectiveness.campaign.name], lower=0)
    s.solve_for(Allocation.x_active, type="bin", name=["active", Allocation.effectiveness.channel.name, Allocation.effectiveness.campaign.name])

    # Constraint: minimum spend per channel when active
    min_spend_bound = model.require(Allocation.x_spend >= Allocation.effectiveness.channel.min_spend * Allocation.x_active)
    s.satisfy(min_spend_bound)

    # Constraint: maximum spend per channel when active
    max_spend_bound = model.require(Allocation.x_spend <= Allocation.effectiveness.channel.max_spend * Allocation.x_active)
    s.satisfy(max_spend_bound)

    # Constraint: per-campaign budget across all channels
    campaign_spend = sum(Allocation.x_spend).where(Allocation.effectiveness.campaign == Campaign).per(Campaign)
    budget_limit = model.require(campaign_spend <= Campaign.budget)
    s.satisfy(budget_limit)

    # Constraint: require at least one active channel per campaign
    campaign_channels = sum(Allocation.x_active).where(Allocation.effectiveness.campaign == Campaign).per(Campaign)
    min_channels = model.require(campaign_channels >= 1)
    s.satisfy(min_channels)

    # Constraint: total budget across all campaigns (scenario parameter)
    total_budget_limit = model.require(sum(Allocation.x_spend) <= total_budget)
    s.satisfy(total_budget_limit)

    # Objective: maximize total expected conversions
    total_conversions = sum(Allocation.x_spend * Allocation.effectiveness.conversion_rate)
    s.maximize(total_conversions)

# Scenarios (what-if analysis)
SCENARIO_PARAM = "total_budget"
SCENARIO_VALUES = [35000, 45000, 55000]

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

scenario_results = []

for scenario_value in SCENARIO_VALUES:
    print(f"\nRunning scenario: {SCENARIO_PARAM} = {scenario_value}")

    # Set scenario parameter value
    total_budget = scenario_value

    # Create fresh Problem for each scenario
    s = Problem(model, Float)
    build_formulation(s)

    s.display()
    s.solve("highs", time_limit_sec=60, _server_side_import=False)
    s.display_solve_info()

    scenario_results.append({
        "scenario": scenario_value,
        "status": str(s.termination_status),
        "objective": s.objective_value,
    })
    print(f"  Status: {s.termination_status}, Objective: {s.objective_value}")

    # Print spend allocation from solver results
    var_df = s.variable_values().to_df()
    spend_df = var_df[var_df["name"].str.startswith("spend") & (var_df["value"] > 0.001)]
    print(f"\n  Spend allocation:")
    print(spend_df.to_string(index=False))

# Summary
print("\n" + "=" * 50)
print("Scenario Analysis Summary")
print("=" * 50)
for result in scenario_results:
    print(f"  {result['scenario']}: {result['status']}, obj={result['objective']}")
