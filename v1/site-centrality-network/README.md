---
title: "Site Centrality Network (moved)"
description: "Moved into warehouse_allocation. Bridge detection + weakly-connected-components patterns are now part of warehouse_allocation's Stage 1 graph analysis."
experience_level: intermediate
industry: "Supply Chain & Logistics"
reasoning_types:
  - Graph
tags:
  - moved
  - graph-analysis
  - bridge-detection
  - weakly-connected-components
  - eigenvector-centrality
---

## This template has moved

The Site Centrality Network template has been merged into [`warehouse_allocation`](../warehouse_allocation/) as part of a v1 portfolio consolidation. All of the patterns previously demonstrated here are preserved:

- **Eigenvector centrality** — was already in `warehouse_allocation` Stage 1.
- **Weakly connected components** — now `warehouse_allocation` Stage 1b.
- **Bridge detection** (cross-region connectors) — now `warehouse_allocation` Stage 1c.

Use [`warehouse_allocation`](../warehouse_allocation/) instead. It chains the full graph analysis (Stage 1a/b/c) with a downstream prescriptive optimization that consumes the centrality scores.
