"""Ad Spend Allocation - Allocate budget across channels to maximize conversions."""

from pathlib import Path
from time import time_ns

from pandas import read_csv
from relationalai.semantics import Model, data, define, require, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel


def define_model(config=None):
    """Define base model with Channel, Campaign, and Effectiveness concepts."""
    model = Model(f"ad_spend_{time_ns()}", config=config, use_lqp=False)

    # Concepts
    Channel = model.Concept("Channel")
    Channel.id = model.Property("{Channel} has {id:int}")
    Channel.name = model.Property("{Channel} has {name:string}")
    Channel.min_spend = model.Property("{Channel} has {min_spend:float}")
    Channel.max_spend = model.Property("{Channel} has {max_spend:float}")
    Channel.roi_coefficient = model.Property("{Channel} has {roi_coefficient:float}")

    Campaign = model.Concept("Campaign")
    Campaign.id = model.Property("{Campaign} has {id:int}")
    Campaign.name = model.Property("{Campaign} has {name:string}")
    Campaign.budget = model.Property("{Campaign} has {budget:float}")
    Campaign.target_conversions = model.Property("{Campaign} has {target_conversions:int}")

    Effectiveness = model.Concept("Effectiveness")
    Effectiveness.channel = model.Property("{Effectiveness} via {channel:Channel}")
    Effectiveness.campaign = model.Property("{Effectiveness} for {campaign:Campaign}")
    Effectiveness.conversion_rate = model.Property("{Effectiveness} has {conversion_rate:float}")

    # Load data
    data_dir = Path(__file__).parent / "data"

    channels_df = read_csv(data_dir / "channels.csv")
    data(channels_df).into(Channel, keys=["id"])

    campaigns_df = read_csv(data_dir / "campaigns.csv")
    data(campaigns_df).into(Campaign, keys=["id"])

    eff_df = read_csv(data_dir / "effectiveness.csv")
    eff_data = data(eff_df)
    where(Channel.id(eff_data.channel_id), Campaign.id(eff_data.campaign_id)).define(
        Effectiveness.new(channel=Channel, campaign=Campaign, conversion_rate=eff_data.conversion_rate)
    )

    # Allocation: decision variable for spend per channel/campaign
    Allocation = model.Concept("Allocation")
    Allocation.effectiveness = model.Property("{Allocation} uses {effectiveness:Effectiveness}")
    Allocation.spend = model.Property("{Allocation} has {spend:float}")
    Allocation.active = model.Property("{Allocation} is {active:float}")
    define(Allocation.new(effectiveness=Effectiveness))

    model.Channel, model.Campaign, model.Effectiveness, model.Allocation = Channel, Campaign, Effectiveness, Allocation
    return model


def define_problem(model):
    """Define decision variables, constraints, and objective."""
    s = SolverModel(model, "cont")
    Channel, Campaign, Effectiveness, Allocation = model.Channel, model.Campaign, model.Effectiveness, model.Allocation

    # Decision variable: continuous spend amount
    s.solve_for(Allocation.spend, name=["spend", Allocation.effectiveness.channel.name, Allocation.effectiveness.campaign.name], lower=0)

    # Decision variable: binary indicator for whether channel is used for campaign
    s.solve_for(Allocation.active, type="bin", name=["active", Allocation.effectiveness.channel.name, Allocation.effectiveness.campaign.name])

    # Constraint: spend bounded by min/max when active
    s.satisfy(require(Allocation.spend >= Allocation.effectiveness.channel.min_spend * Allocation.active))
    s.satisfy(require(Allocation.spend <= Allocation.effectiveness.channel.max_spend * Allocation.active))

    # Constraint: total spend per campaign cannot exceed budget
    Alloc = Allocation.ref()
    campaign_spend = sum(Alloc.spend).where(Alloc.effectiveness.campaign == Campaign).per(Campaign)
    s.satisfy(require(campaign_spend <= Campaign.budget))

    # Constraint: at least one channel per campaign
    campaign_channels = sum(Alloc.active).where(Alloc.effectiveness.campaign == Campaign).per(Campaign)
    s.satisfy(require(campaign_channels >= 1))

    # Objective: maximize total conversions (spend * conversion_rate)
    total_conversions = sum(Allocation.spend * Allocation.effectiveness.conversion_rate)
    s.maximize(total_conversions)

    return s


def solve(config=None, solver_name="highs"):
    """Orchestrate model, problem, and solver execution."""
    model = define_model(config)
    solver_model = define_problem(model)
    solver = Solver(solver_name)
    solver_model.solve(solver, time_limit_sec=60)
    return solver_model


def extract_solution(solver_model):
    """Extract solution as dict with metadata."""
    return {
        "status": solver_model.termination_status,
        "objective": solver_model.objective_value,
        "variables": solver_model.variable_values().to_df(),
    }


if __name__ == "__main__":
    sm = solve()
    sol = extract_solution(sm)

    print(f"Status: {sol['status']}")
    print(f"Total expected conversions: {sol['objective']:.0f}")
    print("\nSpend allocation:")
    df = sol["variables"]
    active = df[df["float"] > 0] if "float" in df.columns else df
    print(active.to_string(index=False))
