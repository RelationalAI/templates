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
from pandas import read_csv

from relationalai.semantics import Model, data, require, select, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

DATA_DIR = Path(__file__).parent / "data"

# Disable pandas inference of string types. This ensures that string columns
# in the CSVs are loaded as object dtype. This is only required when using
# relationalai versions prior to v1.0.
pandas.options.future.infer_string = False

# --------------------------------------------------
# Define the semantic model & load data
# --------------------------------------------------

# Create a Semantics model container.
model = Model("ad_spend", config=globals().get("config", None), use_lqp=False)

# Channel concept: marketing channel with spend bounds (and an extra ROI field
# kept to show how additional attributes can live alongside the optimization inputs).
Channel = model.Concept("Channel")
Channel.id = model.Property("{Channel} has {id:int}")
Channel.name = model.Property("{Channel} has {name:string}")
Channel.min_spend = model.Property("{Channel} has {min_spend:float}")
Channel.max_spend = model.Property("{Channel} has {max_spend:float}")
Channel.roi_coefficient = model.Property("{Channel} has {roi_coefficient:float}")

# Load channels from CSV. The `keys` argument specifies the unique identifier for
# the concept. The .into() method will create one Channel entity per row in
# the CSV, using the specified keys to ensure uniqueness. Other properties are
# populated based on the column names in the CSV matching the property declarations.
data(read_csv(DATA_DIR / "channels.csv")).into(Channel, keys=["id"])

# Campaign concept: each campaign has a total budget across all channels.
# target_conversions is loaded as an example attribute; it is not used as a
# constraint in this template.
Campaign = model.Concept("Campaign")
Campaign.id = model.Property("{Campaign} has {id:int}")
Campaign.name = model.Property("{Campaign} has {name:string}")
Campaign.budget = model.Property("{Campaign} has {budget:float}")
Campaign.target_conversions = model.Property("{Campaign} has {target_conversions:int}")

# Load campaigns from CSV data.
data(read_csv(DATA_DIR / "campaigns.csv")).into(Campaign, keys=["id"])

# Effectiveness concept: models the conversion rate for each channel-campaign pair.
# This is the key input that links channels and campaigns and allows us to model
# the optimization problem. In a real-world scenario, this could be derived from
# historical data or A/B tests rather than loaded from a CSV.
Effectiveness = model.Concept("Effectiveness")
Effectiveness.channel = model.Property("{Effectiveness} via {channel:Channel}")
Effectiveness.campaign = model.Property("{Effectiveness} for {campaign:Campaign}")
Effectiveness.conversion_rate = model.Property("{Effectiveness} has {conversion_rate:float}")

# Load effectiveness data from CSV.
eff_data = data(read_csv(DATA_DIR / "effectiveness.csv"))

# Define Effectiveness entities by joining the CSV data with the Channel and
# Campaign concepts.
where(
    Channel.id == eff_data.channel_id,
    Campaign.id == eff_data.campaign_id
).define(
    Effectiveness.new(channel=Channel, campaign=Campaign, conversion_rate=eff_data.conversion_rate)
)

# --------------------------------------------------
# Model the decision problems
# --------------------------------------------------

# Allocation concept: represents the decision variables for how much to spend on each
# channel-campaign pair. Each Allocation is linked to an Effectiveness entity, which
# provides the conversion rate for that channel-campaign pair. The `spend` and
# `active` properties represent the decision variables that the solver will determine.
Allocation = model.Concept("Allocation")
Allocation.effectiveness = model.Property("{Allocation} uses {effectiveness:Effectiveness}")
Allocation.spend = model.Property("{Allocation} has {spend:float}")
Allocation.active = model.Property("{Allocation} is {active:float}")

# Define Allocation entities.
model.define(Allocation.new(effectiveness=Effectiveness))

# Parameters
total_budget = 45000


def build_formulation(s):
    """Register variables, constraints, and objective on the solver model."""
    # Variable: spend (continuous, >= 0)
    s.solve_for(
        Allocation.spend,
        name=[
            "spend",
            Allocation.effectiveness.channel.name,
            Allocation.effectiveness.campaign.name,
        ],
        lower=0,
    )

    # Variable: active (binary 0/1)
    s.solve_for(
        Allocation.active,
        type="bin",
        name=[
            "active",
            Allocation.effectiveness.channel.name,
            Allocation.effectiveness.campaign.name,
        ],
    )

    # Constraint: minimum spend per channel when active
    min_spend_bound = require(
        Allocation.spend >= Allocation.effectiveness.channel.min_spend * Allocation.active
    )
    s.satisfy(min_spend_bound)

    # Constraint: maximum spend per channel when active
    max_spend_bound = require(
        Allocation.spend <= Allocation.effectiveness.channel.max_spend * Allocation.active
    )
    s.satisfy(max_spend_bound)

    # Constraint: per-campaign budget across all channels
    campaign_spend = (
        sum(Allocation.spend)
        .where(Allocation.effectiveness.campaign == Campaign)
        .per(Campaign)
    )
    budget_limit = require(campaign_spend <= Campaign.budget)
    s.satisfy(budget_limit)

    # Constraint: require at least one active channel per campaign
    campaign_channels = (
        sum(Allocation.active)
        .where(Allocation.effectiveness.campaign == Campaign)
        .per(Campaign)
    )
    min_channels = require(campaign_channels >= 1)
    s.satisfy(min_channels)

    # Constraint: total budget across all campaigns (scenario parameter)
    total_budget_limit = require(sum(Allocation.spend) <= total_budget)
    s.satisfy(total_budget_limit)

    # Objective: maximize total expected conversions
    total_conversions = sum(Allocation.spend * Allocation.effectiveness.conversion_rate)
    s.maximize(total_conversions)


s = SolverModel(model, "cont")
build_formulation(s)

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

    # Create fresh SolverModel for each scenario
    s = SolverModel(model, "cont")
    build_formulation(s)

    # Solve the model with a time limit of 60 seconds. The `Solver` class provides
    # an interface to various optimization solvers. Here we use the open-source
    # HiGHS solver, which is suitable for linear and mixed-integer problems.
    solver_backend = Solver("highs")
    s.solve(solver_backend, time_limit_sec=60)

    scenario_results.append({
        "scenario": scenario_value,
        "status": str(s.termination_status),
        "objective": s.objective_value,
    })
    print(f"  Status: {s.termination_status}, Objective: {s.objective_value}")

    # Print spend allocation from solver results
    var_df = s.variable_values().to_df()
    spend_df = var_df[var_df["name"].str.startswith("spend") & (var_df["float"] > 0.001)].rename(columns={"float": "value"})
    print(f"\n  Spend allocation:")
    print(spend_df.to_string(index=False))

# Summary
print("\n" + "=" * 50)
print("Scenario Analysis Summary")
print("=" * 50)
for result in scenario_results:
    print(f"  {result['scenario']}: {result['status']}, obj={result['objective']}")
