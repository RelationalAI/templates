---
title: "Site Centrality Network"
description: "Identify the most critical sites in a supply chain network using weakly connected components, bridge detection, and eigenvector centrality to assess resilience and detect single points of failure."
experience_level: intermediate
industry: Supply Chain
featured: false
reasoning_types:
  - Graph
tags:
  - graph-analytics
  - eigenvector-centrality
  - weakly-connected-components
  - bridge-detection
  - supply-chain
sidebar:
  order: 4
---

## What this template is for

Supply chain networks can have hidden vulnerabilities: sites that appear ordinary may actually be the sole connector between regions, or the most influential hub in the network. This template demonstrates three complementary graph analysis techniques to assess supply chain resilience:

1. **Weakly Connected Components (WCC)** -- Detect whether the network is unified or fragmented into isolated clusters.
2. **Bridge Detection** -- Identify sites whose operations cross regional boundaries, making them critical connectors.
3. **Eigenvector Centrality** -- Rank sites by importance, where a site is more important if it connects to other important sites.

Together, these analyses answer: "Which warehouses are bridges between supply chain clusters?" and "Which sites are most critical to supply chain resilience?"

## Who this is for

- **Intermediate users** who want to learn multiple graph algorithms applied to a single network
- **Supply chain analysts** assessing network resilience and identifying single points of failure
- **Operations managers** planning contingency strategies for site disruptions

## What you'll build

- Load a 31-site, 47-operation supply chain network from CSV (consumer electronics, 3 regions: APAC, AMERICAS, EMEA)
- Derive Region and Bridge concepts from the base ontology
- Construct an undirected, weighted site dependency graph (SHIP operations as edges, shipment counts as weights)
- Run WCC to identify connected components and detect network fragmentation
- Identify bridge sites that connect different geographic regions
- Compute eigenvector centrality to rank sites by network importance (filtering out STORE/OFFICE types)
- Display regional summaries and top-3 most critical sites

## What's included

- **Self-contained script**: `site_centrality.py` -- Runs the full analysis end-to-end
- **Data**: `data/sites.csv` (31 sites) and `data/operations.csv` (47 operations) from a consumer electronics supply chain

## Prerequisites

- Python >= 3.10
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

## Quickstart

1. Download and extract this template:

   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/site-centrality-network.zip
   unzip site-centrality-network.zip
   cd site-centrality-network
   ```

   > [!TIP]
   > You can also download the template ZIP using the "Download ZIP" button at the top of this page.

2. **Create and activate a virtual environment**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install -U pip
   ```

3. **Install dependencies**

   ```bash
   python -m pip install .
   ```

4. **Configure Snowflake connection and RAI profile**

   ```bash
   rai init
   ```

5. **Run the template**

   ```bash
   python site_centrality.py
   ```

## How it works

The template follows this flow:

```text
CSV files --> Define ontology --> Derive Region/Bridge concepts --> Build weighted graph --> WCC + Bridge detection --> Eigenvector centrality --> Display results
```

### 1. Load Ontology

Site and Operation concepts are loaded from CSV, with Operations linking source and destination sites:

```python
Site = model.Concept("Site", identify_by={"id": String})
Operation = model.Concept("Operation", identify_by={"id": String})
Operation.source_site = model.Relationship(f"{Operation} from {Site}")
Operation.destination_site = model.Relationship(f"{Operation} to {Site}")
```

### 2. Derive Concepts

Region is derived from unique site region IDs. Bridge is a subconcept of Site (using `extends=[]`) that identifies sites with cross-region operations:

```python
Region = model.Concept("Region")
model.define(Region.new(id=Site.region_id))

Bridge = model.Concept("Bridge", extends=[Site])
model.define(Bridge(site1)).where(
    Operation.source_site(op, site1),
    Operation.destination_site(op, site2),
    site1.region != site2.region,
)
```

### 3. Build Graph and Run Algorithms

An undirected, weighted graph uses shipment counts as edge weights:

```python
graph = Graph(model, directed=False, weighted=True, node_concept=Site)

# WCC for cluster detection
wcc = graph.weakly_connected_component()

# Eigenvector centrality for importance ranking
eigenvector = graph.eigenvector_centrality()
```

### 4. Interpret Results

- **Single component** = unified network; **multiple components** = fragmentation risk
- **Bridge sites** = removing them could partition the network across regions
- **High eigenvector centrality** = connected to other important sites (hub effect)

## Customize this template

**Use your own data:**
- Replace CSVs in `data/` with your own site and operation data, keeping the same column names.
- The `TYPE` column in operations.csv determines which operations form graph edges (filtered to `SHIP`).

**Extend the analysis:**
- Add betweenness centrality (`graph.betweenness_centrality()`) for bottleneck detection
- Add PageRank for influence analysis in directed networks
- Combine centrality scores into a composite criticality metric

## Troubleshooting

<details>
  <summary>Why does authentication/configuration fail?</summary>

- Run `rai init` to create/update `raiconfig.toml`.
- If you have multiple profiles, set `RAI_PROFILE` or switch profiles in your config.

</details>

<details>
  <summary>Why are some sites showing 0 centrality?</summary>

- Sites that only appear in TRANSFER (not SHIP) operations won't have graph edges. The graph is filtered to `Operation.type == "SHIP"`.
- STORE and OFFICE site types are excluded from the centrality query.

</details>
