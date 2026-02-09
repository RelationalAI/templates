"""Ad spend allocation (prescriptive optimization) template.

This script demonstrates an end-to-end mixed-integer linear optimization (MILP)
workflow in RelationalAI:

- Load sample CSVs describing marketing channels, campaigns, and channel–campaign
    effectiveness (conversion rate).
- Model those entities as *concepts* with typed properties.
- Create an `Allocation` decision concept with two decision variables per
    channel–campaign pair:
    - `spend` (continuous, $>= 0$)
    - `active` (binary 0/1)
- Add constraints for channel min/max spend (when active), per-campaign budget,
    and "at least one channel per campaign" coverage.
- Maximize total expected conversions: sum(spend * conversion_rate).

Run:
    `python ad_spend_allocation.py`

Output:
    Prints the solver termination status, objective value, and a table of
    non-trivial allocations.
"""

from pathlib import Path

from pandas import read_csv as pd_read_csv

from relationalai.semantics import Model, data, sum, where, require, select
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

def read_csv(path):
    """Read CSV with RAI-compatible dtypes.

    Pandas may use StringDtype for string columns, but RAI's data().into()
    requires object dtype. This function ensures compatibility.
    """
    df = pd_read_csv(path)
    # Convert StringDtype to object for RAI compatibility
    string_cols = df.select_dtypes("string").columns
    if len(string_cols) > 0:
        df = df.astype({col: "object" for col in string_cols})
    return df

# Create a Semantics model container. (This template uses direct compilation
# rather than LQP; keeping it explicit makes template behavior stable.)
model = Model("ad_spend", use_lqp=False)

# --------------------------------------------------
# Define ontology & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# `Channel`: marketing channel with spend bounds (and an extra ROI field kept to
# show how additional attributes can live alongside the optimization inputs).
Channel = model.Concept("Channel")
Channel.id = model.Property("{Channel} has {id:int}")
Channel.name = model.Property("{Channel} has {name:string}")
Channel.min_spend = model.Property("{Channel} has {min_spend:float}")
Channel.max_spend = model.Property("{Channel} has {max_spend:float}")
Channel.roi_coefficient = model.Property("{Channel} has {roi_coefficient:float}")
data(read_csv(data_dir / "channels.csv")).into(Channel, keys=["id"])

# `Campaign`: each campaign has a total budget across all channels.
# `target_conversions` is loaded as an example attribute; it is not used as a
# constraint in this template.
Campaign = model.Concept("Campaign")
Campaign.id = model.Property("{Campaign} has {id:int}")
Campaign.name = model.Property("{Campaign} has {name:string}")
Campaign.budget = model.Property("{Campaign} has {budget:float}")
Campaign.target_conversions = model.Property("{Campaign} has {target_conversions:int}")
data(read_csv(data_dir / "campaigns.csv")).into(Campaign, keys=["id"])

# `Effectiveness`: one row per (channel, campaign) with an expected conversion rate.
Effectiveness = model.Concept("Effectiveness")
Effectiveness.channel = model.Property("{Effectiveness} via {channel:Channel}")
Effectiveness.campaign = model.Property("{Effectiveness} for {campaign:Campaign}")
Effectiveness.conversion_rate = model.Property("{Effectiveness} has {conversion_rate:float}")

eff_data = data(read_csv(data_dir / "effectiveness.csv"))
where(
    Channel.id == eff_data.channel_id,
    Campaign.id == eff_data.campaign_id
).define(
    # Create one `Effectiveness` instance per CSV row, resolving the foreign keys
    # into actual `Channel` and `Campaign` concept instances.
    Effectiveness.new(channel=Channel, campaign=Campaign, conversion_rate=eff_data.conversion_rate)
)

# --------------------------------------------------
# Model the problem
# --------------------------------------------------

# `Allocation`: decision concept (one allocation per effectiveness row).
Allocation = model.Concept("Allocation")
Allocation.effectiveness = model.Property("{Allocation} uses {effectiveness:Effectiveness}")
Allocation.spend = model.Property("{Allocation} has {spend:float}")
Allocation.active = model.Property("{Allocation} is {active:float}")
model.define(Allocation.new(effectiveness=Effectiveness))

solver_model = SolverModel(model, "cont")

# Decision variables.
# The `name=[...]` metadata is used to label variables in solver model. These show up if you print the solver model
# and are helpful for debugging.

# `spend` is continuous with a lower bound of 0.
solver_model.solve_for(
    Allocation.spend,
    name=["spend", Allocation.effectiveness.channel.name, Allocation.effectiveness.campaign.name],
    lower=0
)

# `active` is a binary variable (0 or 1) that indicates whether the channel–campaign pair is active.
solver_model.solve_for(
    Allocation.active,
    type="bin",
    name=["active", Allocation.effectiveness.channel.name, Allocation.effectiveness.campaign.name]
)

# Constraint: spend bounded by per-channel min/max *only when active*.
# If `active = 0`, both bounds force `spend = 0`.
min_spend_bound = require(Allocation.spend >= Allocation.effectiveness.channel.min_spend * Allocation.active)
solver_model.satisfy(min_spend_bound)

max_spend_bound = require(Allocation.spend <= Allocation.effectiveness.channel.max_spend * Allocation.active)
solver_model.satisfy(max_spend_bound)

# Constraint: per-campaign budget across all channels.
campaign_spend = sum(Allocation.spend).where(Allocation.effectiveness.campaign == Campaign).per(Campaign)
budget_limit = require(campaign_spend <= Campaign.budget)
solver_model.satisfy(budget_limit)

# Constraint: require at least one active channel per campaign.
campaign_channels = sum(Allocation.active).where(Allocation.effectiveness.campaign == Campaign).per(Campaign)
min_channels = require(campaign_channels >= 1)
solver_model.satisfy(min_channels)

# Objective: maximize total expected conversions.
total_conversions = sum(Allocation.spend * Allocation.effectiveness.conversion_rate)
solver_model.maximize(total_conversions)

# --------------------------------------------------
# Solve and print a readable solution
# --------------------------------------------------

solver_backend = Solver("highs")
solver_model.solve(solver_backend, time_limit_sec=60)

print(f"Status: {solver_model.termination_status}")
print(f"Total expected conversions: {solver_model.objective_value:.0f}")

allocations = select(
    Allocation.effectiveness.channel.name.alias("channel"),
    Allocation.effectiveness.campaign.name.alias("campaign"),
    Allocation.active.alias("active?"),
    Allocation.spend
).where(
    # Hide zero allocations to keep the output compact.
    Allocation.spend > 0.001
).to_df()

print("\nSpend allocation:")
print(allocations.to_string(index=False))
