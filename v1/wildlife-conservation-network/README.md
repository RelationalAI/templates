---
title: "Wildlife Conservation Network"
description: "Identify collaboration clusters among wildlife-conservation organizations with Louvain community detection and degree centrality, surfacing key coordination hubs for resource sharing."
experience_level: beginner
industry: "Cross-Industry"
reasoning_types:
  - Graph
tags:
  - community-detection
  - louvain
  - centrality
---

## What this template is for

Wildlife conservation requires coordination across many organizations — non-governmental organizations (NGOs), research stations, wildlife reserves, veterinary services, and community programs. Coordination that already works well is hard to see from an org chart, and the organizations best placed to broker resources across groups are rarely the obvious ones. Analyzing the network of partnerships between these organizations makes both visible.

This template discovers natural collaboration clusters — based on geography, species focus, or organizational mission — and identifies the hub organizations within each cluster that are well-positioned to lead coordination and resource-sharing efforts.

**A graph reasoner turns a raw partnership network into a coordination map — the collaboration clusters that already exist and the hub organizations best placed to broker resources across them.**

## Who this is for
- **Beginners** who want to learn community detection with a real-world use case
- **Data scientists** new to RelationalAI looking for a graph analytics example beyond centrality measures
- **Conservation program managers** optimizing partnership strategies and resource allocation
- **Network analysts** studying collaboration patterns in mission-driven organizations

## What you'll build

- A conservation partnership network modeled with RelationalAI's Graph API, built from the bundled organization and partnership CSVs.
- Community assignments from the Louvain algorithm — the collaboration clusters within the network — written onto each `Organization`.
- A degree-centrality ranking that surfaces the hub organization inside each cluster, the one best placed to lead coordination.
- Community-level insight: region and species-focus makeup, hub identity, and cross-community connectors, available both as a CLI report and an interactive Streamlit visualization.

Built using **graph analysis** (Louvain community detection and degree centrality on an undirected, unweighted partnership graph).

## What's included

- **Model**: a single shared ontology — `Organization` nodes and `Partnership` edges — plus the Louvain community and degree-centrality enrichment the graph reasoner writes back. Defined once in `model_setup.py` and reused by both runners.
- **Runner**: `wildlife_conservation_network.py` (CLI report) and `app.py` (interactive Streamlit visualization), both against a Snowflake-connected RAI account.
- **Sample data**: a small network of conservation organizations and the partnerships between them. See *Sample data* below.
- **Outputs**: a per-organization table of community assignments and metrics, a per-community breakdown, and (in the app) an interactive network graph.

## Prerequisites

### Access

- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools

- Python >= 3.10.
- RelationalAI Python SDK (`relationalai == 1.11.0`).
- Streamlit (installed via the optional `.[visualization]` extra) for the interactive app.

## Quickstart

Follow these steps to run the template with the included sample data.
You can customize the data and model as needed after you have it running end-to-end.

1. Download the ZIP file for this template and extract it:

   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/wildlife-conservation-network.zip
   unzip wildlife-conservation-network.zip
   cd wildlife-conservation-network
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

   From this folder:

   ```bash
   python -m pip install .
   ```

4. **Configure Snowflake connection and RAI profile**

   ```bash
   rai init
   ```

5. **Run the template**

   **Option A: Command-line script**

   ```bash
   python wildlife_conservation_network.py
   ```

   **Option B: Interactive Streamlit app**

   ```bash
   # Install additional dependencies for visualization
   python -m pip install .[visualization]

   # Launch the interactive app
   streamlit run app.py
   ```

   The Streamlit app provides:
   - Interactive network visualization colored by community with hover details
   - Community breakdown with detailed statistics and member listings
   - Geographic and species focus analysis
   - Cross-community connector identification
   - Summary statistics and key metrics

6. Expected output (a few lines confirm a successful run):

   ```text
   Louvain community detection -> 3 collaboration clusters (5 / 4 / 3 organizations)
   Global hub: Serengeti Wildlife Trust -- 5 partnerships, degree centrality 0.4545
   ```

   The community ID numbers are arbitrary labels; what matters is which
   organizations group together. The full report and a step-by-step walkthrough
   are in `runbook.md`.

## Template structure

