# inventory rebalancing problem:
# transfer inventory between sites to meet demand at minimum cost

from pathlib import Path

from pandas import read_csv

from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("inventory_rebalancing")
Concept, Property = model.Concept, model.Property

# --------------------------------------------------
# Define ontology & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Concept: sites with current inventory
Site = Concept("Site", identify_by={"id": Integer})
Site.name = Property(f"{Site} has {String:name}")
Site.inventory = Property(f"{Site} has {Integer:inventory}")
site_csv = read_csv(data_dir / "sites.csv")
model.define(Site.new(model.data(site_csv).to_schema()))

# Relationship: lanes between sites with cost and capacity
Lane = Concept("Lane", identify_by={"id": Integer})
Lane.source_id = Property(f"{Lane} has {Integer:source_id}")
Lane.dest_id = Property(f"{Lane} has {Integer:dest_id}")
Lane.source = Property(f"{Lane} from {Site}", short_name="source")
Lane.dest = Property(f"{Lane} to {Site}", short_name="dest")
Lane.cost_per_unit = Property(f"{Lane} has {Float:cost_per_unit}")
Lane.capacity = Property(f"{Lane} has {Integer:capacity}")

lane_csv = read_csv(data_dir / "lanes.csv")
lane_data = model.data(lane_csv)
model.define(
    l := Lane.new(id=lane_data.id, source_id=lane_data.source_id, dest_id=lane_data.dest_id),
    l.cost_per_unit(lane_data.cost_per_unit),
    l.capacity(lane_data.capacity),
)
SourceSite = Site.ref()
DestSite = Site.ref()
model.define(Lane.source(SourceSite)).where(Lane.source_id == SourceSite.id)
model.define(Lane.dest(DestSite)).where(Lane.dest_id == DestSite.id)

# Concept: demand at each site
Demand = Concept("Demand", identify_by={"id": Integer})
Demand.site_id = Property(f"{Demand} has {Integer:site_id}")
Demand.site = Property(f"{Demand} at {Site}")
Demand.quantity = Property(f"{Demand} has {Integer:quantity}")

demand_csv = read_csv(data_dir / "demand.csv")
demand_data = model.data(demand_csv)
model.define(
    d := Demand.new(id=demand_data.id, site_id=demand_data.site_id),
    d.quantity(demand_data.quantity),
)
model.define(Demand.site(Site)).where(Demand.site_id == Site.id)

# --------------------------------------------------
# Model the problem
# --------------------------------------------------

# Decision concept: transfers on each lane
Transfer = Concept("Transfer", identify_by={"lane": Lane})
Transfer.x_quantity = Property(f"{Transfer} has {Float:quantity}")
model.define(Transfer.new(lane=Lane))

TransferRef = Transfer.ref()
DemandRef = Demand.ref()

s = Problem(model, Float)

# Variable: transfer quantity
s.solve_for(Transfer.x_quantity, name=["qty", Transfer.lane.source.name, Transfer.lane.dest.name], lower=0)

# Constraint: transfer cannot exceed lane capacity
capacity_limit = model.require(Transfer.x_quantity <= Transfer.lane.capacity)
s.satisfy(capacity_limit)

# Constraint: total outbound from source cannot exceed source inventory
outbound = sum(TransferRef.x_quantity).where(TransferRef.lane.source == Site).per(Site)
inventory_limit = model.require(outbound <= Site.inventory)
s.satisfy(inventory_limit)

# Constraint: demand satisfaction at each destination site
inbound = sum(TransferRef.x_quantity).where(TransferRef.lane.dest == DemandRef.site).per(DemandRef)
local_inv = sum(Site.inventory).where(Site == DemandRef.site).per(DemandRef)
demand_met = model.require(inbound + local_inv >= DemandRef.quantity)
s.satisfy(demand_met)

# Objective: minimize total transfer cost
total_cost = sum(Transfer.x_quantity * Transfer.lane.cost_per_unit)
s.minimize(total_cost)

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

s.display()
s.solve("highs", time_limit_sec=60, _server_side_import=False)
s.display_solve_info()

print(f"Status: {s.termination_status}")
print(f"Total transfer cost: ${s.objective_value:.2f}")

transfers = model.select(
    Transfer.lane.source.name.alias("from"),
    Transfer.lane.dest.name.alias("to"),
    Transfer.x_quantity,
).where(Transfer.x_quantity > 0.001).to_df()

print("\nTransfers:")
print(transfers.to_string(index=False))
