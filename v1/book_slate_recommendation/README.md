---
title: "Book Slate Recommendation"
description: "Three-pillar Graph + Paths + Prescriptive (MIP) template that picks K books per reader under business rules, with KG-path explanations."
featured: false
experience_level: advanced
industry: "Media"
reasoning_types:
  - Graph
  - Paths
  - Prescriptive
tags:
  - Multi-Reasoner
  - Recommendation
  - Slate
  - Mixed-Integer Programming
  - Explainability
---

# Book Slate Recommendation

## What this template is for

Every consumer-facing platform with a "row of K things" surface --
streaming homepages, e-commerce cross-sell carousels, news feeds,
learning-platform course slates -- has the same problem: pick K items
per user that are *individually* relevant, *collectively* diverse, and
*explainable* enough to meet the platform's business rules and (for
EU and finance / healthcare-regulated platforms) support transparency
obligations on automated decisions.

This template solves that problem in one declarative model:

- **Graph (PageRank)** computes a structural-popularity prior over the
  book-similarity graph -- the same primitive that powers
  Pinterest's Pixie recommender at production scale.
- **Paths** combine two reach signals: a bounded walker
  (`User -> read_Book` length 1, `User -> read_Book -> similar_Book`
  length 2) plus direct shared-entity joins
  (`User -> read_Book -> Author <- candidate`,
  `User -> read_Book -> Subject <- candidate`). Together these produce
  per-`(user, candidate)` typed-evidence counts the prescriptive
  layer reads as data.
- **Prescriptive (MIP, HiGHS)** picks K items per user under subject
  diversity, author uniqueness, freshness, originals exposure,
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

KG-grounded explanations can support transparency obligations that
recsys deployments increasingly face. Regulations to weigh against
your own legal review:

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

The per-typed counts the runner emits per picked item
(`paths_via_author`, `paths_via_subject`, `paths_via_kg_walk`) are a
KG-grounded, decomposable justification that can feed transparency
workflows -- exposing facts about the catalogue rather than model
weights. Whether that is sufficient for any particular legal regime
is a determination for your compliance team.

## Quickstart

1. Download ZIP:
   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/book_slate_recommendation.zip
   unzip book_slate_recommendation.zip
   cd book_slate_recommendation
   ```
   > [!TIP]
   > You can also download the template ZIP using the "Download ZIP" button at the top of this page.

2. Create venv:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   ```

3. Install:
   ```bash
   python -m pip install .
   ```

4. Configure (prompts for Snowflake account, role, and profile name):
   ```bash
   rai init
   ```

5. Run:
   ```bash
   python book_slate_recommendation.py
   ```

6. Expected output. The bundled `data/` directory carries a deterministic Open Library (CC0) slice (~60 books, ~58 authors, 12 subjects); synthetic users and read events are layered on top, and `similar_to` edges are derived from shared-author / shared-subject overlap. The runner prints the formulation, then the solve-result block, then per-user candidate sets, the chosen slate, subject distribution, and per-item explanation-path counts. Solver build strings and exact wall times will vary; objectives are stable at this slice size:
   ```text
   Solve result:
   • status: OPTIMAL
   • objective: 15618.781415528
   • solve time: 0.6s
   • num_points: 1
   • solver: HiGHS_1.13.1

   Final slate per user (K = 3):
      user_id book_id     utility path_count_total
   0        1      18  181.715774                6
   1        1      20  183.444363                6
   2        1      55  182.227725                6
   ...

   Explanation-path support per picked item:
      user_id book_id paths_via_kg_walk paths_via_author paths_via_subject
   0        1      18                 2                1                 3
   1        1      20                 3                1                 2
   2        1      55                 3                0                 3
   ...
   ```

   To pull a larger Open Library slice for a more realistic instance:
   ```bash
   python data/fetch_open_library_slice.py --size md   # ~250 books
   python data/fetch_open_library_slice.py --size lg   # ~600 books
   ```
   The fetch script caches API responses under `data/_cache/`, so reruns are reproducible and offline-friendly after the first pull. After bumping size, retune `EXPLANATION_FLOOR` and `WEAK_EXPLANATION_THRESHOLD` to the new path-count distribution -- the bundled `sm` slice has `path_count_total` in the 2-12 range; larger slices push that higher.