```text
wildlife-conservation-network/
  model_setup.py                     # Shared model, concepts, and graph (used by both runners)
  wildlife_conservation_network.py   # CLI analysis script with detailed output
  app.py                             # Optional Streamlit visualization app
  data/
    organizations.csv                # Conservation organizations (type, region, focus species)
    partnerships.csv                 # Undirected collaboration partnerships between organizations
  README.md                          # this file
  runbook.md                         # analyst-facing paste-testable walkthrough
  pyproject.toml                     # dependencies
```

**Start here**: run `python wildlife_conservation_network.py` for the full CLI analysis end to end, or follow `runbook.md` to rebuild it step by step. The Streamlit app is an optional visualization layer over the same model.

## Sample data

The bundled data is a small, illustrative conservation network — designed to teach community detection on a Snowflake-connected RAI account, not to match a specific program's partnerships.

- **`organizations.csv`** — 12 conservation organizations, each with a `type` (NGO, research station, reserve, and so on), a `region`, and a `focus_species`.
- **`partnerships.csv`** — 19 collaboration partnerships, one row each, given as a pair of organization ids. Partnerships are undirected, so ordering does not matter.

## Model overview

A single shared ontology (defined in `model_setup.py`) backs both runners. The graph reasoner writes community and centrality results back onto the network.

