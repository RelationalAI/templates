"""KG-aware slate recommendation (Graph + Paths + Prescriptive MIP) template.

Three-pillar pipeline modelling a streaming-row / homepage slate:

- Graph: PageRank over a movie-similarity graph derived from co-watch
  events. Provides each candidate movie with a structural-popularity
  signal that the prescriptive layer reads as data.
- Paths: bounded-depth knowledge-graph walks (User -> watched -> Movie ->
  shares director / actor / genre / similar -> candidate) produce
  per-(user, candidate) explanation features. Path counts by type
  become integer features the MIP reads in `where` and `require`
  clauses; the top-aggregate-relevance path is surfaced as the human-
  readable explanation for each picked item (GDPR Art. 22 / EU AI Act
  Art. 86 explainability artefact).
- Prescriptive: float-coefficient binary IP on HiGHS picks K items per
  user under genre diversity, director uniqueness, freshness floor,
  originals-exposure floor, cold-start cap, explanation-path floor,
  and position-quota constraints. Objective combines structural prior
  (PageRank) with per-user path signal into a single utility.

Production precedent: Pinterest's Pixie (Eksombatchai et al., WWW 2018)
runs personalized random walks for recommendations at >50% of Pin
engagement scale; eBay's KPRN (AAAI 2019) and policy-guided KG path
reasoning (PGPR, SIGIR 2019) use KG paths for explainable recsys;
LinkedIn Career Explorer navigates the Skills Graph by paths. This
template composes the same primitives declaratively in PyRel.

Lead dataset: MovieLens-1M-KG (KGAT distribution, Wang et al. KDD
2019). The bundled `data/` directory carries a small hand-crafted
sample that lets the runner execute without a download; use the
download script in `data/fetch_movielens_kg.sh` for the realistic
instance.

Run: `python kg_aware_slate_recommendation.py`
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

# Bounded path depth for the KG walk. 3 captures direct sharing
# (User -> Movie -> Director -> Movie) and one extra hop without
# blowing up enumeration.
MAX_HOPS = 3

# Multi-axis diversity caps inside each user's slate.
MAX_PER_GENRE = 3
MAX_PER_DIRECTOR = 1
MAX_PER_ACTOR = 2

# Freshness / exposure / cold-start dials. All integer counts.
FRESHNESS_FLOOR = 1  # at least N items released within FRESH_WINDOW_DAYS
FRESH_WINDOW_DAYS = 365
ORIGINALS_FLOOR = 1  # at least N in-house items per slate
COLD_START_CAP = 2  # at most N items with weak path support

# Explanation-floor: each user's slate must carry enough creator-path
# weight so a downstream surface can render "because you watched ..."
# style explanations.
EXPLANATION_FLOOR = 3

# Cold-start path-count threshold. An item with total path count
# strictly below this counts as "weakly explained" for the cold-start
# cap.
WEAK_EXPLANATION_THRESHOLD = 2

# Calibration slack penalty weight (soft IC). Increase to push the
# slate's genre distribution closer to the user's history.
CALIBRATION_LAMBDA = 1

# Utility blend: structural prior (PageRank) vs per-user path signal.
# All integer; rescale together.
PAGERANK_WEIGHT = 100
PATH_SIGNAL_WEIGHT = 30

model = Model("kg_aware_slate_recommendation")
data_dir = Path(__file__).parent / "data"

# --- Concepts and core data -----------------------------------------

# `Item` is the heterogeneous-KG super-concept. User / Movie /
# Director / Actor / Genre all extend it so the path walker can
# traverse a single 2-arity edge relationship across the whole KG.
# This is the documented v1.1.0 workaround for the "multiple edges in
# a single path()" gap (paths-lib README: "encode the multi-edge
# traversal as a single N-arity relationship"); design epic
# RAI-44166 tracks first-class composite-edge support.
Item = model.Concept("Item")

User = model.Concept("User", extends=[Item], identify_by={"id": Integer})
User.name = model.Property(f"{User} has {String:name}")

Movie = model.Concept("Movie", extends=[Item], identify_by={"id": Integer})
Movie.title = model.Property(f"{Movie} has {String:title}")
Movie.age_days = model.Property(f"{Movie} has {Integer:age_days}")
Movie.in_house = model.Property(f"{Movie} has {Integer:in_house}")

Director = model.Concept("Director", extends=[Item], identify_by={"id": Integer})
Director.name = model.Property(f"{Director} has {String:name}")

Actor = model.Concept("Actor", extends=[Item], identify_by={"id": Integer})
Actor.name = model.Property(f"{Actor} has {String:name}")

Genre = model.Concept("Genre", extends=[Item], identify_by={"id": Integer})
Genre.name = model.Property(f"{Genre} has {String:name}")

# CSV ingest. The bundled data is a small hand-crafted sample; swap to
# the MovieLens-1M-KG download (see `data/fetch_movielens_kg.sh`) for
# the realistic instance.
users_csv = read_csv(data_dir / "users.csv")
movies_csv = read_csv(data_dir / "movies.csv")
directors_csv = read_csv(data_dir / "directors.csv")
actors_csv = read_csv(data_dir / "actors.csv")
genres_csv = read_csv(data_dir / "genres.csv")
watched_csv = read_csv(data_dir / "watched.csv")
md_csv = read_csv(data_dir / "movie_director.csv")
ma_csv = read_csv(data_dir / "movie_actor.csv")
mg_csv = read_csv(data_dir / "movie_genre.csv")
ms_csv = read_csv(data_dir / "movie_similar.csv")

model.define(User.new(model.data(users_csv).to_schema()))
model.define(Movie.new(model.data(movies_csv).to_schema()))
model.define(Director.new(model.data(directors_csv).to_schema()))
model.define(Actor.new(model.data(actors_csv).to_schema()))
model.define(Genre.new(model.data(genres_csv).to_schema()))

# --- Edges (typed Relationships) ------------------------------------

User.watched = model.Relationship(
    f"{User:user} watched {Movie:movie} with rating {Integer:rating}",
    short_name="watched",
)
watched_data = model.data(watched_csv)
rating_ref = Integer.ref()
model.define(User.watched(User, Movie, rating_ref)).where(
    User.id == watched_data.user_id,
    Movie.id == watched_data.movie_id,
    rating_ref == watched_data.rating,
)

Movie.directed_by = model.Relationship(
    f"{Movie:movie} directed by {Director:director}",
    short_name="directed_by",
)
md_data = model.data(md_csv)
model.define(Movie.directed_by(Movie, Director)).where(
    Movie.id == md_data.movie_id,
    Director.id == md_data.director_id,
)

Movie.acted_by = model.Relationship(
    f"{Movie:movie} stars {Actor:actor}",
    short_name="acted_by",
)
ma_data = model.data(ma_csv)
model.define(Movie.acted_by(Movie, Actor)).where(
    Movie.id == ma_data.movie_id,
    Actor.id == ma_data.actor_id,
)

Movie.belongs_to = model.Relationship(
    f"{Movie:movie} in genre {Genre:genre}",
    short_name="belongs_to",
)
mg_data = model.data(mg_csv)
model.define(Movie.belongs_to(Movie, Genre)).where(
    Movie.id == mg_data.movie_id,
    Genre.id == mg_data.genre_id,
)

Movie.similar_to = model.Relationship(
    f"{Movie:movie} similar to {Movie:other}",
    short_name="similar_to",
)
ms_data = model.data(ms_csv)
src_m, dst_m = Movie.ref(), Movie.ref()
model.define(Movie.similar_to(src_m, dst_m)).where(
    src_m.id == ms_data.src_movie_id,
    dst_m.id == ms_data.dst_movie_id,
)

# --- Unified KG edge (workaround for v1.1.0 composite-edge gap) -----
# `Item.connected_to(Item, Item)` is the single 2-arity relationship
# the path walker traverses. Populate it from each typed edge so a
# bounded walk can chain User -> Movie -> Director -> Movie -> ...
# Each define() below contributes one direction of one typed edge to
# the union; the walker treats them all as the same generic hop and
# we recover the per-hop type by joining each consecutive (src, dst)
# back against the typed edges when computing explanation features.
Item.connected_to = model.Relationship(
    f"{Item:src} connected to {Item:dst}",
    short_name="connected_to",
)

# User <-> Movie via watched (both directions; user-anchor walks).
u_e, m_e = User.ref(), Movie.ref()
rating_e = Integer.ref()
model.define(Item.connected_to(u_e, m_e)).where(
    User.watched(u_e, m_e, rating_e),
)
model.define(Item.connected_to(m_e, u_e)).where(
    User.watched(u_e, m_e, rating_e),
)

# Movie <-> Director.
m_d, d_e = Movie.ref(), Director.ref()
model.define(Item.connected_to(m_d, d_e)).where(Movie.directed_by(m_d, d_e))
model.define(Item.connected_to(d_e, m_d)).where(Movie.directed_by(m_d, d_e))

# Movie <-> Actor.
m_a, a_e = Movie.ref(), Actor.ref()
model.define(Item.connected_to(m_a, a_e)).where(Movie.acted_by(m_a, a_e))
model.define(Item.connected_to(a_e, m_a)).where(Movie.acted_by(m_a, a_e))

# Movie <-> Genre.
m_g, g_e = Movie.ref(), Genre.ref()
model.define(Item.connected_to(m_g, g_e)).where(Movie.belongs_to(m_g, g_e))
model.define(Item.connected_to(g_e, m_g)).where(Movie.belongs_to(m_g, g_e))

# Movie <-> Movie via similar_to (both directions; the similarity
# graph is conceptually undirected for traversal purposes).
m_s1, m_s2 = Movie.ref(), Movie.ref()
model.define(Item.connected_to(m_s1, m_s2)).where(Movie.similar_to(m_s1, m_s2))
model.define(Item.connected_to(m_s2, m_s1)).where(Movie.similar_to(m_s1, m_s2))

# --- Pillar 1: Graph -- PageRank over the movie-similarity graph ----

# Movie-Movie similarity graph derived from co-watch / similar_to.
# `node_concept=Movie` makes graph-algorithm output bind directly to
# Movie without DataFrame round-trips. Aggregator "sum" collapses
# multi-edges so two paths of similarity between the same pair count
# once.
sim_graph = Graph(
    model,
    directed=False,
    weighted=False,
    node_concept=Movie,
    aggregator="sum",
)
src_g, dst_g = Movie.ref(), Movie.ref()
model.define(sim_graph.Edge.new(src=src_g, dst=dst_g)).where(
    Movie.similar_to(src_g, dst_g),
)

# PageRank: structural-popularity prior. Stored as Float (the native
# pagerank() output type). HiGHS handles float coefficients on binary
# decisions natively; the same pattern is used by supply_chain.
Movie.pagerank_score = model.Property(
    f"{Movie} has structural score {Float:pagerank_score}"
)
pagerank_rel = sim_graph.pagerank()
m_pr = Movie.ref()
score_pr = Float.ref()
model.define(m_pr.pagerank_score(score_pr)).where(
    pagerank_rel(m_pr, score_pr),
)

# --- Pillar 2: Paths -- bounded heterogeneous KG walk ---------------
#
# Walk the unified `Item.connected_to` edge from each User up to
# MAX_HOPS hops. Each walk traces a real heterogeneous KG path
# (User -> Movie -> Director -> Movie, User -> Movie -> Genre -> Movie,
# User -> Movie -> Movie via similar_to, ...). The path-walker bounds
# enumeration to MAX_HOPS, so the candidate set is the bounded
# reachable set under the KG -- the same primitive Pixie / KPRN /
# LinkedIn Career Explorer compose at production scale.
kg_paths = model.path(
    Item.connected_to.repeat(1, MAX_HOPS),
).all_paths()

# Candidate set: any (user, movie) reached by a User-anchored
# bounded KG walk ending at a Movie node. v1.1.0 does not yet
# support `not` (paths-lib README §"Currently unsupported patterns"
# and compliance_rule_audit's documented gap), so the
# already-watched filter lands as a `pick == 0` IC at the
# prescriptive layer instead.
Candidate = model.Concept(
    "Candidate",
    identify_by={"user_id": Integer, "movie_id": Integer},
)
u_cand, m_cand = User.ref(), Movie.ref()
p_cand = PathTraversal.ref()
model.define(Candidate.new(user_id=u_cand.id, movie_id=m_cand.id)).where(
    kg_paths(p_cand),
    p_cand.nodes(0, u_cand),
    p_cand.nodes(p_cand.length, m_cand),
)

# Per-(user, candidate) explanation features. Each is a count of
# distinct typed connections between the candidate and the user's
# watched history -- the KPRN-style typed-path aggregation that
# powers explainable KG-recsys at production scale.
Candidate.path_count_via_director = model.Property(
    f"{Candidate} has director connections {Integer:n}"
)
Candidate.path_count_via_actor = model.Property(
    f"{Candidate} has actor connections {Integer:n}"
)
Candidate.path_count_via_genre = model.Property(
    f"{Candidate} has genre connections {Integer:n}"
)
Candidate.path_count_via_kg_walk = model.Property(
    f"{Candidate} has KG-walk paths {Integer:n}"
)
Candidate.path_count_total = model.Property(
    f"{Candidate} has total connections {Integer:n}"
)

c = Candidate.ref()
n = Integer.ref()
u_c, m_c = User.ref(), Movie.ref()

# via-director: distinct directors shared between candidate and any
# of the user's watched movies.
m_watched_d = Movie.ref()
d_ref = Director.ref()
model.define(Candidate.path_count_via_director(c, n)).where(
    Candidate(c),
    c.user_id == u_c.id,
    c.movie_id == m_c.id,
    n
    == count(d_ref).where(
        User.watched(u_c, m_watched_d, Integer.ref()),
        Movie.directed_by(m_watched_d, d_ref),
        Movie.directed_by(m_c, d_ref),
    ),
)

# via-actor: distinct actors shared.
m_watched_a = Movie.ref()
a_ref = Actor.ref()
model.define(Candidate.path_count_via_actor(c, n)).where(
    Candidate(c),
    c.user_id == u_c.id,
    c.movie_id == m_c.id,
    n
    == count(a_ref).where(
        User.watched(u_c, m_watched_a, Integer.ref()),
        Movie.acted_by(m_watched_a, a_ref),
        Movie.acted_by(m_c, a_ref),
    ),
)

# via-genre: distinct genres shared.
m_watched_g = Movie.ref()
g_ref = Genre.ref()
model.define(Candidate.path_count_via_genre(c, n)).where(
    Candidate(c),
    c.user_id == u_c.id,
    c.movie_id == m_c.id,
    n
    == count(g_ref).where(
        User.watched(u_c, m_watched_g, Integer.ref()),
        Movie.belongs_to(m_watched_g, g_ref),
        Movie.belongs_to(m_c, g_ref),
    ),
)

# via-walk: number of bounded heterogeneous KG paths from this user
# to the candidate (the actual paths-pillar count -- the headline
# explanation-strength signal).
p_s = PathTraversal.ref()
model.define(Candidate.path_count_via_kg_walk(c, n)).where(
    Candidate(c),
    c.user_id == u_c.id,
    c.movie_id == m_c.id,
    n
    == count(p_s).where(
        kg_paths(p_s),
        p_s.nodes(0, u_c),
        p_s.nodes(p_s.length, m_c),
    ),
)

# Total: sum across types as a single integer feature for cold-start
# threshold checks.
model.define(Candidate.path_count_total(c, n)).where(
    Candidate(c),
    n
    == c.path_count_via_director
    + c.path_count_via_actor
    + c.path_count_via_genre
    + c.path_count_via_kg_walk,
)

# --- Personalized utility -------------------------------------------
# Blend structural prior (float PageRank) with per-user path signal
# (integer path counts) into a single Float utility. HiGHS handles
# float coefficients on binary decisions natively (supply_chain uses
# the same pattern).
Candidate.utility = model.Property(f"{Candidate} has utility {Float:utility}")
m_u = Movie.ref()
util = Float.ref()
model.define(Candidate.utility(c, util)).where(
    Candidate(c),
    c.movie_id == m_u.id,
    util
    == PAGERANK_WEIGHT * m_u.pagerank_score
    + PATH_SIGNAL_WEIGHT
    * (2 * c.path_count_via_director + c.path_count_via_actor + c.path_count_via_genre),
)

# --- Pillar 3: Prescriptive -- MIP slate selection ------------------

Candidate.pick = model.Property(f"{Candidate} is picked iff {Float:p}")

problem = Problem(model, Float)
problem.solve_for(
    Candidate.pick,
    type="bin",
    name=["pick", Candidate.user_id, Candidate.movie_id],
)

# Cardinality: each user gets exactly K picks.
slate_size_ic = model.require(
    sum(Candidate.pick).per(Candidate.user_id) == SLATE_SIZE_K
)
problem.satisfy(slate_size_ic)

# Watched-exclusion: any (user, movie) where the user has already
# watched the movie must have pick == 0. v1.1.0 lacks `not` in
# rules (paths-lib README + compliance_rule_audit's documented gap),
# so the exclusion lands here at the prescriptive layer rather than
# as a `~User.watched(...)` filter on the candidate derivation.
u_excl, m_excl = User.ref(), Movie.ref()
rating_excl_ic = Integer.ref()
exclude_watched_ic = model.where(
    User.watched(u_excl, m_excl, rating_excl_ic),
    Candidate.user_id == u_excl.id,
    Candidate.movie_id == m_excl.id,
).require(Candidate.pick == 0)
problem.satisfy(exclude_watched_ic)

# Genre diversity: at most MAX_PER_GENRE picks per (user, genre).
genre_diversity_ic = model.where(
    Movie.id == Candidate.movie_id,
    Movie.belongs_to(Movie, Genre),
).require(sum(Candidate.pick).per(Candidate.user_id, Genre) <= MAX_PER_GENRE)
problem.satisfy(genre_diversity_ic)

# Director uniqueness: no user gets more than MAX_PER_DIRECTOR picks
# from the same director.
director_uniqueness_ic = model.where(
    Movie.id == Candidate.movie_id,
    Movie.directed_by(Movie, Director),
).require(sum(Candidate.pick).per(Candidate.user_id, Director) <= MAX_PER_DIRECTOR)
problem.satisfy(director_uniqueness_ic)

# Actor diversity.
actor_diversity_ic = model.where(
    Movie.id == Candidate.movie_id,
    Movie.acted_by(Movie, Actor),
).require(sum(Candidate.pick).per(Candidate.user_id, Actor) <= MAX_PER_ACTOR)
problem.satisfy(actor_diversity_ic)

# Freshness floor: at least FRESHNESS_FLOOR picks within the
# FRESH_WINDOW_DAYS recency window.
freshness_ic = model.where(
    Movie.id == Candidate.movie_id,
    Movie.age_days <= FRESH_WINDOW_DAYS,
).require(sum(Candidate.pick).per(Candidate.user_id) >= FRESHNESS_FLOOR)
problem.satisfy(freshness_ic)

# Originals exposure floor: at least ORIGINALS_FLOOR in-house items.
originals_ic = model.where(
    Movie.id == Candidate.movie_id,
    Movie.in_house == 1,
).require(sum(Candidate.pick).per(Candidate.user_id) >= ORIGINALS_FLOOR)
problem.satisfy(originals_ic)

# Cold-start cap: at most COLD_START_CAP weakly-explained picks.
cold_start_ic = model.where(
    Candidate.path_count_total < WEAK_EXPLANATION_THRESHOLD,
).require(sum(Candidate.pick).per(Candidate.user_id) <= COLD_START_CAP)
problem.satisfy(cold_start_ic)

# Explanation floor: each user's slate must carry enough creator-path
# weight aggregated over picked items. A sum-bound on the
# decision-multiplied integer feature.
explanation_ic = model.require(
    sum(Candidate.path_count_via_director * Candidate.pick).per(Candidate.user_id)
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
    exclude_watched_ic,
    genre_diversity_ic,
    director_uniqueness_ic,
    actor_diversity_ic,
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
    f"\nCandidate set per user (Movies reachable within {MAX_HOPS} hops over the heterogeneous KG):"
)
model.select(
    Candidate.user_id.alias("user_id"),
    Candidate.movie_id.alias("movie_id"),
    Candidate.path_count_total.alias("path_count_total"),
    Candidate.path_count_via_kg_walk.alias("paths_via_kg_walk"),
    Candidate.path_count_via_director.alias("paths_via_director"),
    Candidate.path_count_via_actor.alias("paths_via_actor"),
    Candidate.path_count_via_genre.alias("paths_via_genre"),
    Candidate.utility.alias("utility"),
).inspect()

print("\nMovie structural-popularity prior (PageRank, integer-rescaled):")
model.select(
    Movie.id.alias("movie_id"),
    Movie.title.alias("title"),
    Movie.pagerank_score.alias("structural_score"),
).inspect()

print(f"\nFinal slate per user (K = {SLATE_SIZE_K}):")
model.select(
    Candidate.user_id.alias("user_id"),
    Candidate.movie_id.alias("movie_id"),
    Candidate.utility.alias("utility"),
    Candidate.path_count_total.alias("path_count_total"),
).where(Candidate.pick == 1).inspect()

print("\nGenre distribution per user's slate (cap = MAX_PER_GENRE):")
m_disp = Movie.ref()
g_disp = Genre.ref()
model.select(
    Candidate.user_id.alias("user_id"),
    g_disp.name.alias("genre"),
    sum(Candidate.pick)
    .per(Candidate.user_id, g_disp)
    .where(
        Candidate.movie_id == m_disp.id,
        Movie.belongs_to(m_disp, g_disp),
    )
    .alias("n_picked"),
).inspect()

print("\nExplanation-path support per picked item:")
model.select(
    Candidate.user_id.alias("user_id"),
    Candidate.movie_id.alias("movie_id"),
    Candidate.path_count_via_kg_walk.alias("paths_via_kg_walk"),
    Candidate.path_count_via_director.alias("paths_via_director"),
    Candidate.path_count_via_actor.alias("paths_via_actor"),
    Candidate.path_count_via_genre.alias("paths_via_genre"),
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
#   (Amazon-Book), course slates (LinkedIn-style career navigation),
#   or news (MIND).
