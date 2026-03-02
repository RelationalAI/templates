---
title: "Humanitarian Aid Supply Chain Network"
description: "Use graph reasoning to analyze a humanitarian aid supply chain network with PageRank and Weighted Degree Centrality to optimize resource distribution strategies."
experience_level: intermediate
industry: Humanitarian & Emergency Response
reasoning_types:
  - Graph
tags:
  - supply-chain
  - weighted-graphs
  - pagerank
  - degree-centrality
---

## What this template is for

During humanitarian crises—natural disasters, conflicts, or disease outbreaks—emergency response teams must rapidly deploy aid through complex supply chain networks. This template demonstrates how to use **PageRank** and **Weighted Degree Centrality** — two complementary graph algorithms that reveal different dimensions of network importance — to optimize aid distribution strategies.

By analyzing a network of distribution points (airports, warehouses, border crossings, relief camps) and supply routes, this template helps you:
- **Identify influential hubs** where aid naturally concentrates (PageRank)
- **Find critical coordination nodes** that serve as highly connected network hubs (Weighted Degree Centrality)
- **Prioritize resource deployment** by combining both metrics for strategic decision-making

PageRank simulates how aid flows through the network using iterative random walks, while Weighted Degree Centrality identifies the most connected nodes that serve as coordination points. Together, they provide a comprehensive view of network structure and strategic priorities.

## Who this is for
- **Intermediate users** ready to learn multi-metric graph analysis with iterative algorithms
- **Data scientists** working with supply chain optimization and network resilience
- **Emergency response coordinators** planning humanitarian aid distribution strategies
- **Supply chain analysts** identifying vulnerabilities in complex distribution networks

## What you'll build

- Load a humanitarian aid network with 18 distribution points and 28 directed supply routes from CSV files
- Use RelationalAI's Graph API to model a weighted, directed supply chain network
- Calculate PageRank to identify where aid flows naturally concentrate (influence)
- Calculate Weighted Degree Centrality to find highly connected coordination nodes (network hubs)
- Analyze strategic categories: critical coordination hubs, influential endpoints, and network connectors
- Generate actionable recommendations for resource deployment and network resilience
- Compare multiple graph metrics to make informed strategic decisions

This template uses **RelationalAI's advanced graph algorithms** including PageRank (an iterative algorithm requiring multiple passes over the network) and Weighted Degree Centrality (analyzing network connectivity patterns).

## What's included

- **Shared model setup**: `model_setup.py` - Common model configuration and graph creation (used by both scripts)
- **Command-line script**: `humanitarian_aid_supply_chain.py` - CLI analysis script with detailed output
- **Interactive app**: `app.py` - Streamlit web application with visualizations and interactive analysis
- **Data**: `data/distribution_points.csv` and `data/supply_routes.csv`

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
   curl -O https://private.relational.ai/templates/zips/v1/humanitarian-aid-supply-chain.zip
   unzip humanitarian_aid_supply_chain.zip
   cd humanitarian_aid_supply_chain
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
   python humanitarian_aid_supply_chain.py
   ```

   **Option B: Interactive Streamlit app**

   ```bash
   # Install additional dependencies for visualization
   python -m pip install .[visualization]

   # Launch the interactive app
   streamlit run app.py
   ```


## Template structure

```text
.
├─ README.md                                        # this file
├─ pyproject.toml                                   # dependencies
├─ model_setup.py                                   # shared model configuration (used by both scripts)
├─ humanitarian_aid_supply_chain.py                 # command-line analysis script
├─ app.py                                           # interactive Streamlit web app
└─ data/
   ├─ distribution_points.csv                       # 18 distribution points
   └─ supply_routes.csv                             # 28 directed supply routes
