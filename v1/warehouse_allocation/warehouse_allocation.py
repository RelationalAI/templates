"""Warehouse Allocation (chained graph + prescriptive reasoning) template.

This script demonstrates chaining two reasoner types in RelationalAI:

Stage 1 -- Graph Analysis:
  - Build a distribution network graph from warehouse sites and routes.
  - Run eigenvector centrality to identify critical hub warehouses.
  - Run weakly-connected-components to surface network fragmentation.
  - Detect bridge routes that connect distinct regions.
  - Centrality scores and structural flags are stored as properties on the
    Site / Route concepts.

Stage 2 -- Prescriptive Optimization:
  - Allocate inventory budget across sites to minimize holding cost.
  - Use centrality scores from Stage 1 to ensure critical hubs receive
    adequate stock (minimum allocation proportional to centrality).
  - Satisfy demand at each site.

The key pattern: the graph reasoner enriches the ontology with derived
properties that the prescriptive reasoner references directly -- no manual
data transfer between stages.

Run:
    `python warehouse_allocation.py`

Output:
    Prints centrality ranking, weakly-connected-component summary, bridge
    routes between regions, solver status, total holding cost, and the
    inventory allocation plan.
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Float, Integer, Model, String, sum, where
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.std import aggregates as aggs

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

model = Model("warehouse_allocation")
Concept, Property, Relationship = model.Concept, model.Property, model.Relationship

# Site concept: distribution sites such as warehouses and stores.
Site = Concept("Site", identify_by={"id": Integer})
Site.name = Property(f"{Site} has {String:name}")
Site.region = Property(f"{Site} has {String:region}")
Site.type = Property(f"{Site} has {String:type}")
Site.holding_cost = Property(f"{Site} has {Float:holding_cost}")
model.define(Site.new(model.data(read_csv(DATA_DIR / "sites.csv")).to_schema()))

# Route concept: transport links between distribution sites.
Route = Concept("Route", identify_by={"id": Integer})
Route.source = Relationship(f"{Route} from {Site}", short_name="source")
Route.dest = Relationship(f"{Route} to {Site}", short_name="dest")
Route.capacity = Property(f"{Route} has {Integer:capacity}")
Route.transport_cost = Property(f"{Route} has {Float:transport_cost}")

route_data = model.data(read_csv(DATA_DIR / "routes.csv"))
model.define(
    r := Route.new(
        id=route_data.id,
        source=Site.filter_by(id=route_data.source_id),
        dest=Site.filter_by(id=route_data.dest_id),
    ),
    r.capacity(route_data.capacity),
    r.transport_cost(route_data.transport_cost),
)

# Demand concept: inventory requirements at each site.
Demand = Concept("Demand", identify_by={"id": Integer})
Demand.site = Relationship(f"{Demand} at {Site}")
Demand.quantity = Property(f"{Demand} has {Integer:quantity}")

demand_data = model.data(read_csv(DATA_DIR / "demands.csv"))
model.define(
    d := Demand.new(
        id=demand_data.id,
        site=Site.filter_by(id=demand_data.site_id),
    ),
    d.quantity(demand_data.quantity),
)

# --------------------------------------------------
# Stage 1: Graph Analysis -- identify critical network hubs
# --------------------------------------------------

graph = Graph(model, directed=False, weighted=True, node_concept=Site, aggregator="sum")

# Build edges from routes (undirected, weighted by capacity)
route_ref = Route.ref()
src, dst = Site.ref(), Site.ref()
model.where(route_ref.source(src), route_ref.dest(dst)).define(
    graph.Edge.new(src=src, dst=dst, weight=route_ref.capacity),
)

# Eigenvector centrality: stored directly on Site (via node_concept)
Site.centrality = graph.eigenvector_centrality()

# Display centrality ranking
print("=" * 50)
print("Stage 1a: Eigenvector Centrality")
print("=" * 50)

model.select(
    Site.name.alias("site"),
    Site.type.alias("type"),
    Site.region.alias("region"),
    Site.centrality.alias("centrality"),
).inspect()

# --------------------------------------------------
# Stage 1b: Weakly Connected Components -- surface fragmentation
# --------------------------------------------------

wcc = graph.weakly_connected_component()
site_ref = graph.Node.ref("site")
comp_ref = graph.Node.ref("component_id")

wcc_df = (
    where(wcc(site_ref, comp_ref))
    .select(
        site_ref.id.alias("site_id"),
        site_ref.name.alias("site"),
        site_ref.region.alias("region"),
        comp_ref.id.alias("component_id"),
        aggs.count(site_ref).per(comp_ref).alias("component_size"),
    )
    .to_df()
)

print("\n" + "=" * 50)
print("Stage 1b: Connected Components")
print("=" * 50)
num_components = wcc_df["component_id"].nunique()
if num_components == 1:
    print(f"UNIFIED NETWORK: all {len(wcc_df)} sites in a single component")
else:
    print(f"FRAGMENTED NETWORK: {num_components} separate components detected")
    for comp_id in sorted(wcc_df["component_id"].unique()):
        comp_df = wcc_df[wcc_df["component_id"] == comp_id]
        size = int(comp_df["component_size"].iloc[0])
        regions = ", ".join(sorted(comp_df["region"].unique()))
        print(f"  Component {comp_id}: {size} sites ({regions})")

# --------------------------------------------------
# Stage 1c: Bridge Routes -- cross-region connectors
# --------------------------------------------------
# Routes whose endpoints lie in different regions; losing one of these
# fragments the corresponding inter-region flow.

route_ref = Route.ref()
src, dst = Site.ref(), Site.ref()
Route.is_cross_region = Property(f"{Route} is cross-region {Float:is_cross_region}")
model.where(
    route_ref.source(src),
    route_ref.dest(dst),
    src.region != dst.region,
).define(Route.is_cross_region(route_ref, 1.0))

bridge_df = model.select(
    Route.id.alias("route_id"),
    Route.source.name.alias("from_site"),
    Route.source.region.alias("from_region"),
    Route.dest.name.alias("to_site"),
    Route.dest.region.alias("to_region"),
).where(Route.is_cross_region == 1.0).to_df()

print("\n" + "=" * 50)
print(f"Stage 1c: Bridge Routes ({len(bridge_df)} cross-region connectors)")
print("=" * 50)
if not bridge_df.empty:
    for _, row in bridge_df.iterrows():
        print(f"  {row['from_site']} ({row['from_region']}) -> {row['to_site']} ({row['to_region']})")

# --------------------------------------------------
# Stage 2: Prescriptive -- allocate inventory across sites
# --------------------------------------------------
# The centrality property computed by the graph reasoner above is
# referenced directly in the formulation below.

Site.x_inventory = Property(f"{Site} has inventory allocation {Float:x}")

problem = Problem(model, Float)
problem.solve_for(Site.x_inventory, lower=0, name=["alloc", Site.name])

TOTAL_BUDGET = 2000  # total units to allocate

# Constraint: total allocation within budget
problem.satisfy(model.require(sum(Site.x_inventory) <= TOTAL_BUDGET))

# Constraint: demand satisfaction at each site
DemandRef = Demand.ref()
site_alloc = sum(Site.x_inventory).where(Site == DemandRef.site).per(DemandRef)
problem.satisfy(model.require(site_alloc >= DemandRef.quantity))

# Constraint: critical hubs get minimum allocation proportional to centrality
# Sites with higher centrality are more important to the network and should
# carry proportionally more inventory.
MIN_CENTRALITY_FACTOR = 200
problem.satisfy(model.require(
    Site.x_inventory >= Site.centrality * MIN_CENTRALITY_FACTOR
).where(Site.type("WAREHOUSE")))

# Objective: minimize total holding cost
problem.minimize(sum(Site.x_inventory * Site.holding_cost))

# --------------------------------------------------
# Solve
# --------------------------------------------------

print("\n" + "=" * 50)
print("Stage 2: Inventory Allocation")
print("=" * 50)

problem.display()
problem.solve("highs", time_limit_sec=60)
si = problem.solve_info()
si.display()

print(f"\nStatus: {si.termination_status}")
print(f"Total holding cost: ${si.objective_value:.2f}")

print("\nAllocation plan:")
model.select(
    Site.name.alias("site"),
    Site.type.alias("type"),
    Site.centrality.alias("centrality"),
    Site.x_inventory.alias("allocated"),
    Site.holding_cost.alias("unit_cost"),
).where(Site.x_inventory > 0.01).inspect()
