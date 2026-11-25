"""Dependency graph: the directed SKU graph over the BOM, each SKU's transitive dependencies and
dependents, and its betweenness-centrality bottleneck score and rank."""

from relationalai.semantics import Integer, String
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

# How many other SKUs each SKU transitively depends on, in total and of each type.
dependency, dep_type = SKU.ref(), String.ref()
SKU.n_dependencies = model.Property(f"{SKU} depends on {Integer:n_dependencies} SKUs")
SKU.n_dependencies_by_type = model.Relationship(
    f"{SKU} depends on {Integer:n_dependencies} SKUs of type {String:dep_type}"
)
model.where(SKU.reaches(dependency), dependency != SKU).define(
    SKU.n_dependencies(aggs.count(dependency).per(SKU))
)
model.where(SKU.reaches(dependency), dependency != SKU, dependency.type == dep_type).define(
    SKU.n_dependencies_by_type(aggs.count(dependency).per(SKU, dep_type), dep_type)
)

# The bottlenecks: SKUs with a positive betweenness, ranked highest first, ties by SKU id.
SKU.bottleneck_rank = model.Property(f"{SKU} has bottleneck rank {Integer:bottleneck_rank}")
model.where(SKU.betweenness > 0).define(SKU.bottleneck_rank(aggs.rank(-SKU.betweenness, SKU.id)))