```

**Start here**:
- For command-line analysis: Run `python humanitarian_aid_supply_chain.py`
- For interactive web app: Run `streamlit run app.py`

## Sample data

The sample data represents a realistic humanitarian aid supply chain network during an emergency response:

- **distribution_points.csv**: 18 distribution points including international airports, warehouses, border crossings, ports, regional distribution centers, NGO coordination hubs, relief stations, refugee camps, medical centers, and community hubs. Each has a unique ID, name, type, geographic region, storage capacity (in units), and population served.

- **supply_routes.csv**: 28 directed supply routes representing aid flow pathways with three weights:
  - `route_capacity`: Maximum aid volume (units/day)
  - `reliability_score`: Route reliability (0-1, accounting for road conditions, security, weather)
  - `distance_km`: Physical distance for routing calculations

The network is intentionally medium-sized (18 nodes, 28 edges) to demonstrate real-world complexity while remaining understandable. The network structure includes:
- **Capital region**: Primary entry points (airport, port) and central warehouse hub
- **Remote regions**: Distribution to refugee camps, relief stations, and community centers
- **Mixed connectivity**: Some regions well-connected, others dependent on single routes (bottlenecks)

## Model overview

This model represents a humanitarian aid supply chain as a weighted, directed graph where distribution points are nodes and supply routes are edges with multiple attributes.

- **Key entities**: `DistributionPoint` (aid distribution locations) and `SupplyRoute` (connecting 2 distribution points)
- **Primary identifiers**: Distribution Point ID (integer). A supply route is identified by both a `from_point` and a `to_point`.
- **Graph structure**: Directed, weighted graph using RelationalAI's Graph API
- **Edge weights**: Based on the flow weight for each route with the expected aid throughput considering capacity, reliability, and distance.

### DistributionPoint Concept

The `DistributionPoint` concept represents locations in the humanitarian aid network.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | Integer | Yes | Unique distribution point identifier from `data/distribution_points.csv` |
| `name` | String | No | Point name (e.g., "Central Warehouse") |
| `type` | String | No | Category: Airport, Warehouse, Border, Port, Distribution Center, NGO Hub, Relief Station, Refugee Camp, Medical Center, Community Hub |
| `region` | String | No | Geographic region: Capital, North, South, East, West, Coast |
| `capacity` | Integer | No | Storage/handling capacity in units |
| `population_served` | Integer | No | Number of people directly served by this point |

### SupplyRoute Concept

The `SupplyRoute` concept represents directed supply routes between distribution points with weighted attributes.

| Property | Type | Notes |
|---|---|---|
| `from_point` | DistributionPoint | Source point in the supply route |
| `to_point` | DistributionPoint | Destination point in the supply route |
| `route_capacity` | Integer | Maximum throughput (units/day) |
| `reliability_score` | Float | Route reliability (0-1 scale) |
| `distance_km` | Integer | Physical distance for routing calculations |

### Flow Weight Property

The flow weight property represents expected aid throughput considering capacity, reliability, and distance and is calculated using the following formula:

```text
flow_weight = (route_capacity * reliability_score) / distance_km
```

### Graph Metrics

The template calculates these advanced metrics using RelationalAI's Graph API:

| Metric | Type | Description |
|---|---|---|
| `pagerank` | Float | Influence score (0-1) based on iterative random walk simulation. Higher = more aid naturally flows here |
| `degree_centrality` | Float | Sum of flow weights for all connected routes. Higher = more influential hub |
| `incoming_routes` | Integer | Indegree: number of supply routes delivering TO this point |
| `outgoing_routes` | Integer | Outdegree: number of supply routes originating FROM this point |

## How it works

The template follows this flow:

```text
CSV files → model_setup.create_model() → Calculate PageRank → Calculate Degree Centrality → Analyze strategic categories → Display results
```

### 1. Shared Model Setup

Both the CLI script and Streamlit app use the same model setup from `model_setup.py`:

```python
from model_setup import create_model

# Create the model, concepts, relationships, and graph (all in one call)
model, graph, DistributionPoint, SupplyRoute = create_model()
```

The `create_model()` function handles:
- Creating the RelationalAI model container
- Defining the `DistributionPoint` concept with all properties
- Loading distribution points from CSV
- Defining the `SupplyRoute` concept with weighted properties
- Loading supply routes from CSV
- Creating the weighted, directed graph
- Returning all components for use in analysis

### 2. Calculate PageRank (Iterative Algorithm)

PageRank simulates random walks through the network to identify influential nodes:

```python
# Calculate PageRank with damping factor 0.85
# Damping factor models probability of continuing along routes vs. teleporting
pagerank = graph.pagerank(damping_factor=0.85, tolerance=1e-6, max_iter=100)
```

**How PageRank works:**
1. Start with equal probability at all nodes
2. Iteratively propagate probability along edges
3. Apply damping factor: 85% chance of following an edge, 15% chance of "teleporting" to random node
4. Converge when probabilities stabilize (tolerance threshold)
5. Higher PageRank = more "important" in the network flow

### 3. Calculate Weighted Degree Centrality

Degree Centrality identifies highly connected network hubs:

```python
# Calculate Degree Centrality
degree_centrality = graph.degree_centrality()

# Also calculate degree metrics for context
indegree = graph.indegree()   # Incoming routes
outdegree = graph.outdegree()  # Outgoing routes
```

**How Weighted Degree Centrality works:**
1. Sum the flow weights for all connected routes (capacity × reliability) for each node
2. Higher weighted degree = more influential hub with greater aid throughput capacity
3. Accounts for both connectivity AND the strength/importance of those connections
4. Identifies nodes that serve as critical coordination hubs with substantial flow capacity

### 4. Query and analyze strategic categories

# Query both metrics and assign a strategic category to each distribution point.

```python
from relationalai.semantics import where, select

