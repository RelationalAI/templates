"""Inventory rebalancing (prescriptive optimization) template.

This script demonstrates a network flow optimization in RelationalAI:

- Load sample CSVs describing sites, transfer lanes, and demand.
- Model sites, lanes, and demand as *concepts* with typed properties.
- Choose non-negative transfer quantities subject to capacity and inventory limits.
- Enforce flow conservation at intermediate (transit) sites.
- Satisfy demand at each destination site.
- Minimize total transfer cost.

Run:
    `python inventory_rebalancing.py`

Output:
    Prints the solver termination status, total transfer cost, and a table of
    non-trivial transfers.
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("inventory_rebalancing")
Concept, Property = model.Concept, model.Property

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"

# Site concept: locations with current inventory and type (WAREHOUSE, TRANSIT, STORE).
Site = Concept("Site", identify_by={"id": Integer})
Site.name = Property(f"{Site} has {String:name}")
Site.type = Property(f"{Site} has {String:type}")
Site.inventory = Property(f"{Site} has {Integer:inventory}")
site_csv = read_csv(DATA_DIR / "sites.csv")
model.define(Site.new(model.data(site_csv).to_schema()))

# Lane concept: transfer routes between sites with cost and capacity.
Lane = Concept("Lane", identify_by={"id": Integer})
Lane.source_id = Property(f"{Lane} has {Integer:source_id}")
Lane.dest_id = Property(f"{Lane} has {Integer:dest_id}")
Lane.source = Property(f"{Lane} from {Site}", short_name="source")
Lane.dest = Property(f"{Lane} to {Site}", short_name="dest")
Lane.cost_per_unit = Property(f"{Lane} has {Float:cost_per_unit}")
Lane.capacity = Property(f"{Lane} has {Integer:capacity}")

lane_csv = read_csv(DATA_DIR / "lanes.csv")
lane_data = model.data(lane_csv)
model.define(
    lane := Lane.new(id=lane_data.id, source_id=lane_data.source_id, dest_id=lane_data.dest_id),
    lane.cost_per_unit(lane_data.cost_per_unit),
    lane.capacity(lane_data.capacity),
)
SourceSite = Site.ref()
DestSite = Site.ref()
model.define(Lane.source(SourceSite)).where(Lane.source_id == SourceSite.id)
model.define(Lane.dest(DestSite)).where(Lane.dest_id == DestSite.id)

# Demand concept: quantity requirements at each destination site.
Demand = Concept("Demand", identify_by={"id": Integer})
Demand.site_id = Property(f"{Demand} has {Integer:site_id}")
Demand.site = Property(f"{Demand} at {Site}")
Demand.quantity = Property(f"{Demand} has {Integer:quantity}")

demand_csv = read_csv(DATA_DIR / "demand.csv")
demand_data = model.data(demand_csv)
model.define(
    d := Demand.new(id=demand_data.id, site_id=demand_data.site_id),
    d.quantity(demand_data.quantity),
)
model.define(Demand.site(Site)).where(Demand.site_id == Site.id)

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

# Decision concept: transfers on each lane
Transfer = Concept("Transfer", identify_by={"lane": Lane})
Transfer.x_quantity = Property(f"{Transfer} has {Float:quantity}")
model.define(Transfer.new(lane=Lane))

TransferRef = Transfer.ref()
DemandRef = Demand.ref()

p = Problem(model, Float)

# Variable: transfer quantity
p.solve_for(Transfer.x_quantity, name=["qty", Transfer.lane.source.name, Transfer.lane.dest.name], lower=0)

# Constraint: transfer cannot exceed lane capacity
capacity_limit = model.require(Transfer.x_quantity <= Transfer.lane.capacity)
p.satisfy(capacity_limit)

# Constraint: total outbound from source cannot exceed source inventory
# (applies only to non-transit sites; transit sites have flow conservation instead)
SourceRef = Site.ref()
outbound = sum(TransferRef.x_quantity).where(TransferRef.lane.source == SourceRef).per(SourceRef)
inventory_limit = model.require(outbound <= SourceRef.inventory).where(
    SourceRef.type != "TRANSIT"
)
p.satisfy(inventory_limit)

# Constraint: flow conservation at transit sites (inflow == outflow)
InRef = Transfer.ref()
OutRef = Transfer.ref()
TransitSite = Site.ref()
inflow = sum(InRef.x_quantity).where(InRef.lane.dest == TransitSite).per(TransitSite)
outflow = sum(OutRef.x_quantity).where(OutRef.lane.source == TransitSite).per(TransitSite)
flow_balance = model.require(inflow == outflow).where(TransitSite.type("TRANSIT"))
p.satisfy(flow_balance)

# Constraint: demand satisfaction at each destination site
inbound = sum(TransferRef.x_quantity).where(TransferRef.lane.dest == DemandRef.site).per(DemandRef)
local_inv = sum(Site.inventory).where(Site == DemandRef.site).per(DemandRef)
demand_met = model.require(inbound + local_inv >= DemandRef.quantity)
p.satisfy(demand_met)

# Objective: minimize total transfer cost
total_cost = sum(Transfer.x_quantity * Transfer.lane.cost_per_unit)
p.minimize(total_cost)

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

p.display()
p.solve("highs", time_limit_sec=60)
model.require(p.termination_status() == "OPTIMAL")
si = p.solve_info()
si.display()

print(f"Status: {si.termination_status}")
print(f"Total transfer cost: ${si.objective_value:.2f}")

print("\nTransfers:")
model.select(
    Transfer.lane.source.name.alias("from"),
    Transfer.lane.dest.name.alias("to"),
    Transfer.x_quantity,
).where(Transfer.x_quantity > 0.001).inspect()
