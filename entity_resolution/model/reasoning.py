"""Graph, rules-based, and prescriptive reasoning for entity resolution.

Resolution is the step that makes the downstream reasoning correct. An insurer's
policyholder records are scattered across policy systems (auto, home, life) and
an acquired book, so the same insured looks like several customers -- and their
combined exposure to the carrier is invisible until the records are resolved.
`model/source.py` normalizes, blocks, and scores candidate pairs into two bands --
AUTO_MERGE (merge automatically) and REVIEW (held for a steward). This module
declares the reasoning over them:

- Stage 1 -- Graph: weakly-connected-components over the auto-merged match edges
  clusters records into one insured party, closing transitive chains.
- Stage 2 -- Rules-based: confidence tiers on matches, a duplicate flag, and the
  payoff -- total exposure per resolved party and an accumulation-limit breach
  flag. At the record level no policy looks dangerous; resolved, households breach.
- Stage 3 -- Prescriptive: with a finite reinsurance budget, choose which breached
  households to cede to reinsurance (a knapsack) to transfer the most excess
  exposure off the book. Each refresh of the deployed model runs the solve.

`queries/resolution_report.py` prints Stage 4 from the deployed model: the
record-level vs resolved-level contrast, the review queue (and the breach it still
hides), the cession plan, and pairwise precision / recall / F1.
"""

from relationalai.semantics import Float, String
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.std import aggregates

from .schema import CandidateMatch, Record, ResolvedParty, model

HIGH_TIER = 0.90

ACCUMULATION_LIMIT = 1_000_000.0
REINSURANCE_RATE = 0.12
REINSURANCE_BUDGET = 120_000.0


def cluster_accepted_matches():
    """Cluster records connected by accepted match edges."""
    graph = Graph(model, directed=False, weighted=False, node_concept=Record)

    match_ref = CandidateMatch.ref()
    rec_a, rec_b = Record.ref(), Record.ref()
    model.where(match_ref.rec_a == rec_a, match_ref.rec_b == rec_b).define(
        graph.Edge.new(src=rec_a, dst=rec_b)
    )

    graph.Node.entity_id = graph.weakly_connected_component()

    rep_node = Record.ref()
    model.where(Record.entity_id == rep_node).define(
        Record.entity_key(rep_node.record_id)
    )

    return graph.num_nodes(), graph.num_edges()


def derive_exposure_and_breaches() -> None:
    """Derive match tiers, resolved membership, exposure, and breaches."""
    model.define(CandidateMatch.confidence_tier("HIGH")).where(
        CandidateMatch.score >= HIGH_TIER
    )
    model.define(CandidateMatch.confidence_tier("MEDIUM")).where(
        CandidateMatch.score < HIGH_TIER
    )

    records_per_entity = aggregates.count(Record).per(Record.entity_key)
    model.define(Record.is_duplicate(Record)).where(records_per_entity >= 2)

    model.define(ResolvedParty.new(key=Record.entity_key))
    record, party = Record.ref(), ResolvedParty.ref()
    model.where(record.entity_key == party.key).define(
        record.resolved_party(party)
    )

    party_record = Record.ref()
    model.where(party_record.entity_key == ResolvedParty.key).define(
        ResolvedParty.total_exposure(
            aggregates.sum(party_record.coverage_amount).per(ResolvedParty)
        )
    )
    model.define(ResolvedParty.is_over_limit(ResolvedParty)).where(
        ResolvedParty.total_exposure > ACCUMULATION_LIMIT
    )
    model.where(ResolvedParty.total_exposure > ACCUMULATION_LIMIT).define(
        ResolvedParty.excess(
            ResolvedParty.total_exposure - ACCUMULATION_LIMIT
        )
    )
    model.define(
        ResolvedParty.premium(ResolvedParty.excess * REINSURANCE_RATE)
    )


def choose_reinsurance_cessions():
    """Declare the reinsurance-budget knapsack for breached parties."""
    problem = Problem(model, Float)
    problem.solve_for(
        ResolvedParty.cede,
        where=[ResolvedParty.is_over_limit()],
        name=["cede", ResolvedParty.key],
        type="bin",
        lower=0.0,
        upper=1.0,
    )
    problem.satisfy(
        model.require(
            aggregates.sum(
                ResolvedParty.premium * ResolvedParty.cede
            )
            <= REINSURANCE_BUDGET
        ),
        name=["reinsurance_budget"],
    )
    problem.maximize(
        aggregates.sum(ResolvedParty.excess * ResolvedParty.cede)
    )
    problem.configure("highs", time_limit_sec=60)
    return problem


num_nodes, num_edges = cluster_accepted_matches()
derive_exposure_and_breaches()
problem = choose_reinsurance_cessions()

# The solve's status, published through the model's own relationship.
SolveStatus = model.Relationship(f"reinsurance solve status is {String:status}")
model.define(SolveStatus(problem.termination_status()))
