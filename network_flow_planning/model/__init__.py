"""Network Flow Planning (prescriptive optimization) template: the model.

This package demonstrates a multi-tier network flow problem with fixed-cost
facility opening in RelationalAI:

- Load sample CSVs describing sites (warehouses, hubs, fulfillment centers,
  customers), lanes (directed transport links with cost and capacity), and
  demands (customer orders).
- Model these as a single Site concept distinguished by a `type` property,
  plus Lane and Demand concepts.
- Choose flow on each lane (continuous) and which fulfillment centers to
  open (binary).
- Enforce flow conservation at transit nodes, source supply at warehouses,
  capacity-linked-to-open at fulfillment centers, and demand satisfaction
  at customers.
- Minimize total cost (transport + fixed-cost FC opening).

Run:
    `rai models deploy --path model` deploys this package to the schemas in
    raiconfig.yaml and waits for its first refresh, which runs the solve.
    `python -m queries.network_plan` then prints the report from the deployed model.
"""

from .reasoning import problem
from .schema import Demand, Lane, Site, model
from .source import DATA_DIR

__all__ = ["DATA_DIR", "Demand", "Lane", "Site", "model", "problem"]
