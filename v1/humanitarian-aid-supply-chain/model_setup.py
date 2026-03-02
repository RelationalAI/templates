"""Shared model setup for Humanitarian Aid Supply Chain Network analysis.

This module contains the common model configuration, concept definitions,
and data loading logic used by both the CLI script and Streamlit app.
"""

from pathlib import Path
import pandas as pd

from relationalai.semantics import Model, data, define, String, Integer, Float
from relationalai.semantics.reasoners.graph import Graph

DATA_DIR = Path(__file__).parent / "data"


def create_model():
    """Create and configure the RelationalAI model with all concepts and relationships.

    Returns:
        tuple: (model, graph, DistributionPoint, SupplyRoute)
    """
    # Create a Semantics model container
    model = Model("humanitarian_aid_supply_chain", config=globals().get("config", None))

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
            from_point=from_dist.filter_by(id=routes_data.from_point_id),
            to_point=to_dist.filter_by(id=routes_data.to_point_id),
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

    return model, graph, DistributionPoint, SupplyRoute