## How it works

### Schema

- `Item` super-concept; `User`, `Book`, `Author`, `Subject` all
  `extends=[Item]` so the path walker can chain across the whole
  heterogeneous KG via a single 2-arity edge.
- `User(id, name)`
- `Book(id, title, age_days, in_house)`
- `Author(id, name)`, `Subject(id, name)`
- Typed edges: `User.read(Book, rating)`,
  `Book.written_by(Author)`, `Book.about(Subject)`,
  `Book.similar_to(Book)`.
- Unified KG edge: `Item.connected_to(Item, Item)` populated as the
  symmetric union of the typed edges. Workaround for the v1.1.0
  paths-lib gap on multi-edge `path()` (see paths-lib README,
  "Currently unsupported patterns" §1). First-class composite-edge
  support is on the PyRel roadmap; once it lands, this unified-edge
  layer can be deleted.

### Pipeline

1. **Graph: PageRank over book-similarity.** A `Graph` is built from
   `Book.similar_to`; `pagerank()` returns the per-book structural
   importance, stored as `Book.pagerank_score` (Float). This is the
   per-item popularity prior the prescriptive layer uses, the same
   shape Pinterest's Pixie applies at production scale.

2. **Paths: bounded similarity walks + typed evidence joins.**
   The path walker traverses `Item.connected_to` (the symmetric
   union of `read | written_by | about | similar_to`) anchored at
   each `User` up to `MAX_HOPS = 2` hops. With a Book endpoint at
   length 2, the candidate set is the union of
   `User -> read_Book` (length 1; pruned by the already-read
   exclusion) and `User -> read_Book -> similar_Book` (length 2).
   Author / Subject hubs participate via the `similar_to` edges
   the data pipeline derives from shared author/subject (see
   `book_similar.csv`); 3-hop walks
   (`User -> read_Book -> Author -> candidate_Book`) are not
   enumerated because the heterogeneous KG saturates fast at that
   depth and `MAX_HOPS = 2` is the runtime sweet spot. The
   per-`(user, candidate)` typed-evidence counts
   (`path_count_via_author`, `_via_subject`) are *direct shared-
   entity joins* between the candidate and the user's read history
   (KPRN-style typed aggregation) rather than walks themselves;
   `path_count_via_kg_walk` is the actual count of
   walker-enumerated paths. The composite `path_count_total` feeds
   both the explanation-floor IC and the objective, so all three
   signals contribute to picks.

   The book-similarity input (`data/book_similar.csv`) is the
   *retrieval* artefact in production-recsys terms: the data
   pipeline ships one CC0-derived recipe (shared-author-OR-shared-
   subject), but customers swap it for any retrieval source -- a
   learned embedding's k-NN, a behavioural co-engagement matrix, a
   third-party recommendation API. The model treats it as input
   data; the upstream choice is independent of the slate-stage
   logic this template encodes.

