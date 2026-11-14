"""Dependency graph, bottleneck scores, and assembly chains over the BOM."""

from relationalai.semantics import Integer, not_
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.std import aggregates as aggs

from .schema import SKU, BillOfMaterials, model

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

# Graph size.
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
