"""Site Network Criticality (graph analysis) template.

Answers:
  "Which warehouses are bridges between supply chain clusters?"
  -> Weakly Connected Components + Bridge detection

  "Which warehouses are most critical to supply chain resilience?"
  -> Eigenvector Centrality on weighted site dependency graph

Data: supply chain (sites + operations).
Graph: undirected, weighted by shipment count. Site nodes, SHIP operations as edges.
Derived concepts: Region (from site data), Bridge (cross-region connectors).

Run:
    `python site_centrality.py`

Output:
    Prints connected-component summary, bridge edges between regions, and an
    eigenvector centrality ranking of the most critical sites.
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Float, Integer, Model, String, distinct, select, where
from relationalai.semantics import count as rai_count
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.std import aggregates as aggs

model = Model("site_centrality")

# --------------------------------------------------
# Load data & define semantic model
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Site concept
Site = model.Concept("Site", identify_by={"id": String})
Site.name = model.Property(f"{Site} has {String:name}")
Site.site_type = model.Property(f"{Site} has type {String:site_type}")
Site.region_id = model.Property(f"{Site} in {String:region_id}")
Site.country = model.Property(f"{Site} in {String:country}")

site_data = model.data(read_csv(data_dir / "sites.csv"))
model.define(Site.new(id=site_data["ID"]))
where(Site.id == site_data["ID"]).define(
    Site.name(site_data["NAME"]),
    Site.site_type(site_data["SITE_TYPE"]),
    Site.region_id(site_data["REGION"]),
    Site.country(site_data["COUNTRY"]),
)

# Operation concept
Operation = model.Concept("Operation", identify_by={"id": String})
Operation.type = model.Property(f"{Operation} has {String:type}")
Operation.cost_per_unit = model.Property(f"{Operation} costs {Float:cost_per_unit}")
Operation.capacity_per_day = model.Property(f"{Operation} has capacity {Integer:capacity_per_day}")
Operation.source_site = model.Relationship(f"{Operation} from {Site}", short_name="source_site")
Operation.destination_site = model.Relationship(f"{Operation} to {Site}", short_name="destination_site")

op_data = model.data(read_csv(data_dir / "operations.csv"))
model.define(Operation.new(id=op_data["ID"]))
where(Operation.id == op_data["ID"]).define(
    Operation.type(op_data["TYPE"]),
    Operation.cost_per_unit(op_data["COST_PER_UNIT"]),
    Operation.capacity_per_day(op_data["CAPACITY_PER_DAY"]),
    Operation.source_site(Site.filter_by(id=op_data["SOURCE_SITE_ID"])),
    Operation.destination_site(Site.filter_by(id=op_data["OUTPUT_SITE_ID"])),
)

# --------------------------------------------------
# Derived concepts
# --------------------------------------------------

# Region: derived from unique site region_id values
Region = model.Concept("Region")
model.define(Region.new(id=Site.region_id))

Site.region = model.Relationship(f"{Site} is in {Region}")
model.define(Site.region(Site, Region)).where(Site.region_id == Region.id)

# Shipment count properties (edge weights for graph)
site, op = Site.ref(), Operation.ref()

Site.count_is_destination = model.Relationship(
    f"{Site} has count of incoming shipments {Integer:count_is_destination}"
)
Site.count_is_source = model.Relationship(
    f"{Site} has count of outgoing shipments {Integer:count_is_source}"
)

model.where(
    Operation.destination_site(op, site), Operation.type(op, "SHIP")
).define(Site.count_is_destination(site, rai_count(op).per(site)))

model.where(
    Operation.source_site(op, site), Operation.type(op, "SHIP")
).define(Site.count_is_source(site, rai_count(op).per(site)))

# Bridge: sites whose operations connect different regions
site1, site2 = Site.ref(), Site.ref()
o_region = Region.ref()
op = Operation.ref()

Bridge = model.Concept("Bridge", extends=[Site])
model.define(Bridge(site1)).where(
    Operation.source_site(op, site1),
    Operation.destination_site(op, site2),
    site1.region != site2.region,
)

Bridge.connects_region = model.Relationship(f"{Bridge} connects with {Region}")
model.define(Bridge.connects_region(Bridge, o_region)).where(
    Bridge(site1),
    Operation.source_site(op, site1),
    Operation.destination_site(op, site2),
    site2.region(o_region),
    site1.region != o_region,
)

# --------------------------------------------------
# Build graph: undirected, weighted by shipment count
# --------------------------------------------------

graph = Graph(model, directed=False, weighted=True, node_concept=Site)

site1, site2, op = Site.ref(), Site.ref(), Operation.ref()
model.define(
    graph.Edge.new(src=site1, dst=site2, weight=site1.count_is_source)
).where(
    Operation.source_site(op, site1),
    Operation.destination_site(op, site2),
    Operation.type(op, "SHIP"),
)

print("=== Site Network Graph ===")
graph.num_nodes().inspect()
graph.num_edges().inspect()

# --------------------------------------------------
# Weakly Connected Components + Bridge detection
# --------------------------------------------------

wcc = graph.weakly_connected_component()

site_ref = graph.Node.ref("site")
comp_ref = graph.Node.ref("component_id")

wcc_df = (
    where(wcc(site_ref, comp_ref))
    .select(
        site_ref.id.alias("site_id"),
        site_ref.name.alias("site_name"),
        site_ref.site_type.alias("site_type"),
        site_ref.region.id.alias("region"),
        comp_ref.id.alias("component_id"),
        aggs.count(site_ref).per(comp_ref).alias("component_size"),
    )
    .to_df()
)

num_components = wcc_df["component_id"].nunique()
print("\n=== Connected Components ===")
print(f"Components found: {num_components}")
if num_components == 1:
    print("UNIFIED NETWORK: All sites in a single connected component")
else:
    print(f"FRAGMENTED NETWORK: {num_components} separate components detected")

for comp_id in sorted(wcc_df["component_id"].unique()):
    comp_df = wcc_df[wcc_df["component_id"] == comp_id]
    comp_size = int(comp_df["component_size"].iloc[0])
    regions = ", ".join(sorted(comp_df["region"].unique()))
    print(f"\n  Component {comp_id}: {comp_size} sites ({regions})")
    for _, row in comp_df.sort_values(["region", "site_name"]).iterrows():
        print(f"    - {row['site_name']} ({row['site_type']}, {row['region']})")

# Bridge sites
bridge_df = (
    select(distinct(
        Bridge.id.alias("bridge_site_id"),
        Bridge.name.alias("bridge_site_name"),
        Bridge.region.id.alias("bridge_region"),
        Bridge.connects_region.id.alias("connects_to_region"),
    ))
    .to_df()
)

if len(bridge_df) > 0:
    print("\n=== Bridge Sites (cross-region connectors) ===")
    for bridge_id in sorted(bridge_df["bridge_site_id"].unique()):
        rows = bridge_df[bridge_df["bridge_site_id"] == bridge_id]
        name = rows["bridge_site_name"].iloc[0]
        home_region = rows["bridge_region"].iloc[0]
        connects = ", ".join(sorted(rows["connects_to_region"].unique()))
        print(f"  {name} ({home_region}) -> connects to: {connects}")

# --------------------------------------------------
# Eigenvector Centrality (most critical sites)
# --------------------------------------------------

eigenvector = graph.eigenvector_centrality()

node = graph.Node.ref("n")
score = Float.ref("s")
eig_df = (
    where(
        eigenvector(node, score),
        node.site_type != "STORE",
        node.site_type != "OFFICE",
    )
    .select(
        node.id.alias("site_id"),
        node.name.alias("site_name"),
        node.site_type.alias("site_type"),
        node.region.id.alias("region"),
        score.alias("centrality_score"),
        node.count_is_destination.alias("incoming_connections"),
        node.count_is_source.alias("outgoing_connections"),
    )
    .to_df()
    .sort_values("centrality_score", ascending=False)
    .reset_index(drop=True)
)

print("\n=== Eigenvector Centrality ===")
print(eig_df.to_string(index=False))

print("\n--- Top 3 Most Critical Sites ---")
for idx, (_, row) in enumerate(eig_df.head(3).iterrows(), 1):
    print(f"  {idx}. {row['site_name']} ({row['site_type']}, {row['region']})")
    print(f"     Centrality: {row['centrality_score']:.4f}")

print("\n--- Centrality by Region ---")
for region in sorted(eig_df["region"].unique()):
    region_df = eig_df[eig_df["region"] == region]
    avg = region_df["centrality_score"].mean()
    top = region_df.sort_values("centrality_score", ascending=False).iloc[0]["site_name"]
    print(f"  {region}: {len(region_df)} sites, avg={avg:.4f}, top={top}")
