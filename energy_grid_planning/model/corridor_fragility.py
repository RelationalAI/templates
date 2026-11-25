"""Corridor fragility: the simple generator-to-data-center corridors, each data center substation's most
fragile corridor, and the corridors that remain with the highest-betweenness substation offline."""

from relationalai.semantics import Float, Hash, Integer, String, not_, where
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std import math

# Declares Substation.betweenness, the criticality each corridor sums.
from . import grid_topology  # noqa: F401
from .schema import (
    DataCenterRequest,
    DCSubstation,
    Generator,
    GeneratorSubstation,
    Substation,
    TransmissionLine,
    model,
)

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

MAX_CORRIDOR_HOPS = 6
LOAD_DECIMALS = 6  # corridor loads that agree to this many decimals count as equal (absorbs summation noise)

# --------------------------------------------------
# Stage 3: Paths -- Transmission Corridors & Contingency
#   PREVIEW capability; requires relationalai>=1.27 (ordered string_join).
# --------------------------------------------------
# Composes on Stage 2's Substation.betweenness. Where Stage 2 scores a *node*,
# paths scores the *corridor* feeding each data center: enumerate generator-sub ->
# DC-sub transmission routes, rank each by total betweenness summed along its hops
# (most fragile = greatest through-traffic exposure), then drop every corridor through
# the highest-betweenness substation to see which DC substations reroute.

# Bidirectional Substation<->Substation grid edge from active transmission lines.
Substation.connects_to = model.Relationship(
    f"{Substation} connects to {Substation}", short_name="connects_to"
)
tl_fwd = TransmissionLine.ref()
s_from, s_to = Substation.ref(), Substation.ref()
model.where(
    tl_fwd.from_substation(s_from),
    tl_fwd.to_substation(s_to),
    tl_fwd.is_active == True,
).define(s_from.connects_to(s_to))
tl_rev = TransmissionLine.ref()
s_a, s_b = Substation.ref(), Substation.ref()
model.where(
    tl_rev.from_substation(s_a),
    tl_rev.to_substation(s_b),
    tl_rev.is_active == True,
).define(s_b.connects_to(s_a))

# Typed endpoints: substations hosting a generator (source) and a DC request (sink).
gen_ref, gen_sub = Generator.ref(), Substation.ref()
model.where(gen_ref.substation(gen_sub)).define(GeneratorSubstation(gen_sub))
dc_ref, dc_sub = DataCenterRequest.ref(), Substation.ref()
model.where(dc_ref.substation(dc_sub)).define(DCSubstation(dc_sub))

# Enumerate generator-sub -> DC-sub corridors (finite repeat; the grid is meshed/cyclic).
corridor_src, corridor_dst = GeneratorSubstation.ref(), DCSubstation.ref()
corridor = (
    model.path(
        corridor_src, Substation.connects_to.repeat(1, MAX_CORRIDOR_HOPS), corridor_dst
    )
    .all()
    .paths()
)

# Each corridor's substations in hop order, which the deployed model publishes for the queries.
CorridorStep = model.Relationship(
    f"corridor {Hash:corridor} has {Substation:substation} at hop {Integer:hop}"
)
model.where(corridor).define(
    CorridorStep(corridor, Substation(corridor.nodes), corridor.nodes["index"])
)

# Simple corridors: no substation appears twice. The grid is cyclic, so .all().paths() also yields walks
# that revisit a node; the negated existential drops them in the same where() as the sums below, so on
# every corridor that remains the position sum equals the distinct-substation sum.
def _simple_corridor():
    i, j = Integer.ref(), Integer.ref()
    return not_(where(i < j, corridor.nodes(i) == corridor.nodes(j)))


SimpleCorridor = model.Relationship(f"{Hash:corridor} is a simple corridor")
model.where(corridor, _simple_corridor()).define(SimpleCorridor(corridor))

# Each DC substation's fragility load is the highest corridor score among the simple corridors ending
# at it, where a corridor's score sums Stage 2's betweenness over its nodes.
Substation.fragility_load = model.Property(f"{Substation} has {Float:fragility_load}")
model.where(
    corridor,
    _simple_corridor(),
    total := aggs.sum(Substation(corridor.nodes).betweenness).per(corridor),
    frag := aggs.max(total).per(corridor_dst),
).define(corridor_dst.fragility_load(frag))

# The DC substations ranked by fragility load, highest first, ties to the smaller id. Loads compare to
# LOAD_DECIMALS, so float noise from the order a sum adds its terms cannot reorder equal loads. The load
# is negated so both keys sort ascending.
Substation.fragility_rank = model.Property(f"{Substation} has fragility rank {Integer:fragility_rank}")
model.define(
    Substation.fragility_rank(aggs.rank(-math.round(Substation.fragility_load, LOAD_DECIMALS), Substation.id))
)

