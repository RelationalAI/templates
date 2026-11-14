"""Load the sample sites, routes, and demands into the warehouse allocation model."""

from pathlib import Path

from pandas import read_csv

from .schema import Demand, Route, Site, model

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

model.define(Site.new(model.data(read_csv(DATA_DIR / "sites.csv")).to_schema()))

route_data = model.data(read_csv(DATA_DIR / "routes.csv"))
model.define(
    r := Route.new(
        id=route_data.id,
        source=Site.lookup(id=route_data.source_id),
        dest=Site.lookup(id=route_data.dest_id),
    ),
    r.capacity(route_data.capacity),
    r.transport_cost(route_data.transport_cost),
)

demand_data = model.data(read_csv(DATA_DIR / "demands.csv"))
model.define(
    d := Demand.new(
        id=demand_data.id,
        site=Site.lookup(id=demand_data.site_id),
    ),
    d.quantity(demand_data.quantity),
)
