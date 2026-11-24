"""Dependency graph, bottleneck scores, and assembly chains over the BOM."""

from relationalai.semantics import Hash, Integer, not_
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.std import aggregates as aggs

from .schema import SKU, BillOfMaterials, model

# --------------------------------------------------
# Build graph: SKU nodes, BOM edges (directed)
# Edge: output_sku -> input_sku ("depends on")
# --------------------------------------------------

graph = Graph(
    model,
    name="bom_graph",
    directed=True,
    weighted=False,
    node_concept=SKU,
    edge_concept=BillOfMaterials,
    edge_src_relationship=BillOfMaterials.output_sku,
    edge_dst_relationship=BillOfMaterials.input_sku,
)

# Graph size, which the deployed model publishes for the queries.
node_count, edge_count = Integer.ref(), Integer.ref()
num_nodes = model.Relationship(f"the BOM graph has {Integer:num_nodes} nodes")
num_edges = model.Relationship(f"the BOM graph has {Integer:num_edges} edges")
model.where(graph.num_nodes()(node_count)).define(num_nodes(node_count))
model.where(graph.num_edges()(edge_count)).define(num_edges(edge_count))

# Reachability: all transitive dependency pairs.
reachable = graph.reachable(full=True)

# Betweenness centrality: structural bottlenecks.
betweenness = graph.betweenness_centrality()

# Attach both results to SKU, so the deployed model publishes them for the queries.
SKU.reaches = reachable
SKU.betweenness = betweenness

# How many other SKUs transitively depend on each SKU.
dependent = SKU.ref()
SKU.depended_on_by = model.Property(f"{SKU} is depended on by {Integer:depended_on_by} SKUs")
model.where(dependent.reaches(SKU), dependent != SKU).define(
    SKU.depended_on_by(aggs.count(dependent).per(SKU))
)

# --------------------------------------------------
# Assembly path enumeration
#   PREVIEW capability; requires relationalai>=1.15.
# --------------------------------------------------
# Where betweenness scores a single *node*, this enumerates the full *chains*
# that build each finished good: every bottom-up assembly path from a raw
# material up through its components to the finished good. We derive a binary
# SKU->SKU "feeds into" edge from the BillOfMaterials intermediary (the input
# SKU feeds the output SKU), enumerate all such paths, then mark the
# maximal (non-extendable) chains so that sub-paths can be suppressed.

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

# The chains, which the deployed model publishes for the queries: the SKU at each step of
# each chain, keyed by the chain's path id.
AssemblyStep = model.Relationship(
    f"assembly chain {Hash:path} has {SKU:sku} at step {Integer:step}"
)
model.where(p).define(AssemblyStep(p, SKU(p.nodes), p.nodes["index"]))

# A chain is maximal when nothing feeds its first SKU and its last SKU feeds nothing.
# A chain longer than MAX_ASSEMBLY_HOPS is not enumerated, so it is never marked maximal.
MaximalChain = model.Relationship(f"assembly chain {Hash:path} is maximal")
first, last, upstream, downstream = SKU.ref(), SKU.ref(), SKU.ref(), SKU.ref()
model.where(
    p,
    p.nodes(0) == first,
    p.nodes(p.length) == last,
    not_(upstream.feeds(first)),
    not_(last.feeds(downstream)),
).define(MaximalChain(p))

# Assembly depth of each SKU that ends a maximal chain: the length of the longest one.
end = SKU.ref()
SKU.assembly_depth = model.Property(f"{SKU} has assembly depth {Integer:assembly_depth}")
model.where(MaximalChain(p), p.nodes(p.length) == end).define(
    end.assembly_depth(aggs.max(p.length).per(end))
)
