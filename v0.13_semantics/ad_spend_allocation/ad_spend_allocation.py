# ad spend allocation problem:
# allocate budget across channels to maximize conversions

from pathlib import Path

from pandas import read_csv

from relationalai.semantics import Model, data, define, require, select, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

model = Model("ad_spend", config=globals().get("config", None), use_lqp=False)

# --------------------------------------------------
# Define ontology & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Concept: channels with spend limits and ROI
Channel = model.Concept("Channel")
Channel.id = model.Property("{Channel} has {id:int}")
Channel.name = model.Property("{Channel} has {name:string}")
Channel.min_spend = model.Property("{Channel} has {min_spend:float}")
Channel.max_spend = model.Property("{Channel} has {max_spend:float}")
Channel.roi_coefficient = model.Property("{Channel} has {roi_coefficient:float}")
data(read_csv(data_dir / "channels.csv")).into(Channel, keys=["id"])

# Concept: campaigns with budget and conversion targets
Campaign = model.Concept("Campaign")
Campaign.id = model.Property("{Campaign} has {id:int}")
Campaign.name = model.Property("{Campaign} has {name:string}")
Campaign.budget = model.Property("{Campaign} has {budget:float}")
Campaign.target_conversions = model.Property("{Campaign} has {target_conversions:int}")
data(read_csv(data_dir / "campaigns.csv")).into(Campaign, keys=["id"])

# Relationship: effectiveness rates for each channel/campaign combination
Effectiveness = model.Concept("Effectiveness")
Effectiveness.channel = model.Property("{Effectiveness} via {channel:Channel}")
Effectiveness.campaign = model.Property("{Effectiveness} for {campaign:Campaign}")
Effectiveness.conversion_rate = model.Property("{Effectiveness} has {conversion_rate:float}")

eff_data = data(read_csv(data_dir / "effectiveness.csv"))
where(Channel.id(eff_data.channel_id), Campaign.id(eff_data.campaign_id)).define(
    Effectiveness.new(channel=Channel, campaign=Campaign, conversion_rate=eff_data.conversion_rate)
)

# --------------------------------------------------
# Model the problem
# --------------------------------------------------

# Decision concept: spend allocations per channel/campaign
Allocation = model.Concept("Allocation")
Allocation.effectiveness = model.Property("{Allocation} uses {effectiveness:Effectiveness}")
Allocation.spend = model.Property("{Allocation} has {spend:float}")
Allocation.active = model.Property("{Allocation} is {active:float}")
define(Allocation.new(effectiveness=Effectiveness))

Alloc = Allocation.ref()

s = SolverModel(model, "cont")

# Variable: spend and active
s.solve_for(Allocation.spend, name=["spend", Allocation.effectiveness.channel.name, Allocation.effectiveness.campaign.name], lower=0)
s.solve_for(Allocation.active, type="bin", name=["active", Allocation.effectiveness.channel.name, Allocation.effectiveness.campaign.name])

# Constraint: spend bounded by min/max when active
min_spend_bound = require(Allocation.spend >= Allocation.effectiveness.channel.min_spend * Allocation.active)
s.satisfy(min_spend_bound)

max_spend_bound = require(Allocation.spend <= Allocation.effectiveness.channel.max_spend * Allocation.active)
s.satisfy(max_spend_bound)

# Constraint: total spend per campaign cannot exceed budget
campaign_spend = sum(Alloc.spend).where(Alloc.effectiveness.campaign == Campaign).per(Campaign)
budget_limit = require(campaign_spend <= Campaign.budget)
s.satisfy(budget_limit)

# Constraint: at least one channel per campaign
campaign_channels = sum(Alloc.active).where(Alloc.effectiveness.campaign == Campaign).per(Campaign)
min_channels = require(campaign_channels >= 1)
s.satisfy(min_channels)

# Objective: maximize total conversions
total_conversions = sum(Allocation.spend * Allocation.effectiveness.conversion_rate)
s.maximize(total_conversions)

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

solver = Solver("highs")
s.solve(solver, time_limit_sec=60)

print(f"Status: {s.termination_status}")
print(f"Total expected conversions: {s.objective_value:.0f}")

allocations = select(
    Allocation.effectiveness.channel.name.alias("channel"),
    Allocation.effectiveness.campaign.name.alias("campaign"),
    Allocation.spend
).where(Allocation.spend > 0.001).to_df()

print("\nSpend allocation:")
print(allocations.to_string(index=False))
