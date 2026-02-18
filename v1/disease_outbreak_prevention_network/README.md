---
title: "Disease Outbreak Prevention Network"
description: "Use weighted degree centrality to identify the highest-risk healthcare facilities in a public health network, considering both connection volume and intensity, to prioritize resource deployment during disease outbreaks."
experience_level: beginner
industry: Healthcare
reasoning_types:
  - Graph
tags:
  - graph-analytics
  - degree-centrality
  - public-health
---

## What this template is for

During a disease outbreak, public health officials must quickly decide where to deploy limited resources like vaccines, testing equipment, and emergency response teams. This template demonstrates how to use **weighted degree centrality** — a graph algorithm that combines connectivity with transmission risk metrics — to identify the most strategically important healthcare facilities.

By analyzing a network of hospitals, clinics, testing centers, and community organizations with weighted connections based on patient transfer volumes and contact intensity, this template helps you prioritize facilities that pose the greatest cumulative risk. These high-risk facilities act as critical hubs in the health network, making them ideal locations for maximum resource reach and rapid outbreak containment during an outbreak response.

## Who this is for
- **Beginners** who want to learn weighted degree centrality with a real-world epidemiological use case
- **Data scientists** new to RelationalAI looking for a simple graph analytics example
- **Public health analysts** planning outbreak response strategies
- **Healthcare network planners** optimizing resource allocation

## What you'll build

- Load a public health network with 10 facilities and 15 directed connections with transfer volume and contact intensity metrics
- Use RelationalAI's Graph API to model the healthcare network with weighted edges
- Calculate risk-weighted degree centrality for each facility based on connection weights (transfer_volume × contact_intensity)
- Track incoming and outgoing connections (indegree and outdegree)
- Rank facilities by their cumulative risk (weighted degree centrality scores)
- Identify top priority facilities for resource deployment
- Generate a detailed prioritized list to guide outbreak response decisions

This template uses **RelationalAI's graph modeling** capabilities with the Graph class to represent the network, and built-in weighted graph algorithms to compute degree centrality that accounts for transmission risk factors.

## What's included

- **Shared model setup**: `model_setup.py` - Common model configuration and graph creation (used by both scripts)
- **Command-line script**: `disease_outbreak_prevention_network.py` - CLI analysis script with detailed output
- **Interactive app**: `app.py` - Streamlit web application with visualizations and interactive analysis
- **Data**: `data/facilities.csv` and `data/connections.csv`

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
   curl -O https://private.relational.ai/templates/zips/v1/disease_outbreak_prevention_network.zip
   unzip disease_outbreak_prevention_network.zip
   cd disease_outbreak_prevention_network
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
   python disease_outbreak_prevention_network.py
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
   - Filterable facility rankings table
   - Detailed priority facility analysis
   - CSV export functionality

6. **Expected output**

   ```
   ====================================================================================================
   DISEASE OUTBREAK PREVENTION NETWORK - DEGREE CENTRALITY ANALYSIS
   ====================================================================================================

   Facilities ranked by degree centrality (most connected first):

   Weighted Degree Centrality: Sum of risk-weighted connections (transfer_volume × contact_intensity)
   Higher scores indicate greater cumulative risk and more critical facilities for outbreak response coordination

   These facilities should receive priority for:
   • Vaccine and medical supply deployment
   • Testing station setup
   • Emergency response team positioning

   ----------------------------------------------------------------------------------------------------
   rank                    name               type   region  degree_centrality  incoming_connections  outgoing_connections  total_connections
      1        Central Hospital           Hospital Downtown                178.00                     0                     4                  4
      2      Public Health Dept         Government Downtown                173.00                     2                     2                  4
      3         Westside Clinic             Clinic     West                136.00                     2                     2                  4
      4      Regional Testing Lab     Testing Center Downtown                130.00                     1                     2                  3
      5   North Valley Hospital           Hospital    North                 93.00                     2                     1                  3
      6 Community Health Center      Community Org    North                 85.00                     2                     1                  3
      7 Emergency Response Hub Emergency Services Downtown                 83.00                     3                     0                  3
      8        Eastside Medical             Clinic     East                 42.00                     1                     1                  2
      9     Mobile Testing Unit     Testing Center     West                 41.00                     1                     1                  2
      10  South Community Clinic             Clinic    South                 36.00                     1                     1                  2
   ----------------------------------------------------------------------------------------------------

   🎯 TOP 3 PRIORITY FACILITIES FOR IMMEDIATE RESOURCE DEPLOYMENT:

   #1 - Central Hospital
         Type: Hospital
         Region: Downtown
         Weighted Degree Centrality: 178.00
         Total Connections: 4 (0 incoming, 4 outgoing)

   #2 - Public Health Dept
         Type: Government
         Region: Downtown
         Weighted Degree Centrality: 173.00
         Total Connections: 4 (2 incoming, 2 outgoing)

   #3 - Westside Clinic
         Type: Clinic
         Region: West
         Weighted Degree Centrality: 136.00
         Total Connections: 4 (2 incoming, 2 outgoing)

      📊 NETWORK SUMMARY:
      • Total facilities analyzed: 10
      • Average degree centrality: 105.75
      • Average connections per facility: 3.0
      • Most connected facility: Central Hospital (4 connections)
   ✅ Analysis complete!
   ```

