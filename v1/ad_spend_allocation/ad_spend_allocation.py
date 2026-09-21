"""Ad spend allocation (prescriptive optimization) template.

This script demonstrates a mixed-integer linear optimization (MILP) workflow
in RelationalAI:

- Load sample CSVs describing marketing channels, campaigns, and channel-campaign
  effectiveness (conversion rate).
- Model those entities as *concepts* with typed properties.
- Create an `Allocation` decision concept with two decision variables per
  channel-campaign pair: `spend` (continuous) and `active` (binary).
- Add constraints for channel min/max spend (when active), per-campaign budget,
  and "at least one channel per campaign" coverage.
- Maximize total expected conversions: sum(spend * conversion_rate).
- Run scenario analysis over different total budget levels using Scenario as a
  first-class Concept (single solve, all scenarios simultaneously).

Modeling approach:
- Scenario is a Concept with a total_budget parameter property.
- Decision variables are multi-argument Properties indexed by (Allocation, Scenario).
- Constraints use ref() bindings + .per(Scenario) to scope per-scenario.
- One solve handles all budget levels; results extracted via model.select().

Run:
    `python ad_spend_allocation.py`

Output:
    Prints the solver termination status, objective value, and a table of
    non-trivial allocations for each budget scenario.
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

model = Model("ad_spend")
Concept, Property = model.Concept, model.Property

# Channel concept: marketing channels with spend bounds and ROI coefficient.
Channel = Concept("Channel", identify_by={"id": Integer})
Channel.name = Property(f"{Channel} has {String:name}")
Channel.min_spend = Property(f"{Channel} has {Float:min_spend}")
Channel.max_spend = Property(f"{Channel} has {Float:max_spend}")
Channel.roi_coefficient = Property(f"{Channel} has {Float:roi_coefficient}")

# Load channels from CSV.
channel_csv = read_csv(DATA_DIR / "channels.csv")
model.define(Channel.new(model.data(channel_csv).to_schema()))

# Campaign concept: campaigns with budgets and conversion targets.
Campaign = Concept("Campaign", identify_by={"id": Integer})
Campaign.name = Property(f"{Campaign} has {String:name}")
Campaign.budget = Property(f"{Campaign} has {Float:budget}")
Campaign.target_conversions = Property(f"{Campaign} has {Integer:target_conversions}")

# Load campaigns from CSV.
campaign_csv = read_csv(DATA_DIR / "campaigns.csv")
model.define(Campaign.new(model.data(campaign_csv).to_schema()))

# Effectiveness concept: conversion rate for each channel-campaign pair.
Effectiveness = Concept("Effectiveness", identify_by={"channel_id": Integer, "campaign_id": Integer})
Effectiveness.channel = Property(f"{Effectiveness} via {Channel}")
Effectiveness.campaign = Property(f"{Effectiveness} for {Campaign}")
Effectiveness.conversion_rate = Property(f"{Effectiveness} has {Float:conversion_rate}")

# Load effectiveness pairs from CSV and link to Channel/Campaign.
eff_csv = read_csv(DATA_DIR / "effectiveness.csv")
eff_data = model.data(eff_csv)
model.define(
    e := Effectiveness.new(channel_id=eff_data.channel_id, campaign_id=eff_data.campaign_id),
    e.conversion_rate(eff_data.conversion_rate),
)
model.define(Effectiveness.channel(Channel)).where(Effectiveness.channel_id == Channel.id)
model.define(Effectiveness.campaign(Campaign)).where(Effectiveness.campaign_id == Campaign.id)

# --------------------------------------------------
# Scenario Concept — total_budget parameter variations
# --------------------------------------------------

Scenario = Concept("Scenario", identify_by={"name": String})
Scenario.total_budget = Property(f"{Scenario} has {Float:total_budget}")
scenario_data = model.data(
    [("budget_35k", 35000), ("budget_45k", 45000), ("budget_55k", 55000)],
    columns=["name", "total_budget"],
)
model.define(Scenario.new(scenario_data.to_schema()))

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

# Decision concept: spend allocation per channel-campaign pair
Allocation = Concept("Allocation", identify_by={"effectiveness": Effectiveness})
model.define(Allocation.new(effectiveness=Effectiveness))

# Decision variables — indexed by Scenario (multi-argument Properties)
Allocation.x_spend = Property(f"{Allocation} in {Scenario} has {Float:spend}")
Allocation.x_active = Property(f"{Allocation} in {Scenario} is {Float:active}")

# Refs for binding multi-arg variables in constraints
x_spend = Float.ref()
x_active = Float.ref()

problem = Problem(model, Float)

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
).require(sum(x_spend).where(Allocation.effectiveness.campaign == Campaign).per(Campaign, Scenario) <= Campaign.budget))

# Constraint: require at least one active channel per campaign (per scenario)
problem.satisfy(model.where(
    Allocation.x_active(Scenario, x_active),
    Allocation.effectiveness.campaign(Campaign),
).require(sum(x_active).where(Allocation.effectiveness.campaign == Campaign).per(Campaign, Scenario) >= 1))

# Constraint: total budget across all campaigns (per scenario)
problem.satisfy(model.where(
    Allocation.x_spend(Scenario, x_spend),
).require(sum(x_spend).per(Scenario) <= Scenario.total_budget))

# Objective: maximize total expected conversions
problem.maximize(
    sum(x_spend * Allocation.effectiveness.conversion_rate)
    .where(Allocation.x_spend(Scenario, x_spend))
)

# --------------------------------------------------
# Solve (single solve for all scenarios)
# --------------------------------------------------

problem.display()
problem.solve("highs", time_limit_sec=60)
model.require(problem.termination_status() == "OPTIMAL")
problem.solve_info().display()

# --------------------------------------------------
# Extract results per scenario
# --------------------------------------------------

print("\nSpend allocation per scenario:")
model.select(
    Scenario.name.alias("scenario"),
    Allocation.effectiveness.channel.name.alias("channel"),
    Allocation.effectiveness.campaign.name.alias("campaign"),
    x_spend.alias("spend"),
).where(
    Allocation.x_spend(Scenario, x_spend), x_spend > 0.001
).inspect()
