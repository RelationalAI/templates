"""Cybersecurity attack-path analysis (graph paths) template.

Enumerates multi-step attack chains across an enterprise asset graph by composing
distinct attacker techniques in series -- a capability unlocked by multi-edge path
patterns (relationalai>=1.21):

- Loads Asset nodes (hosts, services, accounts) and three DISTINCT directed edges
  between them, one per technique: exploit_to (vulnerability exploitation),
  cred_to (credential reuse), pivot_to (network lateral movement).
- Enumerates kill-chain attack paths with a multi-relationship sequence:
  ``model.path(a.exploit_to, b.cred_to, c.pivot_to.repeat(1, N), dst)`` -- the
  classic order (exploit a perimeter host, reuse credentials inward, then pivot to
  a crown jewel). The edge order is enforced by the pattern; a single unioned
  "can move" edge or a flat join cannot express "exploit FIRST, then creds, then
  pivots". ``p.relationships`` labels the technique used at each hop.
- Runs a point query between one named internet-facing entry and one named crown
  jewel over a derived ``can_reach`` edge, enumerating every route between them.
- Scores each kill-chain by the asset exposure summed along it, and persists
  ``Asset.on_attack_path`` back to the ontology for the assets that lie on a
  crown-jewel-reaching chain.

Run:
    `rai models deploy --path model` deploys this model to the schema in
    raiconfig.yaml and waits for its first refresh; `python -m
    queries.attack_path_report` then prints the report from the deployed model.
"""

from pathlib import Path

import pandas as pd
from relationalai.semantics import Integer, Model, String

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# Lateral-movement depth: how many pivot_to hops the kill-chain may take after the
# initial exploit + credential reuse. The estate is small, so a low cap suffices.
MAX_PIVOTS = 2
# Maximum length (in edges) of a route in the point query between two named assets.
MAX_ROUTE_HOPS = 6
# The point query's endpoints: a specific internet-facing entry and a crown jewel.
ENTRY_ASSET = "web-01"
TARGET_ASSET = "db-01"


def load_csv(filename):
    return pd.read_csv(DATA_DIR / filename)


# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

model = Model("cybersecurity_attack_paths")

# Asset concept: a host, service, or account in the enterprise estate.
Asset = model.Concept("Asset", identify_by={"id": String})
Asset.name = model.Property(f"{Asset} has {String:name}")
Asset.zone = model.Property(f"{Asset} sits in {String:zone}")
Asset.internet_facing = model.Property(f"{Asset} is internet facing {String:internet_facing}")
Asset.crown_jewel = model.Property(f"{Asset} is crown jewel {String:crown_jewel}")
Asset.exposure_score = model.Property(f"{Asset} has exposure score {Integer:exposure_score}")

# One directed self-relationship per attacker technique. An edge means "an attacker
# on the source asset can reach the destination asset by this technique".
Asset.exploit_to = model.Relationship(f"{Asset} exploits to {Asset}", short_name="exploit_to")
Asset.cred_to = model.Relationship(f"{Asset} reuses credentials to {Asset}", short_name="cred_to")
Asset.pivot_to = model.Relationship(f"{Asset} pivots to {Asset}", short_name="pivot_to")
# Technique-agnostic union edge: an attacker can move from src to dst by SOME
# technique. Used for the point query (any route between two named assets).
Asset.can_reach = model.Relationship(f"{Asset} can reach {Asset}", short_name="can_reach")

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

# --------------------------------------------------
# Paths: kill-chain attack paths (multi-relationship sequence)
#   PREVIEW capability; requires relationalai>=1.21.
# --------------------------------------------------
# model.path(a.exploit_to, b.cred_to, c.pivot_to.repeat(1, MAX_PIVOTS), dst) is a
# MULTI-EDGE pattern: distinct relationships in series. It matches the kill-chain
# order -- one exploit hop, then one credential-reuse hop, then 1..MAX_PIVOTS
# lateral pivots -- ending at the explicit dst endpoint. Filtering the source to
# an internet-facing asset and dst to a crown jewel pins the threat model: an
# externally reachable foothold that ends on a high-value asset.

a, b, c, dst = Asset.ref(), Asset.ref(), Asset.ref(), Asset.ref()
kill = model.path(a.exploit_to, b.cred_to, c.pivot_to.repeat(1, MAX_PIVOTS), dst).all().paths()

# The point query's pattern: routes over the technique-agnostic can_reach edge from
# a pinned entry asset to a pinned crown jewel, 1..MAX_ROUTE_HOPS hops.
src_pt, dst_pt = Asset.ref(), Asset.ref()
route = model.path(src_pt.can_reach.repeat(1, MAX_ROUTE_HOPS), dst_pt).all().paths()

# Asset.on_attack_path marks the assets that lie on a crown-jewel kill-chain, so a
# downstream query can pull them without re-enumerating paths. It is a
# Relationship, not a Property: deploying this rule as a Property fails planning
# on relationalai 2.1.1.
Asset.on_attack_path = model.Relationship(f"{Asset} on attack path {String:on_attack_path}")
on_path, pos = Asset.ref(), Integer.ref()
model.where(
    kill,
    a.internet_facing == "yes",
    dst.crown_jewel == "yes",
    on_path == kill.nodes(pos),
).define(on_path.on_attack_path("yes"))
