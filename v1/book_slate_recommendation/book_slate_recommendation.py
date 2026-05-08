"""Book slate recommendation (Graph + Paths + Prescriptive CSP) template.

Path-driven multi-reasoner pipeline that picks K books per reader
AND orders them by slate position. Slot 1 is hero (top of row);
position-decay engagement is the canonical recsys model, so the
order matters as much as the selection. The Paths pillar is the
architectural centerpiece: bounded heterogeneous-KG walks generate
the candidate set and the per-(user, candidate) explanation evidence.
The Graph pillar pins slot 1 to a structurally-central pick via
``triangle_count``, anchoring the highest-engagement position to a
graph-derived measure. Removing Paths collapses the template (no
Candidate concept, no CSP decisions); removing the Graph contribution
drops the hero pin, weakening the structural quality of the most
visible position:

- Paths (central): bounded
  ``Item.connected_to.repeat(1, 2).all_paths()`` walks enumerate
  ``User -> read_Book`` (length 1; pruned downstream by the
  already-read exclusion) and ``User -> read_Book -> similar_Book``
  (length 2). Each walker-reachable (user, book) becomes a
  ``Candidate``. The per-(user, candidate) typed counts
  (``path_count_via_author``, ``_via_subject``, ``_via_kg_walk``)
  feed the engagement-weighted explanation floor and objective, and
  surface as the per-pick explanation block.
- Graph (hero pin): triangle count over ``Book.similar_to`` per
  Book. Drives ``hero_pin_ic`` -- slot 1 (top of row) must come from
  the densely-embedded subset, so the most-impressed position
  carries graph-derived structural quality. Stronger than a "floor
  somewhere in the slate": it concentrates the Graph pillar's signal
  at the slot that matters most for engagement.
- Prescriptive: pure-integer CSP on MiniZinc decides each
  Candidate's slot in {1, ..., K, K+1}, where slot K+1 means
  unpicked. Constraints: cardinality, slot uniqueness, already-read
  exclusion, distinct-author/subject diversity, freshness,
  originals-exposure, cold-start, hero pin, and explanation-path
  floor. Objective maximizes total position-weighted path support
  ``sum((K + 1 - slot) * path_count_total)`` -- top slots dominate,
  unpicked candidates contribute zero.

Bundled data: a deterministic Open Library (CC0) slice (~60 books,
~58 authors, 12 subjects) pulled by ``data/fetch_open_library_slice.py``.
Customers fetch larger slices by re-running with ``--size md``/``--size lg``.

Run:
    `python book_slate_recommendation.py`

Output:
    Prints the formulation, the solve-result block, the per-user
    candidate set, the chosen slate ordered by slot (1..K), the
    per-user subject distribution, and the per-pick explanation-path
    support.
"""

from pathlib import Path

from pandas import DataFrame, read_csv
from relationalai.semantics import (
    Integer,
    Model,
    String,
    count,
    sum,
)
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.std.paths import PathTraversal

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

# Slate size: the K of "row of K things". Tune to taste.
SLATE_SIZE_K = 3

# Bounded path depth for the KG walk. MAX_HOPS = 2 enumerates
# ``User -> read_Book`` (length 1, pruned by exclude_read_ic) and
# ``User -> read_Book -> similar_Book`` (length 2). Bumping to 3+
# saturates fast on a heterogeneous KG (most users reach most books).
MAX_HOPS = 2

# Topic-span cap: at most this many picks per (user, subject). With
# K=3 picks and MAX_PER_SUBJECT=2, no subject dominates the slate --
# the slate must touch >= 2 distinct subjects. Drop to 1 to force
# every pick on a distinct subject. Expressed as a GCC-style per-
# pair count cap on (user, Subject) (PyRel's prescriptive rewriter
# does not currently support distinct aggregates in ICs, so a
# count-distinct ``>= MIN_DISTINCT`` form would not compile).
MAX_PER_SUBJECT = 2

# Freshness / exposure / cold-start dials. All integer counts.
FRESHNESS_FLOOR = 1  # at least N items released within FRESH_WINDOW_DAYS
# 30-year window is tuned to the bundled bibliographic slice; streaming
# or news platforms typically want 365 * 2 or less.
FRESH_WINDOW_DAYS = 365 * 30
ORIGINALS_FLOOR = 1  # at least N in-house items per slate
COLD_START_CAP = 2  # at most N items with weak path support

