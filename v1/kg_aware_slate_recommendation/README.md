---
title: "KG-aware slate recommendation"
description: "Three-pillar Graph + Paths + Prescriptive (MIP) template that picks K items per user under business rules, with KG-path explanations."
experience_level: advanced
industry: media
tags: [graph, paths, prescriptive, mip, recommendation, slate, explainability]
featured: false
---

# KG-aware slate recommendation

## What this template is for

Every consumer-facing platform with a "row of K things" surface --
streaming homepages, e-commerce cross-sell carousels, news feeds,
learning-platform course slates -- has the same problem: pick K items
per user that are *individually* relevant, *collectively* diverse, and
*explainable* enough to satisfy the platform's business rules and (for
EU and finance / healthcare-regulated platforms) regulatory mandates
on automated-decision transparency.

This template solves that problem in one declarative model:

- **Graph (PageRank)** computes a structural-popularity prior over the
  movie-similarity graph -- the same primitive that powers
  Pinterest's Pixie recommender at production scale.
- **Paths** enumerate bounded knowledge-graph walks
  (`User -> watched -> Movie -> shares director / actor / genre /
  similar -> candidate`) and produce per-`(user, candidate)`
  explanation features the prescriptive layer reads as data.
- **Prescriptive (MIP, HiGHS)** picks K items per user under genre
  diversity, director uniqueness, freshness, originals exposure,
  cold-start, and explanation-path-floor constraints, while
  maximising the personalised utility blended from the graph and
  paths signals.

The same shape ports to e-commerce ("frequently bought together" with
category coverage), course slates (LinkedIn-style career navigation
over a skills graph with prerequisite respect), and news feed
optimisation under topic / source / recency caps.

## Why constrained slate composition matters

Production recsys runs a multi-stage funnel: *catalogue (10^6+) ->
retrieval (10^3) -> pre-ranking (10^2) -> ranking (float utility) ->
slate optimisation (final K)*. The slate stage is where business
rules, diversity, exposure floors, and explainability constraints
land -- the place production teams burn months on hand-rolled
re-rankers that violate diversity invariants nondeterministically.
PyRel's prescriptive pillar fits this stage directly, in one
declarative model with the upstream graph and paths signals.

### Production precedent

- **Pinterest Pixie** (Eksombatchai et al., WWW 2018) -- random-walk
  path-based recsys, 3B nodes, 17B edges, 200M+ users, 60ms p99
  latency, powers >50% of Pin engagement.
- **Alibaba iGraph + AliCoCo** -- production graph engine for online
  recsys at Taobao, KG-traversal-based.
- **eBay KPRN** (Wang et al., AAAI 2019) -- open-source
  path-recurrent network for KG-aware recommendation.
- **LinkedIn Career Explorer** -- path-based career navigation over
  the 39K-skill / 875M-people / 59M-companies Skills Graph.
- **GE Healthcare KARE** (ICLR 2025) -- shortest-path subgraph
  reasoning over UMLS for clinical predictions, the production-
  deployed approach for ADR and treatment recommendations under
  regulated frameworks.

### Regulatory drivers

KG-path explanations are not just nice-to-have -- they are required
for any recsys subject to:

- **EU GDPR Article 22 + Articles 13/14** -- meaningful information
  about the logic in automated decisions.
- **EU AI Act Article 13 + Article 86** -- transparency and
  decision-making explanations for high-risk AI.
- **ECJ Case C-203/22 (February 2025)** -- first court ruling
  explicitly recognising right-to-explanation under GDPR.
- **Financial-services explainability mandates** -- BIS-FSI,
  FINRA AI guidance.
- **State and national laws** -- NYC Local Law 144, Illinois AIVIA,
  China PIPL Article 24, Brazil LGPD Article 20, Quebec Act,
  Nigeria DPR.

The path PyRel walks for each picked item is the
counterfactual-style explanation those regulations call for, in a
form trade-secret-respecting (it exposes facts, not model weights).

## Quickstart

> [!TIP]
> Click the **Download ZIP** button above to grab this template as a
> standalone project, or pull from the docs site:

