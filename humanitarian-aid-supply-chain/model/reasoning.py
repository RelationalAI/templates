"""Supply route graph: PageRank, degree centrality, and in/out route counts."""

from relationalai.semantics import Float, define
from relationalai.semantics.reasoners.graph import Graph

from .schema import DistributionPoint, SupplyRoute, model

# Computed property: effective flow weight combining capacity, reliability, and distance
# Higher values indicate routes that are preferred for aid flow
# Formula: (capacity * reliability) / distance
SupplyRoute.flow_weight = model.Property(f"{SupplyRoute} has {Float:flow_weight}")

# Define the computed flow_weight for each route
# This represents expected aid throughput considering capacity, reliability, and distance
define(SupplyRoute.flow_weight((SupplyRoute.route_capacity * SupplyRoute.reliability_score) / SupplyRoute.distance_km))

# Define directed, weighted graph with DistributionPoint nodes and SupplyRoute edges
graph = Graph(
    model,
    directed=True,
    weighted=True,
    node_concept=DistributionPoint,
    edge_concept=SupplyRoute,
    edge_src_relationship=SupplyRoute.from_point,
    edge_dst_relationship=SupplyRoute.to_point,
    # Use composite flow_weight that combines capacity, reliability, and distance
    # Higher weights indicate routes with better expected aid throughput
    edge_weight_relationship=SupplyRoute.flow_weight
)

# PageRank: Identifies influential hubs where aid naturally flows
# The damping factor (0.85) models the probability of continuing along supply routes
# vs. "teleporting" to a random point (simulates external aid injections)
pagerank = graph.pagerank(damping_factor=0.85, tolerance=1e-6, max_iter=100)

# Degree Centrality: Identifies highly connected network hubs
# Points with high degree centrality have many connections and serve as critical coordination points
# These are essential for network resilience and aid distribution capacity
degree_centrality = graph.degree_centrality()

# Also calculate basic degree metrics for context
indegree = graph.indegree()  # Number of incoming supply routes
outdegree = graph.outdegree()  # Number of outgoing supply routes

# Attach each result to DistributionPoint, so the deployed model publishes it for the queries.
DistributionPoint.pagerank = pagerank
DistributionPoint.degree_centrality = degree_centrality
DistributionPoint.indegree = indegree
DistributionPoint.outdegree = outdegree
