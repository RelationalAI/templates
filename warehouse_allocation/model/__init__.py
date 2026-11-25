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

The graph stage is `network_analysis.py` and the prescriptive stage is
`inventory_allocation.py`, which imports the module whose centrality it reads.

Run:
    `rai models deploy --path model` deploys this package to the schemas in
    raiconfig.yaml and waits for its first refresh, which runs the graph analysis
    and the solve. `python -m queries.allocation_report` then prints the report
    from the deployed model.
"""

from .inventory_allocation import SolveStatus, TotalHoldingCost, problem
from .network_analysis import (
    NetworkComponent,
    NetworkState,
    SiteComponent,
    graph,
    num_components,
)
from .schema import Demand, Route, Site, model
from .source import DATA_DIR

__all__ = [
    "DATA_DIR",
    "Demand",
    "NetworkComponent",
    "NetworkState",
    "Route",
    "Site",
    "SiteComponent",
    "SolveStatus",
    "TotalHoldingCost",
    "graph",
    "model",
    "num_components",
    "problem",
]