# Each user's slate must carry sum((K + 1 - slot) * path_count_total)
# >= EXPLANATION_FLOOR over picked items (slot=K+1 contributes 0).
# Tuned for the bundled ``--size sm`` slice (path_count_total range
# 2-12, K=3 → max position weight 3); retune for ``--size md|lg``.
EXPLANATION_FLOOR = 8

# Cold-start threshold: an item with path_count_total strictly below
# this counts as "weakly explained" for the cold-start cap.
WEAK_EXPLANATION_THRESHOLD = 2

# Hero pin: slot 1 (top of row) must come from a Book whose
# triangle count over the similarity graph meets this threshold.
# This is the Graph pillar's hold on the slate -- pinning a graph-
# derived structural-density measure to the highest-engagement
# position. Tuned for the bundled slice where per-book triangle
# counts range 0-107 with two isolates; threshold of 4 keeps the
# truly-isolated books out of the hero slot. Retune to the data's
# distribution after rescaling.
HERO_EMBEDDEDNESS_THRESHOLD = 4

DATA_DIR = Path(__file__).parent / "data"

# --------------------------------------------------
# Load all CSVs upfront so pre-solve invariants can validate the data
# integrity before any model.define rules are installed.
# --------------------------------------------------

users_csv = read_csv(DATA_DIR / "users.csv")
books_csv = read_csv(DATA_DIR / "books.csv")
authors_csv = read_csv(DATA_DIR / "authors.csv")
subjects_csv = read_csv(DATA_DIR / "subjects.csv")
read_csv_data = read_csv(DATA_DIR / "read.csv")
ba_csv = read_csv(DATA_DIR / "book_author.csv")
bs_csv = read_csv(DATA_DIR / "book_subject.csv")
bsim_csv = read_csv(DATA_DIR / "book_similar.csv")

# Slot positions 1..K. The Slot concept exists so the slot-uniqueness
# IC counts distinct slot Concept values (the social_golfer idiom)
# rather than distinct anonymous Integer values. K+1 is the unpicked
# sentinel and is intentionally not a Slot row -- only filled
# positions are counted.
slots_df = DataFrame({"pos": list(range(1, SLATE_SIZE_K + 1))})

# --------------------------------------------------
# Pre-solve invariants
#
# Catch the common silent-failure modes before the solver runs:
# duplicate keys (would collapse rows), dangling FKs (would silently
# drop joins), and negative ages (would break the freshness predicate).
# Each helper raises a focused ValueError naming the offending rows.
# --------------------------------------------------


def _assert_no_nulls(df, cols, source):
    cols = cols if isinstance(cols, list) else [cols]
    null_cols = [c for c in cols if df[c].isna().any()]
    if null_cols:
        raise ValueError(
            f"{source} has null/NaN values in column(s) {null_cols}. Required "
            f"columns must be fully populated; drop or impute the offending rows."
        )


def _assert_unique_keys(df, key, source):
    cols = key if isinstance(key, list) else [key]
    _assert_no_nulls(df, cols, source)
    dupe_rows = df[df.duplicated(subset=cols, keep=False)]
    if not dupe_rows.empty:
        duplicates = sorted({tuple(row) for row in dupe_rows[cols].itertuples(index=False)})
        raise ValueError(
            f"{source} has duplicate ({', '.join(cols)})={duplicates}. "
            f"Each key must be unique; remove or merge the conflicting rows."
        )


def _assert_no_dangling_fks(child_df, child_col, parent_df, parent_col, source, parent_source):
    _assert_no_nulls(child_df, child_col, source)
    parent_ids = set(int(v) for v in parent_df[parent_col].unique())
    dangling = sorted({int(v) for v in child_df[child_col].unique() if int(v) not in parent_ids})
    if dangling:
        raise ValueError(
            f"{source}.{child_col} references unknown {parent_col}={dangling} "
            f"that does not appear in {parent_source}.{parent_col}. Every "
            f"foreign key must resolve."
        )


def _assert_nonneg_column(df, col, source):
    _assert_no_nulls(df, col, source)
    bad = sorted({int(v) for v in df[col].tolist() if int(v) < 0})
    if bad:
        raise ValueError(f"{source} has negative {col}={bad}. {col} must be >= 0.")


for _df, _key, _src in [
    (users_csv, "id", "users.csv"),
    (books_csv, "id", "books.csv"),
    (authors_csv, "id", "authors.csv"),
    (subjects_csv, "id", "subjects.csv"),
]:
    _assert_unique_keys(_df, _key, _src)

