"""BOM Reachability (graph analysis) template.

Answers:
  "What components does Product X transitively depend on?"
  "Which components are bottleneck dependencies across products?"

Data: supply chain (SKUs + BillOfMaterials).
Graph: directed, unweighted. SKU nodes, BOM rows as edges (output -> input).
  Edge direction: output_sku -> input_sku ("depends on").
Algorithms: reachable(full=True) for transitive dependency tracing,
  betweenness_centrality() for identifying structural bottlenecks.

Run:
    `python bom_reachability.py`

Output:
    Prints transitive dependency lists per finished product and a betweenness
    centrality ranking that flags structural bottleneck components.
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Float, Model, String, where
from relationalai.semantics.reasoners.graph import Graph

model = Model("bom_reachability")

# --------------------------------------------------
# Load data & define semantic model
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# SKU concept
SKU = model.Concept("SKU", identify_by={"id": String})
SKU.name = model.Property(f"{SKU} has {String:name}")
SKU.type = model.Property(f"{SKU} has type {String:type}")
SKU.category = model.Property(f"{SKU} in {String:category}")

sku_data = model.data(read_csv(data_dir / "skus.csv"))
model.define(SKU.new(id=sku_data["ID"]))
where(SKU.id == sku_data["ID"]).define(
    SKU.name(sku_data["NAME"]),
    SKU.type(sku_data["TYPE"]),
    SKU.category(sku_data["CATEGORY"]),
)

# BillOfMaterials concept
BillOfMaterials = model.Concept("BillOfMaterials", identify_by={"id": String})
BillOfMaterials.output_sku = model.Relationship(f"{BillOfMaterials} produces {SKU}")
BillOfMaterials.input_sku = model.Relationship(f"{BillOfMaterials} requires {SKU}")

bom_data = model.data(read_csv(data_dir / "bill_of_materials.csv"))
model.define(BillOfMaterials.new(id=bom_data["ID"]))
where(BillOfMaterials.id == bom_data["ID"]).define(
    BillOfMaterials.output_sku(SKU.filter_by(id=bom_data["OUTPUT_SKU_ID"])),
    BillOfMaterials.input_sku(SKU.filter_by(id=bom_data["INPUT_SKU_ID"])),
)

# --------------------------------------------------
# Build graph: SKU nodes, BOM edges (directed)
# Edge: output_sku -> input_sku ("depends on")
# --------------------------------------------------

graph = Graph(
    model,
    directed=True,
    weighted=False,
    node_concept=SKU,
    edge_concept=BillOfMaterials,
    edge_src_relationship=BillOfMaterials.output_sku,
    edge_dst_relationship=BillOfMaterials.input_sku,
)

print("=== BOM Dependency Graph ===")
graph.num_nodes().inspect()
graph.num_edges().inspect()

# --------------------------------------------------
# Reachability: all transitive dependency pairs
# --------------------------------------------------

reachable = graph.reachable(full=True)

src, dst = graph.Node.ref("src"), graph.Node.ref("dst")
all_deps_df = (
    where(reachable(src, dst))
    .select(
        src.id.alias("product_id"),
        src.name.alias("product_name"),
        src.type.alias("product_type"),
        dst.id.alias("dep_id"),
        dst.name.alias("dep_name"),
        dst.type.alias("dep_type"),
    )
    .to_df()
)

print(f"\nTotal reachable pairs: {len(all_deps_df)}")

# --------------------------------------------------
# Dependencies of each finished good
# --------------------------------------------------

finished = all_deps_df[all_deps_df["product_type"] == "FINISHED_GOOD"]
for product_id in sorted(finished["product_id"].unique()):
    deps = finished[(finished["product_id"] == product_id) & (finished["dep_id"] != product_id)]
    if len(deps) > 0:
        product_name = deps["product_name"].iloc[0]
        print(f"\n--- Dependencies of '{product_name}' ({product_id}) ---")
        print(f"  {len(deps)} transitive dependencies:")
        for dep_type in ["COMPONENT", "RAW_MATERIAL"]:
            type_deps = deps[deps["dep_type"] == dep_type]
            if len(type_deps) > 0:
                print(f"\n  {dep_type}s ({len(type_deps)}):")
                for _, row in type_deps.sort_values("dep_name").iterrows():
                    print(f"    - {row['dep_name']} ({row['dep_id']})")

# --------------------------------------------------
# Most depended-on components
# --------------------------------------------------

non_self = all_deps_df[all_deps_df["product_id"] != all_deps_df["dep_id"]]
if len(non_self) > 0:
    dep_counts = (
        non_self.groupby(["dep_id", "dep_name", "dep_type"])
        .size()
        .reset_index(name="depended_on_by")
        .sort_values("depended_on_by", ascending=False)
    )
    print("\n=== Most Depended-On SKUs ===")
    print(dep_counts.to_string(index=False))

# --------------------------------------------------
# Betweenness centrality: structural bottlenecks
# --------------------------------------------------

betweenness = graph.betweenness_centrality()

node = graph.Node.ref("n")
score = Float.ref("s")
btw_df = (
    where(betweenness(node, score))
    .select(
        node.id.alias("sku_id"),
        node.name.alias("sku_name"),
        node.type.alias("type"),
        node.category.alias("category"),
        score.alias("betweenness"),
    )
    .to_df()
    .sort_values("betweenness", ascending=False)
    .reset_index(drop=True)
)

print("\n=== Betweenness Centrality (bottleneck components) ===")
print(btw_df.to_string(index=False))

bottlenecks = btw_df[btw_df["betweenness"] > 0]
if len(bottlenecks) > 0:
    top = bottlenecks.iloc[0]
    print(f"\nTop bottleneck: {top['sku_name']} (betweenness={top['betweenness']:.4f})")
    print("  Sits on the most dependency paths -- disruption here affects the most product lines.")
