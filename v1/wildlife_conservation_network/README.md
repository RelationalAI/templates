---
title: "Wildlife Conservation Network"
description: "Use the Louvain community detection algorithm and degree centrality analysis to identify collaboration clusters among wildlife conservation organizations, helping optimize resource sharing and identify key coordination hubs."
experience_level: beginner
industry: Environment & Sustainability
reasoning_types:
  - Graph
tags:
  - graph-analytics
  - community-detection
  - louvain
  - centrality-analysis
  - wildlife-conservation
---

## What this template is for

Wildlife conservation requires coordination across many organizations—NGOs, research stations, wildlife reserves, veterinary services, and community programs. This template demonstrates how to use graph analytics to understand conservation networks:

- **Louvain algorithm** — a community detection method that finds clusters of densely connected nodes in a network — to identify groups of conservation organizations that work closely together
- **Degree centrality** — a connectivity measure that identifies the most influential organizations within each community

By analyzing a network of conservation partnerships, this template helps you discover natural collaboration clusters based on geography, species focus, or organizational mission. These communities reveal which organizations form tight-knit working groups, where coordination is already strong, and where opportunities exist for better cross-community collaboration. Degree centrality then identifies the hub organizations within each cluster that are well-positioned to lead coordination efforts and resource sharing initiatives.

## Who this is for
- **Beginners** who want to learn community detection with a real-world use case
- **Data scientists** new to RelationalAI looking for a graph analytics example beyond centrality measures
- **Conservation program managers** optimizing partnership strategies and resource allocation
- **Network analysts** studying collaboration patterns in mission-driven organizations

## What you'll build

- Load a wildlife conservation network with 12 organizations and 19 undirected partnerships from CSV files
- Use RelationalAI's Graph API to model the conservation partnership network
- Apply the Louvain algorithm to detect communities (collaboration clusters)
- Calculate degree centrality to identify which organizations serve as hubs within each community
- Analyze community characteristics (region, species focus, organization types, hub organizations)
- Generate insights on intra-community collaboration, hub organization leadership potential, and cross-community coordination opportunities

This template uses **RelationalAI's graph modeling** capabilities with the Graph class to represent the network, the built-in Louvain algorithm for community detection, and degree centrality analysis to identify influential organizations within each cluster.

## What's included

- **Shared model setup**: `model_setup.py` - Common model configuration and graph creation (used by both scripts)
- **Command-line script**: `wildlife_conservation_network.py` - CLI analysis script with detailed output
- **Interactive app**: `app.py` - Streamlit web application with visualizations and interactive analysis
- **Data**: `data/organizations.csv` and `data/partnerships.csv`

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools
- Python >= 3.10
- pandas library
- streamlit and plotly (optional, for interactive web app)

## Quickstart

Follow these steps to run the template with the included sample data.
You can customize the data and model as needed after you have it running end-to-end.

1. Download the ZIP file for this template and extract it:

   ```bash
   curl -O https://private.relational.ai/templates/zips/v1/wildlife_conservation_network.zip
   unzip wildlife_conservation_network.zip
   cd wildlife_conservation_network
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


## Template structure

```text
.
├─ README.md                                        # this file
├─ pyproject.toml                                   # dependencies
├─ model_setup.py                                   # shared model configuration (used by both scripts)
├─ wildlife_conservation_network.py                 # command-line analysis script
├─ app.py                                           # interactive Streamlit web app
└─ data/
   ├─ organizations.csv                             # 12 conservation organizations
   └─ partnerships.csv                              # 19 partnership connections
```

**Start here**:
- For command-line analysis: Run `python wildlife_conservation_network.py`
- For interactive web app: Run `streamlit run app.py`

## Sample data

The sample data represents a simplified wildlife conservation network across African regions:

- **organizations.csv**: 12 conservation organizations including NGOs, research stations, wildlife reserves, veterinary services, security units, and community programs. Each has a unique ID, name, type, geographic region, and species focus (elephants, rhinos, big cats, or multiple species).
- **partnerships.csv**: 19 undirected partnerships representing active collaborations like joint research projects, resource sharing agreements, cross-training programs, and coordinated anti-poaching efforts. Each partnership connects two organizations.

The network is intentionally small (12 nodes, 19 edges) to make it easy to understand and verify the community detection results. The Louvain algorithm naturally separates the network into:
- **East African community**: Focused on elephants, big cats, and diverse species with research and community engagement
- **Southern African community**: Focused on rhino conservation with security and reserve management

## Model overview

This model represents a wildlife conservation network as an undirected graph where organizations are nodes and partnerships are edges.

- **Key entities**: `Organization` (conservation orgs) with a `partners_with` relationship
- **Primary identifiers**: Organization ID (integer)
- **Graph structure**: Undirected, unweighted graph using RelationalAI's Graph API

### Organization Concept

The `Organization` concept represents conservation entities working to protect wildlife.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | Integer | Yes | Unique organization identifier from `data/organizations.csv` |
| `name` | String | No | Organization name (e.g., "Serengeti Wildlife Trust") |
| `type` | String | No | Category: NGO, Research, Reserve, Medical, Security, Community |
| `region` | String | No | Geographic region: East Africa, Southern Africa |
| `focus_species` | String | No | Primary conservation focus: Elephants, Rhinos, Lions & Leopards, Multiple Species |

### Organization Relationship

The `partners_with` relationship represents undirected partnerships between organizations (joint projects, resource sharing, coordination).

| Property | Type | Notes |
|---|---|---|
| `org1` | Organization | One organization in the partnership |
| `org2` | Organization | Other organization in the partnership |

Since partnerships are bidirectional, the relationship is defined in both directions to create an undirected graph.

### Graph Metrics

The template calculates these key metrics using RelationalAI's Graph API:

| Metric | Type | Description |
|---|---|---|
| `community` | Integer | Community ID assigned by Louvain algorithm. Organizations with the same ID belong to the same collaboration cluster |
| `degree_centrality` | Float | Normalized connectivity score (0-1) indicating an organization's relative importance within the network. Higher values indicate hub organizations with more connections and greater influence on coordination efforts |
| `partnerships` | Integer | Total number of partnership connections for each organization (raw count of collaborations) |

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

### Use your own data

- Replace the CSV files in the `data/` directory with your own conservation network, keeping the same column names (or update the logic in wildlife_conservation_network.py).
- Make sure that organizations in **partnerships.csv** only reference valid organization IDs.
- You can add additional properties to organizations (budget, staff size, years active) by adding columns to the CSV and corresponding properties to the model.

### Extend the model

**Add weighted partnerships**: Weight edges by collaboration intensity (number of joint projects, funding shared, frequency of interaction). Update `weighted=True` in the Graph definition and add weight values to edges.

**Try different community detection algorithms**: RelationalAI supports multiple algorithms:
- `graph.label_propagation()` - Faster but less accurate for small networks
- `graph.weakly_connected_components()` - Finds completely disconnected groups
- Experiment to see which algorithm best reveals your network's structure

**Add temporal analysis**: Include partnership start dates to analyze how communities evolve over time.

**Calculate modularity**: Measure how well the detected communities separate from each other (higher modularity = better community structure).

## Troubleshooting

<details>
  <summary>Why does authentication/configuration fail?</summary>

- Run `rai init` to create/update `raiconfig.toml`.
- If you have multiple profiles, set `RAI_PROFILE` or switch profiles in your config.

</details>

<details>
  <summary>Why does the script fail to connect to the RAI Native App?</summary>

- Verify the Snowflake account/role/warehouse and `rai_app_name` are correct in `raiconfig.toml`.
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
