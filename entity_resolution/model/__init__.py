"""Entity-resolution model: loaded source facts and the reasoning over them.

`rai models deploy --path model` deploys everything this package declares.
"""

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

# isort: split
# The reasoning declares rules over the facts loaded above.
from .reasoning import (
    ACCUMULATION_LIMIT,
    REINSURANCE_BUDGET,
    REINSURANCE_RATE,
    SolveStatus,
    num_edges,
    num_nodes,
    problem,
)

__all__ = [
    "ACCUMULATION_LIMIT",
    "AUTO_MERGE",
    "REINSURANCE_BUDGET",
    "REINSURANCE_RATE",
    "REVIEW_FLOOR",
    "CandidateMatch",
    "Record",
    "ResolvedParty",
    "ReviewPair",
    "SolveStatus",
    "candidate_count",
    "load_ground_truth",
    "matches_df",
    "model",
    "num_edges",
    "num_nodes",
    "problem",
    "record_ids",
    "records_df",
    "review_df",
]