# Foreign-key edges in the schema. Each row says "<source>.<col>
# references <parent_source>.<parent_col>". Update this table when you
# add a new edge table or rewire a FK; the loop below validates every
# edge in one place.
_FK_EDGES = [
    (read_csv_data, "user_id", users_csv, "id", "read.csv", "users.csv"),
    (read_csv_data, "book_id", books_csv, "id", "read.csv", "books.csv"),
    (ba_csv, "book_id", books_csv, "id", "book_author.csv", "books.csv"),
    (ba_csv, "author_id", authors_csv, "id", "book_author.csv", "authors.csv"),
    (bs_csv, "book_id", books_csv, "id", "book_subject.csv", "books.csv"),
    (bs_csv, "subject_id", subjects_csv, "id", "book_subject.csv", "subjects.csv"),
    (bsim_csv, "src_book_id", books_csv, "id", "book_similar.csv", "books.csv"),
    (bsim_csv, "dst_book_id", books_csv, "id", "book_similar.csv", "books.csv"),
]
for _cdf, _ccol, _pdf, _pcol, _csrc, _psrc in _FK_EDGES:
    _assert_no_dangling_fks(_cdf, _ccol, _pdf, _pcol, _csrc, _psrc)

_assert_nonneg_column(books_csv, "age_days", "books.csv")

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

model = Model("book_slate_recommendation")

# Item super-concept: heterogeneous-KG node base for User/Book/Author/
# Subject. The path walker traverses a single 2-arity edge relationship
# (Item.connected_to, defined below) across the whole KG -- the
# documented v1.1.0 workaround for the "multiple edges in a single
# path()" gap (paths-lib README §"Currently unsupported patterns").
# First-class composite-edge support is on the PyRel roadmap; once
# it lands, the unified-edge layer below can be deleted.
Item = model.Concept("Item")

# User concept: a reader.
User = model.Concept("User", extends=[Item], identify_by={"id": Integer})
User.name = model.Property(f"{User} has {String:name}")

# Book concept: a catalog item with bibliographic and freshness/
# in-house attributes. ``in_house`` is an Integer 0/1 flag.
Book = model.Concept("Book", extends=[Item], identify_by={"id": Integer})
Book.title = model.Property(f"{Book} has {String:title}")
Book.age_days = model.Property(f"{Book} has {Integer:age_days}")
Book.in_house = model.Property(f"{Book} has {Integer:in_house}")

# Author concept: a book's writer.
Author = model.Concept("Author", extends=[Item], identify_by={"id": Integer})
Author.name = model.Property(f"{Author} has {String:name}")

# Subject concept: a topical category attached to books.
Subject = model.Concept("Subject", extends=[Item], identify_by={"id": Integer})
Subject.name = model.Property(f"{Subject} has {String:name}")

# Slot concept: positions 1..K in the slate. Used by the slot-
# uniqueness IC to express a per-pair count cap (at most one
# Candidate per (user, Slot.pos)) -- the GCC-style CSP idiom.
# Slot K+1 (unpicked) is intentionally not a Slot row, so the cap
# only applies to filled positions.
Slot = model.Concept("Slot", identify_by={"pos": Integer})

model.define(User.new(model.data(users_csv).to_schema()))
model.define(Book.new(model.data(books_csv).to_schema()))
model.define(Author.new(model.data(authors_csv).to_schema()))
model.define(Subject.new(model.data(subjects_csv).to_schema()))
model.define(Slot.new(model.data(slots_df).to_schema()))

# Typed edges between concepts: read events, authorship, subject
# attachment, and the book-similarity input.

User.read = model.Relationship(
    f"{User:user} read {Book:book} with rating {Integer:rating}",
    short_name="read",
)
read_data = model.data(read_csv_data)
rating_ref = Integer.ref()
model.define(User.read(User, Book, rating_ref)).where(
    User.id == read_data.user_id,
    Book.id == read_data.book_id,
    rating_ref == read_data.rating,
)

Book.written_by = model.Relationship(
    f"{Book:book} written by {Author:author}",
    short_name="written_by",
)
ba_data = model.data(ba_csv)
model.define(Book.written_by(Book, Author)).where(
    Book.id == ba_data.book_id,
    Author.id == ba_data.author_id,
)

Book.about = model.Relationship(
    f"{Book:book} about subject {Subject:subject}",
    short_name="about",
)
bs_data = model.data(bs_csv)
model.define(Book.about(Book, Subject)).where(
    Book.id == bs_data.book_id,
    Subject.id == bs_data.subject_id,
)