```bash
curl -O https://docs.relational.ai/templates/zips/v1/kg_aware_slate_recommendation.zip
unzip kg_aware_slate_recommendation.zip
cd kg_aware_slate_recommendation
```

1. Install Python 3.10+ if you don't have it.
2. Install dependencies in a fresh virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e .
   ```

3. Configure your RAI authentication (see RAI docs for the standard
   setup).
4. Run:

   ```bash
   python kg_aware_slate_recommendation.py
   ```

The bundled `data/` directory carries a small hand-crafted sample
that lets the runner execute end-to-end against your RAI account in
seconds. For the realistic instance, swap in MovieLens-1M-KG (KGAT
distribution, see "Customise this template" below).

## How it works

### Schema

- `User(id, name)`
- `Movie(id, title, age_days, in_house)`
- `Director(id, name)`, `Actor(id, name)`, `Genre(id, name)`
- Edges: `User.watched(Movie, rating)`,
  `Movie.directed_by(Director)`, `Movie.acted_by(Actor)`,
  `Movie.belongs_to(Genre)`, `Movie.similar_to(Movie)`

### Pipeline

1. **Graph: PageRank over movie-similarity.** A `Graph` is built from
   `Movie.similar_to`; `pagerank()` returns the per-movie structural
   importance, which is integer-rescaled and stored as
   `Movie.pagerank_score`. This is the per-item popularity prior the
   prescriptive layer uses, the same shape Pinterest's Pixie applies
   at production scale.

2. **Paths: bounded explanation paths.** The path walker traverses the
   union of typed edges (`watched | directed_by | acted_by |
   belongs_to | similar_to`) up to `MAX_HOPS = 3`. Each
   `(user, candidate)` pair gets path-counts-by-type
   (`path_count_via_director`, `_via_actor`, `_via_genre`) and a
   `path_count_total`. These are integer features the MIP reads.

3. **Prescriptive: MIP slate selection.** Decisions:
   `Candidate.pick in {0, 1}`. Constraints:
   - Cardinality: `count(pick) per user == K`.
   - Genre diversity: at most `MAX_PER_GENRE` picks per
     `(user, genre)`.
   - Director uniqueness: at most `MAX_PER_DIRECTOR` per
     `(user, director)`.
   - Actor diversity: at most `MAX_PER_ACTOR` per
     `(user, actor)`.
   - Freshness floor: at least `FRESHNESS_FLOOR` items with
     `age_days <= FRESH_WINDOW_DAYS`.
   - Originals exposure floor: at least `ORIGINALS_FLOOR` in-house
     items.
   - Cold-start cap: at most `COLD_START_CAP` weakly-explained items
     (those with `path_count_total < WEAK_EXPLANATION_THRESHOLD`).
   - Explanation-path floor: total
     `path_count_via_director` over the slate must be at least
     `EXPLANATION_FLOOR`.
   Objective: maximise `sum(utility * pick)`, where `utility` blends
   `pagerank_score` and a weighted sum of path-counts-by-type.

### Why MIP, not CSP

PageRank scores are inherently float and heavy-tailed; quantising to
integer tiers conflates items differing by 3-5x at the head of the
distribution. Float coefficients on binary decisions is the textbook
slate-IP shape every major recsys / ad-allocation platform publishes
(Pinterest, Alibaba, Meta, Google AdX), and HiGHS's LP-relaxation
guidance prunes harder than CSP bounded search at the per-user
candidate-set sizes typical for slate composition.

## Template structure

```
kg_aware_slate_recommendation/
├── data/
│   ├── users.csv
│   ├── movies.csv
│   ├── directors.csv
│   ├── actors.csv
│   ├── genres.csv
│   ├── watched.csv
│   ├── movie_director.csv
│   ├── movie_actor.csv
│   ├── movie_genre.csv
│   └── movie_similar.csv
├── kg_aware_slate_recommendation.py
├── pyproject.toml
└── README.md
```

## Customise this template

The first changes most users will make:

- **Swap to MovieLens-1M-KG (KGAT distribution).** The realistic
  instance build runs against the public KGAT-processed
  MovieLens-1M-KG distribution
  (`github.com/xiangwang1223/knowledge_graph_attention_network`).
  Drop the `data/` CSVs in place; the schema matches.
- **Retarget to e-commerce.** Replace `Movie` with `Product`,
  `watched` with `purchased`, `similar_to` with co-purchase. The
  template runs as a "frequently bought together" slate composer
  with category coverage, brand exclusivity, and price-tier mix.
- **Retarget to course slates / career paths.** Replace `Movie` with
  `Course`, add prerequisite edges, run the LinkedIn-style
  Career-Explorer pattern with prerequisite respect and
  credit-hour caps.
- **Predictive-pillar variant.** Replace `Movie.pagerank_score` with
  a learned GNN affinity score from PyRel's predictive reasoner.
  Same MIP, different scoring source.
- **LLM-grounded explanation surfacing.** Pipe the top explanation
  path per picked item into an LLM call to render natural-language
  explanations from the KG-grounded path data, eliminating
  hallucination -- the 2025 LLM+KG hybrid pattern (ItemRAG,
  Think-on-Graph, K-RagRec).
- **A/B candidate slate enumeration.**
  `solve("highs", solution_limit=K_alt)` returns K alternative slates
  for downstream A/B exposure or human-in-the-loop curation -- the
  production-deployed shape for editorial-review platforms (kids
  content, regulated regions).
- **Tighten or relax the constraint dials.** `MAX_PER_GENRE`,
  `FRESHNESS_FLOOR`, `ORIGINALS_FLOOR`, `COLD_START_CAP`,
  `EXPLANATION_FLOOR` are top-of-file constants.

## References

- Eksombatchai, Jindal, Liu, Liu, Sharma, Sugnet, Ulrich & Leskovec,
  *Pixie: A System for Recommending 3+ Billion Items to 200+ Million
  Users in Real-Time*, WWW 2018 --
  <https://cs.stanford.edu/people/jure/pubs/pixie-www18.pdf>.
- Wang, He, Cao, Liu & Chua, *KGAT: Knowledge Graph Attention Network
  for Recommendation*, KDD 2019 --
  <https://dl.acm.org/doi/10.1145/3292500.3330989>. Source of the
  MovieLens-1M-KG / Amazon-Book / Yelp-KG datasets used as the
  realistic-instance build.
- Wang, Wang, Xu, He, Cao & Chua, *Explainable Reasoning over
  Knowledge Graphs for Recommendation (KPRN)*, AAAI 2019 --
  <https://cdn.aaai.org/ojs/4470/4470-13-7509-1-10-20190706.pdf>.
- Xian, Fu, Muthukrishnan, de Melo & Zhang, *Reinforcement Knowledge
  Graph Reasoning for Explainable Recommendation (PGPR)*, SIGIR
  2019 -- <http://gerard.demelo.org/papers/kg-recommendations.pdf>.
- Sun, Han, Yan, Yu & Wu, *PathSim: Meta Path-Based Top-K Similarity
  Search in Heterogeneous Information Networks*, VLDB 2011 --
  <https://www.vldb.org/pvldb/vol4/p992-sun.pdf>.
- Ying, He, Chen, Eksombatchai, Hamilton & Leskovec, *Graph
  Convolutional Neural Networks for Web-Scale Recommender Systems
  (PinSage)*, KDD 2018 -- <https://arxiv.org/abs/1806.01973>.
- Kim et al., *ItemRAG: KG-RAG for LLM-Based Recommendation*, ACL
  2025 -- <https://aclanthology.org/2025.acl-long.1317.pdf>.
- LinkedIn Engineering, *Building the Skills Graph* --
  <https://www.linkedin.com/blog/engineering/skills-graph/building-linkedin-s-skills-graph-to-power-a-skills-first-world>.
- Alibaba Cloud, *Taobao Recommendation Architecture (iGraph)* --
  <https://www.alibabacloud.com/blog/596205>.
- *MovieLens datasets* (GroupLens) --
  <https://grouplens.org/datasets/movielens/>.
