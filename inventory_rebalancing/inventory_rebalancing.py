"""Inventory Rebalancing - Transfer inventory between sites to meet demand at minimum cost."""

from pathlib import Path
from time import time_ns

from pandas import read_csv
from relationalai.semantics import Model, data, define, require, sum
from relationalai.semantics.reasoners.optimization import Solver, SolverModel


def define_model(config=None):
    """Define base model with Site, Lane, and Demand concepts."""
    model = Model(f"inventory_rebalancing_{time_ns()}", config=config, use_lqp=False)
    Concept, Property, Relationship = model.Concept, model.Property, model.Relationship

    data_dir = Path(__file__).parent / "data"

    # Site: warehouse/store locations with initial inventory
    Site = Concept("Site")
    Site.name = Property("{Site} has name {name:String}")
    Site.inventory = Property("{Site} has inventory {inventory:int}")
    sites_df = read_csv(data_dir / "sites.csv")
    data(sites_df).into(Site, id="id", properties=["name", "inventory"])

    # Lane: transfer routes between sites
    Lane = Concept("Lane")
    Lane.cost_per_unit = Property("{Lane} has cost_per_unit {cost_per_unit:float}")
    Lane.capacity = Property("{Lane} has capacity {capacity:int}")
    Lane.source = Relationship("{Lane} from {source:Site}")
    Lane.dest = Relationship("{Lane} to {dest:Site}")
    lanes_df = read_csv(data_dir / "lanes.csv")
    data(lanes_df).into(
        Lane,
        id="id",
        properties=["cost_per_unit", "capacity"],
        relationships={"source": ("source_id", Site), "dest": ("dest_id", Site)},
    )

    # Demand: required quantity at destination sites
    Demand = Concept("Demand")
    Demand.quantity = Property("{Demand} has quantity {quantity:int}")
    Demand.site = Relationship("{Demand} at {site:Site}")
    demand_df = read_csv(data_dir / "demand.csv")
    data(demand_df).into(
        Demand,
        id="id",
        properties=["quantity"],
        relationships={"site": ("site_id", Site)},
    )

    # Transfer: decision variable for transfer quantity on each lane
    Transfer = Concept("Transfer")
    Transfer.lane = Relationship("{Transfer} uses {lane:Lane}")
    Transfer.quantity = Property("{Transfer} has quantity {quantity:float}")
    define(Transfer.new(lane=Lane))

    model.Site, model.Lane, model.Demand, model.Transfer = Site, Lane, Demand, Transfer
    return model


def define_problem(model):
    """Define decision variables, constraints, and objective."""
    s = SolverModel(model, "cont")
    Site, Lane, Demand, Transfer = model.Site, model.Lane, model.Demand, model.Transfer

    # Decision variable: quantity to transfer on each lane
    s.solve_for(Transfer.quantity, name=Transfer.lane, lower=0)

    # Constraint: transfer cannot exceed lane capacity
    s.satisfy(require(Transfer.quantity <= Transfer.lane.capacity))

    # Constraint: total outbound from source cannot exceed source inventory
    Tr = Transfer.ref()
    outbound = sum(Tr.quantity).where(Tr.lane.source == Site).per(Site)
    s.satisfy(require(outbound <= Site.inventory))

    # Constraint: demand satisfaction at each destination site
    Dm = Demand.ref()
    inbound = sum(Tr.quantity).where(Tr.lane.dest == Dm.site).per(Dm)
    local_inv = sum(Site.inventory).where(Site == Dm.site).per(Dm)
    s.satisfy(require(inbound + local_inv >= Dm.quantity))

    # Objective: minimize total transfer cost
    total_cost = sum(Transfer.quantity * Transfer.lane.cost_per_unit)
    s.minimize(total_cost)

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
    print(f"Total transfer cost: ${sol['objective']:.2f}")
    print("\nTransfers:")
    df = sol["variables"]
    active = df[df["float"] > 0] if "float" in df.columns else df
    print(active.to_string(index=False))
