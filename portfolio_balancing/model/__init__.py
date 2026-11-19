"""Portfolio Balancing -- multi-reasoner (rules + graph + prescriptive) template: the model.

Four-stage pipeline on a single shared ontology:
- Stage 1 -- Rules: derived flags on existing portfolio data (overconcentrated
  holdings, sector concentration, high-risk traders).
- Stage 2 -- Graph: correlation graph over stocks + Louvain clustering,
  then per-cluster representative selection by highest Sharpe. Collapses
  redundant bets before the optimizer sees them.
- Stage 3 -- Prescriptive: bi-objective QP via epsilon constraint on the
  representative-only universe. Position and sector limits apply; non-reps
  are forced to zero. Budget x regime as Scenario Concept so all
  combinations solve in one call.
- Stage 4 -- Crisis stress: compare base vs crisis frontiers. Crisis
  covariance via PSD-preserving correlation shrinkage, derived in PyRel.

Volatility, correlation, and regime covariance are all PyRel derived
properties on Stock -- no numpy precomputation -- so the ontology is the
single source of truth for every solver input.

Every solve is a named Problem in the model. The anchors come first; the epsilon-constraint
targets of the grid, adaptive, and dichotomic drivers are rules over earlier solves' results
(values and shadow prices), so one refresh runs the whole sensitivity-guided frontier. Each
solve publishes its status and a FrontierPoint per scenario.

Run:
    `rai models deploy --path model` deploys this package to the schemas in
    raiconfig.yaml and waits for its first refresh, which runs the rules, the graph,
    and the solves. `python -m queries.portfolio_report` prints the report from the
    deployed model.

Output:
    Stage 1: compliance violations.
    Stage 2: cluster count/sizes, intra- vs inter-cluster avg correlation.
    Stage 3: anchor solves, then a sensitivity-guided frontier -- three drivers
        (grid / adaptive / dichotomic) compared by approximation quality, plus a
        shadow-price-vs-secant table showing each dual equals the frontier slope.
    Stage 4: per-scenario efficient frontier with exact dual marginals and knee,
        then a base-vs-crisis volatility table per frontier point.
"""

from .reasoning import (
    ADAPTIVE_SOLVES,
    CORR_THRESHOLD,
    CRISIS_ALPHA,
    DICHOTOMIC_SOLVES,
    GRID_SOLVES,
    N_SOLVES,
    POSITION_LIMIT,
    REFERENCE_SCENARIO,
    SECTOR_LIMIT,
    SolveStatus,
)
from .schema import (
    Account,
    FrontierPoint,
    Holding,
    Regime,
    Scenario,
    Sector,
    Stock,
    Transaction,
    User,
    model,
)
from .source import DATA_DIR

__all__ = [
    "ADAPTIVE_SOLVES",
    "CORR_THRESHOLD",
    "CRISIS_ALPHA",
    "DATA_DIR",
    "DICHOTOMIC_SOLVES",
    "GRID_SOLVES",
    "N_SOLVES",
    "POSITION_LIMIT",
    "REFERENCE_SCENARIO",
    "SECTOR_LIMIT",
    "Account",
    "FrontierPoint",
    "Holding",
    "Regime",
    "Scenario",
    "Sector",
    "SolveStatus",
    "Stock",
    "Transaction",
    "User",
    "model",
]
