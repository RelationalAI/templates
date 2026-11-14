"""Warehouse Allocation (chained graph + prescriptive reasoning) template: the model.

This package demonstrates chaining two reasoner types in RelationalAI:

Stage 1 -- Graph Analysis:
  - Build a distribution network graph from warehouse sites and routes.
  - Run eigenvector centrality to identify critical hub warehouses.
  - Run weakly-connected-components to surface network fragmentation.
  - Detect bridge routes that connect distinct regions.
  - Centrality scores and structural flags are stored as properties on the
    Site / Route concepts.

Stage 2 -- Prescriptive Optimization:
  - Allocate inventory budget across sites to minimize holding cost.
  - Use centrality scores from Stage 1 to ensure critical hubs receive
    adequate stock (minimum allocation proportional to centrality).
  - Satisfy demand at each site.

The key pattern: the graph reasoner enriches the ontology with derived
properties that the prescriptive reasoner references directly -- no manual
data transfer between stages.

Run:
    `rai models deploy --path model` deploys this package to the schemas in
    raiconfig.yaml and waits for its first refresh, which runs the graph analysis
    and the solve. `python -m queries.allocation_report` then prints the report
    from the deployed model.
"""

from .reasoning import SolveStatus, TotalHoldingCost, graph, problem, wcc
from .schema import Demand, Route, Site, model
from .source import DATA_DIR

__all__ = [
    "DATA_DIR",
    "Demand",
    "Route",
    "Site",
    "SolveStatus",
    "TotalHoldingCost",
    "graph",
    "model",
    "problem",
    "wcc",
]
