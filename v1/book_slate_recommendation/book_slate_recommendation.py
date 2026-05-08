"""Book slate recommendation (Graph + Paths + Prescriptive CSP) template.

Path-driven multi-reasoner pipeline that picks K books per reader
under business rules. The Paths pillar is the architectural
centerpiece: bounded heterogeneous-KG walks generate the candidate
set AND the per-(user, candidate) explanation evidence. The Graph
pillar contributes a structural-embeddedness floor (per-book triangle
count over `Book.similar_to`) that the path walker alone cannot
enforce. Removing Paths collapses the template (no Candidate concept,
no CSP decisions); removing the Graph contribution drops the
embeddedness floor IC, weakening structural diversity:

- Paths (central): bounded
  `Item.connected_to.repeat(1, 2).all_paths()` walks enumerate
  `User -> read_Book` (length 1; pruned downstream by the
  already-read exclusion) and `User -> read_Book -> similar_Book`
  (length 2). Each walker-reachable (user, book) becomes a
  `Candidate`. The per-(user, candidate) typed counts
  (`path_count_via_author`, `_via_subject`, `_via_kg_walk`) feed
  both IC clauses (cold-start, explanation-floor) and the objective,
  and surface as the per-pick explanation block.
- Graph (structural embeddedness): triangle count over
  `Book.similar_to` per Book. Drives `embeddedness_ic` -- a per-user
  floor on picks whose Book is densely embedded in the similarity
  graph. Distinct from any per-book popularity scalar: triangle
  count is a topological measure of where the Book sits in the
  similarity neighborhood, not how heavily it's been engaged with.
- Prescriptive: pure-integer CSP on MiniZinc picks K items per user
  under cardinality, already-read exclusion, subject diversity,
  author uniqueness, freshness, originals-exposure, cold-start,
  explanation-path floor, and structural-embeddedness floor
  constraints; objective maximizes total `path_count_total` over
  the picked slate.

Bundled data: a deterministic Open Library (CC0) slice (~60 books,
~58 authors, 12 subjects) pulled by `data/fetch_open_library_slice.py`.
Customers fetch larger slices by re-running with `--size md`/`--size lg`.

Run:
    `python book_slate_recommendation.py`

Output:
    Prints the formulation, the solve-result block, the per-user
    candidate set, the chosen slate (K books per user), the per-user
    subject distribution, and the per-pick explanation-path support.
"""

from pathlib import Path

from pandas import read_csv
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

# Per-author cap: at most this many picks per (user, author).
MAX_PER_AUTHOR = 1

# Topic-span floor: each user's slate must touch at least this many
# distinct subjects. With K=3 picks across 12 subjects, =2 leaves room
# for two-of-a-kind plus one different; raise to K to force every pick
# on a distinct subject. Expressed via ``count(Subject, ...)`` over
# distinct picked-book subjects -- a CSP idiom that doesn't reduce to
# ``sum`` of indicators.
MIN_DISTINCT_SUBJECTS = 2

# Freshness / exposure / cold-start dials. All integer counts.
FRESHNESS_FLOOR = 1  # at least N items released within FRESH_WINDOW_DAYS
# 30-year window is tuned to the bundled bibliographic slice; streaming
# or news platforms typically want 365 * 2 or less.
FRESH_WINDOW_DAYS = 365 * 30
ORIGINALS_FLOOR = 1  # at least N in-house items per slate
COLD_START_CAP = 2  # at most N items with weak path support

# Each user's slate must carry sum(path_count_total) >= EXPLANATION_FLOOR
# over picked items. Tuned for the bundled ``--size sm`` slice
# (path_count_total range 2-12); retune for ``--size md|lg``.
EXPLANATION_FLOOR = 4

# Cold-start threshold: an item with path_count_total strictly below
# this counts as "weakly explained" for the cold-start cap.
WEAK_EXPLANATION_THRESHOLD = 2

# Structural-embeddedness floor: at least EMBEDDEDNESS_FLOOR picks per
# user must come from books that are well-embedded in the similarity
# graph -- specifically, books whose triangle count (number of
# similar-to triangles they participate in) meets EMBEDDEDNESS_THRESHOLD.
# This is the Graph pillar's hold on the slate: a structural-density
# constraint that the path walker alone cannot enforce. Tuned for the
# bundled slice where per-book triangle counts range 0-107 with two
# isolates; threshold of 4 keeps the truly-isolated books from saturating
# a slate. Retune to the data's distribution after rescaling.
EMBEDDEDNESS_THRESHOLD = 4
EMBEDDEDNESS_FLOOR = 1

