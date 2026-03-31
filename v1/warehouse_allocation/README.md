---
title: "Warehouse Allocation"
description: "Allocate inventory across a distribution network using graph centrality to prioritize critical hubs."
featured: false
experience_level: intermediate
industry: "Supply Chain & Logistics"
reasoning_types:
  - Graph
  - Prescriptive
tags:
  - Chained Reasoning
  - Eigenvector Centrality
  - Network Flow
  - Inventory Optimization
---

# Warehouse Allocation

## What this template is for

Distribution networks have critical hub warehouses that connect many downstream sites. Identifying these hubs and ensuring they carry adequate inventory is essential for supply chain resilience.

This template chains two reasoning stages:

1. **Graph analysis** identifies which warehouses are most critical to the network using eigenvector centrality on the route topology.
2. **Prescriptive optimization** allocates a limited inventory budget across sites, using the centrality scores from Stage 1 to enforce minimum stock levels at critical hubs.

The key pattern: the graph reasoner writes centrality scores as properties on the Site concept, and the prescriptive reasoner references those properties directly in its constraints. No manual data transfer between stages -- the ontology carries enrichment forward.

## Who this is for

- Data scientists learning to chain multiple RAI reasoner types
- Supply chain teams wanting network-aware inventory planning
- Anyone interested in combining graph analytics with optimization

## What you'll build

- A distribution network graph with eigenvector centrality analysis
- An inventory allocation model that uses centrality as a constraint input
- A two-stage pipeline where graph results feed optimization

## What's included

- `warehouse_allocation.py` -- Main script with Stage 1 (graph) and Stage 2 (prescriptive)
- `data/sites.csv` -- Warehouse and store locations with holding costs
- `data/routes.csv` -- Distribution routes with capacity and transport cost
- `data/demands.csv` -- Demand requirements per site
- `pyproject.toml` -- Python package configuration with dependencies

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools
- Python >= 3.10

## Quickstart

1. Download ZIP:
   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/warehouse_allocation.zip
   unzip warehouse_allocation.zip
   cd warehouse_allocation
   ```
   > [!TIP]
   > You can also download the template ZIP using the "Download ZIP" button at the top of this page.

2. Create venv:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   ```

3. Install:
   ```bash
   python -m pip install .
   ```

4. Configure:
   ```bash
   rai init
   ```

5. Run:
   ```bash
   python warehouse_allocation.py
   ```

## Template structure

```text
.
├── README.md
├── pyproject.toml
├── warehouse_allocation.py
└── data/
    ├── sites.csv
    ├── routes.csv
    └── demands.csv
```

## How it works

### Stage 1: Graph centrality

An undirected weighted graph is built from the route network, with route capacity as edge weight. Eigenvector centrality identifies sites whose connections make them structurally important:

```python
graph = Graph(model, directed=False, weighted=True, node_concept=Site, aggregator="sum")
Site.centrality = graph.eigenvector_centrality()
```

### Stage 2: Inventory allocation

The optimization allocates inventory across sites to minimize holding cost, subject to:
- Total budget constraint
- Demand satisfaction at each site
- **Centrality-based minimum**: warehouses must hold stock proportional to their centrality score

```python
p.satisfy(model.require(
    Site.x_inventory >= Site.centrality * MIN_CENTRALITY_FACTOR
).where(Site.type("WAREHOUSE")))
```

The `Site.centrality` property was populated by Stage 1 and is referenced directly here.

## Customize this template

- **Add more sites and routes**: Extend the CSVs. The graph and optimization automatically adapt to new topology.
- **Change the centrality algorithm**: Replace `eigenvector_centrality()` with `pagerank()` or `betweenness_centrality()` for different notions of importance.
- **Add a third stage**: Use rule-based reasoning to flag sites that are both high-centrality and under-stocked, feeding into an alerting workflow.
- **Scenario analysis**: Loop over different budget levels or centrality thresholds to see how allocation shifts.