Book.similar_to = model.Relationship(
    f"{Book:book} similar to {Book:other}",
    short_name="similar_to",
)
bsim_data = model.data(bsim_csv)
src_b, dst_b = Book.ref(), Book.ref()
model.define(Book.similar_to(src_b, dst_b)).where(
    src_b.id == bsim_data.src_book_id,
    dst_b.id == bsim_data.dst_book_id,
)

# Unified KG edge: a single 2-arity Item.connected_to relationship
# the path walker traverses. Workaround for the v1.1.0 paths-lib
# composite-edge gap (see Item-concept comment above). Each define()
# below contributes one direction of one typed edge to the union; the
# walker treats them all as the same generic hop. The typed-evidence
# properties below join candidate books directly against the user's
# read history via Book.written_by / Book.about rather than
# introspecting walker paths -- simpler and faster.
Item.connected_to = model.Relationship(
    f"{Item:src} connected to {Item:dst}",
    short_name="connected_to",
)

# User <-> Book via read (both directions; user-anchor walks).
u_e, b_e = User.ref(), Book.ref()
rating_e = Integer.ref()
model.define(Item.connected_to(u_e, b_e)).where(
    User.read(u_e, b_e, rating_e),
)
model.define(Item.connected_to(b_e, u_e)).where(
    User.read(u_e, b_e, rating_e),
)

# Book <-> Author.
b_a, a_e = Book.ref(), Author.ref()
model.define(Item.connected_to(b_a, a_e)).where(Book.written_by(b_a, a_e))
model.define(Item.connected_to(a_e, b_a)).where(Book.written_by(b_a, a_e))

# Book <-> Subject.
b_s, s_e = Book.ref(), Subject.ref()
model.define(Item.connected_to(b_s, s_e)).where(Book.about(b_s, s_e))
model.define(Item.connected_to(s_e, b_s)).where(Book.about(b_s, s_e))

# Book <-> Book via similar_to (both directions; the similarity graph
# is conceptually undirected for traversal purposes).
b_s1, b_s2 = Book.ref(), Book.ref()
model.define(Item.connected_to(b_s1, b_s2)).where(Book.similar_to(b_s1, b_s2))
model.define(Item.connected_to(b_s2, b_s1)).where(Book.similar_to(b_s1, b_s2))

# --------------------------------------------------
# Pillar 1: Paths -- bounded KG walk (architectural centerpiece)
#
# This is the load-bearing pillar. The Candidate concept is derived
# from the path walker; without paths there are no candidates and no
# CSP variables. The per-typed counts produced here feed the
# engagement-weighted explanation floor, the cold-start cap, and the
# objective.
# --------------------------------------------------

# Walk the unified ``Item.connected_to`` edge from each User up to
# MAX_HOPS hops. The path-walker bounds enumeration to MAX_HOPS, so
# the candidate set is the bounded reachable set under the KG.
kg_paths = model.path(
    Item.connected_to.repeat(1, MAX_HOPS),
).all_paths()

# Candidate set: any (user, book) reached by a User-anchored bounded
# KG walk ending at a Book node. The already-read exclusion lands as
# a ``slot == K+1`` IC (``exclude_read_ic`` below) rather than as a
# pre-pruning filter on this rule -- which keeps the candidate-
# derivation rule a pure positive join over the path walker, at the
# minor CSP cost of a few wasted integer variables forced to K+1.
Candidate = model.Concept(
    "Candidate",
    identify_by={"user_id": Integer, "book_id": Integer},
)
u_cand, b_cand = User.ref(), Book.ref()
p_cand = PathTraversal.ref()
model.define(Candidate.new(user_id=u_cand.id, book_id=b_cand.id)).where(
    kg_paths(p_cand),
    p_cand.nodes(0, u_cand),
    p_cand.nodes(p_cand.length, b_cand),
)

# Per-(user, candidate) explanation features: counts of distinct
# typed connections between the candidate and the user's read
# history.
#
# Each ``count`` expression is followed by ``| 0`` so the property is
# defined for *every* Candidate (not only those with at least one
# match). PyRel aggregates over an empty group produce no row, and
# the position-weighted explanation IC would silently drop Candidates
# whose property is undefined.
#
# Arithmetic ``a + s + w`` (not ``sum(model.union(a, s, w))``) --
# union inside an aggregate body strips keys and deduplicates on
# projected values, undercounting whenever two of the three typed
# counts share a value. See ``experiments/count_variants.py`` for
# the divergence across formulations.
Candidate.path_count_via_author = model.Property(f"{Candidate} has author connections {Integer:n}")
Candidate.path_count_via_subject = model.Property(
    f"{Candidate} has subject connections {Integer:n}"
)
Candidate.path_count_via_kg_walk = model.Property(f"{Candidate} has KG-walk paths {Integer:n}")
Candidate.path_count_total = model.Property(f"{Candidate} has total connections {Integer:n}")

