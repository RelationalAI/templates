"""Match bands: each accepted match's confidence tier, how many pairs land in the auto-merge and
review bands, and how far blocking cuts the number of record pairs compared."""

from relationalai.semantics import Float, Integer
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std import floats

from .schema import CandidateMatch, CandidatePairCount, Record, ReviewPair, model

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

# An accepted match scoring at or above this is HIGH confidence, below it MEDIUM.
HIGH_TIER = 0.90

# --------------------------------------------------
# Confidence tiers of the accepted matches
# --------------------------------------------------

model.define(CandidateMatch.confidence_tier("HIGH")).where(
    CandidateMatch.score >= HIGH_TIER
)
model.define(CandidateMatch.confidence_tier("MEDIUM")).where(
    CandidateMatch.score < HIGH_TIER
)

# --------------------------------------------------
# Band sizes and the blocking reduction
# --------------------------------------------------

# Pairs in the auto-merge band (accepted matches) and in the review band.
num_auto_merges = model.Relationship(f"auto-merge accepted {Integer:n_matches} pairs")
num_review_pairs = model.Relationship(f"the review band holds {Integer:n_pairs} pairs")
model.define(
    num_auto_merges(aggs.count(CandidateMatch) | 0),
    num_review_pairs(aggs.count(ReviewPair) | 0),
)

# Every unordered pair of records, and the share of those comparisons that
# blocking avoids.
num_all_pairs = model.Relationship(f"there are {Integer:n_pairs} possible record pairs")
_n_records = Integer.ref()
model.where(_n_records == aggs.count(Record)).define(
    num_all_pairs(_n_records * (_n_records - 1) // 2)
)
comparison_reduction = model.Relationship(
    f"blocking avoids {Float:reduction} of the possible comparisons"
)
_candidates, _possible = Integer.ref(), Integer.ref()
model.where(CandidatePairCount(_candidates), num_all_pairs(_possible)).define(
    comparison_reduction(1 - floats.float(_candidates) / floats.float(_possible))
)