# Each DC substation's most fragile route: the simple corridor with the highest load (to LOAD_DECIMALS),
# ties to the smaller joined substation ids (ids have a fixed width, so text order is id-list order). The
# route lists the substation names from generator to DC substation.
Substation.fragile_route = model.Property(f"{Substation} has most fragile route {String:fragile_route}")
model.where(
    corridor,
    _simple_corridor(),
    total := aggs.sum(Substation(corridor.nodes).betweenness).per(corridor),
    ids := aggs.string_join(
        Substation(corridor.nodes).id, sep=",", index=corridor.nodes["index"]
    ).per(corridor),
    aggs.rank(-math.round(total, LOAD_DECIMALS), ids).per(corridor_dst) == 1,
    route := aggs.string_join(
        Substation(corridor.nodes).name, sep=" -> ", index=corridor.nodes["index"]
    ).per(corridor),
).define(corridor_dst.fragile_route(route))

# Contingency: the substation with the highest betweenness (ties to the smaller id) goes offline, and every
# corridor through it is dropped. The remaining corridors keep their baseline betweenness.
Substation.is_offline = model.Relationship(f"{Substation} is offline in the contingency")
model.where(aggs.rank(-Substation.betweenness, Substation.id) == 1).define(Substation.is_offline())


# Corridors that avoid the offline substation. The node is read at its own index, as in _simple_corridor, so
# the test applies to the whole corridor; a bare corridor.nodes would bind the node the sums below iterate
# over and only drop the offline substation from them.
def _avoids_offline():
    k, offline = Integer.ref(), Substation.ref()
    return not_(where(offline.is_offline(), corridor.nodes(k) == offline))


# Each DC substation's most fragile route with the offline substation removed; a DC substation with no
# corridor left has none.
Substation.contingency_route = model.Property(
    f"{Substation} has contingency route {String:contingency_route}"
)
model.where(
    corridor,
    _simple_corridor(),
    _avoids_offline(),
    total := aggs.sum(Substation(corridor.nodes).betweenness).per(corridor),
    ids := aggs.string_join(
        Substation(corridor.nodes).id, sep=",", index=corridor.nodes["index"]
    ).per(corridor),
    aggs.rank(-math.round(total, LOAD_DECIMALS), ids).per(corridor_dst) == 1,
    route := aggs.string_join(
        Substation(corridor.nodes).name, sep=" -> ", index=corridor.nodes["index"]
    ).per(corridor),
).define(corridor_dst.contingency_route(route))

# The corridor counts: simple corridors, DC substations with a corridor before and after the contingency,
# those whose most fragile route changes, and those left with none.
CorridorSummary = model.Concept("CorridorSummary", identify_by={"id": Integer})
CorridorSummary.n_corridors = model.Property(f"{CorridorSummary} has {Integer:n_corridors} simple corridors")
CorridorSummary.n_served = model.Property(f"{CorridorSummary} serves {Integer:n_served} DC substations")
CorridorSummary.n_served_contingency = model.Property(
    f"{CorridorSummary} serves {Integer:n_served_contingency} DC substations in the contingency"
)
CorridorSummary.n_rerouted = model.Property(f"{CorridorSummary} reroutes {Integer:n_rerouted} DC substations")
CorridorSummary.n_lost = model.Property(f"{CorridorSummary} loses {Integer:n_lost} DC substations")
model.define(CorridorSummary.new(id=1))
_corridor, _dc = Hash.ref(), Substation.ref()
_route, _contingency_route = String.ref(), String.ref()
model.define(
    CorridorSummary.n_corridors(
        aggs.count(_corridor).per(CorridorSummary).where(SimpleCorridor(_corridor)) | 0
    ),
    CorridorSummary.n_served(
        aggs.count(_dc).per(CorridorSummary).where(_dc.fragile_route(_route)) | 0
    ),
    CorridorSummary.n_served_contingency(
        aggs.count(_dc).per(CorridorSummary).where(_dc.contingency_route(_contingency_route)) | 0
    ),
    CorridorSummary.n_rerouted(
        aggs.count(_dc).per(CorridorSummary).where(
            _dc.fragile_route(_route), _dc.contingency_route(_contingency_route), _route != _contingency_route
        )
        | 0
    ),
    CorridorSummary.n_lost(
        aggs.count(_dc).per(CorridorSummary).where(
            _dc.fragile_route(_route), not_(_dc.contingency_route(_contingency_route))
        )
        | 0
    ),
)
