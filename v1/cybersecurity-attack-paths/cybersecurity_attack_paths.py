"""Cybersecurity attack-path analysis (graph paths) template.

Enumerates multi-step attack chains across an enterprise asset graph by composing
distinct attacker techniques in series -- a capability unlocked by multi-edge path
patterns (relationalai>=1.15):

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
    /opt/homebrew/bin/python3.11 cybersecurity_attack_paths.py

Output:
    Prints the kill-chain attack paths into crown jewels (with the technique at
    each hop), every route between a chosen entry point and a chosen crown jewel,
    the kill-chains ranked by total asset exposure, and the assets flagged
    on a crown-jewel attack path.
"""

from pathlib import Path

import pandas as pd
from relationalai.semantics import Integer, Model, String

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"

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
#   PREVIEW capability; requires relationalai>=1.15.
# --------------------------------------------------
# model.path(a.exploit_to, b.cred_to, c.pivot_to.repeat(1, MAX_PIVOTS), dst) is a
# MULTI-EDGE pattern: distinct relationships in series. It matches the kill-chain
# order -- one exploit hop, then one credential-reuse hop, then 1..MAX_PIVOTS
# lateral pivots -- ending at the explicit dst endpoint. Filtering the source to
# an internet-facing asset and dst to a crown jewel pins the threat model: an
# externally reachable foothold that ends on a high-value asset.

print("=== Cybersecurity Attack Paths: kill-chain into crown jewels ===")

a, b, c, dst = Asset.ref(), Asset.ref(), Asset.ref(), Asset.ref()
kill = model.path(a.exploit_to, b.cred_to, c.pivot_to.repeat(1, MAX_PIVOTS), dst).all_paths()
kill_df = (
    model.where(
        kill,
        a.internet_facing == "yes",
        dst.crown_jewel == "yes",
    )
    .select(
        kill.alias("path_id"),
        kill.nodes["index"].alias("step"),
        Asset(kill.nodes).id.alias("asset_id"),
        Asset(kill.nodes).name.alias("asset_name"),
    )
    .to_df()
)
# Technique at each hop (the relationship label), as a separate projection.
hop_df = (
    model.where(
        kill,
        a.internet_facing == "yes",
        dst.crown_jewel == "yes",
    )
    .select(
        kill.alias("path_id"),
        kill.relationships["index"].alias("hop"),
        kill.relationships["relationship"].alias("technique"),
    )
    .to_df()
)

kill_df["step"] = kill_df["step"].astype(int)
kill_df = kill_df.drop_duplicates(["path_id", "step"]).sort_values(["path_id", "step"])
hop_df["hop"] = hop_df["hop"].astype(int)
hop_df = hop_df.drop_duplicates(["path_id", "hop"]).sort_values(["path_id", "hop"])

# Reassemble each kill-chain: ordered asset names + the technique used at each hop.
def technique_label(raw):
    # relationship labels arrive as e.g. "-<exploit_to>->"; strip to the verb stem.
    return raw.strip("-<>⟨⟩→ ").replace("_to", "")

chains = []
for pid, g in kill_df.groupby("path_id"):
    assets = list(g.sort_values("step")["asset_name"])
    techs = [technique_label(t) for t in
             hop_df[hop_df["path_id"] == pid].sort_values("hop")["technique"]]
    labelled = assets[0]
    for nm, tech in zip(assets[1:], techs):
        labelled += f"  --[{tech}]-->  {nm}"
    chains.append({"path_id": pid, "hops": len(assets) - 1, "asset_ids": tuple(
        g.sort_values("step")["asset_id"]), "labelled": labelled})

print(f"\n{len(chains)} kill-chain attack path(s) reach a crown jewel "
      f"(exploit -> cred -> 1-{MAX_PIVOTS} pivots, from an internet-facing asset):")
for ch in sorted(chains, key=lambda c: c["hops"]):
    print(f"  [{ch['hops']} hops] {ch['labelled']}")

# --------------------------------------------------
# Point query: every route between one entry and one crown jewel
# --------------------------------------------------
# Pin both endpoints by id and enumerate all simple routes between them over the
# technique-agnostic can_reach edge (any technique, 1..MAX_ROUTE_HOPS). This is the
# >=1.15 native point query -- src/dst unified to specific assets inside all_paths().

src_pt, dst_pt = Asset.ref(), Asset.ref()
route = model.path(src_pt.can_reach.repeat(1, MAX_ROUTE_HOPS), dst_pt).all_paths()
route_df = (
    model.where(
        route,
        src_pt.id == ENTRY_ASSET,
        dst_pt.id == TARGET_ASSET,
    )
    .select(
        route.alias("path_id"),
        route.nodes["index"].alias("step"),
        Asset(route.nodes).id.alias("asset_id"),
    )
    .to_df()
)
route_df["step"] = route_df["step"].astype(int)
route_df = route_df.drop_duplicates(["path_id", "step"]).sort_values(["path_id", "step"])
routes = []
for pid, g in route_df.groupby("path_id"):
    seq = list(g.sort_values("step")["asset_id"])
    if len(set(seq)) == len(seq):  # simple
        routes.append(tuple(seq))
routes = sorted(set(routes), key=len)

print(f"\n=== Point query: all routes from {ENTRY_ASSET} to {TARGET_ASSET} "
      f"(any technique, <= {MAX_ROUTE_HOPS} hops, simple) ===")
print(f"  {len(routes)} route(s):")
for seq in routes:
    print("    " + " -> ".join(seq))

# --------------------------------------------------
# Rank kill-chains by total asset exposure
# --------------------------------------------------
# The riskiest chain is the one whose assets carry the most exposure overall -- the
# first remediation target. Exposure is a per-asset score (a stand-in for a CVSS /
# attack-surface metric) summed across the chain's distinct assets.

exposure = dict(
    model.select(Asset.id.alias("id"), Asset.exposure_score.alias("e")).to_df()
    .itertuples(index=False, name=None)
)
for ch in chains:
    ch["total_exposure"] = sum(exposure[i] for i in ch["asset_ids"])

print("\n=== Kill-chains ranked by total asset exposure (highest = remediate first) ===")
for ch in sorted(chains, key=lambda c: c["total_exposure"], reverse=True):
    print(f"  exposure {ch['total_exposure']:>3}  ({ch['hops']} hops)  {ch['labelled']}")

# --------------------------------------------------
# Persist: flag assets that lie on a crown-jewel attack path
# --------------------------------------------------
# Bind the result back onto the ontology so a downstream query can pull the assets
# on a kill-chain without re-enumerating paths.

Asset.on_attack_path = model.Property(f"{Asset} on attack path {String:on_attack_path}")
on_path_ids = sorted({i for ch in chains for i in ch["asset_ids"]})
flag_data = model.data(pd.DataFrame({"id": on_path_ids}))
fa = Asset.ref()
model.where(fa.id == flag_data["id"]).define(fa.on_attack_path("yes"))

x = Asset.ref()
flagged = (
    model.where(
        x.on_attack_path == "yes",
    )
    .select(x.id.alias("id"), x.name.alias("name"), x.zone.alias("zone"))
    .to_df()
)

print("\n=== Assets on a crown-jewel attack path (Asset.on_attack_path persisted) ===")
print(f"  {len(flagged)} of {len(exposure)} assets:")
for _, r in flagged.sort_values("id").iterrows():
    print(f"    {r['id']:<8} {r['name']:<24} ({r['zone']})")
