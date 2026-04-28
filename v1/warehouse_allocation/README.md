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

This template chains **Graph** analysis and **Prescriptive** optimization to allocate inventory across a distribution network using centrality to prioritize critical hubs.

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

6. Expected output:
   ```text
   ==================================================
   Stage 1: Network Centrality Ranking
   ==================================================

               site       type   region  centrality
      Atlanta_DC  WAREHOUSE    SOUTH    0.321427
     Chicago_Hub  WAREHOUSE  MIDWEST    0.631380
      Dallas_Hub  WAREHOUSE    SOUTH    0.350735
       Denver_DC  WAREHOUSE     WEST    0.212727
      Detroit_DC  WAREHOUSE  MIDWEST    0.511638
        LA_Store      STORE     WEST    0.057216
     Miami_Store      STORE    SOUTH    0.139914
       NYC_Store      STORE     EAST    0.184369
   Phoenix_Store      STORE     WEST    0.093792
   Seattle_Store      STORE     WEST    0.048634

   ==================================================
   Stage 2: Inventory Allocation
   ==================================================

   Status: OPTIMAL
   Total holding cost: $13713.29

   Allocation plan:
               site       type  centrality   allocated  unit_cost
      Atlanta_DC  WAREHOUSE    0.321427   70.000000        9.0
     Chicago_Hub  WAREHOUSE    0.631380  126.275907       12.0
      Dallas_Hub  WAREHOUSE    0.350735   70.146993       11.0
       Denver_DC  WAREHOUSE    0.212727   42.545325       13.0
      Detroit_DC  WAREHOUSE    0.511638  102.327586       10.0
        LA_Store      STORE    0.057216  120.000000       18.0
     Miami_Store      STORE    0.139914  100.000000       16.0
       NYC_Store      STORE    0.184369  150.000000       20.0
   Phoenix_Store      STORE    0.093792   90.000000       14.0
   Seattle_Store      STORE    0.048634   80.000000       15.0
   ```

   The graph analysis identifies Chicago_Hub (0.63) and Detroit_DC (0.51) as
   the most central network nodes. The optimizer allocates more inventory to
   these high-centrality warehouses -- Chicago gets 126 units and Detroit 102 --
   while stores receive exactly their minimum demand. The centrality floor
   constraint ensures critical hubs carry buffer stock proportional to their
   network importance.

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

This section walks through the highlights in `warehouse_allocation.py`.

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
problem.satisfy(model.require(
    Site.x_inventory >= Site.centrality * MIN_CENTRALITY_FACTOR
).where(Site.type("WAREHOUSE")))
```

The `Site.centrality` property was populated by Stage 1 and is referenced directly here.

## Customize this template

- **Add more sites and routes**: Extend the CSVs. The graph and optimization automatically adapt to new topology.
- **Change the centrality algorithm**: Replace `eigenvector_centrality()` with `pagerank()` or `betweenness_centrality()` for different notions of importance.
- **Add a third stage**: Use rule-based reasoning to flag sites that are both high-centrality and under-stocked, feeding into an alerting workflow.
- **Scenario analysis**: Loop over different budget levels or centrality thresholds to see how allocation shifts.

## Troubleshooting

<details>
<summary><code>ModuleNotFoundError</code></summary>

Make sure you activated the virtual environment and ran `python -m pip install .` to install all dependencies listed in `pyproject.toml`.
</details>

<details>
<summary>Connection or authentication errors</summary>

Run `rai init` to configure your Snowflake connection. Verify that the RAI Native App is installed and your user has the required permissions.
</details>
