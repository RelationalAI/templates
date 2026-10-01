"""Network Flow Planning (prescriptive optimization) template.

This script demonstrates a multi-tier network flow problem with fixed-cost
facility opening in RelationalAI:

- Load sample CSVs describing sites (warehouses, hubs, fulfillment centers,
  customers), lanes (directed transport links with cost and capacity), and
  demands (customer orders).
- Model these as a single Site concept distinguished by a `type` property,
  plus Lane and Demand concepts.
- Choose flow on each lane (continuous) and which fulfillment centers to
  open (binary).
- Enforce flow conservation at transit nodes, source supply at warehouses,
  capacity-linked-to-open at fulfillment centers, and demand satisfaction
  at customers.
- Minimize total cost (transport + fixed-cost FC opening).

Run:
    `python network_flow_planning.py`

Output:
    Prints solver termination status, total cost (transport + fixed
    components), the set of opened fulfillment centers, and the active flow
    plan across the network.
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

model = Model("network_flow_planning")

# Site concept: a node in the distribution network. The `type` property
# differentiates warehouses (have inventory), transit hubs (pass-through),
# fulfillment centers (have capacity + fixed_cost; binary open decision),
# and customers (have demand).
Site = model.Concept("Site", identify_by={"id": Integer})
Site.name = model.Property(f"{Site} has {String:name}")
Site.type = model.Property(f"{Site} has {String:type}")
Site.inventory = model.Property(f"{Site} has {Float:inventory}")
Site.capacity = model.Property(f"{Site} has {Float:capacity}")
Site.fixed_cost = model.Property(f"{Site} has {Float:fixed_cost}")

# Load sites.
site_csv = read_csv(DATA_DIR / "sites.csv")
model.define(Site.new(model.data(site_csv).to_schema()))

# Lane concept: directed transport link between two sites with a unit cost
# and a flow capacity.
Lane = model.Concept("Lane", identify_by={"id": Integer})
Lane.source = model.Relationship(f"{Lane} from {Site}", short_name="source")
Lane.dest = model.Relationship(f"{Lane} to {Site}", short_name="dest")
Lane.cost_per_unit = model.Property(f"{Lane} has {Float:cost_per_unit}")
Lane.capacity = model.Property(f"{Lane} has {Float:capacity}")

# Load lanes.
lane_csv = read_csv(DATA_DIR / "lanes.csv")
lane_data = model.data(lane_csv)
model.define(
    lane := Lane.new(
        id=lane_data.id,
        source=Site.lookup(id=lane_data.source_id),
        dest=Site.lookup(id=lane_data.dest_id),
    ),
    lane.cost_per_unit(lane_data.cost_per_unit),
    lane.capacity(lane_data.capacity),
)

# Demand concept: a customer order at a particular site with a quantity.
Demand = model.Concept("Demand", identify_by={"id": Integer})
Demand.site = model.Relationship(f"{Demand} placed at {Site}", short_name="site")
Demand.quantity = model.Property(f"{Demand} has {Float:quantity}")
Demand.customer = model.Property(f"{Demand} for {String:customer}")
Demand.priority = model.Property(f"{Demand} has {Integer:priority}")

# Load demands.
demand_csv = read_csv(DATA_DIR / "demand.csv")
demand_data = model.data(demand_csv)
model.define(
    d := Demand.new(
        id=demand_data.id,
        site=Site.lookup(id=demand_data.site_id),
    ),
    d.quantity(demand_data.quantity),
    d.customer(demand_data.customer),
    d.priority(demand_data.priority),
)

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

# Decision variables on the model itself.
Lane.x_flow = model.Property(f"{Lane} carries {Float:flow}")
Site.x_open = model.Property(f"{Site} is open {Float:open}")

problem = Problem(model, Float)

# Variable: flow on each lane (continuous, bounded by lane capacity).
problem.solve_for(
    Lane.x_flow,
    lower=0,
    upper=Lane.capacity,
    name=["flow", Lane.id],
)

# Variable: open/close decision per fulfillment center (binary).
# Restricted to sites with positive fixed_cost — i.e., the FC sites.
problem.solve_for(
    Site.x_open,
    type="bin",
    name=["open", Site.name],
    where=[Site.fixed_cost > 0],
)

# Constraint: source supply — outflow from each warehouse cannot exceed its
# inventory.
out_lane = Lane.ref()
problem.satisfy(model.where(
    Site.inventory > 0,
).require(
    sum(out_lane.x_flow).where(out_lane.source == Site).per(Site) <= Site.inventory
))

# Constraint: flow conservation at hubs — inflow equals outflow.
in_lane = Lane.ref()
out_lane = Lane.ref()
problem.satisfy(model.where(
    Site.type == "HUB",
).require(
    sum(in_lane.x_flow).where(in_lane.dest == Site).per(Site)
    == sum(out_lane.x_flow).where(out_lane.source == Site).per(Site)
))

# Constraint: flow conservation at fulfillment centers — inflow equals outflow.
in_lane = Lane.ref()
out_lane = Lane.ref()
problem.satisfy(model.where(
    Site.type == "FULFILLMENT_CENTER",
).require(
    sum(in_lane.x_flow).where(in_lane.dest == Site).per(Site)
    == sum(out_lane.x_flow).where(out_lane.source == Site).per(Site)
))

# Constraint: FC capacity gated by open decision — total inflow at an FC cannot
# exceed its capacity unless x_open == 1.
in_lane = Lane.ref()
problem.satisfy(model.where(
    Site.fixed_cost > 0,
).require(
    sum(in_lane.x_flow).where(in_lane.dest == Site).per(Site)
    <= Site.capacity * Site.x_open
))

# Constraint: demand satisfaction — total inflow at each customer site must
# meet aggregate demand at that site.
in_lane = Lane.ref()
demand_ref = Demand.ref()
problem.satisfy(model.where(
    Site.type == "CUSTOMER",
).require(
    sum(in_lane.x_flow).where(in_lane.dest == Site).per(Site)
    >= sum(demand_ref.quantity).where(demand_ref.site == Site).per(Site)
))

# Objective: minimize transport cost + fixed cost of opened fulfillment centers.
# Each branch of model.union must be a per-entity expression (per Lane and per
# Site here), aggregated by the outer sum.
problem.minimize(sum(model.union(
    Lane.cost_per_unit * Lane.x_flow,
    Site.fixed_cost * Site.x_open,
)))

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

problem.display()
problem.solve("highs", time_limit_sec=60)
model.require(problem.termination_status() == "OPTIMAL")
si = problem.solve_info()
si.display()

print(f"\nStatus: {si.termination_status}")
print(f"Total cost: ${si.objective_value:,.2f}")

print("\nOpened fulfillment centers:")
model.select(
    Site.name.alias("fulfillment_center"),
    Site.capacity.alias("capacity"),
    Site.fixed_cost.alias("fixed_cost"),
).where(Site.x_open > 0.5).inspect()

print("\nActive flows:")
model.select(
    Lane.source.name.alias("from_site"),
    Lane.dest.name.alias("to_site"),
    Lane.x_flow.alias("flow"),
    Lane.cost_per_unit.alias("unit_cost"),
).where(Lane.x_flow > 0.001).inspect()