# Strong-walker floor: at least ``MIN_STRONG_WALKERS`` picks per user
# must have ``path_count_via_kg_walk >= STRONG_WALKER_THRESHOLD``.
# Walker count is the headline output of the Paths pillar; this IC
# anchors at least one pick to it directly so the slate doesn't lean
# entirely on the cheaper shared-author / shared-subject joins.
STRONG_WALKER_THRESHOLD = 3
MIN_STRONG_WALKERS = 1

# Path-evidence diversity floor: each user's slate must touch at
# least this many distinct *primary path-evidence types*, where each
# Candidate's primary type is the argmax of its three typed counts
# (author, subject, walker). Forces the slate to span the
# heterogeneous KG's evidence channels rather than leaning on one.
# Uses ``count(Integer.ref() over distinct primary_evidence values,
# pick == 1)`` -- distinct-value counting that ``sum(pick)`` cannot
# express.
MIN_EVIDENCE_TYPES = 2

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

model.define(User.new(model.data(users_csv).to_schema()))
model.define(Book.new(model.data(books_csv).to_schema()))
model.define(Author.new(model.data(authors_csv).to_schema()))
model.define(Subject.new(model.data(subjects_csv).to_schema()))

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
# CSP variables. The per-typed counts produced here are reused by
# the explanation-floor IC, the cold-start cap, and the objective.
# --------------------------------------------------

# Walk the unified ``Item.connected_to`` edge from each User up to
# MAX_HOPS hops. The path-walker bounds enumeration to MAX_HOPS, so
# the candidate set is the bounded reachable set under the KG.
kg_paths = model.path(
    Item.connected_to.repeat(1, MAX_HOPS),
).all_paths()

# Candidate set: any (user, book) reached by a User-anchored bounded
# KG walk ending at a Book node. The already-read exclusion lands as
# a ``pick == 0`` IC (``exclude_read_ic`` below) rather than as a
# pre-pruning filter on this rule -- which keeps the candidate-
# derivation rule a pure positive join over the path walker, at the
# minor CSP cost of a few wasted binary variables forced to 0.
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
# the sum-floor IC ``sum(path_count_total * pick) >= EXPLANATION_FLOOR``
# would silently drop Candidates whose property is undefined.
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
# threshold checks.
model.define(Candidate.path_count_total(c, n)).where(
    Candidate(c),
    n == c.path_count_via_author + c.path_count_via_subject + c.path_count_via_kg_walk,
)

# Primary path-evidence type: argmax of the three typed counts,
# encoded as Integer ∈ {1=author-shared, 2=subject-shared, 3=KG-walker}.
# Each rule's where clauses are mutually exclusive across the three
# tie cases, so exactly one rule fires per Candidate. This Integer-
# valued property -- not a binary indicator -- is what makes
# ``count(Integer.ref(), condition).per(...)`` over distinct values
# meaningful in ``path_evidence_diversity_ic`` below: the multi-valued
# property carries information no binary indicator could.
Candidate.primary_evidence = model.Property(f"{Candidate} has primary evidence type {Integer:src}")
# 1 = author-shared (a strictly the max)
model.define(Candidate.primary_evidence(c, 1)).where(
    Candidate(c),
    c.path_count_via_author > c.path_count_via_subject,
    c.path_count_via_author > c.path_count_via_kg_walk,
)
# 2 = subject-shared (s >= a, s strictly > w)
model.define(Candidate.primary_evidence(c, 2)).where(
    Candidate(c),
    c.path_count_via_subject >= c.path_count_via_author,
    c.path_count_via_subject > c.path_count_via_kg_walk,
)
# 3 = KG-walker (w >= a and w >= s) -- catches walker-max and ties
model.define(Candidate.primary_evidence(c, 3)).where(
    Candidate(c),
    c.path_count_via_kg_walk >= c.path_count_via_author,
    c.path_count_via_kg_walk >= c.path_count_via_subject,
)

