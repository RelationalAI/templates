"""Load the sample assets and attack steps into the attack-path model."""

from pathlib import Path

import pandas as pd

from .schema import Asset, model

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def load_csv(filename):
    return pd.read_csv(DATA_DIR / filename)


# Load asset data.
asset_data = model.data(load_csv("assets.csv"))
model.define(Asset.new(id=asset_data["id"]))
model.where(Asset.id == asset_data["id"]).define(
    Asset.name(asset_data["name"]),
    Asset.zone(asset_data["zone"]),
    Asset.internet_facing(asset_data["internet_facing"]),
    Asset.crown_jewel(asset_data["crown_jewel"]),
    Asset.exposure_score(asset_data["exposure_score"]),
)

# Load attack steps. Each row is one technique-specific edge: its technique picks the
# typed edge it populates, and every row populates the can_reach union.
steps = model.data(load_csv("attack_steps.csv"))
u, v = Asset.ref(), Asset.ref()
step_ends = (u.id == steps["src"], v.id == steps["dst"])
model.where(*step_ends, steps["technique"] == "exploit").define(u.exploit_to(v))
model.where(*step_ends, steps["technique"] == "cred").define(u.cred_to(v))
model.where(*step_ends, steps["technique"] == "pivot").define(u.pivot_to(v))
model.where(*step_ends).define(u.can_reach(v))
