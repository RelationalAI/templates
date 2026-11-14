"""Entity-resolution model: loaded source facts and the reasoning over them.

`rai models deploy --path model` deploys everything this package declares.
"""

from .schema import CandidateMatch, CandidatePairCount, Record, ResolvedParty, ReviewPair, model
from .source import AUTO_MERGE, REVIEW_FLOOR, load_ground_truth

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
    "CandidatePairCount",
    "Record",
    "ResolvedParty",
    "ReviewPair",
    "SolveStatus",
    "load_ground_truth",
    "model",
    "num_edges",
    "num_nodes",
    "problem",
]
