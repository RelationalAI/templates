"""Kill-chain attack paths: the exploit, credential-reuse, and pivot chains from an internet-facing
asset into a crown jewel, each chain's steps, techniques, hop count, exposure, and remediation
priority, and the assets that lie on a chain."""

from relationalai.semantics import Hash, Integer, String
from relationalai.semantics.std import aggregates as aggs

from .schema import Asset, model

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

# Lateral-movement depth: how many pivot_to hops the kill-chain may take after the
# initial exploit + credential reuse. The estate is small, so a low cap suffices.
MAX_PIVOTS = 2

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
# crown-jewel kill-chains' assets, techniques, hop counts, and total exposure.
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

# Each kill-chain's length in hops, and how many kill-chains there are.
KillChainHops = model.Relationship(f"kill chain {Hash:path} has {Integer:hops} hops")
model.where(*crown_kill).define(KillChainHops(kill, kill.length))
KillChainCount = model.Relationship(f"there are {Integer:n_chains} kill chains")
chain, chain_hops = Hash.ref(), Integer.ref()
model.define(KillChainCount(aggs.count(chain).where(KillChainHops(chain, chain_hops)) | 0))

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

# Remediation priority: 1 for the kill-chain with the most total exposure. Ties go to the
# lower path id. The exposure is negated so both keys sort ascending.
KillChainPriority = model.Relationship(
    f"kill chain {Hash:path} has remediation priority {Integer:priority}"
)
exposed_chain, chain_exposure = Hash.ref(), Integer.ref()
model.where(
    KillChainExposure(exposed_chain, chain_exposure),
    priority := aggs.rank(-chain_exposure, exposed_chain),
).define(KillChainPriority(exposed_chain, priority))

# How many assets there are, and how many of them lie on a crown-jewel kill-chain.
AssetCoverage = model.Relationship(
    f"the estate has {Integer:n_assets} assets, {Integer:n_on_attack_path} on an attack path"
)
flagged_asset = Asset.ref()
model.define(AssetCoverage(
    aggs.count(Asset),
    aggs.count(flagged_asset).where(flagged_asset.on_attack_path == "yes") | 0,
))