- **Key entities**: `Organization` (the network's nodes), `Partnership` (the collaboration edges).
- **Primary identifiers**: integer `id` on `Organization`; `Partnership` is identified by its two endpoint organizations.
- **Important invariants**: every `Partnership` endpoint must reference a valid `Organization` id; the graph is undirected and unweighted, so a partnership counts once regardless of row order.

### Concepts

**`Organization`** — a conservation organization; a node in the partnership graph.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | Integer | Yes | Loaded from `data/organizations.csv` |
| `name` | String | No | e.g. `Serengeti Wildlife Trust` |
| `type` | String | No | Organization type (NGO, research station, and so on) |
| `region` | String | No | Geographic region |
| `focus_species` | String | No | Primary species focus |

**`Partnership`** — an undirected collaboration between two organizations; an edge in the graph.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `org1` | Relationship | Yes | First endpoint on `Organization` |
| `org2` | Relationship | Yes | Second endpoint on `Organization` |

### Relationships

- `Partnership.org1` and `Partnership.org2` -> `Organization` — the two endpoints of a collaboration; together they define the undirected graph edges the Louvain and centrality algorithms run over.

## How it works

The template follows this flow:

```text
CSV files → model_setup.create_model() → Apply Louvain → Analyze communities → Display results
```

### 1. Shared Model Setup

Both the CLI script and Streamlit app use the same model setup from `model_setup.py`:

```python
from model_setup import create_model

# Create the model, concepts, relationships, and graph (all in one call)
model, graph, Organization = create_model()
```

The `create_model()` function handles:
- Creating the RelationalAI model container
- Defining the `Organization` concept with all properties
- Loading organizations from CSV
- Defining the `Partnership` concept for edges
- Loading partnerships from CSV
- Creating the undirected, unweighted graph
- Returning all components for use in analysis

### 2. Apply Community Detection and Centrality Analysis

Use the built-in Louvain algorithm to detect communities and calculate centrality metrics:

```python
# Apply Louvain algorithm for community detection
louvain_communities = graph.louvain()

# Calculate degree centrality to identify hub organizations within communities
degree_centrality = graph.degree_centrality()

# Also calculate degree (raw partnership count) for additional analysis
degree = graph.degree()
```

The Louvain algorithm works by:
1. Optimizing modularity (a measure of how well the network divides into communities)
2. Iteratively grouping nodes to maximize within-community connections
3. Minimizing between-community connections
4. Returning a community ID for each node

Degree centrality then normalizes the partnership counts to a 0-1 scale, making it easier to compare organizations across different community sizes. Organizations with higher centrality are well-positioned hubs that could lead coordination efforts within their community.

### 3. Query and Analyze Communities

Query the graph to retrieve community assignments and metrics:

```python
from relationalai.semantics import where, Integer, Float

# Create variable references
org = graph.Node.ref("org")
community_id = Integer.ref("community_id")
centr_score = Float.ref("centr_score")
partner_count = Integer.ref("partner_count")

# Query the graph
results = where(
    louvain_communities(org, community_id),
    degree_centrality(org, centr_score),
    degree(org, partner_count)
).select(
    org.id,
    org.name,
    org.type,
    org.region,
    org.focus_species,
    community_id.alias("community"),
    centr_score.alias("degree_centrality"),
    partner_count.alias("partnerships")
).to_df()

# Sort by community, then by centrality within each community
results = results.sort_values(["community", "degree_centrality"], ascending=[True, False])
```

### 4. CLI Script Analysis

The `wildlife_conservation_network.py` script displays:
- A table of all organizations with their community assignments and metrics
- Detailed breakdown of each detected community (size, region, species focus, hub organization)
- Network-wide summary statistics
- Actionable recommendations for conservation coordination

### 5. Interactive Streamlit App

The included `app.py` provides an interactive web interface using the same shared model:

```python
import streamlit as st
from model_setup import create_model

# Load the same model and query results
model, graph, Organization = create_model()
results = get_results(model, graph, Organization)
```

The Streamlit app features:
- **Interactive network graph**: Nodes colored by community, sized by partnerships
- **Community breakdown**: Expandable sections with detailed metrics for each cluster
- **Strategic analysis**: Cross-community connectors, geographic distribution, species focus
- **Summary statistics**: Sidebar with key network metrics and hub organizations

## Customize this template

Focus on the first changes most users will make.

### Use your own data

- Replace the CSV files in `data/` with your own conservation network, keeping the same column names (or update the logic in `model_setup.py`).
- Make sure organizations in `partnerships.csv` only reference valid organization ids from `organizations.csv`.
- For Snowflake-backed runs, swap the `pd.read_csv(...)` calls for `data(snowflake_table)` calls in `model_setup.py`.

### Tune parameters

- The graph is built undirected and unweighted in `model_setup.py`. Adding edge weights (see *Extend the model*) is the main lever on how the community detection partitions the network.

### Extend the model

- **Add organization properties** — budget, staff size, years active — by adding columns to `organizations.csv` and corresponding properties in `model_setup.py`.
- **Add weighted partnerships** — weight edges by collaboration intensity (joint projects, shared funding, interaction frequency). Set `weighted=True` in the Graph definition and add weight values to edges.
- **Try different community-detection algorithms** — `graph.label_propagation()` (faster, less accurate on small networks) or `graph.weakly_connected_component()` (completely disconnected groups); experiment to see which best reveals your network's structure.
- **Add temporal analysis** — include partnership start dates to study how communities evolve over time.

### Scale up / productionize

- Replace the `data/` CSV bundle with ingestion from your partnership system of record.
- The bundled network is small; Louvain and degree centrality scale to much larger graphs. Pin dependencies via `pyproject.toml` for reproducible runs.

## Troubleshooting

<details>
  <summary>Why does authentication/configuration fail?</summary>

- Run `rai init` to create/update `raiconfig.yaml`.
- If you have multiple profiles, set `RAI_PROFILE` or switch profiles in your config.

</details>

<details>
  <summary>Why does the script fail to connect to the RAI Native App?</summary>

- Verify the Snowflake account/role/warehouse and `rai_app_name` are correct in `raiconfig.yaml`.
- Ensure the RAI Native App is installed and you have access.

</details>

<details>
  <summary>Why does Louvain detect only 1 community?</summary>

- Your network might be very densely connected, or too small for meaningful community structure.
- Try adding more organizations and partnerships, or ensure there are distinct clusters in your data.
- For completely disconnected groups, use `graph.weakly_connected_components()` instead.

</details>

<details>
  <summary>Why are community IDs different each time I run the script?</summary>

- Community ID numbers (0, 1, 2...) are arbitrary labels assigned by the algorithm.
- What matters is which organizations are grouped together, not the specific ID number.
- The Louvain algorithm can have some randomness, so community assignments might vary slightly between runs, but the overall structure should be consistent.

</details>

## Learn more

### Core concepts

- [Graph modeling](https://docs.relational.ai/) — building a graph from ontology concepts and relationships, as this template does with `Organization` and `Partnership`.
- [PyRel v1 query language](https://docs.relational.ai/) — `where(...)` / `select(...)` to read algorithm results back out.

### Reasoner reference

- [Graph reasoner](https://docs.relational.ai/) — Louvain community detection, degree centrality, and other built-in graph algorithms.

## Support

- File issues at the RelationalAI templates repository.
