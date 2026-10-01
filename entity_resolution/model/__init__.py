"""Entity-resolution model and loaded source facts."""

from .schema import CandidateMatch, Record, ResolvedParty, ReviewPair, model
from .source import (
    AUTO_MERGE,
    REVIEW_FLOOR,
    candidate_count,
    load_ground_truth,
    matches_df,
    record_ids,
    records_df,
    review_df,
)

__all__ = [
    "AUTO_MERGE",
    "REVIEW_FLOOR",
    "CandidateMatch",
    "Record",
    "ResolvedParty",
    "ReviewPair",
    "candidate_count",
    "load_ground_truth",
    "matches_df",
    "model",
    "record_ids",
    "records_df",
    "review_df",
]
