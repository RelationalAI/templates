"""Load the sample distribution points and supply routes into the humanitarian aid supply chain model."""

from pathlib import Path

import pandas as pd
from relationalai.semantics import data, define

from .schema import DistributionPoint, SupplyRoute, model

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

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
