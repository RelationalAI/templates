"""Ad Spend Allocation - Allocate budget across channels to maximize conversions."""

from pathlib import Path
from time import time_ns

from pandas import read_csv
from relationalai.semantics import Model, data, define, require, sum
from relationalai.semantics.reasoners.optimization import Solver, SolverModel


def define_model(config=None):
    """Define base model with Channel, Campaign, and Effectiveness concepts."""
    model = Model(f"ad_spend_{time_ns()}", config=config, use_lqp=False)
    Concept, Property, Relationship = model.Concept, model.Property, model.Relationship

    data_dir = Path(__file__).parent / "data"

    # Channel: advertising channels with spend limits
    Channel = Concept("Channel")
    Channel.name = Property("{Channel} has name {name:String}")
    Channel.min_spend = Property("{Channel} has min_spend {min_spend:float}")
    Channel.max_spend = Property("{Channel} has max_spend {max_spend:float}")
    Channel.roi_coefficient = Property("{Channel} has roi_coefficient {roi_coefficient:float}")
    channels_df = read_csv(data_dir / "channels.csv")
    data(channels_df).into(Channel, id="id", properties=["name", "min_spend", "max_spend", "roi_coefficient"])

    # Campaign: marketing campaigns with budgets and targets
    Campaign = Concept("Campaign")
    Campaign.name = Property("{Campaign} has name {name:String}")
    Campaign.budget = Property("{Campaign} has budget {budget:float}")
    Campaign.target_conversions = Property("{Campaign} has target_conversions {target_conversions:int}")
    campaigns_df = read_csv(data_dir / "campaigns.csv")
    data(campaigns_df).into(Campaign, id="id", properties=["name", "budget", "target_conversions"])

    # Effectiveness: conversion rate for channel/campaign combinations
    Effectiveness = Concept("Effectiveness")
    Effectiveness.channel = Relationship("{Effectiveness} via {channel:Channel}")
    Effectiveness.campaign = Relationship("{Effectiveness} for {campaign:Campaign}")
    Effectiveness.conversion_rate = Property("{Effectiveness} has conversion_rate {conversion_rate:float}")
    eff_df = read_csv(data_dir / "effectiveness.csv")
    data(eff_df).into(
        Effectiveness,
        keys=["channel_id", "campaign_id"],
        properties=["conversion_rate"],
        relationships={"channel": ("channel_id", Channel), "campaign": ("campaign_id", Campaign)},
    )

    # Allocation: decision variable for spend per channel/campaign
    Allocation = Concept("Allocation")
    Allocation.effectiveness = Relationship("{Allocation} uses {effectiveness:Effectiveness}")
    Allocation.spend = Property("{Allocation} has spend {spend:float}")
    Allocation.active = Property("{Allocation} is active {active:float}")
    define(Allocation.new(effectiveness=Effectiveness))

    model.Channel, model.Campaign, model.Effectiveness, model.Allocation = Channel, Campaign, Effectiveness, Allocation
    return model


def define_problem(model):
    """Define decision variables, constraints, and objective."""
    s = SolverModel(model, "cont")
    Channel, Campaign, Effectiveness, Allocation = model.Channel, model.Campaign, model.Effectiveness, model.Allocation

    # Decision variable: continuous spend amount
    s.solve_for(Allocation.spend, name=[Allocation.effectiveness.channel, Allocation.effectiveness.campaign], lower=0)

    # Decision variable: binary indicator for whether channel is used for campaign
    s.solve_for(Allocation.active, type="bin", name=["active", Allocation.effectiveness.channel, Allocation.effectiveness.campaign])

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
