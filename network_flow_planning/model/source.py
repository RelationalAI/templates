"""Load the sample sites, lanes, and demands into the network flow planning model."""

from pathlib import Path

from pandas import read_csv

from .schema import Demand, Lane, Site, model

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# Load sites.
site_csv = read_csv(DATA_DIR / "sites.csv")
model.define(Site.new(model.data(site_csv).to_schema()))

# Load lanes.
lane_csv = read_csv(DATA_DIR / "lanes.csv")
lane_data = model.data(lane_csv)
model.define(
    lane := Lane.new(
        id=lane_data.id,
        source=Site.lookup(id=lane_data.source_id),
        dest=Site.lookup(id=lane_data.dest_id),
    ),
    lane.cost_per_unit(lane_data.cost_per_unit),
    lane.capacity(lane_data.capacity),
)

# Load demands.
demand_csv = read_csv(DATA_DIR / "demand.csv")
demand_data = model.data(demand_csv)
model.define(
    d := Demand.new(
        id=demand_data.id,
        site=Site.lookup(id=demand_data.site_id),
    ),
    d.quantity(demand_data.quantity),
    d.customer(demand_data.customer),
    d.priority(demand_data.priority),
)
