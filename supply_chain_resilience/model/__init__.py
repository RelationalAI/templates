"""Supply chain resilience (multi-reasoner) template: the model.

This package declares a chained multi-reasoner workflow in RelationalAI,
combining graph analysis, rules-based classification, and prescriptive
optimization for supply chain risk management:

- Stage 0 -- Blast-radius pre-analysis: build a directed Business graph from
  shipment data, run upstream reachability from high-priority demand customers
  to surface every supplier they transitively depend upon. This shows the
  exposure footprint before any optimization runs.
- Stage 1 -- Graph: build a site dependency graph from shipping operations,
  compute eigenvector centrality to identify critical warehouses and bridges
  between supply chain regions.
- Stage 2 -- Rules: classify suppliers by risk level (avoid/watch/reliable)
  using reliability scores and ML delay predictions. Flag late shipments
  and escalated demand orders.
- Stage 3 -- Prescriptive: solve a minimum-cost network flow that routes
  supply to meet demand. Graph centrality feeds a bottleneck penalty in the
  objective. Supplier risk flags feed hard constraints (no flow from "avoid"
  suppliers) and surcharges (extra cost for "watch" suppliers).
- Scenario analysis: re-solve with disruptions (critical site offline,
  supplier downgrade) to quantify resilience costs. Each scenario is its own problem.

Run:
    `rai models deploy --path model` deploys this package to the schemas in
    raiconfig.yaml and waits for its first refresh, which runs the solves.
    `python -m queries.resilience_report` then prints the report from the deployed model.
"""

from .reasoning import (
    baseline,
    biz_graph,
    biz_num_edges,
    biz_num_nodes,
    eigenvector,
    graph,
    num_edges,
    num_nodes,
    reachable_to,
    site_offline,
    target_customer,
    watch_avoid,
    wcc,
)
from .schema import Business, DelayPrediction, Demand, Operation, Shipment, Site, model
from .source import DATA_DIR

__all__ = [
    "DATA_DIR",
    "Business",
    "DelayPrediction",
    "Demand",
    "Operation",
    "Shipment",
    "Site",
    "baseline",
    "biz_graph",
    "biz_num_edges",
    "biz_num_nodes",
    "eigenvector",
    "graph",
    "model",
    "num_edges",
    "num_nodes",
    "reachable_to",
    "site_offline",
    "target_customer",
    "watch_avoid",
    "wcc",
]