# --------------------------------------------------
# Pillar 2: Graph -- structural embeddedness over book-similarity
#
# Supporting pillar: per-Book triangle count over the similarity
# graph, used by ``embeddedness_ic`` to floor the slate's well-
# connected picks. The triangle-count signal is graph-derived (it
# depends on the similarity-graph topology), so unlike a per-Book
# popularity scalar, it cannot be supplied externally without
# reconstructing the graph -- which is what makes this contribution
# Graph-pillar work, not just a data-layer input.
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
# ``embeddedness_ic`` below to floor the slate's well-connected picks,
# distinguishing books central to dense neighborhoods from books that
# sit on isolated edges of the similarity graph. Triangle count is
# graph-derived: it depends on the topology of ``Book.similar_to``,
# not on a per-book scalar that could be supplied externally.
Book.triangle_count = model.Property(f"{Book} has structural embeddedness {Integer:triangle_count}")
triangle_rel = sim_graph.triangle_count()
b_tc = Book.ref()
tc = Integer.ref()
model.define(b_tc.triangle_count(tc)).where(
    triangle_rel(b_tc, tc),
)

# --------------------------------------------------
# Pillar 3: Prescriptive -- CSP slate selection (MiniZinc)
# --------------------------------------------------

Candidate.pick = model.Property(f"{Candidate} is picked iff {Integer:p}")

problem = Problem(model, Integer)
problem.solve_for(
    Candidate.pick,
    type="bin",
    name=["pick", Candidate.user_id, Candidate.book_id],
)

# Cardinality: each user gets exactly K picks. Anchored on
# ``Candidate.user_id``, so users with zero candidates after the
# path-walker / exclude-read pipeline are silently skipped (they
# receive no slate); the pre-solve assertion below flags such users.
# Same anchoring caveat applies to the floor ICs below.
slate_size_ic = model.require(sum(Candidate.pick).per(Candidate.user_id) == SLATE_SIZE_K)
problem.satisfy(slate_size_ic)

# Already-read exclusion: any (user, book) where the user has already
# read the book must have pick == 0. Lands at the prescriptive layer
# rather than as a pre-pruning filter on Candidate derivation; the
# alternative would need a positive complement of ``User.read`` (a
# Cartesian-minus-existing-tuples relation with no scalar comparator
# to lean on). The ``pick == 0`` IC keeps the rule pipeline pure-
# positive at minor CSP cost (a few wasted binary variables).
u_excl, b_excl = User.ref(), Book.ref()
rating_excl_ic = Integer.ref()
exclude_read_ic = model.where(
    User.read(u_excl, b_excl, rating_excl_ic),
    Candidate.user_id == u_excl.id,
    Candidate.book_id == b_excl.id,
).require(Candidate.pick == 0)
problem.satisfy(exclude_read_ic)

# Author uniqueness: no user gets more than MAX_PER_AUTHOR picks from
# the same author.
author_uniqueness_ic = model.where(
    Book.id == Candidate.book_id,
    Book.written_by(Book, Author),
).require(sum(Candidate.pick).per(Candidate.user_id, Author) <= MAX_PER_AUTHOR)
problem.satisfy(author_uniqueness_ic)

# Subject span floor: each user's slate must touch at least
# ``MIN_DISTINCT_SUBJECTS`` distinct subjects. Uses ``count(Subject, ...)``
# rather than ``sum(indicator)`` because we need *distinct-value*
# counting -- "how many different subjects the picked books cover" --
# which a sum of binary picks cannot express directly. CSP-native idiom
# (see PyRel ``social_golfer.py`` for the canonical
# ``count(Entity, condition).per(...)`` form). Combined with the
# rank-uniqueness ICs (one Candidate per rank-slot per user), this
# also bounds per-subject repetition: with K picks, MIN_DISTINCT_SUBJECTS
# distinct subjects, and the slot uniqueness, no subject can capture
# more than ``K - MIN_DISTINCT_SUBJECTS + 1`` picks.
subject_span_ic = model.where(
    Book.id == Candidate.book_id,
    Book.about(Book, Subject),
).require(count(Subject, Candidate.pick == 1).per(Candidate.user_id) >= MIN_DISTINCT_SUBJECTS)
problem.satisfy(subject_span_ic)

