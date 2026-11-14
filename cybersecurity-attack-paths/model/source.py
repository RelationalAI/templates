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

# Load attack steps. Each row is one technique-specific edge; split by technique to
# populate the three typed edges, and load every row into the can_reach union.
steps_df = load_csv("attack_steps.csv")
for technique, rel in [("exploit", "exploit_to"), ("cred", "cred_to"), ("pivot", "pivot_to")]:
    sub = model.data(steps_df[steps_df["technique"] == technique][["src", "dst"]])
    u, v = Asset.ref(), Asset.ref()
    model.where(
        u.id == sub["src"],
        v.id == sub["dst"],
    ).define(getattr(u, rel)(v))

all_steps = model.data(steps_df[["src", "dst"]])
ru, rv = Asset.ref(), Asset.ref()
model.where(
    ru.id == all_steps["src"],
    rv.id == all_steps["dst"],
).define(ru.can_reach(rv))