## Template structure

```text
.
├─ README.md                                        # this file
├─ pyproject.toml                                   # dependencies
├─ model_setup.py                                   # shared model configuration (used by both scripts)
├─ disease_outbreak_prevention_network.py           # command-line analysis script
├─ app.py                                           # interactive Streamlit web app
└─ data/
   ├─ facilities.csv                                # 10 healthcare facilities
   └─ connections.csv                               # 15 network connections
```

**Start here**:
- For command-line analysis: Run `python disease_outbreak_prevention_network.py`
- For interactive web app: Run `streamlit run app.py`

## Sample data

The sample data represents a simplified public health network in a metropolitan area:

- **facilities.csv**: 10 facilities including hospitals, clinics, testing centers, community organizations, government agencies, and emergency services. Each has a unique ID, name, type, and geographic region.
- **connections.csv**: 15 directed connections representing relationships like patient referral pathways, data sharing agreements, and coordination partnerships. Each connection includes transfer volume (1-10 scale) and contact intensity (1-10 scale) metrics that are multiplied together to create the risk weight for each connection.

The network is intentionally small (10 nodes, 15 edges) to make it easy to understand and verify the centrality calculations manually.

## Model overview

This model represents a public health network as a directed graph where facilities are nodes and connections are edges weighted by transmission risk.

- **Key entities**: `Facility` (healthcare facilities) with `FacilityConnection` relationships
- **Primary identifiers**: Facility ID (integer)
- **Graph structure**: Directed, weighted graph using RelationalAI's Graph API, with edges weighted by risk factors

### Facility Concept

The `Facility` concept represents healthcare facilities, testing centers, and community organizations in the network.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | Integer | Yes | Unique facility identifier from `data/facilities.csv` |
| `name` | String | No | Facility name (e.g., "Central Hospital") |
| `type` | String | No | Category: Hospital, Clinic, Testing Center, Community Org, Government, Emergency Services |
| `region` | String | No | Geographic region: Downtown, North, South, East, West |

### Facility Connection Relationship

The `FacilityConnection` relationship represents directed connections between facilities (patient referrals, data sharing, coordination partnerships) with transmission risk metrics.

| Property | Type | Notes |
|---|---|---|
| `from_facility` | Facility | Source facility in the connection |
| `to_facility` | Facility | Target facility in the connection |
| `transfer_volume` | Float | Volume of patient transfers, samples, or resources (1-10 scale) |
| `contact_intensity` | Float | Frequency/intensity of contacts between facilities (1-10 scale) |
| `risk_weight` | Float | Calculated as transfer_volume × contact_intensity; used to weight edges in the graph |

### Graph Metrics

The template calculates three key metrics using RelationalAI's Graph API:

