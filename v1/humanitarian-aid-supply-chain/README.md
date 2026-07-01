---
title: "Humanitarian Aid Supply Chain Network"
description: "Analyze a humanitarian aid supply-chain network with PageRank and weighted degree centrality to optimize resource distribution."
experience_level: intermediate
industry: "Supply Chain & Logistics"
reasoning_types:
  - Graph
tags:
  - supply-chain
  - weighted-graphs
  - pagerank
  - degree-centrality
---

## What this template is for

During humanitarian crises—natural disasters, conflicts, or disease outbreaks—emergency response teams must rapidly deploy aid through complex supply chain networks. This template uses **Graph** reasoning — specifically PageRank and Weighted Degree Centrality, two complementary algorithms that reveal different dimensions of network importance — to optimize aid distribution strategies.

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

- A weighted, directed supply-chain graph over distribution points and routes, built with RelationalAI's Graph API
- A per-node PageRank score identifying where aid naturally concentrates (influence)
- A per-node Weighted Degree Centrality score surfacing highly connected coordination hubs
- A strategic classification of every distribution point (critical coordination hub, influential endpoint, or network connector) from the two metrics together
- A ranked deployment-priority table with actionable recommendations, exportable to CSV
- An optional Streamlit dashboard visualizing the network and rankings interactively

Built using **graph analysis** — PageRank (an iterative random-walk algorithm) and Weighted Degree Centrality (network-connectivity analysis) on a shared supply-chain ontology.

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
- RelationalAI Python SDK (`relationalai == 1.11.0`)
- For the interactive app only: the `visualization` extra (`python -m pip install .[visualization]`)

## Quickstart

Follow these steps to run the template with the included sample data.
You can customize the data and model as needed after you have it running end-to-end.

1. Download the ZIP file for this template and extract it:

   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/humanitarian-aid-supply-chain.zip
   unzip humanitarian-aid-supply-chain.zip
   cd humanitarian-aid-supply-chain
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

   The Streamlit app provides:
   - Interactive network visualization with directional arrows
   - Filterable distribution-point rankings table
   - Detailed strategic-category analysis
   - CSV export functionality

6. Expected output (a few lines confirm a successful run):

   ```text
   By PageRank (where aid concentrates):
     Emergency Field Hospital   0.1097
   By weighted degree centrality (coordination hubs):
     Central Warehouse          794.81  (9 routes)

   Strategic categories: 2 critical coordination hubs,
     4 influential endpoints, 4 network connectors
   ```

   See `runbook.md` for the full ranked tables and the strategic-category walkthrough.

## Template structure

```text
humanitarian-aid-supply-chain/
├── README.md                          # this file
├── pyproject.toml                     # dependencies
├── model_setup.py                     # shared model + graph construction
├── humanitarian_aid_supply_chain.py   # CLI analysis script
├── app.py                             # optional Streamlit dashboard
├── runbook.md                         # analyst-facing walkthrough
└── data/
    ├── distribution_points.csv        # 18 distribution points
    └── supply_routes.csv              # 28 directed supply routes
```

**Start here**: run `python humanitarian_aid_supply_chain.py` for the full command-line analysis, or launch `streamlit run app.py` for the interactive dashboard. Both build the model through `model_setup.create_model()`.

## Sample data

The bundled data is small and illustrative — an 18-node humanitarian relief network sized to make the two centrality metrics tell contrasting stories, not to match a specific operation.

- **`distribution_points.csv`** (18 rows) — airports, warehouses, border crossings, and relief camps, each with a type, region, capacity, and population served.
- **`supply_routes.csv`** (28 rows) — directed routes between points, each carrying a throughput capacity, a reliability score, and a physical distance used to derive the flow weight.

## Model overview

The model is a small graph ontology: distribution points connected by directed, weighted supply routes. Graph metrics are computed at query time from the route graph rather than stored on the point.

- **Key entities**: `DistributionPoint`, `SupplyRoute`.
- **Primary identifiers**: `DistributionPoint.id` (integer); `SupplyRoute` is keyed by its `(from_point, to_point)` pair.
- **Important invariants**: `reliability_score` is a fraction in `[0, 1]`; capacity and distance are positive; the derived `flow_weight` combines all three into the edge weight the graph algorithms read.

