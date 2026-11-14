"""Energy grid planning (multi-reasoner) template: the model.

This package demonstrates a five-stage multi-reasoner pipeline in RelationalAI,
combining forecast enrichment, graph analysis, path-based corridor fragility,
rules-based compliance, and prescriptive optimization on a single shared ontology:

- Stage 1 -- Forecast: read the demand_forecasts CSV and enrich each Substation
  with a predicted_load property consumed by downstream stages.
- Stage 2 -- Graph: compute weakly connected components, Louvain community
  detection, and multi-metric centrality (betweenness, degree, eigenvector) on
  the transmission grid topology. Results are stored directly as Substation
  properties on the shared ontology.
- Stage 3 -- Paths (PREVIEW, relationalai>=1.15): enumerate generator-sub ->
  DC-sub transmission corridors, rank each by Stage 2 betweenness summed along
  the route (most fragile = greatest through-traffic exposure), and re-enumerate
  with the highest-betweenness substation offline. Persists Substation.fragility_load.
- Stage 4 -- Rules: declarative interconnection queue compliance checks
  (capacity, structural criticality, low-carbon mandate) that consume Stage 1
  and 2 enrichments.
- Stage 5 -- Prescriptive: joint DC approval + grid upgrade optimization using
  InvestmentLevel as a Scenario Concept. One solve across 5 budget levels
  produces a Pareto frontier with results queryable directly from the ontology.

Run:
    `rai models deploy --path model` deploys this package to the schemas in
    raiconfig.yaml and waits for its first refresh, which runs the graph analysis,
    the corridor search, and the solve. `python -m queries.energy_grid_report` then
    prints the report from the deployed model.
"""

from .reasoning import (
    CRITICAL_THRESHOLD,
    MAX_CORRIDOR_HOPS,
    SolveObjective,
    SolveStatus,
    corridor,
)
from .schema import (
    DataCenterRequest,
    DemandForecast,
    InvestmentLevel,
    InvestmentPortfolio,
    Substation,
    SubstationUpgrade,
    model,
)
from .source import DATA_DIR

__all__ = [
    "CRITICAL_THRESHOLD",
    "DATA_DIR",
    "MAX_CORRIDOR_HOPS",
    "DataCenterRequest",
    "DemandForecast",
    "InvestmentLevel",
    "InvestmentPortfolio",
    "SolveObjective",
    "SolveStatus",
    "Substation",
    "SubstationUpgrade",
    "corridor",
    "model",
]
