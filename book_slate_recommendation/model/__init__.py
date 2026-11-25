"""Book slate recommendation (Graph + Prescriptive CSP) template: the model.

Multi-reasoner pipeline that picks K books per reader AND orders
them by slate position. Slot 1 is hero (top of row); position-decay
engagement is the canonical recsys model, so the order matters as
much as the selection. The architectural centerpiece is bounded
heterogeneous-KG walks via the PyRel path library
(``relationalai.semantics.std.path``): the walks generate the
Candidate concept and the per-(user, candidate) explanation
evidence that feeds the Prescriptive reasoner. The Graph
reasoner separately contributes per-Book ``triangle_count``
over the similarity graph, which the hero-pin IC ties to slot
1 so the highest-engagement position carries graph-derived
structural quality:

- Bounded KG walks (path library, central):
  ``model.path(user, Item.connected_to.repeat(1, 2), book)`` matches
  ``User -> read_Book`` walks (length 1; pruned downstream by the
  already-read exclusion) and ``User -> read_Book -> similar_Book``
  walks (length 2). Each user and book joined by a walk
  (``.exists()``) becomes a ``Candidate``. The per-(user, candidate)
  typed counts (``path_count_via_author``, ``_via_subject``,
  ``_via_kg_walk``, the last from ``.all().count()``) feed the
  engagement-weighted explanation floor and objective, and surface
  as the per-pick explanation block.
- Graph reasoner (hero pin): triangle count over ``Book.similar_to``
  per Book. Drives ``hero_pin_ic`` -- slot 1 (top of row) must come
  from the densely-embedded subset, so the most-impressed position
  carries graph-derived structural quality. Stronger than a "floor
  somewhere in the slate": it concentrates the Graph signal at the
  slot that matters most for engagement.
- Prescriptive reasoner: pure-integer CSP on MiniZinc decides each
  Candidate's slot in {1, ..., K, K+1}, where slot K+1 means
  unpicked. Constraints: cardinality, slot uniqueness, already-read
  exclusion, author uniqueness, subject concentration cap,
  freshness, originals-exposure, cold-start, hero pin, and
  explanation-path floor. Objective maximizes total position-
  weighted path support ``sum((K + 1 - slot) * path_count_total)``
  -- top slots dominate, unpicked candidates contribute zero.

Bundled data: a deterministic Open Library (CC0) slice (~59 books,
~52 authors, 12 subjects) pulled by ``data/fetch_open_library_slice.py``.
Customers fetch larger slices by re-running with ``--size md``/``--size lg``.

Modules, one per stage (each module imports the modules whose
declarations it reads):

- ``candidate_paths.py``: the bounded KG walks, the candidates they reach,
  their explanation path counts, and which candidates are already read.
- ``book_embeddedness.py``: the triangle count of each book over the
  similarity graph.
- ``slate_selection.py``: the slot constraint program, its status and
  objective, and each user's slate of picks.

Run:
    `rai models deploy --path model` deploys this package to the schemas in
    raiconfig.yaml and waits for its first refresh, which runs the solve.
    `python -m queries.slate_report` then prints the report from the deployed
    model.
"""

from .candidate_paths import MAX_HOPS, Candidate
from .schema import Author, Book, Subject, User, model
from .slate_selection import (
    COLD_START_CAP,
    EXPLANATION_FLOOR,
    FRESH_WINDOW_DAYS,
    FRESHNESS_FLOOR,
    HERO_EMBEDDEDNESS_THRESHOLD,
    MAX_PER_SUBJECT,
    ORIGINALS_FLOOR,
    SLATE_SIZE_K,
    WEAK_EXPLANATION_THRESHOLD,
    Slate,
    SolveStatus,
    TotalSupport,
    problem,
)
from .source import DATA_DIR

__all__ = [
    "COLD_START_CAP",
    "DATA_DIR",
    "EXPLANATION_FLOOR",
    "FRESHNESS_FLOOR",
    "FRESH_WINDOW_DAYS",
    "HERO_EMBEDDEDNESS_THRESHOLD",
    "MAX_HOPS",
    "MAX_PER_SUBJECT",
    "ORIGINALS_FLOOR",
    "SLATE_SIZE_K",
    "WEAK_EXPLANATION_THRESHOLD",
    "Author",
    "Book",
    "Candidate",
    "Slate",
    "SolveStatus",
    "Subject",
    "TotalSupport",
    "User",
    "model",
    "problem",
]
