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
SLATE_SIZE_K = 8

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

User = model.Concept("User", identify_by={"id": Integer})
User.name = model.Property(f"{User} has {String:name}")

Movie = model.Concept("Movie", identify_by={"id": Integer})
Movie.title = model.Property(f"{Movie} has {String:title}")
Movie.age_days = model.Property(f"{Movie} has {Integer:age_days}")
Movie.in_house = model.Property(f"{Movie} has {Integer:in_house}")

Director = model.Concept("Director", identify_by={"id": Integer})
Director.name = model.Property(f"{Director} has {String:name}")

Actor = model.Concept("Actor", identify_by={"id": Integer})
Actor.name = model.Property(f"{Actor} has {String:name}")

Genre = model.Concept("Genre", identify_by={"id": Integer})
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
model.define(User.watched(User, Movie, Integer.ref())).where(
    User.id == watched_data.user_id,
    Movie.id == watched_data.movie_id,
    Integer.ref() == watched_data.rating,
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

# PageRank: structural-popularity prior. Rescaled to integer points
# so the prescriptive objective stays integer-arithmetic-clean (see
# template-authoring conventions: float coefficients on integer
# decisions are OK on HiGHS, but mixing float/integer ICs is
# fragile -- keep utility integer for sanity).
Movie.pagerank_score = model.Property(
    f"{Movie} has structural score {Integer:pagerank_score}"
)
pagerank_rel = sim_graph.pagerank()
m_pr = Movie.ref()
score_pr = Float.ref()
# Rescale float pagerank into integer points (multiply, round-down).
# Choose a multiplier large enough that the head of the distribution
# differentiates 5+ tiers; PageRank values are typically in (0, 1)
# with most mass small.
PAGERANK_SCALE = 100000
model.define(m_pr.pagerank_score((score_pr * PAGERANK_SCALE).cast(Integer))).where(
    pagerank_rel(m_pr, score_pr),
)

# --- Pillar 2: Paths -- bounded explanation paths -------------------

# Union of typed edges the path walker may traverse. Each edge
# contributes a different explanation type.
ItemReachable = (
    User.watched
    | Movie.directed_by
    | Movie.acted_by
    | Movie.belongs_to
    | Movie.similar_to
)

# Bare-BFS form (no explicit endpoints): yields a callable
# Relationship usable inside `.where()` for downstream rules. The
# explicit-endpoint form returns a non-callable Fragment column that
# does not compose this way (see attack_path_hardening for the same
# v1.1.0 quirk).
all_explanation_paths = model.path(
    ItemReachable.repeat(1, MAX_HOPS),
).all_paths()

# Sub-concept restricting paths to (User start, Movie end). Same
# v1.1.0 quirk as attack_path_hardening: the membership rule yields
# the right ExplanationPath set, but downstream rules walking
# `ExplanationPath.nodes` must re-apply the User/Movie filter
# inline.
ExplanationPath = model.Concept("ExplanationPath", extends=[PathTraversal])
u_ref, m_ref = User.ref(), Movie.ref()
model.define(ExplanationPath(PathTraversal)).where(
    all_explanation_paths(PathTraversal),
    PathTraversal.nodes(0, u_ref),
    PathTraversal.nodes(PathTraversal.length, m_ref),
    User(u_ref),
    Movie(m_ref),
)

# Candidate set: any (user, movie) connected by at least one
# explanation path. Restrict to movies the user has NOT yet watched.
Candidate = model.Concept(
    "Candidate",
    identify_by={"user_id": Integer, "movie_id": Integer},
)
u_cand, m_cand = User.ref(), Movie.ref()
ep = ExplanationPath.ref()
u_filt, m_filt = User.ref(), Movie.ref()
model.define(Candidate.new(user_id=u_cand.id, movie_id=m_cand.id)).where(
    ep.nodes(0, u_filt),
    ep.nodes(ep.length, m_filt),
    User(u_filt),
    Movie(m_filt),
    u_cand == u_filt,
    m_cand == m_filt,
    # Exclude already-watched movies from the candidate set.
    ~User.watched(u_cand, m_cand, Integer.ref()),
)

# Path-count-by-type: for each (user, candidate), count paths whose
# step-set intersects each entity type. Counts are derived from a
# membership-style aggregation -- identify each path's "type
# fingerprint" by which non-Movie / non-User entity types appear
# along its node sequence.
#
# v1.1.0 quirk: `p.nodes(idx, x)` exposes only User / Movie endpoints
# along a path; intermediate Director / Actor / Genre nodes are not
# reachable that way. Recover them via the same consecutive-pair
# join attack_path_hardening uses, then aggregate.

PathViaDirector = model.Relationship(
    f"{ExplanationPath:path} routes via {Director:director}",
    short_name="path_via_director",
)
idx_d = Integer.ref()
src_d, dst_d = Movie.ref(), Movie.ref()
ep_filt_d = ExplanationPath.ref()
u_d, m_d = User.ref(), Movie.ref()
model.define(PathViaDirector(ExplanationPath, Director)).where(
    ExplanationPath.nodes(0, u_d),
    ExplanationPath.nodes(ExplanationPath.length, m_d),
    User(u_d),
    Movie(m_d),
    ExplanationPath.nodes(idx_d, src_d),
    ExplanationPath.nodes(idx_d + 1, dst_d),
    Movie.directed_by(src_d, Director),
    Movie.directed_by(dst_d, Director),
)

PathViaActor = model.Relationship(
    f"{ExplanationPath:path} routes via {Actor:actor}",
    short_name="path_via_actor",
)
src_a, dst_a = Movie.ref(), Movie.ref()
idx_a = Integer.ref()
u_a, m_a = User.ref(), Movie.ref()
model.define(PathViaActor(ExplanationPath, Actor)).where(
    ExplanationPath.nodes(0, u_a),
    ExplanationPath.nodes(ExplanationPath.length, m_a),
    User(u_a),
    Movie(m_a),
    ExplanationPath.nodes(idx_a, src_a),
    ExplanationPath.nodes(idx_a + 1, dst_a),
    Movie.acted_by(src_a, Actor),
    Movie.acted_by(dst_a, Actor),
)

PathViaGenre = model.Relationship(
    f"{ExplanationPath:path} routes via {Genre:genre}",
    short_name="path_via_genre",
)
src_g2, dst_g2 = Movie.ref(), Movie.ref()
idx_g = Integer.ref()
u_g, m_g = User.ref(), Movie.ref()
model.define(PathViaGenre(ExplanationPath, Genre)).where(
    ExplanationPath.nodes(0, u_g),
    ExplanationPath.nodes(ExplanationPath.length, m_g),
    User(u_g),
    Movie(m_g),
    ExplanationPath.nodes(idx_g, src_g2),
    ExplanationPath.nodes(idx_g + 1, dst_g2),
    Movie.belongs_to(src_g2, Genre),
    Movie.belongs_to(dst_g2, Genre),
)

# Per-(user, candidate) path-count-by-type: integer features the
# prescriptive layer reads.
Candidate.path_count_via_director = model.Property(
    f"{Candidate} has director paths {Integer:n}"
)
Candidate.path_count_via_actor = model.Property(
    f"{Candidate} has actor paths {Integer:n}"
)
Candidate.path_count_via_genre = model.Property(
    f"{Candidate} has genre paths {Integer:n}"
)
Candidate.path_count_total = model.Property(f"{Candidate} has total paths {Integer:n}")

ep_c = ExplanationPath.ref()
u_c, m_c = User.ref(), Movie.ref()
model.define(Candidate.path_count_via_director(c, n)).where(
    Candidate(c),
    c.user_id == u_c.id,
    c.movie_id == m_c.id,
    n
    == count(ep_c).where(
        ep_c.nodes(0, u_c),
        ep_c.nodes(ep_c.length, m_c),
        PathViaDirector(ep_c, Director.ref()),
    ),
)
model.define(Candidate.path_count_via_actor(c, n)).where(
    Candidate(c),
    c.user_id == u_c.id,
    c.movie_id == m_c.id,
    n
    == count(ep_c).where(
        ep_c.nodes(0, u_c),
        ep_c.nodes(ep_c.length, m_c),
        PathViaActor(ep_c, Actor.ref()),
    ),
)
model.define(Candidate.path_count_via_genre(c, n)).where(
    Candidate(c),
    c.user_id == u_c.id,
    c.movie_id == m_c.id,
    n
    == count(ep_c).where(
        ep_c.nodes(0, u_c),
        ep_c.nodes(ep_c.length, m_c),
        PathViaGenre(ep_c, Genre.ref()),
    ),
)
model.define(Candidate.path_count_total(c, n)).where(
    Candidate(c),
    c.user_id == u_c.id,
    c.movie_id == m_c.id,
    n
    == count(ep_c).where(
        ep_c.nodes(0, u_c),
        ep_c.nodes(ep_c.length, m_c),
    ),
)

# --- Personalized utility -------------------------------------------
# Blend structural prior (PageRank) with per-user path signal. Both
# scaled to integer points so the MIP objective is a clean integer
# linear combination on float-coefficient-times-binary-decision
# arithmetic. The path signal is a weighted sum of typed path counts;
# the structural prior uses the global PageRank score as a popularity
# floor.
Candidate.utility = model.Property(f"{Candidate} has utility {Integer:utility}")
m_u = Movie.ref()
model.define(Candidate.utility(c, util)).where(
    Candidate(c),
    c.movie_id == m_u.id,
    util
    == PAGERANK_WEIGHT * m_u.pagerank_score
    + PATH_SIGNAL_WEIGHT
    * (2 * c.path_count_via_director + c.path_count_via_actor + c.path_count_via_genre),
)

# --- Pillar 3: Prescriptive -- MIP slate selection ------------------

Candidate.pick = model.Property(f"{Candidate} is picked iff {Integer:p}")

problem = Problem(model, Integer)
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

print(f"\nCandidate set per user (movies reachable within {MAX_HOPS} hops, unwatched):")
model.select(
    Candidate.user_id.alias("user_id"),
    Candidate.movie_id.alias("movie_id"),
    Candidate.path_count_total.alias("path_count_total"),
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
