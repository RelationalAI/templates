---
title: "Disease Outbreak Prevention"
description: "Use weighted degree centrality to identify the highest-risk healthcare facilities in a public health network, considering both connection volume and intensity, to prioritize resource deployment during disease outbreaks."
experience_level: intermediate
industry: Healthcare
featured: true
reasoning_types:
  - Graph
tags:
  - graph-analytics
  - degree-centrality
  - public-health
sidebar:
  order: 3
---

## What this template is for

During a disease outbreak, public health officials must quickly decide where to deploy limited resources like vaccines, testing equipment, and emergency response teams. This template demonstrates how to use **weighted degree centrality** — a graph algorithm that combines connectivity with transmission risk metrics — to identify the most strategically important healthcare facilities.

By analyzing a network of hospitals, clinics, testing centers, and community organizations with weighted connections based on patient transfer volumes and contact intensity, this template helps you prioritize facilities that pose the greatest cumulative risk. These high-risk facilities act as critical hubs in the health network, making them ideal locations for maximum resource reach and rapid outbreak containment during an outbreak response.

## Who this is for

- **Intermediate users** who want to learn weighted degree centrality with a real-world epidemiological use case
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

- Python >= 3.10
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

## Quickstart

Follow these steps to run the template with the included sample data.
You can customize the data and model as needed after you have it running end-to-end.

1. Download the ZIP file for this template and extract it:

   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/disease-outbreak-prevention.zip
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

Use RelationalAI's Graph API to define weighted centrality metrics:

```python
# Weighted degree centrality (sum of risk-weighted edge weights)
degree_centrality = graph.degree_centrality()

# Incoming edges (indegree count)
incoming_edges = graph.indegree()

# Outgoing edges (outdegree count)
outgoing_edges = graph.outdegree()
```

The weighted degree centrality incorporates the risk weights (transfer_volume × contact_intensity) from each edge, providing a measure of cumulative transmission risk rather than just connectivity count.

### 3. Query and Rank Facilities

Query the graph to retrieve all metrics and rank facilities:

```python
from relationalai.semantics import where, Float, Integer

# Create variable references
facility = graph.Node.ref("facility")
centr_score = Float.ref("centr_score")
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

**Use your own data:**

- Replace the CSV files in the `data/` directory with your own network, keeping the same column names (or update the logic in disease_outbreak_prevention_network.py).
- Make sure that the facilities in **connections.csv** only references valid facility IDs.

**Extend the model:**

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