c = Candidate.ref()
n = Integer.ref()
u_c, b_c = User.ref(), Book.ref()

# via-author: distinct authors shared between candidate and any of
# the user's read books.
b_read_a = Book.ref()
a_ref = Author.ref()
model.define(Candidate.path_count_via_author(c, n)).where(
    Candidate(c),
    n
    == count(a_ref)
    .per(c)
    .where(
        c.user_id == u_c.id,
        c.book_id == b_c.id,
        User.read(u_c, b_read_a, Integer.ref()),
        Book.written_by(b_read_a, a_ref),
        Book.written_by(b_c, a_ref),
    )
    | 0,
)

# via-subject: distinct subjects shared.
b_read_s = Book.ref()
s_ref = Subject.ref()
model.define(Candidate.path_count_via_subject(c, n)).where(
    Candidate(c),
    n
    == count(s_ref)
    .per(c)
    .where(
        c.user_id == u_c.id,
        c.book_id == b_c.id,
        User.read(u_c, b_read_s, Integer.ref()),
        Book.about(b_read_s, s_ref),
        Book.about(b_c, s_ref),
    )
    | 0,
)

# via-walk: number of bounded heterogeneous KG paths from this user
# to the candidate (the actual paths-pillar count -- the headline
# explanation-strength signal).
p_s = PathTraversal.ref()
model.define(Candidate.path_count_via_kg_walk(c, n)).where(
    Candidate(c),
    n
    == count(p_s)
    .per(c)
    .where(
        kg_paths(p_s),
        c.user_id == u_c.id,
        c.book_id == b_c.id,
        p_s.nodes(0, u_c),
        p_s.nodes(p_s.length, b_c),
    )
    | 0,
)

# Total: sum across types as a single integer feature for cold-start
# threshold checks and explanation/objective weighting.
model.define(Candidate.path_count_total(c, n)).where(
    Candidate(c),
    n == c.path_count_via_author + c.path_count_via_subject + c.path_count_via_kg_walk,
)

# --------------------------------------------------
# Pillar 2: Graph -- structural embeddedness over book-similarity
#
# Supporting pillar: per-Book triangle count over the similarity
# graph, used by ``hero_pin_ic`` to pin slot 1 (the highest-
# engagement position) to a structurally-central pick. The triangle-
# count signal is graph-derived (it depends on the similarity-graph
# topology), so unlike a per-Book popularity scalar, it cannot be
# supplied externally without reconstructing the graph -- which is
# what makes this contribution Graph-pillar work, not just a
# data-layer input.
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

# --------------------------------------------------
# Pillar 3: Prescriptive -- CSP slate selection (MiniZinc)
#
# Decision: ``Candidate.slot`` ∈ {1, 2, ..., K, K+1}. Slot 1..K are
# slate positions (1 = top of row); slot K+1 is the unpicked sentinel.
# The K+1 encoding lets the position-weighted objective and
# explanation floor use the simple coefficient ``(K + 1 - slot)``,
# which is 0 at slot K+1 -- no auxiliary picked/unpicked indicator.
# --------------------------------------------------

Candidate.slot = model.Property(f"{Candidate} is at slate slot {Integer:s}")

problem = Problem(model, Integer)
problem.solve_for(
    Candidate.slot,
    type="int",
    lower=1,
    upper=SLATE_SIZE_K + 1,
    name=["slot", Candidate.user_id, Candidate.book_id],
)

# Cardinality: exactly K Candidates per user have slot <= K (i.e.,
# are picked; slot K+1 means unpicked). The decision-dep filter
# ``Candidate.slot <= SLATE_SIZE_K`` lives inside ``count``'s second
# argument, not the outer ``where`` -- PyRel rejects decision-
# variable-dependent expressions in top-level ``where`` clauses
# because those iterate over data rows.
slate_size_ic = model.require(
    count(Candidate, Candidate.slot <= SLATE_SIZE_K).per(Candidate.user_id) == SLATE_SIZE_K
)
problem.satisfy(slate_size_ic)

