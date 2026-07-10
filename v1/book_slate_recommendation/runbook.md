# Runbook: Book Slate Recommendation — Multi-Reasoner Walkthrough

A reading-app team wants each user's top-3 book slate to be both relevant *and* explainable — every pick backed by a real connection through the catalog's knowledge graph (a shared author, a shared subject, or a similar book the user already read), not a black-box score. This chain counts those explanation paths over the knowledge graph, then runs an optimizer that assembles each user's slate to maximize weighted path support under diversity and explanation-quality rules. The graph evidence and the slate decision are different reasoners on one ontology.

## The chain

```
59 books, 25 users, a knowledge graph of authors / subjects / similar-books and a
150-row read history. The chain counts explanation paths from each user to each
candidate book, then picks each user's 3-book slate to maximize weighted, well-explained
support — OPTIMAL, every user gets an ordered, subject-diverse, fully-explained slate.

  ─────────────────────────────────────────────────────────────────
  STAGE 1  Graph        ──►  Candidate.path_count_total / triangle_count
                             For each (user, candidate book), count the
                             knowledge-graph paths connecting them (via
                             authors read, subjects read, similar books).
  ─────────────────────────────────────────────────────────────────
  STAGE 2  Prescriptive ──►  Candidate.slot   (each user's K=3 slate)
                             Maximize sum((K+1-slot) x path_count_total);
                             subject diversity + an explanation floor +
                             cold-start handling. OPTIMAL, one ordered slate per user.
  ─────────────────────────────────────────────────────────────────
```

## Workflow

> **How to use this walkthrough.** Each section below is a Prompt that an analyst pastes into a fresh agent session loaded with the named `/rai-*` skill. Prompts are designed to run **in order, in a single session** — every step relies on enrichments the previous steps wrote back to the shared ontology, so the agent inherits accumulated model state across prompts.

### 1. Build ontology

**Prompt**

```
/rai-ontology Build an ontology from the data/ CSVs: books, authors, subjects, users, the read history (which user read which book, with a rating), and the knowledge-graph edges — book_author (a book's authors), book_subject (a book's subjects), and book_similar (books similar to a book). Model these as relationships so a book connects to its authors, subjects, similar books, and readers.
```

**Response**

Loads `Book` (59), `Author` (52), `Subject` (12), `User` (25), a 150-row read history, and the knowledge-graph edges (71 book-author, 128 book-subject, 400 book-similar) — a catalog knowledge graph linking users to books through what they've read and how books relate.

### 2. Examine ontology

**Prompt**

```
/rai-pyrel What concepts and relationships does the ontology have, and how many rows are in each?
```

**Response**

Concepts: 59 `Book`, 52 `Author`, 12 `Subject`, 25 `User`, connected by the read history (150) and the author/subject/similar edges (71 / 128 / 400). Each user has read a handful of books, giving the graph entry points for recommendations.

### 3. Discover reasoner questions

**Prompt**

```
/rai-discovery We want each user's top-3 book recommendations to be explainable — backed by knowledge-graph paths through shared authors, subjects, or similar books — and diverse. How should we break this down?
```

**Response**

Routes to a graph step (count the explanation paths from each user to each candidate book) feeding a prescriptive step (pick each user's slate to maximize well-explained support under diversity and quality rules).

### 4. Count explanation paths

**Prompt**

```
/rai-graph-analysis For each user and each unread candidate book, count the knowledge-graph paths that connect them — through an author of a book they read, a subject of a book they read, and books similar to ones they read. Persist the total path count per candidate (and the triangle count) so the recommender can weight by explanation strength.
```

**Response**

For every (user, unread book) candidate, the connecting paths are counted across the author, subject, and similar-book routes and persisted as `Candidate.path_count_total` (with `triangle_count`). Books with more independent paths to a user's history score as better-explained candidates; books below a weak-explanation threshold are treated as cold-start.

### 5. Assemble each user's slate

**Prompt**

```
/rai-prescriptive-problem For each user, pick an ordered 3-book slate (slots 1–3) to maximize weighted explanation support — sum of (4 − slot) times the candidate's path count, so stronger picks go in higher slots — while keeping the slate subject-diverse and meeting a minimum total explanation floor. Persist each user's chosen books and slots.
```

**Response**

OPTIMAL — all 25 users get an ordered 3-book slate (`Candidate.slot`) that maximizes high-slot path support subject to subject diversity and the per-user explanation floor; the chosen books and slots are written back. (The objective value depends on how explanation paths are counted and where the diversity grain and explanation floor are set — and a near-ubiquitous subject may force the diversity rule onto each book's primary subject to stay feasible — so the exact total varies with those modeling choices. What's stable: every user receives a full, subject-diverse, ordered slate that clears the floor, each pick backed by concrete graph paths.)

### 6. Read the slates

**Prompt**

```
/rai-prescriptive-results What does each user's slate look like, and how is each pick explained?

```

**Response**

Each user has a 3-book slate ordered by explanation strength, every pick backed by its path support broken out by route — paths via a shared author, via a shared subject, and via similar books already read. The subject-diversity rule keeps a slate from being three books on one topic, and the explanation floor keeps weakly-connected (cold-start) books out unless nothing better connects — so every recommendation comes with a concrete, queryable "why."

## Data

Bundled CSVs in `data/`: 59 books, 52 authors, 12 subjects, 25 users, 150 reads, plus the author/subject/similar knowledge-graph edges. The slate size (K=3), explanation floor, and cold-start threshold are constants in the script. Full chain in `book_slate_recommendation.py`.
