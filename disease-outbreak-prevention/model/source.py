"""Load the sample facilities and their connections into the disease outbreak prevention model."""

from pathlib import Path

import pandas as pd
from relationalai.semantics import data, define

from .schema import Facility, FacilityConnection, model

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# Load facilities from CSV
facility_df = pd.read_csv(DATA_DIR / "facilities.csv")
facility_data = data(facility_df)

# Create Facility instances with properties mapped to DataFrame columns
model.define(
    Facility.new(
        id=facility_data.id,
        name=facility_data.name,
        type=facility_data.type,
        region=facility_data.region
    )
)

# Load connection data from CSV
connections_data = data(pd.read_csv(DATA_DIR / "connections.csv"))

# Create facility connections
f_from, f_to = Facility.ref("from_facility"), Facility.ref("to_facility")

define(
    FacilityConnection.new(
        from_facility=f_from.lookup(id=connections_data.from_facility_id),
        to_facility=f_to.lookup(id=connections_data.to_facility_id),
        transfer_volume=connections_data.transfer_volume,
        contact_intensity=connections_data.contact_intensity
    )
)
