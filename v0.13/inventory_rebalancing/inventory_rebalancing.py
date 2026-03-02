"""Inventory Rebalancing (prescriptive optimization) template.

This script demonstrates a simple inventory transfer optimization model in RelationalAI:

- Load sample CSVs describing sites, transfer lanes, and demand.
- Model sites, lanes, and demand as *concepts*.
- Choose non-negative transfer quantities subject to capacity and inventory limits.
- Satisfy demand at each destination site.
- Minimize total transfer cost.

Run:
    `python inventory_rebalancing.py`

Output:
    Prints the solver termination status, total transfer cost, and a table of
    non-trivial transfers.
"""

from pathlib import Path

import pandas
from pandas import read_csv

from relationalai.semantics import Model, data, define, require, select, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"

# Disable pandas inference of string types. This ensures that string columns
# in the CSVs are loaded as object dtype. This is only required when using
# relationalai versions prior to v1.0.
pandas.options.future.infer_string = False

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

model = Model("inventory_rebalancing", config=globals().get("config", None), use_lqp=False)

# Concept: sites with current inventory
Site = model.Concept("Site")
Site.id = model.Property("{Site} has {id:int}")
Site.name = model.Property("{Site} has {name:string}")
Site.inventory = model.Property("{Site} has {inventory:int}")

# Load site data from CSV and populate the Site concept.
data(read_csv(DATA_DIR / "sites.csv")).into(Site, keys=["id"])

# Relationship: lanes between sites with cost and capacity
Lane = model.Concept("Lane")
Lane.id = model.Property("{Lane} has {id:int}")
Lane.source = model.Property("{Lane} from {source:Site}")
Lane.dest = model.Property("{Lane} to {dest:Site}")
Lane.cost_per_unit = model.Property("{Lane} has {cost_per_unit:float}")
Lane.capacity = model.Property("{Lane} has {capacity:int}")

# Load lane data from CSV and create Lane entities.
lanes_data = data(read_csv(DATA_DIR / "lanes.csv"))
Dest = Site.ref()
where(
    Site.id == lanes_data.source_id,
    Dest.id == lanes_data.dest_id
).define(
    Lane.new(
        id=lanes_data.id,
        source=Site,
        dest=Dest,
        cost_per_unit=lanes_data.cost_per_unit,
        capacity=lanes_data.capacity
    )
)

# Concept: demand at each site
Demand = model.Concept("Demand")
Demand.id = model.Property("{Demand} has {id:int}")
Demand.site = model.Property("{Demand} at {site:Site}")
Demand.quantity = model.Property("{Demand} has {quantity:int}")

# Load demand data from CSV and create Demand entities.
demand_data = data(read_csv(DATA_DIR / "demand.csv"))
where(Site.id == demand_data.site_id).define(
    Demand.new(id=demand_data.id, site=Site, quantity=demand_data.quantity)
)

# --------------------------------------------------
# Model the problem
# --------------------------------------------------

# Decision concept: transfers on each lane
Transfer = model.Concept("Transfer")
Transfer.lane = model.Property("{Transfer} uses {lane:Lane}")
Transfer.x_quantity = model.Property("{Transfer} has {quantity:float}")
define(Transfer.new(lane=Lane))

Tr = Transfer.ref()
Dm = Demand.ref()

s = SolverModel(model, "cont")

# Variable: transfer quantity
s.solve_for(Transfer.x_quantity, name=["qty", Transfer.lane.source.name, Transfer.lane.dest.name], lower=0)

# Constraint: transfer cannot exceed lane capacity
capacity_limit = require(Transfer.x_quantity <= Transfer.lane.capacity)
s.satisfy(capacity_limit)

# Constraint: total outbound from source cannot exceed source inventory
outbound = sum(Tr.quantity).where(Tr.lane.source == Site).per(Site)
inventory_limit = require(outbound <= Site.inventory)
s.satisfy(inventory_limit)

# Constraint: demand satisfaction at each destination site
inbound = sum(Tr.quantity).where(Tr.lane.dest == Dm.site).per(Dm)
local_inv = sum(Site.inventory).where(Site == Dm.site).per(Dm)
demand_met = require(inbound + local_inv >= Dm.quantity)
s.satisfy(demand_met)

# Objective: minimize total transfer cost
total_cost = sum(Transfer.x_quantity * Transfer.lane.cost_per_unit)
s.minimize(total_cost)

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

solver = Solver("highs")
s.solve(solver, time_limit_sec=60)

print(f"Status: {s.termination_status}")
print(f"Total transfer cost: ${s.objective_value:.2f}")

transfers = select(
    Transfer.lane.source.name.alias("from"),
    Transfer.lane.dest.name.alias("to"),
    Transfer.x_quantity
).where(Transfer.x_quantity > 0.001).to_df()

print("\nTransfers:")
print(transfers.to_string(index=False))
