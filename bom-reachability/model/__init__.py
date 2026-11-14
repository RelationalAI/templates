"""BOM Reachability (graph analysis) template.

Answers:
  "What components does Product X transitively depend on?"
  "Which components are bottleneck dependencies across products?"

Data: supply chain (SKUs + BillOfMaterials).
Graph: directed, unweighted. SKU nodes, BOM rows as edges (output -> input).
  Edge direction: output_sku -> input_sku ("depends on").
Algorithms: reachable(full=True) for transitive dependency tracing,
  betweenness_centrality() for identifying structural bottlenecks.

Assembly path enumeration (PREVIEW, requires relationalai>=1.15): enumerate the
  bottom-up assembly chains that build each finished good. Derives a binary
  SKU->SKU "feeds into" edge from the BillOfMaterials intermediary (input feeds
  output), enumerates every assembly path with model.path(...).all().paths(),
  filters to the maximal (longest non-extendable) chains so sub-paths are
  suppressed, and persists the longest assembly depth of each SKU that ends a
  chain (feeds nothing further) back onto the SKU ontology.

Deploy:
    `rai models deploy --path model` deploys this model to the schema in
    raiconfig.yaml and waits for its first refresh; `python -m
    queries.dependency_report` then prints the report from the deployed model.
"""

from pathlib import Path

import pandas as pd
from relationalai.semantics import Integer, Model, String, not_, where
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.std import aggregates as aggs

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

model = Model("bom_reachability")

# SKU concept
SKU = model.Concept("SKU", identify_by={"id": String})
SKU.name = model.Property(f"{SKU} has {String:name}")
SKU.type = model.Property(f"{SKU} has type {String:type}")
SKU.category = model.Property(f"{SKU} in {String:category}")

sku_data = model.data(pd.read_csv(DATA_DIR / "skus.csv"))
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

bom_data = model.data(pd.read_csv(DATA_DIR / "bill_of_materials.csv"))
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

# Graph results the report reads, declared here so they deploy with the model.
num_nodes = graph.num_nodes()
num_edges = graph.num_edges()

# Reachability: all transitive dependency pairs.
reachable = graph.reachable(full=True)

# Betweenness centrality: structural bottlenecks.
betweenness = graph.betweenness_centrality()

# --------------------------------------------------
# Assembly path enumeration
#   PREVIEW capability; requires relationalai>=1.15.
# --------------------------------------------------
# Where betweenness scores a single *node*, this enumerates the full *chains*
# that build each finished good: every bottom-up assembly path from a raw
# material up through its components to the finished good. We derive a binary
# SKU->SKU "feeds into" edge from the BillOfMaterials intermediary (the input
# SKU feeds the output SKU), enumerate all such paths, then keep only the
# maximal (longest, non-extendable) chains so that sub-paths are suppressed.

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
# -> finished goods, never back), so .all().paths() already yields simple paths --
# there is no cycle risk, and the repeat bound only needs to cover the BOM depth.
# Deepest chain here is raw_material -> component -> finished_good (2 hops); we
# allow extra headroom so deeper BOMs enumerate fully.
MAX_ASSEMBLY_HOPS = 4
p = model.path(SKU.feeds.repeat(1, MAX_ASSEMBLY_HOPS)).all().paths()

# Persist an assembly depth onto every SKU that ends an assembly chain (it feeds
# nothing further): the length of the longest chain that ends at it.
built, next_sku = SKU.ref(), SKU.ref()
chain = model.path(SKU.feeds.repeat(1, MAX_ASSEMBLY_HOPS), built).all().paths()
SKU.assembly_depth = model.Property(f"{SKU} has assembly depth {Integer:assembly_depth}")
model.where(chain, not_(built.feeds(next_sku))).define(
    built.assembly_depth(aggs.max(chain.length).per(built))
)
