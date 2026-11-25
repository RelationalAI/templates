"""Entity-resolution model: loaded source facts and the reasoning over them.

`rai models deploy --path model` deploys everything this package declares. The stages live in five
modules, each of which imports the modules whose declarations it reads:
  1. Graph        -- weakly connected components over the accepted match edges cluster records
                     into insured parties (`match_graph.py`).
  2. Rules        -- confidence tiers, band sizes, and the blocking reduction (`match_bands.py`);
                     each party's records, golden record, total exposure, and accumulation-limit
                     breach (`resolved_parties.py`); the breaches confirming the review queue
                     would surface (`review_queue.py`).
  3. Prescriptive -- which breached parties to cede to reinsurance within the premium budget
                     (`reinsurance_cessions.py`).

`model/source.py` normalizes, blocks, and scores candidate pairs into the auto-merge and review
bands; `queries/resolution_report.py` prints the report from the deployed model.
"""

from .match_bands import (
    comparison_reduction,
    num_all_pairs,
    num_auto_merges,
    num_review_pairs,
)
from .match_graph import num_edges, num_nodes
from .reinsurance_cessions import (
    REINSURANCE_BUDGET,
    SolveStatus,
    ceded_excess,
    ceded_premium,
    problem,
)
from .resolved_parties import (
    ACCUMULATION_LIMIT,
    REINSURANCE_RATE,
    num_parties,
    num_party_breaches,
    num_record_breaches,
)
from .review_queue import num_confirmed_breaches, num_surfaced_breaches
from .schema import CandidateMatch, CandidatePairCount, Record, ResolvedParty, ReviewPair, model
from .source import AUTO_MERGE, REVIEW_FLOOR, load_ground_truth

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
    "ceded_excess",
    "ceded_premium",
    "comparison_reduction",
    "load_ground_truth",
    "model",
    "num_all_pairs",
    "num_auto_merges",
    "num_confirmed_breaches",
    "num_edges",
    "num_nodes",
    "num_parties",
    "num_party_breaches",
    "num_record_breaches",
    "num_review_pairs",
    "num_surfaced_breaches",
    "problem",
]