3. **Prescriptive: MIP slate selection.** Decisions:
   `Candidate.pick in {0, 1}`. Constraints:
   - Cardinality: `count(pick) per user == K`.
   - Subject diversity: at most `MAX_PER_SUBJECT` picks per
     `(user, subject)`.
   - Author uniqueness: at most `MAX_PER_AUTHOR` per
     `(user, author)`.
   - Freshness floor: at least `FRESHNESS_FLOOR` items with
     `age_days <= FRESH_WINDOW_DAYS`.
   - Originals exposure floor: at least `ORIGINALS_FLOOR` in-house
     items.
   - Cold-start cap: at most `COLD_START_CAP` weakly-explained items
     (those with `path_count_total < WEAK_EXPLANATION_THRESHOLD`).
   - Explanation-path floor: total
     `path_count_total` (author + subject + KG-walk evidence) over
     the slate must be at least `EXPLANATION_FLOOR`.
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
book_slate_recommendation/
├── data/
│   ├── fetch_open_library_slice.py    # CC0 slice fetcher
│   ├── users.csv
│   ├── books.csv
│   ├── authors.csv
│   ├── subjects.csv
│   ├── read.csv
│   ├── book_author.csv
│   ├── book_subject.csv
│   └── book_similar.csv
├── experiments/                       # author notes; safe to skip
├── book_slate_recommendation.py
├── pyproject.toml
└── README.md
```

Bibliographic data is sourced from Open Library
(<https://openlibrary.org/dev/docs/api>), released under CC0 (public
domain). Synthetic users and read events, plus the derived similar_to
edges, are generated deterministically by the fetch script.

## Customise this template

The first changes most users will make:

- **Scale the Open Library slice.** Re-run
  `python data/fetch_open_library_slice.py --size md|lg` to pull a
  larger CC0 slice (~250 / ~600 books). The fetch script is
  idempotent and caches API responses under `data/_cache/`.
  Two things to retune at larger sizes: (1) the
  `EXPLANATION_FLOOR` / `WEAK_EXPLANATION_THRESHOLD` constants in the
  runner are tuned for `sm`'s `path_count_total` distribution
  (range 2-12); larger slices produce much higher walk counts and
  these thresholds become trivially satisfied unless rescaled.
  (2) HiGHS `time_limit_sec=60` is comfortable at `sm` (~1k binary
  decisions); raise it for `lg` (~120k decisions × 8 ICs).
- **Retarget to e-commerce.** Replace `Book` with `Product`,
  `read` with `purchased`, `similar_to` with co-purchase. The
  template runs as a "frequently bought together" slate composer
  with category coverage, brand exclusivity, and price-tier mix.
- **Retarget to course slates / career paths.** Replace `Book` with
  `Course`, add prerequisite edges, run the LinkedIn-style
  Career-Explorer pattern with prerequisite respect and
  credit-hour caps.
- **Predictive-pillar variant.** Replace `Book.pagerank_score` with
  a learned GNN affinity score from PyRel's predictive reasoner.
  Same MIP, different scoring source.
- **LLM-grounded explanation surfacing.** Pipe each picked item's
  per-typed counts -- and, if extended, the top-N enumerated paths
  the walker found -- into an LLM call to render natural-language
  explanations grounded in KG facts, eliminating hallucination -- the
  2025 LLM+KG hybrid pattern (ItemRAG, Think-on-Graph, K-RagRec).
  Materialising the actual top paths (rather than just counts) is a
  small extension of the runner's final `inspect()`: select on
  `kg_paths(p_s)` joined to picked candidates and emit
  `p_s.nodes(...)` for the top few by `path_count_via_kg_walk`.
- **A/B candidate slate enumeration.**
  `solve("highs", solution_limit=K_alt)` returns K alternative slates
  for downstream A/B exposure or human-in-the-loop curation -- the
  production-deployed shape for editorial-review platforms (kids
  content, regulated regions).
- **Tighten or relax the constraint dials.** `MAX_PER_SUBJECT`,
  `MAX_PER_AUTHOR`, `FRESHNESS_FLOOR`, `ORIGINALS_FLOOR`,
  `COLD_START_CAP`, `EXPLANATION_FLOOR` are top-of-file constants.

## References

- Eksombatchai, Jindal, Liu, Liu, Sharma, Sugnet, Ulrich & Leskovec,
  *Pixie: A System for Recommending 3+ Billion Items to 200+ Million
  Users in Real-Time*, WWW 2018 --
  <https://cs.stanford.edu/people/jure/pubs/pixie-www18.pdf>.
- Wang, He, Cao, Liu & Chua, *KGAT: Knowledge Graph Attention Network
  for Recommendation*, KDD 2019 --
  <https://dl.acm.org/doi/10.1145/3292500.3330989>. Reference for
  MovieLens / Amazon-Book / Yelp-KG-style heterogeneous-KG recsys.
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
- *Open Library Developer API* (CC0) --
  <https://openlibrary.org/dev/docs/api>. Bibliographic catalogue
  used by the bundled slice; `data/fetch_open_library_slice.py`
  pulls deterministic cuts.
