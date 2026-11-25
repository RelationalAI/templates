"""Load the sample organizations and partnerships into the wildlife conservation model."""

from pathlib import Path

import pandas as pd
from relationalai.semantics import data, define

from .schema import Organization, Partnership, model

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# Load organizations from CSV
org_df = pd.read_csv(DATA_DIR / "organizations.csv")
org_data = data(org_df)

# Create Organization instances with properties mapped to DataFrame columns
model.define(
    Organization.new(
        id=org_data.id,
        name=org_data.name,
        type=org_data.type,
        region=org_data.region,
        focus_species=org_data.focus_species
    )
)

# Load partnership data from CSV
partnerships_data = data(pd.read_csv(DATA_DIR / "partnerships.csv"))

# Create partnerships (undirected relationships in conservation network)
org_from, org_to = Organization.ref("org1"), Organization.ref("org2")

define(
    Partnership.new(
        org1=org_from.lookup(id=partnerships_data.from_org_id),
        org2=org_to.lookup(id=partnerships_data.to_org_id)
    )
)
