"""Ad spend allocation (prescriptive optimization) template.

This script demonstrates an end-to-end mixed-integer linear optimization (MILP)
workflow in RelationalAI:

- Load sample CSVs describing marketing channels, campaigns, and channel-campaign
    effectiveness (conversion rate).
- Model those entities as *concepts* with typed properties.
- Create an `Allocation` decision concept with two decision variables per
    channel-campaign pair:
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

import pandas

pandas.options.future.infer_string = False
from pandas import read_csv
from relationalai.semantics import Model, data, require, select, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

DATA_DIR = Path(__file__).parent / "data"

# Create a Semantics model container.
model = Model("ad_spend", use_lqp=False)

# --------------------------------------------------
# Define ontology & load data
# --------------------------------------------------

Channel = model.Concept("Channel")
Channel.id = model.Property("{Channel} has {id:int}")
Channel.name = model.Property("{Channel} has {name:string}")
Channel.min_spend = model.Property("{Channel} has {min_spend:float}")
Channel.max_spend = model.Property("{Channel} has {max_spend:float}")
Channel.roi_coefficient = model.Property("{Channel} has {roi_coefficient:float}")
data(read_csv(DATA_DIR / "channels.csv")).into(Channel, keys=["id"])

Campaign = model.Concept("Campaign")
Campaign.id = model.Property("{Campaign} has {id:int}")
Campaign.name = model.Property("{Campaign} has {name:string}")
Campaign.budget = model.Property("{Campaign} has {budget:float}")
Campaign.target_conversions = model.Property("{Campaign} has {target_conversions:int}")
data(read_csv(DATA_DIR / "campaigns.csv")).into(Campaign, keys=["id"])

Effectiveness = model.Concept("Effectiveness")
Effectiveness.channel = model.Property("{Effectiveness} via {channel:Channel}")
Effectiveness.campaign = model.Property("{Effectiveness} for {campaign:Campaign}")
Effectiveness.conversion_rate = model.Property(
    "{Effectiveness} has {conversion_rate:float}"
)

eff_data = data(read_csv(DATA_DIR / "effectiveness.csv"))
where(Channel.id == eff_data.channel_id, Campaign.id == eff_data.campaign_id).define(
    Effectiveness.new(
        channel=Channel, campaign=Campaign, conversion_rate=eff_data.conversion_rate
    )
)

# --------------------------------------------------
# Model the problem
# --------------------------------------------------

Allocation = model.Concept("Allocation")
Allocation.effectiveness = model.Property(
    "{Allocation} uses {effectiveness:Effectiveness}"
)
Allocation.spend = model.Property("{Allocation} has {spend:float}")
Allocation.active = model.Property("{Allocation} is {active:float}")
model.define(Allocation.new(effectiveness=Effectiveness))

# Parameters
# (none beyond scenario parameter)

# Scenarios (what-if analysis)
SCENARIO_PARAM = "total_budget"
SCENARIO_VALUES = [35000, 45000, 55000]

# --------------------------------------------------
# Solve with Scenario Analysis (Numeric Parameter)
# --------------------------------------------------

scenario_results = []

for scenario_value in SCENARIO_VALUES:
    print(f"\nRunning scenario: {SCENARIO_PARAM} = {scenario_value}")

    # Set scenario parameter value
    total_budget = scenario_value

    # Create fresh SolverModel for each scenario
    solver_model = SolverModel(model, "cont")

    # Variable: spend (continuous, >= 0)
    solver_model.solve_for(
        Allocation.spend,
        name=[
            "spend",
            Allocation.effectiveness.channel.name,
            Allocation.effectiveness.campaign.name,
        ],
        lower=0,
    )

    # Variable: active (binary 0/1)
    solver_model.solve_for(
        Allocation.active,
        type="bin",
        name=[
            "active",
            Allocation.effectiveness.channel.name,
            Allocation.effectiveness.campaign.name,
        ],
    )

    # Constraint: spend bounded by per-channel min/max when active
    min_spend_bound = require(
        Allocation.spend >= Allocation.effectiveness.channel.min_spend * Allocation.active
    )
    solver_model.satisfy(min_spend_bound)

    max_spend_bound = require(
        Allocation.spend <= Allocation.effectiveness.channel.max_spend * Allocation.active
    )
    solver_model.satisfy(max_spend_bound)

    # Constraint: per-campaign budget across all channels
    campaign_spend = (
        sum(Allocation.spend)
        .where(Allocation.effectiveness.campaign == Campaign)
        .per(Campaign)
    )
    budget_limit = require(campaign_spend <= Campaign.budget)
    solver_model.satisfy(budget_limit)

    # Constraint: require at least one active channel per campaign
    campaign_channels = (
        sum(Allocation.active)
        .where(Allocation.effectiveness.campaign == Campaign)
        .per(Campaign)
    )
    min_channels = require(campaign_channels >= 1)
    solver_model.satisfy(min_channels)

    # Constraint: total budget across all campaigns (scenario parameter)
    total_budget_limit = require(sum(Allocation.spend) <= total_budget)
    solver_model.satisfy(total_budget_limit)

    # Objective: maximize total expected conversions
    total_conversions = sum(Allocation.spend * Allocation.effectiveness.conversion_rate)
    solver_model.maximize(total_conversions)

    solver_backend = Solver("highs")
    solver_model.solve(solver_backend, time_limit_sec=60)

    scenario_results.append({
        "scenario": scenario_value,
        "status": str(solver_model.termination_status),
        "objective": solver_model.objective_value,
    })
    print(f"  Status: {solver_model.termination_status}, Objective: {solver_model.objective_value}")

    # Print spend allocation from solver results
    var_df = solver_model.variable_values().to_df()
    spend_df = var_df[var_df["name"].str.startswith("spend") & (var_df["float"] > 0.001)].rename(columns={"float": "value"})
    print(f"\n  Spend allocation:")
    print(spend_df.to_string(index=False))

# Summary
print("\n" + "=" * 50)
print("Scenario Analysis Summary")
print("=" * 50)
for result in scenario_results:
    print(f"  {result['scenario']}: {result['status']}, obj={result['objective']}")
