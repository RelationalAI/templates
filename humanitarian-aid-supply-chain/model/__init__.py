"""Humanitarian Aid Supply Chain Network (graph analytics) template: the model.

This package declares a humanitarian aid supply chain and its PageRank and Degree
Centrality metrics in RelationalAI:

- Load a network of distribution points and supply routes from CSV files.
- Apply PageRank to identify the most influential distribution hubs where aid naturally flows.
- Calculate Degree Centrality to find highly connected critical nodes that serve as network hubs.
- Calculate each point's incoming and outgoing route counts.

Run:
    `rai models deploy --path model` deploys this model to the schema in
    raiconfig.yaml and waits for its first refresh, which computes the graph metrics.
    `python -m queries.distribution_point_ranking` then prints the ranked report, and
    `streamlit run app.py` starts the interactive app, both from the deployed model.
"""

from pathlib import Path

import pandas as pd
from relationalai.semantics import Float, Integer, Model, String, data, define
from relationalai.semantics.reasoners.graph import Graph

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# Create a Semantics model container
model = Model("humanitarian_aid_supply_chain")

# DistributionPoint concept: airports, warehouses, border crossings, relief camps, etc.
DistributionPoint = model.Concept("DistributionPoint", identify_by={"id": Integer})
DistributionPoint.name = model.Property(f"{DistributionPoint} has {String:name}")
DistributionPoint.type = model.Property(f"{DistributionPoint} has {String:type}")
DistributionPoint.region = model.Property(f"{DistributionPoint} has {String:region}")
DistributionPoint.capacity = model.Property(f"{DistributionPoint} has {Integer:capacity}")
DistributionPoint.population_served = model.Property(f"{DistributionPoint} has {Integer:population_served}")

# Load distribution points from CSV
points_df = pd.read_csv(DATA_DIR / "distribution_points.csv")
points_data = data(points_df)

# Create DistributionPoint instances with properties mapped to DataFrame columns
model.define(
    DistributionPoint.new(
        id=points_data.id,
        name=points_data.name,
        type=points_data.type,
        region=points_data.region,
        capacity=points_data.capacity,
        population_served=points_data.population_served
    )
)

# SupplyRoute concept to represent edges in the network
SupplyRoute = model.Concept(
    "SupplyRoute",
    identify_by={"from_point": DistributionPoint, "to_point": DistributionPoint}
)
SupplyRoute.route_capacity = model.Property(f"{SupplyRoute} has {Integer:route_capacity}")
SupplyRoute.reliability_score = model.Property(f"{SupplyRoute} has {Float:reliability_score}")
SupplyRoute.distance_km = model.Property(f"{SupplyRoute} has {Float:distance_km}")

# Computed property: effective flow weight combining capacity, reliability, and distance
# Higher values indicate routes that are preferred for aid flow
# Formula: (capacity * reliability) / distance
SupplyRoute.flow_weight = model.Property(f"{SupplyRoute} has {Float:flow_weight}")

# Load supply route data from CSV
routes_data = data(pd.read_csv(DATA_DIR / "supply_routes.csv"))
from_dist, to_dist = DistributionPoint.ref("from_point"), DistributionPoint.ref("to_point")

define(
    SupplyRoute.new(
        from_point=from_dist.lookup(id=routes_data.from_point_id),
        to_point=to_dist.lookup(id=routes_data.to_point_id),
        route_capacity=routes_data.route_capacity,
        reliability_score=routes_data.reliability_score,
        distance_km=routes_data.distance_km
    )
)

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