# Freshness floor: at least FRESHNESS_FLOOR picks within the
# FRESH_WINDOW_DAYS recency window.
freshness_ic = model.where(
    Book.id == Candidate.book_id,
    Book.age_days <= FRESH_WINDOW_DAYS,
).require(sum(Candidate.pick).per(Candidate.user_id) >= FRESHNESS_FLOOR)
problem.satisfy(freshness_ic)

# Originals exposure floor: at least ORIGINALS_FLOOR in-house items.
originals_ic = model.where(
    Book.id == Candidate.book_id,
    Book.in_house == 1,
).require(sum(Candidate.pick).per(Candidate.user_id) >= ORIGINALS_FLOOR)
problem.satisfy(originals_ic)

# Cold-start cap: at most COLD_START_CAP weakly-explained picks.
cold_start_ic = model.where(
    Candidate.path_count_total < WEAK_EXPLANATION_THRESHOLD,
).require(sum(Candidate.pick).per(Candidate.user_id) <= COLD_START_CAP)
problem.satisfy(cold_start_ic)

# Explanation floor: each user's slate must carry enough cumulative
# KG-path evidence (author + subject overlap, plus walks) aggregated
# over picked items. ``path_count_total * pick`` zeroes the
# contribution of unpicked candidates (pick is 0/1 binary).
explanation_ic = model.require(
    sum(Candidate.path_count_total * Candidate.pick).per(Candidate.user_id) >= EXPLANATION_FLOOR
)
problem.satisfy(explanation_ic)

# Embeddedness floor: each user's slate must carry at least
# EMBEDDEDNESS_FLOOR picks whose Book has triangle_count >=
# EMBEDDEDNESS_THRESHOLD. The Graph pillar's structural contribution
# to the slate -- without this, the path walker's reach can drop the
# entire slate onto sparsely-embedded books in the similarity graph.
embeddedness_ic = model.where(
    Book.id == Candidate.book_id,
    Book.triangle_count >= EMBEDDEDNESS_THRESHOLD,
).require(sum(Candidate.pick).per(Candidate.user_id) >= EMBEDDEDNESS_FLOOR)
problem.satisfy(embeddedness_ic)

# Walker-evidence floor: each user's slate must include at least
# ``MIN_STRONG_WALKERS`` picks whose ``path_count_via_kg_walk`` clears
# ``STRONG_WALKER_THRESHOLD``. The walker count is the headline output
# of the Paths pillar (the ``Item.connected_to.repeat(1, MAX_HOPS)``
# traversal); insisting that at least one pick stand on it directly
# anchors the slate to the pillar's distinctive signal, separate from
# the cheaper shared-author / shared-subject joins.
strong_walker_ic = model.where(
    Candidate.path_count_via_kg_walk >= STRONG_WALKER_THRESHOLD,
).require(sum(Candidate.pick).per(Candidate.user_id) >= MIN_STRONG_WALKERS)
problem.satisfy(strong_walker_ic)

# Path-evidence diversity: each user's slate must touch at least
# ``MIN_EVIDENCE_TYPES`` distinct primary-evidence types (author,
# subject, walker). Forces the slate to span the heterogeneous KG's
# evidence channels rather than leaning on one. Uses
# ``count(Integer.ref() distinct primary_evidence values, condition)``
# -- the social_golfer pattern -- because the multi-valued
# ``Candidate.primary_evidence`` carries information that no binary
# pick indicator could encode.
src_ref = Integer.ref()
path_evidence_diversity_ic = model.where(
    Candidate.primary_evidence == src_ref,
).require(count(src_ref, Candidate.pick == 1).per(Candidate.user_id) >= MIN_EVIDENCE_TYPES)
problem.satisfy(path_evidence_diversity_ic)

# Position-weighted objective: total rank-decay-weighted path support.
problem.maximize(sum(Candidate.path_count_total * Candidate.pick))

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

problem.display()