### Concepts

**`DistributionPoint`** — a node in the relief network (airport, warehouse, border crossing, or relief camp). Loaded from `data/distribution_points.csv`.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | Integer | Yes | Point identifier |
| `name` | String | No | Human-readable name |
| `type` | String | No | Airport / Warehouse / Border Crossing / Relief Camp |
| `region` | String | No | Geographic region |
| `capacity` | Integer | No | Site throughput capacity (units/day) |
| `population_served` | Integer | No | People the point serves |

**`SupplyRoute`** — a directed route between two distribution points, with weighted attributes. Loaded from `data/supply_routes.csv`.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `from_point` | `DistributionPoint` | Yes | Source point (composite key) |
| `to_point` | `DistributionPoint` | Yes | Destination point (composite key) |
| `route_capacity` | Integer | No | Maximum throughput (units/day) |
| `reliability_score` | Float | No | Route reliability, `[0, 1]` |
| `distance_km` | Float | No | Physical distance for routing calculations |
| `flow_weight` | Float | No | Derived edge weight: `(route_capacity * reliability_score) / distance_km` |

### Graph metrics

These are computed by the Graph API over the route graph at query time (not stored as `DistributionPoint` properties).

| Metric | Type | Notes |
|---|---|---|
| `pagerank` | Float | Influence score from iterative random walk; higher means more aid naturally flows here |
| `degree_centrality` | Float | Sum of flow weights across a point's routes; higher means a more connected hub |
| `incoming_routes` | Integer | Indegree: routes delivering to this point |
| `outgoing_routes` | Integer | Outdegree: routes originating from this point |

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

Query both metrics and assign a strategic category to each distribution point.

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

Focus on the first changes most users will make.

### Use your own data

- Replace the CSVs in `data/` with your own network, keeping the same column names (or update the loading logic in `model_setup.py`).
- Ensure supply routes only reference valid distribution-point IDs.
- Add properties to distribution points (organization, contact info, GPS coordinates) by adding CSV columns and the corresponding properties in `model_setup.py`.

### Tune parameters

- **PageRank damping factor** — higher damping (0.90-0.95) emphasizes network structure over teleportation; lower damping (0.70-0.80) emphasizes direct connections over global influence.
- **Edge-weight formula** — change the `flow_weight` formula in `model_setup.py` to reweight the graph. Higher weights indicate stronger connections that PageRank favors.

  The current formula `(route_capacity * reliability_score) / distance_km` balances all three factors. Alternatives:
  - Capacity-focused: `route_capacity` (maximize throughput)
  - Reliability-focused: `reliability_score` (emphasize route stability)
  - Simple combined: `route_capacity * reliability_score` (ignore distance)

### Extend the model

- **Try additional algorithms**:
  - `graph.louvain()` — community detection to find regional distribution clusters
  - `graph.is_reachable(point1, point2)` — verify connectivity between two locations
  - `graph.distance(point1, point2)` — shortest-path length between points
  - `graph.weakly_connected_components()` — identify disconnected network regions
- **Add temporal analysis** — include route availability schedules or seasonal variations to model time-dependent supply chains.
- **Incorporate risk factors** — add node properties for conflict zones, disease prevalence, or disaster risk to prioritize safe routes.

### Scale up / productionize

- Swap the `read_csv(...)` loads in `model_setup.py` for `model.data(snowflake_table)` calls to run against a network catalog maintained in Snowflake.
- Pin `relationalai` in `pyproject.toml` for reproducible runs, and schedule the CLI script to refresh rankings as the network changes.

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

## Learn more

### Core concepts

- [Graph analysis](https://docs.relational.ai/) — building graphs from an ontology and running centrality and community algorithms.
- [PyRel v1 modeling](https://docs.relational.ai/) — concepts, properties, and loading CSV data into relations.

### Modeling reference

- [PageRank and centrality](https://docs.relational.ai/) — influence and connectivity measures, damping, and convergence.

### Deeper dives

- [Querying graph results](https://docs.relational.ai/) — selecting, aliasing, and exporting metric results to DataFrames and CSV.

## Support

- File issues at the RelationalAI templates repository.
