"""Reinsurance cessions: the knapsack that chooses which breached parties to cede within the premium
budget, the solve's status, and the excess exposure and premium the plan cedes."""

from relationalai.semantics import Float, String
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.std import aggregates as aggs

# Declares the over-limit flag, excess, and premium the decision reads.
from . import resolved_parties  # noqa: F401
from .schema import ResolvedParty, model

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

REINSURANCE_BUDGET = 120_000.0

# The reinsurance-budget knapsack for breached parties.
problem = Problem(model, Float, name="entity_resolution")
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
        aggs.sum(
            ResolvedParty.premium * ResolvedParty.cede
        )
        <= REINSURANCE_BUDGET
    ),
    name=["reinsurance_budget"],
)
problem.maximize(
    aggs.sum(ResolvedParty.excess * ResolvedParty.cede)
)
problem.configure("highs", time_limit_sec=60)

# The solve's status, which the deployed model publishes for the queries.
SolveStatus = model.Relationship(f"reinsurance solve status is {String:status}")
model.define(SolveStatus(problem.termination_status()))

# The excess exposure and premium of the ceded parties (zero for an empty plan). They are
# nullary relationships: a property computed from the solution on ResolvedParty would fail
# the deploy.
ceded_excess = model.Relationship(f"the cession plan cedes {Float:excess} of excess exposure")
ceded_premium = model.Relationship(f"the cession plan pays {Float:premium} of premium")
_ceded = ResolvedParty.cede > 0.5
model.define(
    ceded_excess(aggs.sum(ResolvedParty, ResolvedParty.excess).where(_ceded) | 0.0),
    ceded_premium(aggs.sum(ResolvedParty, ResolvedParty.premium).where(_ceded) | 0.0),
)
