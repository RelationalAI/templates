"""Kill-chain attack paths, the entry-to-crown-jewel route query, and the on-attack-path flag."""

from relationalai.semantics import Integer, String

from .schema import Asset, model

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

# Lateral-movement depth: how many pivot_to hops the kill-chain may take after the
# initial exploit + credential reuse. The estate is small, so a low cap suffices.
MAX_PIVOTS = 2
# Maximum length (in edges) of a route in the point query between two named assets.
MAX_ROUTE_HOPS = 6
# The point query's endpoints: a specific internet-facing entry and a crown jewel.
ENTRY_ASSET = "web-01"
TARGET_ASSET = "db-01"

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