# Create variable references
point = graph.Node.ref("point")
pr_score = Float.ref("pr_score")
dc_score = Float.ref("dc_score")
in_routes = Integer.ref("in_routes")
out_routes = Integer.ref("out_routes")

# Query all metrics together
results = where(
    pagerank(point, pr_score),
    degree_centrality(point, dc_score),
    indegree(point, in_routes),
    outdegree(point, out_routes)
).select(
    point.id,
    point.name,
    point.type,
    point.region,
    point.capacity,
    point.population_served,
    pr_score.alias("pagerank"),
    dc_score.alias("degree_centrality"),
    in_routes.alias("incoming_routes"),
    out_routes.alias("outgoing_routes")
).to_df()

# Assign a strategic category based on both metrics
pr_threshold = results['pagerank'].quantile(0.70)
dc_threshold = results['degree_centrality'].quantile(0.70)

# Critical Coordination Hubs: High PageRank + High Degree Centrality
critical_hubs = results[
    (results['pagerank'] >= pr_threshold) &
    (results['degree_centrality'] >= dc_threshold)
]

# Influential Endpoints: High PageRank + Lower Degree Centrality
influential_endpoints = results[
    (results['pagerank'] >= pr_threshold) &
    (results['degree_centrality'] < dc_threshold)
]

# Network Connectors: Lower PageRank + High Degree Centrality
connectors = results[
    (results['pagerank'] < pr_threshold) &
    (results['degree_centrality'] >= dc_threshold)
]
```

### 5. Display strategic analysis and recommendations

**CLI script** (`humanitarian_aid_supply_chain.py`) prints:
- Ranked table of all distribution points with both metrics
- Strategic category analysis (Critical Coordination Hubs, Influential Endpoints, Network Connectors)
- Network-wide and regional statistics
- Actionable recommendations for emergency response teams

**Streamlit app** (`app.py`) provides:
- Interactive overview with top-5 rankings
- Network visualization with color-coded nodes by strategic category
- Detailed filterable rankings with CSV export
- Strategic analysis with expandable details for each category
- Regional distribution statistics

## Customize this template

### Use your own data

- Replace the CSV files in the `data/` directory with your own supply chain network, keeping the same column names (or update the logic in `model_setup.py`).
- Ensure that supply routes only reference valid distribution point IDs.
- You can add additional properties to distribution points (organization, contact info, GPS coordinates) by adding columns to the CSV and corresponding properties to the model in `model_setup.py`.

### Extend the model

**Adjust PageRank parameters**: Experiment with different damping factors:
- Higher damping (0.90-0.95): More emphasis on network structure, less on random teleportation
- Lower damping (0.70-0.80): More emphasis on direct connections, less on global influence

**Add different edge weights**: Change the graph edge weight formula in `model_setup.py` to optimize for different factors. Remember: **for PageRank, use direct multipliers**—higher weights indicate stronger connections that PageRank will favor.

Current formula: `(route_capacity * reliability_score) / distance_km` — good for balanced optimization

Alternative formulas (all using direct multipliers):
- Capacity-focused: `route_capacity` (maximize throughput)
- Reliability-focused: `reliability_score` (emphasize route stability)
- Simple combined: `route_capacity * reliability_score` (ignore distance)

**Try additional algorithms**:
- `graph.louvain()` - Community detection to identify regional aid distribution clusters
- `graph.is_reachable(point1, point2)` - Verify connectivity between specific locations
- `graph.distance(point1, point2)` - Calculate shortest path length between points
- `graph.weakly_connected_components()` - Identify disconnected network regions

**Add temporal analysis**: Include route availability schedules or seasonal variations to model time-dependent supply chains.

**Incorporate risk factors**: Add node properties for conflict zones, disease prevalence, or natural disaster risk to prioritize safe routes.

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
  <summary>Why does PageRank not converge?</summary>

- Your network might have disconnected components or unusual structure.
- Try increasing `max_iter` (default 100) or adjusting `tolerance` (default 1e-6).
- Check that your graph has valid edges and nodes.

</details>

<details>
  <summary>How do I decide between PageRank and Degree Centrality?</summary>

- **Use PageRank** to identify where resources naturally accumulate (influence, importance)
- **Use Degree Centrality** to identify highly connected coordination hubs (network structure)
- **Use both together** (like this template) for comprehensive strategic analysis
- They measure different things: PageRank = "influence/flow", Degree Centrality = "connectivity/hub importance"

</details>

<details>
  <summary>Can I use this for other types of supply chains?</summary>

- Yes! This template works for any directed supply chain:
  - Manufacturing supply chains (factories → warehouses → retailers)
  - Food distribution networks (farms → processing → distribution → stores)
  - Pharmaceutical supply chains (manufacturers → distributors → pharmacies)
  - Just update the CSV data and entity names to match your domain.

</details>
