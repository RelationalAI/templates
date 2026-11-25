"""Book structural embeddedness: the triangle count of each book over the similarity graph."""

from relationalai.semantics import Integer
from relationalai.semantics.reasoners.graph import Graph

from .schema import Book, model

# --------------------------------------------------
# Stage 1: Graph reasoner -- structural embeddedness over book-similarity
#
# Per-Book triangle count over the similarity graph, used by
# ``hero_pin_ic`` to pin slot 1 (the highest-engagement position) to
# a structurally-central pick. The triangle-count signal is graph-
# derived (it depends on the similarity-graph topology), so unlike a
# per-Book popularity scalar, it cannot be supplied externally
# without reconstructing the graph -- which is what makes this an
# irreducible Graph-reasoner contribution, not just a data-layer
# input.
# --------------------------------------------------

# Book-Book similarity graph derived from shared authors / subjects.
# ``node_concept=Book`` makes graph-algorithm output bind directly to
# Book without DataFrame round-trips. Aggregator "sum" collapses
# multi-edges so two paths of similarity between the same pair count
# once.
sim_graph = Graph(
    model,
    directed=False,
    weighted=False,
    node_concept=Book,
    aggregator="sum",
    name="book_similarity_graph",
)
src_g, dst_g = Book.ref(), Book.ref()
model.define(sim_graph.Edge.new(src=src_g, dst=dst_g)).where(
    Book.similar_to(src_g, dst_g),
)

# Triangle count: per-Book count of similar_to triangles the book
# participates in -- a structural-embeddedness measure. Used by
# ``hero_pin_ic`` below to pin the hero slot (slot 1) to a densely-
# embedded book, distinguishing books central to dense neighborhoods
# from books that sit on isolated edges of the similarity graph.
# Triangle count is graph-derived: it depends on the topology of
# ``Book.similar_to``, not on a per-book scalar that could be
# supplied externally.
Book.triangle_count = model.Property(f"{Book} has structural embeddedness {Integer:triangle_count}")
triangle_rel = sim_graph.triangle_count()
b_tc = Book.ref()
tc = Integer.ref()
model.define(b_tc.triangle_count(tc)).where(
    triangle_rel(b_tc, tc),
)
