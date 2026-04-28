---
title: "Supplier Impact Analysis (moved)"
description: "Moved into supply_chain_resilience. Multi-hop blast-radius reachability is now Stage 0 of that template."
experience_level: intermediate
industry: "Supply Chain & Logistics"
reasoning_types:
  - Graph
tags:
  - moved
  - reachability
  - blast-radius
  - graph-analysis
---

## This template has moved

The Supplier Impact Analysis template has been merged into [`supply_chain_resilience`](../supply_chain_resilience/) as part of a v1 portfolio consolidation. The blast-radius reachability pattern now runs as **Stage 0 — Blast-Radius Pre-Analysis** before the multi-reasoner pipeline:

- A directed Business graph is built from `Shipment.supplier → Shipment.customer` edges.
- Upstream reachability traces every supplier each high-priority demand customer transitively depends on, surfacing the exposure footprint BEFORE the MILP runs.

For pure transitive-dependency tracing on a different domain (bill-of-materials), see [`bom-reachability`](../bom-reachability/).
