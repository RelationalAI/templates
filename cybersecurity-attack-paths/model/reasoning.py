"""Kill-chain attack paths, the entry-to-crown-jewel route query, and the on-attack-path flag."""

from relationalai.semantics import Hash, Integer, String, not_, where
from relationalai.semantics.std import aggregates as aggs

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
#   PREVIEW capability.
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

# The crown-jewel kill-chains: an internet-facing foothold that ends on a crown jewel.
crown_kill = [kill, a.internet_facing == "yes", dst.crown_jewel == "yes"]

# Asset.on_attack_path marks the assets that lie on a crown-jewel kill-chain, so a
# downstream query can pull them without re-enumerating paths. It is a
# Relationship, not a Property: deploying this rule as a Property fails planning.
Asset.on_attack_path = model.Relationship(f"{Asset} on attack path {String:on_attack_path}")
on_path, pos = Asset.ref(), Integer.ref()
model.where(*crown_kill, on_path == kill.nodes(pos)).define(on_path.on_attack_path("yes"))

# --------------------------------------------------
# Published paths
# --------------------------------------------------
# The deployed model publishes the paths the report reads, keyed by each path's id: the
# crown-jewel kill-chains' assets, techniques, and total exposure, and the point query's
# simple routes.
KillChainStep = model.Relationship(
    f"kill chain {Hash:path} has {Asset:asset} at step {Integer:step}"
)
model.where(*crown_kill).define(KillChainStep(kill, Asset(kill.nodes), kill.nodes["index"]))

# The technique at each hop is the traversed relationship's label, e.g. "Asset.exploit_to".
KillChainHop = model.Relationship(
    f"kill chain {Hash:path} uses {String:technique} at hop {Integer:hop}"
)
model.where(*crown_kill).define(
    KillChainHop(kill, kill.relationships["relationship"], kill.relationships["index"])
)

# Exposure is a per-asset score (a stand-in for a CVSS / attack-surface metric) summed ALONG
# each kill-chain IN PYREL: aggregates.sum(Asset(kill.nodes).exposure_score).per(kill) sums
# the per-node value over each path's node sequence -- the core paths-only aggregation. This
# is a position-sum (every node position, with repetition); it equals the distinct-asset sum
# because each kill-chain here is a simple path (no asset revisited).
KillChainExposure = model.Relationship(
    f"kill chain {Hash:path} has total exposure {Integer:total_exposure}"
)
model.where(*crown_kill, total := aggs.sum(Asset(kill.nodes).exposure_score).per(kill)).define(
    KillChainExposure(kill, total)
)

# Keep only SIMPLE routes (no asset revisited). .all().paths() has WALK semantics and no
# native simple-path mode, so drop node-repeating walks with a negated existential over
# positions -- expressed natively in the route's where() (no pandas).
i, j = Integer.ref(), Integer.ref()
RouteStep = model.Relationship(
    f"entry-to-target route {Hash:path} has {Asset:asset} at step {Integer:step}"
)
model.where(
    route,
    src_pt.id == ENTRY_ASSET,
    dst_pt.id == TARGET_ASSET,
    not_(where(i < j, route.nodes(i) == route.nodes(j))),
).define(RouteStep(route, Asset(route.nodes), route.nodes["index"]))
