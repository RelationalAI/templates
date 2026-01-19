"""Inventory Rebalancing - Transfer inventory between sites to meet demand at minimum cost."""

from pathlib import Path
from time import time_ns

from pandas import read_csv
from relationalai.semantics import Model, data, define, require, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel


def define_model(config=None):
    """Define base model with Site, Lane, and Demand concepts."""
    model = Model(f"inventory_rebalancing_{time_ns()}", config=config, use_lqp=False)

    # Concepts
    Site = model.Concept("Site")
    Site.id = model.Property("{Site} has {id:int}")
    Site.name = model.Property("{Site} has {name:string}")
    Site.inventory = model.Property("{Site} has {inventory:int}")

    Lane = model.Concept("Lane")
    Lane.id = model.Property("{Lane} has {id:int}")
    Lane.source = model.Property("{Lane} from {source:Site}")
    Lane.dest = model.Property("{Lane} to {dest:Site}")
    Lane.cost_per_unit = model.Property("{Lane} has {cost_per_unit:float}")
    Lane.capacity = model.Property("{Lane} has {capacity:int}")

    Demand = model.Concept("Demand")
    Demand.id = model.Property("{Demand} has {id:int}")
    Demand.site = model.Property("{Demand} at {site:Site}")
    Demand.quantity = model.Property("{Demand} has {quantity:int}")

    # Load data
    data_dir = Path(__file__).parent / "data"

    sites_df = read_csv(data_dir / "sites.csv")
    data(sites_df).into(Site, keys=["id"])

    lanes_df = read_csv(data_dir / "lanes.csv")
    lanes_data = data(lanes_df)
    where(Site.id(lanes_data.source_id), (Dest := Site.ref()).id(lanes_data.dest_id)).define(
        Lane.new(id=lanes_data.id, source=Site, dest=Dest,
                 cost_per_unit=lanes_data.cost_per_unit, capacity=lanes_data.capacity)
    )

    demand_df = read_csv(data_dir / "demand.csv")
    demand_data = data(demand_df)
    where(Site.id(demand_data.site_id)).define(
        Demand.new(id=demand_data.id, site=Site, quantity=demand_data.quantity)
    )

    # Transfer: decision variable for transfer quantity on each lane
    Transfer = model.Concept("Transfer")
    Transfer.lane = model.Property("{Transfer} uses {lane:Lane}")
    Transfer.quantity = model.Property("{Transfer} has {quantity:float}")
    define(Transfer.new(lane=Lane))

    model.Site, model.Lane, model.Demand, model.Transfer = Site, Lane, Demand, Transfer
    return model


def define_problem(model):
    """Define decision variables, constraints, and objective."""
    s = SolverModel(model, "cont")
    Site, Lane, Demand, Transfer = model.Site, model.Lane, model.Demand, model.Transfer

    # Decision variable: quantity to transfer on each lane
    s.solve_for(Transfer.quantity, name=Transfer.lane.id, lower=0)

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
