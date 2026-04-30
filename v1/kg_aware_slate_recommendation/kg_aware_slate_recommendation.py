"""KG-aware slate recommendation (Graph + Paths + Prescriptive MIP) template.

Three-pillar pipeline modelling a content-row / homepage slate:

- Graph: PageRank over a book-similarity graph derived from shared
  authors and shared subjects. Provides each candidate book with a
  structural-popularity signal that the prescriptive layer reads as
  data.
- Paths: bounded-depth knowledge-graph walks
  (``User -> read -> Book -> shares author / subject / similar ->
  candidate``) produce per-(user, candidate) explanation features.
  Path counts by type become integer features the MIP reads in
  ``where`` and ``require`` clauses; the top-aggregate-relevance
  path is surfaced as the human-readable explanation for each picked
  item (GDPR Art. 22 / EU AI Act Art. 86 explainability artefact).
- Prescriptive: float-coefficient binary IP on HiGHS picks K items per
  user under subject diversity, author uniqueness, freshness floor,
  originals-exposure floor, cold-start cap, and explanation-path
  floor constraints. Objective combines structural prior (PageRank)
  with per-user path signal into a single utility.

Production precedent: Pinterest's Pixie (Eksombatchai et al., WWW 2018)
runs personalized random walks for recommendations at >50% of Pin
engagement scale; eBay's KPRN (AAAI 2019) and policy-guided KG path
reasoning (PGPR, SIGIR 2019) use KG paths for explainable recsys;
LinkedIn Career Explorer navigates the Skills Graph by paths. This
template composes the same primitives declaratively in PyRel.

Lead dataset: Open Library (CC0). The bundled ``data/`` directory
carries a small slice (~60 books, ~30-40 authors, ~12 subjects) pulled
by ``data/fetch_open_library_slice.py``. Customers fetch larger slices
by re-running that script with ``--size md`` / ``--size lg``. The
domain is plain bibliographic catalogue, so no licensing exposure --
the template ships in full.

Run: ``python kg_aware_slate_recommendation.py``
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

# --- Configuration --------------------------------------------------

# Slate size: the K of "row of K things". 8 is a typical streaming-row
# size; tune to taste.
SLATE_SIZE_K = 3

# Bounded path depth for the KG walk. 2 hops means each path is
# (User -> middle -> Book); ``middle`` can be a Book reached via
# ``read`` (then a similar_to edge lands on the candidate), or an
# Author / Subject node shared between a read anchor and the
# candidate. 3+ hops over a heterogeneous KG saturates quickly
# (every user reaches every book via a subject or author hub), so 2
# is the sweet spot for both differentiation and runtime.
MAX_HOPS = 2

# Multi-axis diversity caps inside each user's slate.
MAX_PER_SUBJECT = 3
MAX_PER_AUTHOR = 1

# Freshness / exposure / cold-start dials. All integer counts.
FRESHNESS_FLOOR = 1  # at least N items released within FRESH_WINDOW_DAYS
FRESH_WINDOW_DAYS = 365 * 30  # 30 years -- catalogue mix
ORIGINALS_FLOOR = 1  # at least N in-house items per slate
COLD_START_CAP = 2  # at most N items with weak path support

# Explanation-floor: each user's slate must carry enough cumulative
# KG-path evidence (author + subject overlap, plus walks) aggregated
# over picked items. Sum-bound on path_count_total over picked items.
EXPLANATION_FLOOR = 4

# Cold-start path-count threshold. An item with total path count
# strictly below this counts as "weakly explained" for the cold-start
# cap.
WEAK_EXPLANATION_THRESHOLD = 2

# Utility blend: structural prior (PageRank) vs per-user path signal.
PAGERANK_WEIGHT = 100.0
PATH_SIGNAL_WEIGHT = 30.0

model = Model("kg_aware_slate_recommendation")
data_dir = Path(__file__).parent / "data"

# --- Concepts and core data -----------------------------------------

# ``Item`` is the heterogeneous-KG super-concept. User / Book / Author
# / Subject all extend it so the path walker can traverse a single
# 2-arity edge relationship across the whole KG. This is the
# documented v1.1.0 workaround for the "multiple edges in a single
# path()" gap (paths-lib README: "encode the multi-edge traversal as
# a single N-arity relationship"); design epic RAI-44166 tracks
# first-class composite-edge support.
Item = model.Concept("Item")

User = model.Concept("User", extends=[Item], identify_by={"id": Integer})
User.name = model.Property(f"{User} has {String:name}")

Book = model.Concept("Book", extends=[Item], identify_by={"id": Integer})
Book.title = model.Property(f"{Book} has {String:title}")
Book.age_days = model.Property(f"{Book} has {Integer:age_days}")
Book.in_house = model.Property(f"{Book} has {Integer:in_house}")

Author = model.Concept("Author", extends=[Item], identify_by={"id": Integer})
Author.name = model.Property(f"{Author} has {String:name}")

Subject = model.Concept("Subject", extends=[Item], identify_by={"id": Integer})
Subject.name = model.Property(f"{Subject} has {String:name}")

# CSV ingest. The bundled data is a deterministic slice of Open
# Library (CC0); regenerate or scale with
# ``data/fetch_open_library_slice.py --size sm|md|lg``.
users_csv = read_csv(data_dir / "users.csv")
books_csv = read_csv(data_dir / "books.csv")
authors_csv = read_csv(data_dir / "authors.csv")
subjects_csv = read_csv(data_dir / "subjects.csv")
read_csv_data = read_csv(data_dir / "read.csv")
ba_csv = read_csv(data_dir / "book_author.csv")
bs_csv = read_csv(data_dir / "book_subject.csv")
bsim_csv = read_csv(data_dir / "book_similar.csv")

model.define(User.new(model.data(users_csv).to_schema()))
model.define(Book.new(model.data(books_csv).to_schema()))
model.define(Author.new(model.data(authors_csv).to_schema()))
model.define(Subject.new(model.data(subjects_csv).to_schema()))

# --- Edges (typed Relationships) ------------------------------------

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

# --- Unified KG edge (workaround for v1.1.0 composite-edge gap) -----
# ``Item.connected_to(Item, Item)`` is the single 2-arity relationship
# the path walker traverses. Populate it from each typed edge so a
# bounded walk can chain User -> Book -> Author -> Book -> ...
# Each define() below contributes one direction of one typed edge to
# the union; the walker treats them all as the same generic hop and
# we recover the per-hop type by joining each consecutive (src, dst)
# back against the typed edges when computing explanation features.
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

# --- Pillar 1: Graph -- PageRank over the book-similarity graph -----

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
# decisions natively; the same pattern is used by supply_chain.
Book.pagerank_score = model.Property(
    f"{Book} has structural score {Float:pagerank_score}"
)
pagerank_rel = sim_graph.pagerank()
b_pr = Book.ref()
score_pr = Float.ref()
model.define(b_pr.pagerank_score(score_pr)).where(
    pagerank_rel(b_pr, score_pr),
)

# --- Pillar 2: Paths -- bounded heterogeneous KG walk ---------------
#
# Walk the unified ``Item.connected_to`` edge from each User up to
# MAX_HOPS hops. Each walk traces a real heterogeneous KG path
# (User -> Book -> Author -> Book, User -> Book -> Subject -> Book,
# User -> Book -> Book via similar_to, ...). The path-walker bounds
# enumeration to MAX_HOPS, so the candidate set is the bounded
# reachable set under the KG -- the same primitive Pixie / KPRN /
# LinkedIn Career Explorer compose at production scale.
kg_paths = model.path(
    Item.connected_to.repeat(1, MAX_HOPS),
).all_paths()

# Candidate set: any (user, book) reached by a User-anchored bounded
# KG walk ending at a Book node. v1.1.0 does not yet support ``not``
# (paths-lib README §"Currently unsupported patterns" and
# compliance_rule_audit's documented gap), so the already-read filter
# lands as a ``pick == 0`` IC at the prescriptive layer instead.
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
# s, w))``). PyRel's union strips keys and deduplicates on projected
# values (pinned by
# ``test_e2e_rewriter_semantic_equivalence_highs::u_same_prop`` —
# ``sum(model.union(X.v, X.v)) == 10`` not 20), so a sum-of-union
# formulation silently undercounts whenever two of the three typed
# counts share a value for the same Candidate. ``experiments/
# count_variants.py`` empirically reproduces the divergence (variant F:
# pick_5_12 coefficient = 6 vs A's 7). Bag arithmetic on the densified
# per-typed counts is the right surface here.
Candidate.path_count_via_author = model.Property(
    f"{Candidate} has author connections {Integer:n}"
)
Candidate.path_count_via_subject = model.Property(
    f"{Candidate} has subject connections {Integer:n}"
)
Candidate.path_count_via_kg_walk = model.Property(
    f"{Candidate} has KG-walk paths {Integer:n}"
)
Candidate.path_count_total = model.Property(
    f"{Candidate} has total connections {Integer:n}"
)

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

# --- Personalized utility -------------------------------------------
# Blend structural prior (float PageRank) with per-user path signal
# (integer path counts) into a single Float utility. HiGHS handles
# float coefficients on binary decisions natively (supply_chain uses
# the same pattern).
Candidate.utility = model.Property(f"{Candidate} has utility {Float:utility}")
b_u = Book.ref()
util = Float.ref()
model.define(Candidate.utility(c, util)).where(
    Candidate(c),
    c.book_id == b_u.id,
    util
    == PAGERANK_WEIGHT * b_u.pagerank_score
    + PATH_SIGNAL_WEIGHT * (2 * c.path_count_via_author + c.path_count_via_subject),
)

# --- Pillar 3: Prescriptive -- MIP slate selection ------------------

Candidate.pick = model.Property(f"{Candidate} is picked iff {Float:p}")

problem = Problem(model, Float)
problem.solve_for(
    Candidate.pick,
    type="bin",
    name=["pick", Candidate.user_id, Candidate.book_id],
)

# Cardinality: each user gets exactly K picks.
slate_size_ic = model.require(
    sum(Candidate.pick).per(Candidate.user_id) == SLATE_SIZE_K
)
problem.satisfy(slate_size_ic)

# Already-read exclusion: any (user, book) where the user has already
# read the book must have pick == 0. v1.1.0 lacks ``not`` in rules
# (paths-lib README + compliance_rule_audit's documented gap), so
# the exclusion lands here at the prescriptive layer rather than as
# a ``~User.read(...)`` filter on the candidate derivation.
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
    sum(Candidate.path_count_total * Candidate.pick).per(Candidate.user_id)
    >= EXPLANATION_FLOOR
)
problem.satisfy(explanation_ic)

# Objective: maximise total per-user utility, summed across users.
problem.maximize(sum(Candidate.utility * Candidate.pick))

# --- Solve and verify -----------------------------------------------

problem.display()
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

# --- Inspect results ------------------------------------------------

print("\nUsers in this run:")
model.select(
    User.id.alias("user_id"),
    User.name.alias("user"),
).inspect()

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

print(f"\nFinal slate per user (K = {SLATE_SIZE_K}):")
model.select(
    Candidate.user_id.alias("user_id"),
    Candidate.book_id.alias("book_id"),
    Candidate.utility.alias("utility"),
    Candidate.path_count_total.alias("path_count_total"),
).where(Candidate.pick == 1).inspect()

print("\nSubject distribution per user's slate (cap = MAX_PER_SUBJECT):")
b_disp = Book.ref()
s_disp = Subject.ref()
model.select(
    Candidate.user_id.alias("user_id"),
    s_disp.name.alias("subject"),
    sum(Candidate.pick)
    .per(Candidate.user_id, s_disp)
    .where(
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

# --- Customize-section variants (documented for the README, not
# wired into the lead runner):
# - Replace pagerank_score with a learned GNN affinity (Predictive
#   pillar variant).
# - Pipe top-explanation-path into an LLM call to render
#   natural-language explanations (KG-grounded, hallucination-free).
# - solve(..., solution_limit=K_alt) returns K alternative slates for
#   A/B exposure or human-in-the-loop curation.
# - Customize the typed edges to retarget the template at e-commerce
#   (Open Library -> Open Food Facts / Amazon-Book), course slates
#   (LinkedIn-style career navigation), or news (MIND).
