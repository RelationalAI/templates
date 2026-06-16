"""BOM Reachability (graph analysis) template.

Answers:
  "What components does Product X transitively depend on?"
  "Which components are bottleneck dependencies across products?"

Data: supply chain (SKUs + BillOfMaterials).
Graph: directed, unweighted. SKU nodes, BOM rows as edges (output -> input).
  Edge direction: output_sku -> input_sku ("depends on").
Algorithms: reachable(full=True) for transitive dependency tracing,
  betweenness_centrality() for identifying structural bottlenecks.

Assembly path enumeration (PREVIEW, requires relationalai>=1.13): enumerate the
  bottom-up assembly chains that build each finished good. Derives a binary
  SKU->SKU "feeds into" edge from the BillOfMaterials intermediary (input feeds
  output), enumerates every assembly path with model.path(...).all_paths(),
  filters to the maximal (longest non-extendable) chains so sub-paths are
  suppressed, and persists each finished good's longest assembly depth back onto
  the SKU ontology.

Run:
    `python bom_reachability.py`

Output:
    Prints transitive dependency lists per finished product, a betweenness
    centrality ranking that flags structural bottleneck components, and the
    maximal raw-material -> finished-good assembly chains with per-finished-good
    assembly depth.
"""

from pathlib import Path

import pandas as pd
from pandas import read_csv
from relationalai.semantics import Float, Integer, Model, String, where
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
    BillOfMaterials.output_sku(SKU.lookup(id=bom_data["OUTPUT_SKU_ID"])),
    BillOfMaterials.input_sku(SKU.lookup(id=bom_data["INPUT_SKU_ID"])),
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

# --------------------------------------------------
# Assembly path enumeration
#   PREVIEW capability; requires relationalai>=1.13.
# --------------------------------------------------
# Where betweenness scores a single *node*, this enumerates the full *chains*
# that build each finished good: every bottom-up assembly path from a raw
# material up through its components to the finished good. We derive a binary
# SKU->SKU "feeds into" edge from the BillOfMaterials intermediary (the input
# SKU feeds the output SKU), enumerate all such paths, then keep only the
# maximal (longest, non-extendable) chains so that sub-paths are suppressed.

print("\n=== Assembly Path Enumeration (PREVIEW) ===")

# Binary SKU->SKU edge: input_sku "feeds into" output_sku. This is the
# build-direction (bottom-up) reverse of the depends-on graph edge above.
SKU.feeds = model.Relationship(f"{SKU} feeds into {SKU}", short_name="feeds")
bom_ref = BillOfMaterials.ref()
sku_in, sku_out = SKU.ref(), SKU.ref()
model.where(
    bom_ref.input_sku(sku_in),
    bom_ref.output_sku(sku_out),
).define(sku_in.feeds(sku_out))

# Enumerate every assembly chain. The BOM is a DAG (raw materials -> components
# -> finished goods, never back), so .all_paths() already yields simple paths --
# there is no cycle risk, and the repeat bound only needs to cover the BOM depth.
# Deepest chain here is raw_material -> component -> finished_good (2 hops); we
# allow extra headroom so deeper BOMs enumerate fully.
MAX_ASSEMBLY_HOPS = 4
p = model.path(SKU.feeds.repeat(1, MAX_ASSEMBLY_HOPS)).all_paths()
assembly_df = (
    model.where(p)
    .select(
        p.alias("path"),
        p.nodes["index"].alias("step"),
        SKU(p.nodes).id.alias("sku_id"),
        SKU(p.nodes).name.alias("sku_name"),
    )
    .to_df()
)

# Reassemble each path in pandas: group on the path id, order by step index.
assembly_df["step"] = assembly_df["step"].astype(int)
paths = []
for path_id, grp in assembly_df.groupby("path"):
    ordered = grp.sort_values("step")
    ids = ordered["sku_id"].tolist()
    names = ordered["sku_name"].tolist()
    paths.append({"ids": ids, "names": names, "length": len(ids) - 1})

print(f"\n  Enumerated {len(paths)} assembly path(s) (<= {MAX_ASSEMBLY_HOPS} hops).")

# (a) All assembly paths, longest first.
print("\n  All assembly chains (feeds-into order):")
for path in sorted(paths, key=lambda x: -x["length"]):
    print(f"    [{path['length']} hop] " + " -> ".join(path["names"]))

# (b) Maximal paths: keep only the longest, non-extendable chains -- a chain
# that is NOT a contiguous sub-sequence (prefix or suffix) of any longer chain.
# Suppressing these sub-paths leaves just the end-to-end assembly routes.
def _is_contiguous_subsequence(short, long):
    """True if `short` appears as a contiguous run inside `long`."""
    if len(short) >= len(long):
        return False
    return any(long[i:i + len(short)] == short for i in range(len(long) - len(short) + 1))


maximal = [
    path
    for path in paths
    if not any(
        other is not path and _is_contiguous_subsequence(path["ids"], other["ids"])
        for other in paths
    )
]

print(f"\n  Maximal assembly chains ({len(maximal)} of {len(paths)}, sub-paths suppressed):")
for path in sorted(maximal, key=lambda x: -x["length"]):
    print(f"    [{path['length']} hop] " + " -> ".join(path["names"]))

# Persist each finished good's longest assembly depth back onto the SKU ontology.
# The terminal SKU of a maximal chain is the thing it builds; the deepest chain
# ending there is that finished good's assembly depth.
SKU.assembly_depth = model.Property(f"{SKU} has assembly depth {Integer:assembly_depth}")
depth_by_sku = {}
for path in maximal:
    terminal = path["ids"][-1]
    depth_by_sku[terminal] = max(depth_by_sku.get(terminal, 0), path["length"])

if depth_by_sku:
    depth_rows = pd.DataFrame(
        [{"sku_id": sku_id, "assembly_depth": depth} for sku_id, depth in depth_by_sku.items()]
    )
    depth_data = model.data(depth_rows)
    model.define(SKU.assembly_depth(depth_data.assembly_depth)).where(
        SKU.id == depth_data.sku_id
    )

    print("\n  Assembly depth persisted onto SKU (longest chain terminating at each):")
    depth_df = (
        where(SKU.assembly_depth > 0)
        .select(
            SKU.id.alias("sku_id"),
            SKU.name.alias("sku_name"),
            SKU.type.alias("type"),
            SKU.assembly_depth.alias("assembly_depth"),
        )
        .to_df()
        .sort_values("assembly_depth", ascending=False)
        .reset_index(drop=True)
    )
    print(depth_df.to_string(index=False))
