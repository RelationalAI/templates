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

Modules: `compliance_flags.py` (Stage 1), `correlation_clusters.py` (Stage 2),
`regime_covariance.py` (the base and crisis covariance), `efficient_frontier.py` (Stage 3,
the solves and the frontier points they publish), and `crisis_volatility.py` (Stage 4,
the base-versus-crisis volatility of each frontier point). Each module imports the modules
whose declarations it reads.

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

from . import crisis_volatility
from .compliance_flags import POSITION_LIMIT, SECTOR_LIMIT, SectorExposure
from .correlation_clusters import (
    CORR_THRESHOLD,
    Cluster,
    inter_cluster_correlation,
    intra_cluster_correlation,
    num_clusters,
    num_edges,
    num_representatives,
    num_stocks,
)
from .efficient_frontier import (
    ADAPTIVE_SOLVES,
    DICHOTOMIC_SOLVES,
    GRID_SOLVES,
    N_SOLVES,
    REFERENCE_SCENARIO,
    SolveStatus,
)
from .regime_covariance import CRISIS_ALPHA
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
    "Cluster",
    "FrontierPoint",
    "Holding",
    "Regime",
    "Scenario",
    "Sector",
    "SectorExposure",
    "SolveStatus",
    "Stock",
    "Transaction",
    "User",
    "crisis_volatility",
    "inter_cluster_correlation",
    "intra_cluster_correlation",
    "model",
    "num_clusters",
    "num_edges",
    "num_representatives",
    "num_stocks",
]
