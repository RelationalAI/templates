"""Slate selection: the constraint program that assigns each candidate a slot, the solve's status and
objective, and each reader's resulting slate."""

from relationalai.semantics import Integer, String, count, std, sum
from relationalai.semantics.reasoners.prescriptive import Problem

# Declares Book.triangle_count, the structural-embeddedness measure the hero pin reads.
from . import book_embeddedness  # noqa: F401
from .candidate_paths import Candidate
from .schema import Author, Book, Slot, Subject, User, model

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

# Slate size: the K of "row of K things". Tune to taste.
SLATE_SIZE_K = 3

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
# This is the Graph reasoner's hold on the slate -- pinning a graph-
# derived structural-density measure to the highest-engagement
# position. Tuned for the bundled slice where per-book triangle
# counts range 0-107 with two isolates; threshold of 4 keeps the
# truly-isolated books out of the hero slot. Retune to the data's
# distribution after rescaling.
HERO_EMBEDDEDNESS_THRESHOLD = 4

# --------------------------------------------------
# Stage 2: Prescriptive reasoner -- CSP slate selection (MiniZinc)
#
# Decision: ``Candidate.slot`` ∈ {1, 2, ..., K, K+1}. Slot 1..K are
# slate positions (1 = top of row); slot K+1 is the unpicked sentinel.
# The K+1 encoding lets the position-weighted objective and
# explanation floor use the simple coefficient ``(K + 1 - slot)``,
# which is 0 at slot K+1 -- no auxiliary picked/unpicked indicator.
# --------------------------------------------------

Candidate.slot = model.Property(f"{Candidate} is at slate slot {Integer:s}")

problem = Problem(model, Integer, name="book_slate_recommendation")
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
# because those iterate over data rows. Every per-group IC below names
# its group keys (``Candidate.user_id``, plus ``Slot``, ``Author`` or
# ``Subject``) in the ``where`` clause: that clause is what gives the
# constraint one instance per group.
slate_size_ic = model.where(Candidate.user_id).require(
    count(Candidate, Candidate.slot <= SLATE_SIZE_K).per(Candidate.user_id) == SLATE_SIZE_K
)
problem.satisfy(slate_size_ic)

# Slot positions 1..K. The Slot concept exists so the slot-uniqueness IC
# counts distinct slot Concept values (the social_golfer idiom) rather
# than distinct anonymous Integer values. K+1 is the unpicked sentinel
# and is intentionally not a Slot row -- only filled positions are
# counted.
model.define(Slot.new(pos=std.common.range(1, SLATE_SIZE_K + 1)))

# Slot uniqueness: at most one Candidate per (user, slot position).
# Counts Candidates whose slot decision equals each Slot's pos, per
# (user, Slot). Combined with slate_size_ic (K picks per user) and
# the slot domain {1..K+1}, this is a bijection between picks and
# positions 1..K. Per-pair count cap is the CSP-native shape for
# all-different over decision variables once you also pin the
# total-pick count.
slot_uniqueness_ic = model.where(Candidate.user_id, Slot).require(
    count(Candidate, Candidate.slot == Slot.pos).per(Candidate.user_id, Slot) <= 1
)
problem.satisfy(slot_uniqueness_ic)

# Already-read exclusion: any (user, book) where the user has already
# read the book must have ``slot == K+1`` (unpicked). Lands at the
# prescriptive layer rather than as a pre-pruning filter on Candidate
# derivation: Candidate stays the full reachable set, and the cost is a
# few wasted integer variables forced to the unpicked sentinel.
exclude_read_ic = model.where(Candidate.is_read()).require(Candidate.slot == SLATE_SIZE_K + 1)
problem.satisfy(exclude_read_ic)

# Author uniqueness: at most one picked Candidate per (user, Author).
# GCC-style per-pair count cap: no two picks share an author (a book
# can have several authors). Per-pair caps are PyRel's CSP-
# native shape for "no value repeats more than X times across
# decisions" -- the same shape ``slot_uniqueness_ic`` uses to keep
# slot positions unique.
author_uniqueness_ic = model.where(
    Book.id == Candidate.book_id,
    Book.written_by(Book, Author),
    Candidate.user_id,
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
    Candidate.user_id,
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
    Candidate.user_id,
).require(
    count(Candidate, Candidate.slot <= SLATE_SIZE_K).per(Candidate.user_id) >= FRESHNESS_FLOOR
)
problem.satisfy(freshness_ic)

