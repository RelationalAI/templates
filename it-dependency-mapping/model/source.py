"""Load the sample features and dependency edges into the IT dependency mapping model."""

from pathlib import Path

import pandas as pd

from .schema import Feature, model

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def load_csv(path):
    return pd.read_csv(path)


# Load feature data from CSV.
feature_data = model.data(load_csv(DATA_DIR / "features.csv"))
model.define(Feature.new(id=feature_data["id"]))
model.where(Feature.id == feature_data["id"]).define(
    Feature.name(feature_data["name"]),
    Feature.owner(feature_data["owner"]),
    Feature.deploy_tier(feature_data["deploy_tier"]),
)

# Load dependency edges from CSV (upstream feature -> downstream feature).
dependency_data = model.data(load_csv(DATA_DIR / "dependencies.csv"))
upstream, downstream = Feature.ref(), Feature.ref()
model.where(
    upstream.id == dependency_data["from_feature"],
    downstream.id == dependency_data["to_feature"],
).define(upstream.contributes_to(downstream))