| Metric | Type | Description |
|---|---|---|
| `degree_centrality` | Float | Weighted degree centrality: sum of edge weights (risk_weight values) for all connections. Higher values indicate greater cumulative transmission risk |
| `incoming_connections` | Integer | Indegree: number of facilities that connect TO this facility |
| `outgoing_connections` | Integer | Outdegree: number of facilities this facility connects TO |

## How it works

The template follows this flow:

```text
CSV files → model_setup.create_model() → Calculate metrics → Analyze strategic priorities → Display results
```

### 1. Shared Model Setup

Both the CLI script and Streamlit app use the same model setup from `model_setup.py`:

```python
from model_setup import create_model

# Create the model, concepts, relationships, and graph (all in one call)
model, graph, Facility = create_model()
```

The `create_model()` function handles:
- Creating the RelationalAI model container
- Defining the `Facility` concept with all properties
- Loading facilities from CSV
- Defining the `FacilityConnection` concept for edges with transfer_volume, contact_intensity, and risk_weight properties
- Loading connections from CSV with their risk metrics
- Calculating risk_weight as transfer_volume × contact_intensity for each connection
- Creating the directed, weighted graph using risk_weight as edge weights
- Returning all components for use in analysis

### 2. Calculate Graph Metrics

Use RelationalAI's Graph API to compute weighted centrality metrics:

```python
# Calculate weighted degree centrality (sum of risk-weighted edge weights)
degree_centrality = graph.degree_centrality()

# Calculate incoming edges (indegree count)
incoming_edges = graph.indegree()

# Calculate outgoing edges (outdegree count)
outgoing_edges = graph.outdegree()
```

The weighted degree centrality incorporates the risk weights (transfer_volume × contact_intensity) from each edge, providing a measure of cumulative transmission risk rather than just connectivity count.

### 3. Query and Rank Facilities

Query the graph to retrieve all metrics and rank facilities:

```python
from relationalai.semantics import where, Float, Integer

# Create variable references
facility = graph.Node.ref("facility")
centr_score = Float.ref("d_score")
in_edges = Integer.ref("in_edges")
out_edges = Integer.ref("out_edges")

# Query the graph
results = where(
    degree_centrality(facility, centr_score),
    incoming_edges(facility, in_edges),
    outgoing_edges(facility, out_edges)
).select(
    facility.id,
    facility.name,
    facility.type,
    facility.region,
    centr_score.alias("degree_centrality"),
    in_edges.alias("incoming_connections"),
    out_edges.alias("outgoing_connections")
).to_df()

# Sort by degree centrality (descending)
results = results.sort_values("degree_centrality", ascending=False)
results.insert(0, "rank", range(1, len(results) + 1))
```

### 4. CLI Script Analysis

The `disease_outbreak_prevention_network.py` script displays:
- A ranked table of all facilities with their metrics
- Detailed breakdown of the top 3 priority facilities
- Network-wide summary statistics
- Actionable recommendations for outbreak response

### 5. Interactive Streamlit App

The included `app.py` provides an interactive web interface using the same shared model:

```python
import streamlit as st
from model_setup import create_model

# Load the same model and query results
model, graph, Facility = create_model()
results = get_results(model, graph, Facility)
```

The Streamlit app features:
- **Interactive network graph**: Directed edges with arrows, hover for facility details, region-based layout
- **Filterable rankings table**: Filter by facility type and region, download as CSV
- **Priority facility analysis**: Expandable sections with detailed metrics and role analysis
- **Summary statistics**: Sidebar with key network metrics

## Customize this template

### Use your own data

- Replace the CSV files in the `data/` directory with your own network, keeping the same column names (or update the logic in disease_outbreak_prevention_network.py).
- Make sure that the facilities in **connections.csv** only references valid facility IDs.


### Extend the model

**Add more risk factors**: The template already uses weighted connections (transfer_volume × contact_intensity). You could extend this by:
- Adding additional risk metrics to connections (e.g., disease prevalence, facility bed capacity)
- Creating a more sophisticated risk formula (e.g., weighted average of multiple factors)
- Adding temporal aspects (e.g., seasonal variation in transmission rates)

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