# Originals exposure floor: at least ORIGINALS_FLOOR in-house items.
originals_ic = model.where(
    Book.id == Candidate.book_id,
    Book.in_house == 1,
    Candidate.user_id,
).require(
    count(Candidate, Candidate.slot <= SLATE_SIZE_K).per(Candidate.user_id) >= ORIGINALS_FLOOR
)
problem.satisfy(originals_ic)

# Cold-start cap: at most COLD_START_CAP weakly-explained picks.
cold_start_ic = model.where(
    Candidate.path_count_total < WEAK_EXPLANATION_THRESHOLD,
    Candidate.user_id,
).require(count(Candidate, Candidate.slot <= SLATE_SIZE_K).per(Candidate.user_id) <= COLD_START_CAP)
problem.satisfy(cold_start_ic)

# Hero pin: slot 1 (top of row) must come from a Book with
# triangle_count >= HERO_EMBEDDEDNESS_THRESHOLD. Counts the
# eligible-and-at-slot-1 Candidates per user; combined with
# slot_uniqueness_ic (exactly one Candidate at slot 1 per user),
# >= 1 forces the slot-1 Candidate to be eligible. This is the
# Graph reasoner's hold on the slate, tied to the highest-engagement
# position rather than a "somewhere in the slate" floor.
hero_pin_ic = model.where(
    Book.id == Candidate.book_id,
    Book.triangle_count >= HERO_EMBEDDEDNESS_THRESHOLD,
    Candidate.user_id,
).require(count(Candidate, Candidate.slot == 1).per(Candidate.user_id) >= 1)
problem.satisfy(hero_pin_ic)

# Explanation floor: each user's slate must carry enough cumulative
# position-weighted KG-path evidence over picked items. The
# ``(K + 1 - slot)`` weight is K at slot 1 (hero), 1 at slot K, and
# 0 at slot K+1 (unpicked) -- so the sum naturally restricts to
# picked items without needing an indicator multiplier. Top picks
# count more, matching the engagement-decay model the objective
# also encodes.
explanation_ic = model.where(Candidate.user_id).require(
    sum((SLATE_SIZE_K + 1 - Candidate.slot) * Candidate.path_count_total).per(Candidate.user_id)
    >= EXPLANATION_FLOOR
)
problem.satisfy(explanation_ic)

# Position-weighted objective: maximize total engagement-weighted
# path support. ``(K + 1 - slot)`` is K at slot 1 (hero), 1 at slot
# K (bottom), 0 at slot K+1 (unpicked). The solver places highest-
# path-support Candidates at slot 1 because the weight is largest
# there, matching the canonical recsys position-decay engagement
# model.
problem.maximize(sum((SLATE_SIZE_K + 1 - Candidate.slot) * Candidate.path_count_total))

# --------------------------------------------------
# Configure the solve
# --------------------------------------------------

# Each refresh of the deployed model runs this solve.
problem.configure("minizinc", time_limit_sec=180)

# The solve's status and objective, which the deployed model publishes for the queries.
SolveStatus = model.Relationship(f"slate solve status is {String:status}")
TotalSupport = model.Relationship(f"slate total position-weighted path support is {Integer:support}")
model.define(SolveStatus(problem.termination_status()), TotalSupport(problem.objective_value()))

# --------------------------------------------------
# The slate: each user's picked candidates and the subjects they cover
# --------------------------------------------------

# Values computed from the solution live on Slate, not Candidate: such a
# property on the concept the solve reads fails the deploy. A user's picks are the
# candidates in slots 1..K.
Slate = model.Concept("Slate", identify_by={"user_id": Integer})
Slate.picks = model.Relationship(f"{Slate} picks {Candidate}")
model.define(Slate.new(user_id=User.id))
model.where(
    Slate.user_id == Candidate.user_id,
    Candidate.slot <= SLATE_SIZE_K,
).define(Slate.picks(Candidate))

# Picks per subject: a book counts toward every subject it is about.
Slate.picks_by_subject = model.Relationship(
    f"{Slate} has {Integer:n_picked} picks on subject {Subject:subject}"
)
picked_subject = Subject.ref()
model.where(
    Slate.picks(Candidate),
    Book.id == Candidate.book_id,
    Book.about(Book, picked_subject),
).define(Slate.picks_by_subject(count(Candidate).per(Slate, picked_subject), picked_subject))