# Slot uniqueness: at most one Candidate per (user, slot position).
# Counts Candidates whose slot decision equals each Slot's pos, per
# (user, Slot). Combined with slate_size_ic (K picks per user) and
# the slot domain {1..K+1}, this is a bijection between picks and
# positions 1..K. Per-pair count cap is the CSP-native shape for
# all-different over decision variables once you also pin the
# total-pick count.
slot_uniqueness_ic = model.require(
    count(Candidate, Candidate.slot == Slot.pos).per(Candidate.user_id, Slot) <= 1
)
problem.satisfy(slot_uniqueness_ic)

# Already-read exclusion: any (user, book) where the user has already
# read the book must have ``slot == K+1`` (unpicked). Lands at the
# prescriptive layer rather than as a pre-pruning filter on Candidate
# derivation; the alternative would need a positive complement of
# ``User.read`` (a Cartesian-minus-existing-tuples relation with no
# scalar comparator to lean on). The ``slot == K+1`` IC keeps the
# rule pipeline pure-positive at minor CSP cost (a few wasted integer
# variables forced to the unpicked sentinel).
u_excl, b_excl = User.ref(), Book.ref()
rating_excl_ic = Integer.ref()
exclude_read_ic = model.where(
    User.read(u_excl, b_excl, rating_excl_ic),
    Candidate.user_id == u_excl.id,
    Candidate.book_id == b_excl.id,
).require(Candidate.slot == SLATE_SIZE_K + 1)
problem.satisfy(exclude_read_ic)

# Author uniqueness: at most one picked Candidate per (user, Author).
# GCC-style per-pair count cap. With every Book having exactly one
# Author in the bundled data, this is equivalent to "the K picks
# come from K distinct Authors". Per-pair caps are PyRel's CSP-
# native shape for "no value repeats more than X times across
# decisions" -- the same shape ``slot_uniqueness_ic`` uses to keep
# slot positions unique.
author_uniqueness_ic = model.where(
    Book.id == Candidate.book_id,
    Book.written_by(Book, Author),
).require(count(Candidate, Candidate.slot <= SLATE_SIZE_K).per(Candidate.user_id, Author) <= 1)
problem.satisfy(author_uniqueness_ic)

# Subject concentration cap: at most ``MAX_PER_SUBJECT`` picks per
# (user, Subject). Same per-pair cap shape; with K=3 and
# MAX_PER_SUBJECT=2, the slate must touch at least 2 Subjects (no
# Subject can sweep all 3 picks). Books are multi-subject in this
# data, so the bound is on Subject-attribution counts rather than
# distinct-Subject coverage directly.
subject_span_ic = model.where(
    Book.id == Candidate.book_id,
    Book.about(Book, Subject),
).require(
    count(Candidate, Candidate.slot <= SLATE_SIZE_K).per(Candidate.user_id, Subject)
    <= MAX_PER_SUBJECT
)
problem.satisfy(subject_span_ic)

# Freshness floor: at least FRESHNESS_FLOOR picks within the
# FRESH_WINDOW_DAYS recency window.
freshness_ic = model.where(
    Book.id == Candidate.book_id,
    Book.age_days <= FRESH_WINDOW_DAYS,
).require(
    count(Candidate, Candidate.slot <= SLATE_SIZE_K).per(Candidate.user_id) >= FRESHNESS_FLOOR
)
problem.satisfy(freshness_ic)

# Originals exposure floor: at least ORIGINALS_FLOOR in-house items.
originals_ic = model.where(
    Book.id == Candidate.book_id,
    Book.in_house == 1,
).require(
    count(Candidate, Candidate.slot <= SLATE_SIZE_K).per(Candidate.user_id) >= ORIGINALS_FLOOR
)
problem.satisfy(originals_ic)

# Cold-start cap: at most COLD_START_CAP weakly-explained picks.
cold_start_ic = model.where(
    Candidate.path_count_total < WEAK_EXPLANATION_THRESHOLD,
).require(count(Candidate, Candidate.slot <= SLATE_SIZE_K).per(Candidate.user_id) <= COLD_START_CAP)
problem.satisfy(cold_start_ic)

# Hero pin: slot 1 (top of row) must come from a Book with
# triangle_count >= HERO_EMBEDDEDNESS_THRESHOLD. Counts the
# eligible-and-at-slot-1 Candidates per user; combined with
# slot_uniqueness_ic (exactly one Candidate at slot 1 per user),
# >= 1 forces the slot-1 Candidate to be eligible. This is the
# Graph pillar's hold on the slate, tied to the highest-engagement
# position rather than a "somewhere in the slate" floor.
hero_pin_ic = model.where(
    Book.id == Candidate.book_id,
    Book.triangle_count >= HERO_EMBEDDEDNESS_THRESHOLD,
).require(count(Candidate, Candidate.slot == 1).per(Candidate.user_id) >= 1)
problem.satisfy(hero_pin_ic)

