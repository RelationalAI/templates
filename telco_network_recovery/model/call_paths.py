"""Call paths: the simple call routes from the highest-PageRank subscriber, the routing towers on them,
and the top route by influence load."""

from relationalai.semantics import Float, Hash, Integer, not_, where
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std import math

# Declares Subscriber.influence_score, the PageRank the paths are ranked by.
from . import customer_impact  # noqa: F401
from .schema import CallDetailRecord, CellTower, Subscriber, model

# --------------------------------------------------
# Stage 4: Paths -- Call-path enumeration through critical towers
#   PREVIEW capability.
# --------------------------------------------------
# Composes on Stage 3's Subscriber.influence_score (PageRank). Where
# PageRank scores a *node*, paths scores the *call route*: the model
# enumerates caller -> ... -> callee chains from the top-PageRank
# subscriber, recovers the routing tower on each hop, and ranks each
# route by total influence summed along the chain. The routing tower
# is the auxiliary middle field of an arity-3 edge, so each enumerated
# path also tells us which towers the influence flows through.

# Arity-3 call edge: {Subscriber:caller} via {CellTower:tower} calls {Subscriber:callee}.
# First/last fields (caller/callee) are the path endpoints; the tower is the
# auxiliary middle field (field_index 1), recoverable per hop via
# relationship_fields. Derived from CallDetailRecord's caller/callee/routed_through.
Subscriber.calls_via = model.Relationship(
    f"{Subscriber:caller} via {CellTower:tower} calls {Subscriber:callee}",
    short_name="calls_via",
)
cdr_edge = CallDetailRecord.ref()
caller_sub, callee_sub, via_tower = Subscriber.ref(), Subscriber.ref(), CellTower.ref()
model.where(
    cdr_edge.caller(caller_sub),
    cdr_edge.callee(callee_sub),
    cdr_edge.routed_through(via_tower),
).define(caller_sub.calls_via(via_tower, callee_sub))

# Path enumeration is declared here, in the model: a deployed model only has the
# path tables its own rules ask for, so a query cannot enumerate new paths. The
# scope is a deterministic seed -- the highest-PageRank subscriber, the smallest
# ID on an exact tie -- and call paths of up to PATH_MAX_HOPS hops, keeping
# simple paths only (the call graph is cyclic, so the negated existential drops
# walks that revisit a node). Both rank keys sort ascending, with the score
# negated, because the rules that read graph results run on the Logic engine,
# whose rank does not mix ascending and descending keys.
PATH_MAX_HOPS = 3

Subscriber.is_seed_hub = model.Relationship(f"{Subscriber} is the seed hub")
model.define(Subscriber.is_seed_hub()).where(
    aggs.rank(-Subscriber.influence_score, Subscriber.id) == 1
)

seed = Subscriber.ref()
i, j = Integer.ref(), Integer.ref()
call_path = model.path(seed, Subscriber.calls_via.repeat(1, PATH_MAX_HOPS)).all().paths()
simple_hub_path = (seed.is_seed_hub(), call_path, not_(where(i < j, call_path.nodes(i) == call_path.nodes(j))))

SimplePathCount = model.Relationship(f"simple call paths from the seed hub number {Integer:paths}")
model.define(SimplePathCount(aggs.count(call_path).where(*simple_hub_path)))

# The routing tower on each hop is field_index 1 of the arity-3 edge
# (caller=0, tower=1, callee=2).
routing_tower = CellTower.ref()
RoutingTowerCount = model.Relationship(f"routing towers on those paths number {Integer:towers}")
model.define(
    RoutingTowerCount(
        aggs.count(routing_tower).where(
            *simple_hub_path,
            call_path.relationship_fields["field_index"] == 1,
            routing_tower == CellTower(call_path.relationship_fields["field"]),
        )
    )
)

# Rank the simple paths by influence load, the PageRank summed along each path's
# nodes and rounded to six decimals, so paths whose printed loads agree tie, and
# keep the seed hub's highest.
def path_influence_load():
    return math.round(aggs.sum(Subscriber(call_path.nodes).influence_score).per(call_path), 6)


Subscriber.top_call_path_influence = model.Property(f"{Subscriber} has {Float:top_call_path_influence}")
model.where(
    *simple_hub_path,
    load := path_influence_load(),
    top := aggs.max(load).per(seed),
).define(seed.top_call_path_influence(top))

# The winning route: the simple path with the highest influence load (on a tie,
# the smallest path ID), published step by step with the tower on each hop.
TopCallPath = model.Relationship(f"{Hash:path} is the seed hub's top call path")
model.where(
    *simple_hub_path,
    load := path_influence_load(),
    aggs.rank(-load, call_path) == 1,
).define(TopCallPath(call_path))
TopCallPathStep = model.Relationship(
    f"the top call path visits {Subscriber:subscriber} at step {Integer:step}"
)
model.where(*simple_hub_path, TopCallPath(call_path)).define(
    TopCallPathStep(Subscriber(call_path.nodes), call_path.nodes["index"])
)
TopCallPathHop = model.Relationship(
    f"the top call path routes hop {Integer:hop} through {CellTower:tower}"
)
model.where(
    *simple_hub_path,
    TopCallPath(call_path),
    call_path.relationship_fields["field_index"] == 1,
).define(
    TopCallPathHop(
        call_path.relationship_fields["index"],
        CellTower(call_path.relationship_fields["field"]),
    )
)