# Pre-solve floor assertion: per-user floor ICs anchor on Candidate
# rows, so a user with no candidates left after exclude_read is
# silently skipped instead of flagged as infeasible. Compute the
# unread candidate set per user explicitly and refuse to solve if
# any user falls below SLATE_SIZE_K, FRESHNESS_FLOOR, or
# ORIGINALS_FLOOR -- sparse customer reach hits a clear Python-level
# error rather than a quiet missing-row contract violation.
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
# Join unread candidates with Book attributes so the assertion can
# also validate the per-user fresh and in-house pools that
# freshness_ic and originals_ic implicitly require.
unread_with_book = unread.merge(
    books_csv[["id", "age_days", "in_house"]].rename(columns={"id": "book_id"}),
    on="book_id",
    how="left",
)
unread_counts = unread_with_book.groupby("user_id").size()
fresh_counts = (
    unread_with_book[unread_with_book["age_days"] <= FRESH_WINDOW_DAYS].groupby("user_id").size()
)
in_house_counts = unread_with_book[unread_with_book["in_house"] == 1].groupby("user_id").size()
all_users = set(users_csv["id"])
absent_from_unread = sorted(all_users - set(unread_counts.index))
short_total = sorted(unread_counts[unread_counts < SLATE_SIZE_K].index.tolist())
short_fresh = sorted(list(all_users - set(fresh_counts[fresh_counts >= FRESHNESS_FLOOR].index)))
short_in_house = sorted(
    list(all_users - set(in_house_counts[in_house_counts >= ORIGINALS_FLOOR].index))
)
if absent_from_unread or short_total or short_fresh or short_in_house:
    raise ValueError(
        "Per-user candidate floor violated:\n"
        f"  users absent from unread candidate table: {absent_from_unread}\n"
        f"  users with < SLATE_SIZE_K={SLATE_SIZE_K} unread candidates: {short_total}\n"
        f"  users with < FRESHNESS_FLOOR={FRESHNESS_FLOOR} unread fresh "
        f"(age_days <= {FRESH_WINDOW_DAYS}) candidates: {short_fresh}\n"
        f"  users with < ORIGINALS_FLOOR={ORIGINALS_FLOOR} unread in-house "
        f"candidates: {short_in_house}\n"
        "Densify Book.similar_to or refresh the data slice with denser "
        "fresh / in-house coverage before re-running."
    )

print("\nUnread candidate count per user (pre-solve diagnostic):")
print(unread_counts.sort_index().to_string())

problem.solve("minizinc", time_limit_sec=60)
problem.solve_info().display()

problem.verify(
    slate_size_ic,
    exclude_read_ic,
    author_uniqueness_ic,
    subject_span_ic,
    freshness_ic,
    originals_ic,
    cold_start_ic,
    explanation_ic,
    embeddedness_ic,
    strong_walker_ic,
    path_evidence_diversity_ic,
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

# Headline output: the chosen slate per user, sorted by rank.
print(f"\nFinal slate per user (K = {SLATE_SIZE_K}, ordered by rank):")
b_pick = Book.ref()
tc_pick = Integer.ref()
model.select(
    Candidate.user_id.alias("user_id"),
    Candidate.pick.alias("pick"),
    Candidate.book_id.alias("book_id"),
    Candidate.path_count_total.alias("path_count_total"),
    tc_pick.alias("triangle_count"),
).where(
    Candidate.pick == 1,
    b_pick.id == Candidate.book_id,
    b_pick.triangle_count == tc_pick,
).inspect()

print("\nSubject distribution per user's slate:")
u_disp = User.ref()
b_disp = Book.ref()
s_disp = Subject.ref()
model.select(
    u_disp.id.alias("user_id"),
    s_disp.name.alias("subject"),
    sum(Candidate.pick)
    .per(u_disp, s_disp)
    .where(
        Candidate.user_id == u_disp.id,
        Candidate.book_id == b_disp.id,
        Book.about(b_disp, s_disp),
    )
    .alias("n_picked"),
).inspect()

print(
    "\nExplanation-path support per picked item (with primary-evidence type 1=author, 2=subject, 3=walker):"
)
model.select(
    Candidate.user_id.alias("user_id"),
    Candidate.pick.alias("pick"),
    Candidate.book_id.alias("book_id"),
    Candidate.primary_evidence.alias("primary_evidence"),
    Candidate.path_count_via_kg_walk.alias("paths_via_kg_walk"),
    Candidate.path_count_via_author.alias("paths_via_author"),
    Candidate.path_count_via_subject.alias("paths_via_subject"),
).where(Candidate.pick == 1).inspect()

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
