"""Lot genealogy: backward reachability over the lot genealogy graph, which links each unit to every
lot beneath it and each candidate factor to the units it touches."""

from relationalai.semantics import Integer
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.std import aggregates as aggs

from .schema import Factor, Lot, Unit, model

# --------------------------------------------------
# Stage 1 -- Graph: backward reachability over the lot genealogy
# --------------------------------------------------

# Directed parent -> child genealogy graph on Lot. Following edges from a
# top-tier lot reaches every lot consumed beneath it.
graph = Graph(model, directed=True, weighted=False, node_concept=Lot, name="lot_genealogy")
parent, child = Lot.ref(), Lot.ref()
model.where(parent.consumes(child)).define(graph.Edge.new(src=parent, dst=child))

# The graph's size, which the deployed model publishes for the queries.
node_count, edge_count = Integer.ref(), Integer.ref()
num_nodes = model.Relationship(f"the lot genealogy graph has {Integer:num_nodes} nodes")
num_edges = model.Relationship(f"the lot genealogy graph has {Integer:num_edges} edges")
model.where(graph.num_nodes()(node_count)).define(num_nodes(node_count))
model.where(graph.num_edges()(edge_count)).define(num_edges(edge_count))

# Transitive closure: which lots each top-tier lot reaches.
reach = graph.reachable(full=True)

# Unit.touches_lot: a unit touches the top-tier lots it consumes directly,
# plus every lot reachable beneath them. This backward closure is what lets a
# deep contaminated lot be attributed to the finished units that carry it.
Unit.touches_lot = model.Relationship(f"{Unit} touches {Lot:lot}")
model.where((u := Unit.ref()).consumes_lot(top := Lot.ref())).define(Unit.touches_lot(u, top))
model.where(
    (u := Unit.ref()).consumes_lot(top := Lot.ref()),
    reach(top, deep := Lot.ref())
).define(Unit.touches_lot(u, deep))

# Factor.touches: the unified incidence the diagnosis ranges over. Lot factors
# inherit the genealogy closure; machine and shift factors come from process.
Factor.touches = model.Relationship(f"{Factor} touches {Unit}")
model.where((u := Unit.ref()).touches_lot((f := Factor.ref()).lot)).define(Factor.touches(f, u))
model.where((u := Unit.ref()).ran_on((f := Factor.ref()).machine)).define(Factor.touches(f, u))
model.where((u := Unit.ref()).shift == (f := Factor.ref()).shift_name).define(Factor.touches(f, u))

# The number of (factor, unit) incidence facts the closure yields.
num_incidence = model.Relationship(
    f"backward reachability yields {Integer:num_incidence} factor-unit incidence facts"
)
model.define(num_incidence(aggs.count(Factor, Unit).where(Factor.touches(Unit))))