# Explanation floor: each user's slate must carry enough cumulative
# position-weighted KG-path evidence over picked items. The
# ``(K + 1 - slot)`` weight is K at slot 1 (hero), 1 at slot K, and
# 0 at slot K+1 (unpicked) -- so the sum naturally restricts to
# picked items without needing an indicator multiplier. Top picks
# count more, matching the engagement-decay model the objective
# also encodes.
explanation_ic = model.require(
    sum((SLATE_SIZE_K + 1 - Candidate.slot) * Candidate.path_count_total).per(Candidate.user_id)
    >= EXPLANATION_FLOOR
)
problem.satisfy(explanation_ic)

# Position-weighted objective: maximize total engagement-weighted
# path support. ``(K + 1 - slot)`` decays with position; unpicked
# (slot K+1) contributes 0. The solver places highest-path-support
# Candidates at the lowest slot indices (top of row) because that
# maximizes the weighted sum, matching the canonical recsys
# position-decay engagement model.
problem.maximize(sum((SLATE_SIZE_K + 1 - Candidate.slot) * Candidate.path_count_total))

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

problem.display()

# Pre-solve floor assertion: per-user floor ICs anchor on Candidate
# rows, so a user with no candidates left after exclude_read is
# silently skipped instead of flagged as infeasible. Compute the
# unread candidate set per user explicitly and refuse to solve if
# any user falls below SLATE_SIZE_K, FRESHNESS_FLOOR, ORIGINALS_FLOOR,
# K distinct authors, or 1 hero-eligible candidate -- sparse customer
# reach hits a clear Python-level error rather than a quiet
# missing-row contract violation.
candidate_df = model.select(
    Candidate.user_id.alias("user_id"),
    Candidate.book_id.alias("book_id"),
).to_df()
unread = candidate_df.merge(
    read_csv_data[["user_id", "book_id"]],
    on=["user_id", "book_id"],
    how="left",
    indicator=True,
)
unread = unread[unread["_merge"] == "left_only"][["user_id", "book_id"]]
# Pull triangle counts so the hero-eligible feasibility check can
# count books meeting HERO_EMBEDDEDNESS_THRESHOLD per user.
triangle_df = model.select(
    Book.id.alias("book_id"),
    Book.triangle_count.alias("triangle_count"),
).to_df()
# PyRel returns Int128Array-backed columns; cast to native int so
# pandas comparisons against Python ints work in the feasibility
# checks below.
triangle_df["book_id"] = triangle_df["book_id"].astype(int)
triangle_df["triangle_count"] = triangle_df["triangle_count"].astype(int)
unread_with_book = unread.merge(
    books_csv[["id", "age_days", "in_house"]].rename(columns={"id": "book_id"}),
    on="book_id",
    how="left",
).merge(triangle_df, on="book_id", how="left")
unread_authors = unread.merge(
    ba_csv[["book_id", "author_id"]],
    on="book_id",
    how="left",
)
unread_counts = unread_with_book.groupby("user_id").size()
fresh_counts = (
    unread_with_book[unread_with_book["age_days"] <= FRESH_WINDOW_DAYS].groupby("user_id").size()
)
in_house_counts = unread_with_book[unread_with_book["in_house"] == 1].groupby("user_id").size()
hero_counts = (
    unread_with_book[unread_with_book["triangle_count"] >= HERO_EMBEDDEDNESS_THRESHOLD]
    .groupby("user_id")
    .size()
)
distinct_author_counts = unread_authors.groupby("user_id")["author_id"].nunique()
all_users = set(users_csv["id"])
absent_from_unread = sorted(all_users - set(unread_counts.index))
short_total = sorted(unread_counts[unread_counts < SLATE_SIZE_K].index.tolist())
short_fresh = sorted(list(all_users - set(fresh_counts[fresh_counts >= FRESHNESS_FLOOR].index)))
short_in_house = sorted(
    list(all_users - set(in_house_counts[in_house_counts >= ORIGINALS_FLOOR].index))
)
short_hero = sorted(list(all_users - set(hero_counts[hero_counts >= 1].index)))
short_authors = sorted(
    list(all_users - set(distinct_author_counts[distinct_author_counts >= SLATE_SIZE_K].index))
)
if (
    absent_from_unread
    or short_total
    or short_fresh
    or short_in_house
    or short_hero
    or short_authors
):
    raise ValueError(
        "Per-user candidate floor violated:\n"
        f"  users absent from unread candidate table: {absent_from_unread}\n"
        f"  users with < SLATE_SIZE_K={SLATE_SIZE_K} unread candidates: {short_total}\n"
        f"  users with < FRESHNESS_FLOOR={FRESHNESS_FLOOR} unread fresh "
        f"(age_days <= {FRESH_WINDOW_DAYS}) candidates: {short_fresh}\n"
        f"  users with < ORIGINALS_FLOOR={ORIGINALS_FLOOR} unread in-house "
        f"candidates: {short_in_house}\n"
        f"  users with no unread hero-eligible (triangle_count >= "
        f"{HERO_EMBEDDEDNESS_THRESHOLD}) candidates: {short_hero}\n"
        f"  users with < SLATE_SIZE_K={SLATE_SIZE_K} distinct unread authors: {short_authors}\n"
        "Densify Book.similar_to or refresh the data slice with denser "
        "fresh / in-house / hero coverage before re-running."
    )

