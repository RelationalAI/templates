"""Book slate recommendation (Graph + Paths + Prescriptive MIP) template.

Three-pillar pipeline that picks K books per reader under business
rules, blending a structural-popularity prior, bounded-walk path
evidence, and per-typed shared-entity joins into a personalized
utility:

- Graph: PageRank over a book-similarity graph (`Book.similar_to`)
  produces each candidate's `pagerank_score`.
- Paths: bounded `Item.connected_to.repeat(1, 2).all_paths()` walks
  enumerate `User -> read_Book` (length 1; pruned downstream by the
  already-read exclusion) and `User -> read_Book -> similar_Book`
  (length 2). The per-(user, candidate) typed counts
  (`path_count_via_author`, `_via_subject`, `_via_kg_walk`) feed both
  IC clauses and the objective, and surface as the per-pick
  explanation block.
- Prescriptive: float-coefficient binary IP on HiGHS picks K items
  per user under cardinality, already-read exclusion, subject
  diversity, author uniqueness, freshness, originals-exposure,
  cold-start, and explanation-path floor constraints; objective
  maximizes total `utility = w1 * pagerank + w2 * path_total`.

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
    Float,
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

# Slate size: the K of "row of K things". Streaming rows are
# typically 5-10; this template uses 3 to keep the bundled-data
# instance small. Tune to taste.
SLATE_SIZE_K = 3

# Bounded path depth for the KG walk. With a Book endpoint and
# MAX_HOPS = 2, the walker enumerates ``User -> read_Book`` (length 1)
# and ``User -> read_Book -> similar_Book`` (length 2) -- the
# similarity-walk reach over books the user has already engaged with.
# Author / Subject hubs participate in candidate generation only via
# the ``Book.similar_to`` edges that the data pipeline derives from
# shared author/subject (and that are also re-used directly by the
# typed-evidence joins below). Bumping to 3+ hops would let the walker
# traverse Author/Subject hubs explicitly, but the heterogeneous KG
# saturates fast (most users would reach most books) -- so 2 is the
# sweet spot for differentiation and runtime.
MAX_HOPS = 2

# Multi-axis diversity caps inside each user's slate.
MAX_PER_SUBJECT = 3
MAX_PER_AUTHOR = 1

# Freshness / exposure / cold-start dials. All integer counts.
FRESHNESS_FLOOR = 1  # at least N items released within FRESH_WINDOW_DAYS
# 30 years is a *catalog-framing* default tuned to the bibliographic
# Open Library slice (publication dates back centuries; a tighter
# window would mark almost everything stale). Streaming / news / e-
# commerce platforms typically want 365 * 2 (2 years) or less so the
# freshness floor visibly constrains.
FRESH_WINDOW_DAYS = 365 * 30
ORIGINALS_FLOOR = 1  # at least N in-house items per slate
COLD_START_CAP = 2  # at most N items with weak path support

# Explanation-floor: each user's slate must carry enough cumulative
# KG-path evidence (author + subject overlap, plus walks) aggregated
# over picked items. Sum-bound on path_count_total over picked items.
# Tuned for the bundled ``--size sm`` slice (path_count_total ranges
# 2-12 there); customers running ``--size md`` / ``--size lg`` should
# re-tune EXPLANATION_FLOOR / WEAK_EXPLANATION_THRESHOLD to the new
# distribution (inspect via the "Candidate set per user" print at the
# end of the runner).
EXPLANATION_FLOOR = 4

# Cold-start path-count threshold. An item with total path count
# strictly below this counts as "weakly explained" for the cold-start
# cap.
WEAK_EXPLANATION_THRESHOLD = 2

# Utility blend: structural prior (PageRank) vs per-user path signal.
# Demo-grade defaults tuned for the bundled ``--size sm`` slice. With
# PageRank ~ 1e-3 to 3e-2 and path counts ~ 2-12, the unscaled
# contributions per item are PageRank ~ 0.1-3 and path-signal ~ 60-360;
# the path signal dominates and PageRank effectively serves as a
# tie-breaker when path-signal ties between candidates. This is fine
# for the demo (the slate is path-driven anyway), but production
# deployments wanting a meaningful blend should: (a) min-max-
# normalize both signals to [0, 1] before applying these weights so
# the constants represent *business preference* rather than *scale
# correction*; (b) calibrate to held-out click / read data; (c) keep
# a sensitivity table per slice size (the bundled ``experiments/``
# folder has the harness for this).
PAGERANK_WEIGHT = 100.0
PATH_SIGNAL_WEIGHT = 30.0

DATA_DIR = Path(__file__).parent / "data"

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

# Bundled CSVs are a deterministic Open Library (CC0) slice;
# regenerate or scale with ``data/fetch_open_library_slice.py --size
# sm|md|lg``.

# Load user data from CSV.
users_csv = read_csv(DATA_DIR / "users.csv")
# Load book data from CSV.
books_csv = read_csv(DATA_DIR / "books.csv")
# Load author data from CSV.
authors_csv = read_csv(DATA_DIR / "authors.csv")
# Load subject data from CSV.
subjects_csv = read_csv(DATA_DIR / "subjects.csv")
# Load read-event data from CSV.
read_csv_data = read_csv(DATA_DIR / "read.csv")
# Load book-author edge data from CSV.
ba_csv = read_csv(DATA_DIR / "book_author.csv")
# Load book-subject edge data from CSV.
bs_csv = read_csv(DATA_DIR / "book_subject.csv")
# Load book-similarity edge data from CSV.
bsim_csv = read_csv(DATA_DIR / "book_similar.csv")

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
# composite-edge gap (see Item-concept comment above).
# ``Item.connected_to(Item, Item)`` is the single 2-arity relationship
# the path walker traverses. Populate it from each typed edge so a
# bounded walk can chain User -> Book -> Author -> Book -> ...
# Each define() below contributes one direction of one typed edge to
# the union; the walker treats them all as the same generic hop. The
# typed-evidence properties below (``path_count_via_author`` /
# ``_via_subject``) do *not* introspect the walker's path edges -- they
# join the candidate Book directly against the user's read history via
# ``Book.written_by`` / ``Book.about``. Recovering per-hop type from
# the walker's enumerated paths is possible (re-join each consecutive
# (src, dst) back against the typed edges) but is not what this
# template ships -- the typed counts here are simpler and faster.
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
# Pillar 1: Graph -- PageRank over the book-similarity graph
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

# PageRank: structural-popularity prior. Stored as Float (the native
# pagerank() output type). HiGHS handles float coefficients on binary
# decisions natively, so no quantization step is needed.
Book.pagerank_score = model.Property(f"{Book} has structural score {Float:pagerank_score}")
pagerank_rel = sim_graph.pagerank()
b_pr = Book.ref()
score_pr = Float.ref()
model.define(b_pr.pagerank_score(score_pr)).where(
    pagerank_rel(b_pr, score_pr),
)

# --------------------------------------------------
# Pillar 2: Paths -- bounded similarity walk
# --------------------------------------------------

# Walk the unified ``Item.connected_to`` edge from each User up to
# MAX_HOPS hops. With a Book endpoint at length 2, the walker
# enumerates ``User -> read_Book`` (length 1; the user's own read
# books, pruned downstream by ``exclude_read_ic``) and
# ``User -> read_Book -> similar_Book`` (length 2). The path-walker
# bounds enumeration to MAX_HOPS, so the candidate set is the bounded
# reachable set under the KG -- the same primitive Pixie / KPRN /
# LinkedIn's skills-graph career navigation compose at production scale.
kg_paths = model.path(
    Item.connected_to.repeat(1, MAX_HOPS),
).all_paths()

# Candidate set: any (user, book) reached by a User-anchored bounded
# KG walk ending at a Book node. The already-read exclusion lands as
# a ``pick == 0`` IC at the prescriptive layer (see
# ``exclude_read_ic`` below) rather than as a pre-pruning filter on
# this rule -- this avoids needing a positive complement of
# ``User.read`` (a Cartesian-minus-existing-tuples relation, with no
# scalar comparator analogous to the ``<`` form in
# ``Stock.is_non_representative`` in ``v1/portfolio_balancing/portfolio_balancing.py``) and keeps
# the candidate-derivation rule a pure positive join over the path
# walker.
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

# Per-(user, candidate) explanation features. Each is a count of
# distinct typed connections between the candidate and the user's
# read history -- the KPRN-style typed-path aggregation that
# powers explainable KG-recsys at production scale.
#
# count() is scoped per-Candidate via ``.per(c)``. Each ``count``
# expression is followed by ``| 0`` so the property is defined for
# *every* Candidate (not only those with at least one match): PyRel
# aggregates over an empty group produce no row, and downstream
# composite properties / sum-floor MIP constraints silently drop
# Candidates whose property is undefined. The ``| 0`` default keeps
# ``path_count_via_author``, ``_via_subject``, ``_via_kg_walk``, and
# the composite ``path_count_total`` dense-coverage; without it,
# ``sum(path_count_total * pick).per(user_id) >= floor`` is
# vacuously infeasible whenever a user's only-with-total candidate
# is forced to pick=0 by ``exclude_read_ic``.
#
# Composition style: arithmetic ``a + s + w`` (not ``sum(model.union(a,
# s, w))``). PyRel's ``model.union`` inside an aggregate body strips
# keys and deduplicates on projected values, so
# ``sum(model.union(X.v, X.v)) == 10`` (not 20) -- a sum-of-union
# formulation silently undercounts whenever two of the three typed
# counts share a value for the same Candidate. The
# ``experiments/count_variants.py`` harness reproduces the divergence
# across six formulations of this pattern; bag arithmetic on the
# densified per-typed counts is the right surface here.
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

# Personalized utility: blend structural prior (float PageRank) with per-user path signal
# (integer path counts) into a single Float utility. HiGHS handles
# float coefficients on binary decisions natively, so the blend
# stores directly as Float without a quantization step.
Candidate.utility = model.Property(f"{Candidate} has utility {Float:utility}")
b_u = Book.ref()
util = Float.ref()
model.define(Candidate.utility(c, util)).where(
    Candidate(c),
    c.book_id == b_u.id,
    util == PAGERANK_WEIGHT * b_u.pagerank_score + PATH_SIGNAL_WEIGHT * c.path_count_total,
)

# --------------------------------------------------
# Pillar 3: Prescriptive -- MIP slate selection
# --------------------------------------------------

Candidate.pick = model.Property(f"{Candidate} is picked iff {Float:p}")

problem = Problem(model, Float)
problem.solve_for(
    Candidate.pick,
    type="bin",
    name=["pick", Candidate.user_id, Candidate.book_id],
)

# Data preconditions for OPTIMAL on customer slices:
#  (1) every user must have at least ``SLATE_SIZE_K`` candidates in
#      their 2-hop reach AFTER the already-read exclusion (else
#      ``slate_size_ic`` ∧ ``exclude_read_ic`` are jointly infeasible).
#      Note that exclude_read_ic prunes aggressively: every length-1
#      walk ``User -> read_Book`` lands a read book in Candidate,
#      and these are all forced to ``pick == 0``. The recommendable
#      candidates come from length-2 ``read_Book -> similar_Book``
#      walks, so a user whose reads have no ``similar_to`` neighbors
#      (sparse customer data) will be infeasible without obvious
#      signal.
#  (2) for every user, the 2-hop reach must contain at least
#      ``FRESHNESS_FLOOR`` books with ``age_days <= FRESH_WINDOW_DAYS``
#      and at least ``ORIGINALS_FLOOR`` books with ``in_house == 1``
#      (else the corresponding floor IC is infeasible for that user).
#      These are independent floors -- a user with no candidate that
#      is BOTH fresh and in-house must spend ``FRESHNESS_FLOOR +
#      ORIGINALS_FLOOR`` distinct picks on the disjoint pools, not
#      ``max(FRESHNESS_FLOOR, ORIGINALS_FLOOR)``.
#  (3) author_uniqueness_ic (``MAX_PER_AUTHOR=1``) requires at least
#      ``SLATE_SIZE_K`` distinct authors in the user's reach;
#      subject_diversity_ic similarly bounds per-subject picks. A
#      user whose reach concentrates in fewer than K authors is
#      infeasible even when total candidate count is large.
#  (4) cold_start_ic (≤ ``COLD_START_CAP`` weak picks) and
#      explanation_ic (>= ``EXPLANATION_FLOOR`` total path evidence)
#      together imply at least ``K - COLD_START_CAP`` candidates
#      per user with ``path_count_total >= WEAK_EXPLANATION_THRESHOLD``,
#      and a strong-candidate path-count sum that meets
#      ``EXPLANATION_FLOOR - COLD_START_CAP * (WEAK_EXPLANATION_THRESHOLD - 1)``.
#      Customers retuning these dials (especially raising
#      ``EXPLANATION_FLOOR``) need to inspect the per-user
#      path-count distribution and ensure both bounds remain
#      satisfiable.
#  (5) every Book picked must have at least one
#      ``Book.about(Subject)`` and one ``Book.written_by(Author)``
#      row, else the diversity / uniqueness caps silently exempt
#      that Book (the IC's join filters it out). The bundled
#      fetcher guarantees both; customer data should be checked.
# Violations surface as ``INFEASIBLE`` from HiGHS plus the
# ``model.require(termination_status() == "OPTIMAL")`` failure at
# script tail. To diagnose, comment out the OPTIMAL require, re-run,
# and inspect the ``Candidate set per user`` print (which fires only
# on a successful solve under the current order). For pre-solve
# inspection of candidate sets, run a separate quick session that
# stops before ``problem.solve(...)``.

# Cardinality: each user gets exactly K picks.
#
# IC-anchoring caveat: this IC is anchored on ``Candidate.user_id``,
# so it generates one constraint row per user that has at least one
# Candidate. Users with **zero** candidates after the path-walker /
# exclude-read pipeline (e.g., a customer importing data where some
# users' reads have no ``similar_to`` neighbours) are silently
# skipped: the IC does not fire for them, and they receive no slate.
# The pre-solve diagnostic below ("Candidate count per user") flags
# such users; downstream tooling should treat absence from the
# Final-slate output as a per-user infeasibility signal. Same
# anchoring caveat applies to ``freshness_ic``, ``originals_ic``, and
# ``explanation_ic`` below -- a user with candidates but none
# matching the ``where`` filter passes vacuously rather than
# becoming infeasible. The bundled ``--size sm`` slice avoids the
# sharp edges by guaranteeing dense per-user reach; customers
# bringing sparse data should add a pre-solve assert on per-user
# candidate counts before relying on the floor ICs.
slate_size_ic = model.require(sum(Candidate.pick).per(Candidate.user_id) == SLATE_SIZE_K)
problem.satisfy(slate_size_ic)

# Already-read exclusion: any (user, book) where the user has already
# read the book must have pick == 0. Lands at the prescriptive layer
# rather than as a pre-pruning filter on Candidate derivation -- the
# alternative would need a positive complement of ``User.read`` (the
# Cartesian-minus-existing-tuples relation), and unlike the
# ordered-comparator workaround used in
# ``Stock.is_non_representative`` in ``v1/portfolio_balancing/portfolio_balancing.py`` ("non-
# representative stocks") there is no scalar comparator separating
# "read" from "not read" here. The ``pick == 0`` IC keeps the rule
# pipeline pure-positive at minor MIP cost (a few wasted binary
# variables forced to 0).
u_excl, b_excl = User.ref(), Book.ref()
rating_excl_ic = Integer.ref()
exclude_read_ic = model.where(
    User.read(u_excl, b_excl, rating_excl_ic),
    Candidate.user_id == u_excl.id,
    Candidate.book_id == b_excl.id,
).require(Candidate.pick == 0)
problem.satisfy(exclude_read_ic)

# Subject diversity: at most MAX_PER_SUBJECT picks per (user, subject).
subject_diversity_ic = model.where(
    Book.id == Candidate.book_id,
    Book.about(Book, Subject),
).require(sum(Candidate.pick).per(Candidate.user_id, Subject) <= MAX_PER_SUBJECT)
problem.satisfy(subject_diversity_ic)

# Author uniqueness: no user gets more than MAX_PER_AUTHOR picks from
# the same author.
author_uniqueness_ic = model.where(
    Book.id == Candidate.book_id,
    Book.written_by(Book, Author),
).require(sum(Candidate.pick).per(Candidate.user_id, Author) <= MAX_PER_AUTHOR)
problem.satisfy(author_uniqueness_ic)

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
# over picked items. A sum-bound on the decision-multiplied integer
# feature.
explanation_ic = model.require(
    sum(Candidate.path_count_total * Candidate.pick).per(Candidate.user_id) >= EXPLANATION_FLOOR
)
problem.satisfy(explanation_ic)

# Objective: maximize total per-user utility, summed across users.
problem.maximize(sum(Candidate.utility * Candidate.pick))

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

problem.display()

# Pre-solve assertion: per-user floor ICs (slate_size_ic,
# freshness_ic, originals_ic, explanation_ic) anchor on Candidate
# rows, so a user with no Candidate left after exclude_read is
# silently skipped instead of being flagged as infeasible. Compute
# the un-read candidate set per user explicitly and refuse to solve
# if any user has fewer than SLATE_SIZE_K, so customer data with
# sparse reach hits a clear Python-level error rather than a quiet
# missing-row contract violation. The runner's bundled --size sm
# slice satisfies this trivially; --size md/lg also do, and customer
# data flagged here should be re-fetched with denser similar_to
# edges before re-running.
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
unread = unread[unread["_merge"] == "left_only"]
unread_counts = unread.groupby("user_id").size()
all_users = set(users_csv["id"])
missing_users = sorted(all_users - set(unread_counts.index))
short_users = sorted(unread_counts[unread_counts < SLATE_SIZE_K].index.tolist())
if missing_users or short_users:
    raise ValueError(
        "Per-user candidate floor violated: "
        f"missing users (no candidates at all): {missing_users}; "
        f"users with < SLATE_SIZE_K={SLATE_SIZE_K} unread candidates: "
        f"{short_users}. Densify Book.similar_to (the data pipeline "
        "input) or relax SLATE_SIZE_K before re-running."
    )

print("\nUnread candidate count per user (pre-solve diagnostic):")
print(unread_counts.sort_index().to_string())

problem.solve("highs", time_limit_sec=60)
problem.solve_info().display()

problem.verify(
    slate_size_ic,
    exclude_read_ic,
    subject_diversity_ic,
    author_uniqueness_ic,
    freshness_ic,
    originals_ic,
    cold_start_ic,
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

# Headline output: the chosen slate per user.
print(f"\nFinal slate per user (K = {SLATE_SIZE_K}):")
model.select(
    Candidate.user_id.alias("user_id"),
    Candidate.book_id.alias("book_id"),
    Candidate.utility.alias("utility"),
    Candidate.path_count_total.alias("path_count_total"),
).where(Candidate.pick == 1).inspect()

print("\nSubject distribution per user's slate (cap = MAX_PER_SUBJECT):")
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

print("\nExplanation-path support per picked item:")
model.select(
    Candidate.user_id.alias("user_id"),
    Candidate.book_id.alias("book_id"),
    Candidate.path_count_via_kg_walk.alias("paths_via_kg_walk"),
    Candidate.path_count_via_author.alias("paths_via_author"),
    Candidate.path_count_via_subject.alias("paths_via_subject"),
).where(Candidate.pick == 1).inspect()

# Diagnostics (verbose; useful for sizing the candidate set and
# inspecting the structural prior, can be commented out for cleaner
# customer-facing output).

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
    Candidate.utility.alias("utility"),
).inspect()

print("\nBook structural-popularity prior (PageRank):")
model.select(
    Book.id.alias("book_id"),
    Book.title.alias("title"),
    Book.pagerank_score.alias("structural_score"),
).inspect()

# --- Customize-section variants (documented for the README, not
# wired into the lead runner):
# - Replace ``Book.pagerank_score`` with any custom per-book scoring
#   signal (collaborative-filtering co-occurrence, learned-embedding
#   k-NN affinity, third-party scoring API). Same MIP, different
#   prior.
# - Pipe per-typed counts (and, optionally, materialized top-N paths
#   from a small extension of the inspect() above) into an LLM call to
#   render natural-language, KG-grounded, hallucination-free
#   explanations.
# - solve(..., solution_limit=K_alt) returns K alternative slates for
#   A/B exposure or human-in-the-loop curation.
# - Customize the typed edges to retarget the template at e-commerce
#   (Open Library -> Open Food Facts / Amazon-Book), course slates
#   (LinkedIn-style career navigation), or news (MIND).
