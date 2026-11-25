"""Book structural embeddedness: the triangle count of each book over the similarity graph."""

from relationalai.semantics import Integer
from relationalai.semantics.reasoners.graph import Graph

from .schema import Book, model

# --------------------------------------------------
# Stage 2: Graph reasoner -- structural embeddedness over book-similarity
#
# Per-Book triangle count over the similarity graph, which the hero pin
# (``hero_pin_ic`` in slate_selection.py) uses to keep slot 1, the
# highest-engagement position, for a structurally central pick. The count
# depends on the graph's topology, so unlike a per-Book popularity scalar it
# cannot be supplied as a data-layer input.
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
# participates in, which distinguishes books central to dense neighborhoods
# from books on isolated edges of the similarity graph.
Book.triangle_count = model.Property(f"{Book} has structural embeddedness {Integer:triangle_count}")
triangle_rel = sim_graph.triangle_count()
b_tc = Book.ref()
tc = Integer.ref()
model.define(b_tc.triangle_count(tc)).where(
    triangle_rel(b_tc, tc),
)