print("\nUnread candidate count per user (pre-solve diagnostic):")
print(unread_counts.sort_index().to_string())

problem.solve("minizinc", time_limit_sec=60)
problem.solve_info().display()

problem.verify(
    slate_size_ic,
    slot_uniqueness_ic,
    exclude_read_ic,
    author_uniqueness_ic,
    subject_span_ic,
    freshness_ic,
    originals_ic,
    cold_start_ic,
    hero_pin_ic,
    explanation_ic,
)
model.require(problem.termination_status() == "OPTIMAL")

# --------------------------------------------------
# Inspect results
# --------------------------------------------------

print("\nUsers in this run:")
model.select(
    User.id.alias("user_id"),
    User.name.alias("user"),
).inspect()

# Headline output: the chosen slate per user, ordered by slot
# (1=hero/top of row, K=bottom).
print(f"\nFinal slate per user (K = {SLATE_SIZE_K}, slot 1 = top of row):")
b_pick = Book.ref()
tc_pick = Integer.ref()
slate_df = (
    model.select(
        Candidate.user_id.alias("user_id"),
        Candidate.slot.alias("slot"),
        Candidate.book_id.alias("book_id"),
        Candidate.path_count_total.alias("path_count_total"),
        tc_pick.alias("triangle_count"),
    )
    .where(
        Candidate.slot <= SLATE_SIZE_K,
        b_pick.id == Candidate.book_id,
        b_pick.triangle_count == tc_pick,
    )
    .to_df()
)
print(slate_df.sort_values(["user_id", "slot"]).to_string(index=False))

print("\nSubject distribution per user's slate:")
u_disp = User.ref()
b_disp = Book.ref()
s_disp = Subject.ref()
model.select(
    u_disp.id.alias("user_id"),
    s_disp.name.alias("subject"),
    count(Candidate)
    .per(u_disp, s_disp)
    .where(
        Candidate.user_id == u_disp.id,
        Candidate.book_id == b_disp.id,
        Book.about(b_disp, s_disp),
        Candidate.slot <= SLATE_SIZE_K,
    )
    .alias("n_picked"),
).inspect()

print("\nExplanation-path support per picked item (ordered by slot):")
expl_df = (
    model.select(
        Candidate.user_id.alias("user_id"),
        Candidate.slot.alias("slot"),
        Candidate.book_id.alias("book_id"),
        Candidate.path_count_via_kg_walk.alias("paths_via_kg_walk"),
        Candidate.path_count_via_author.alias("paths_via_author"),
        Candidate.path_count_via_subject.alias("paths_via_subject"),
    )
    .where(Candidate.slot <= SLATE_SIZE_K)
    .to_df()
)
print(expl_df.sort_values(["user_id", "slot"]).to_string(index=False))

# Diagnostics: candidate set sizing and structural-embeddedness map.

print(
    f"\nCandidate set per user (Books reachable within {MAX_HOPS} hops over the heterogeneous KG):"
)
model.select(
    Candidate.user_id.alias("user_id"),
    Candidate.book_id.alias("book_id"),
    Candidate.path_count_total.alias("path_count_total"),
    Candidate.path_count_via_kg_walk.alias("paths_via_kg_walk"),
    Candidate.path_count_via_author.alias("paths_via_author"),
    Candidate.path_count_via_subject.alias("paths_via_subject"),
).inspect()

print("\nBook structural embeddedness (similar_to triangle counts):")
model.select(
    Book.id.alias("book_id"),
    Book.title.alias("title"),
    Book.triangle_count.alias("triangle_count"),
).inspect()
