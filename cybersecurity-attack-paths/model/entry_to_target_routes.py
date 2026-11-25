"""Entry-to-target routes: every simple route over any technique from one internet-facing entry
asset to one crown jewel, each route's assets, and how many routes there are."""

from relationalai.semantics import Hash, Integer, not_, where
from relationalai.semantics.std import aggregates as aggs

from .schema import Asset, model

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

# Maximum length (in edges) of a route in the point query between two named assets.
MAX_ROUTE_HOPS = 6
# The point query's endpoints: a specific internet-facing entry and a crown jewel.
ENTRY_ASSET = "web-01"
TARGET_ASSET = "db-01"

# --------------------------------------------------
# Paths: routes between two named assets
# --------------------------------------------------
# The point query's pattern: routes over the technique-agnostic can_reach edge from
# a pinned entry asset to a pinned crown jewel, 1..MAX_ROUTE_HOPS hops.
src_pt, dst_pt = Asset.ref(), Asset.ref()
route = model.path(src_pt.can_reach.repeat(1, MAX_ROUTE_HOPS), dst_pt).all().paths()

# Keep only SIMPLE routes (no asset revisited). .all().paths() has WALK semantics and no
# native simple-path mode, so drop node-repeating walks with a negated existential over
# positions -- expressed natively in the route's where() (no pandas).
i, j = Integer.ref(), Integer.ref()
simple_route = [
    route,
    src_pt.id == ENTRY_ASSET,
    dst_pt.id == TARGET_ASSET,
    not_(where(i < j, route.nodes(i) == route.nodes(j))),
]

# The deployed model publishes the routes the report reads, keyed by each route's id: the
# assets in order, and how many routes there are.
RouteStep = model.Relationship(
    f"entry-to-target route {Hash:path} has {Asset:asset} at step {Integer:step}"
)
model.where(*simple_route).define(RouteStep(route, Asset(route.nodes), route.nodes["index"]))
RouteCount = model.Relationship(f"there are {Integer:n_routes} entry-to-target routes")
counted_route, route_asset, route_step = Hash.ref(), Asset.ref(), Integer.ref()
model.define(RouteCount(
    aggs.count(counted_route).where(RouteStep(counted_route, route_asset, route_step)) | 0
))
