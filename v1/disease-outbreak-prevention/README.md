---
title: "Disease Outbreak Prevention"
description: "Rank the highest-risk facilities in a public health network by weighted degree centrality (connection volume and intensity) to prioritize resource deployment during outbreaks."
experience_level: intermediate
industry: "Healthcare & Life Sciences"
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

- A risk-weighted facility ranking — every facility scored by weighted degree centrality (`transfer_volume x contact_intensity` summed over its edges) — produced by **graph analysis**.
- Per-facility connectivity signals: incoming and outgoing connection counts (indegree and outdegree) alongside the centrality score.
- A prioritized shortlist of the highest-risk facilities to guide where limited outbreak-response resources go first.
- An optional interactive Streamlit view of the same ranking, with a network visualization and CSV export.

Built using **graph analysis** (a directed, weighted graph with `Facility` as the node concept and built-in weighted degree centrality).

## What's included

- **Model**: shared setup in `model_setup.py` — the `Facility` concept, the `FacilityConnection` edge concept (with `transfer_volume`, `contact_intensity`, and a derived `risk_weight`), and the directed weighted `Graph` built from them.
- **Runner**: `disease_outbreak_prevention_network.py` (command-line analysis with detailed output) and `app.py` (optional Streamlit web app), both driven by the same shared model.
- **Sample data**: `data/facilities.csv` and `data/connections.csv`.
- **Outputs**: a ranked facility table, a top-priority breakdown, and network summary statistics printed to stdout; the Streamlit app adds an interactive network graph and CSV export.

## Prerequisites

### Access

- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools

- Python >= 3.10
- RelationalAI Python SDK (`relationalai == 1.11.0`).
- Optional: `streamlit`, `plotly`, `numpy` for the interactive app (installed via the `visualization` extra).

## Quickstart

Follow these steps to run the template with the included sample data.
You can customize the data and model as needed after you have it running end-to-end.

1. Download the ZIP file for this template and extract it:

   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/disease-outbreak-prevention.zip
   unzip disease-outbreak-prevention.zip
   cd disease-outbreak-prevention
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

6. Expected output — a few lines confirm a successful run:

   ```text
   Top facilities by weighted degree centrality (transmission risk):
     1. Central Hospital        260
     2. Public Health Dept      260
     3. Regional Testing Lab    218
     4. Emergency Response Hub  188
   ```

   The full ranked table, top-priority breakdown, and network summary print above and below this; see `runbook.md` for the complete walkthrough.

## Template structure

```text
disease-outbreak-prevention/
  disease_outbreak_prevention_network.py  # main CLI analysis script
  app.py                                  # optional Streamlit web app
  model_setup.py                          # shared model + graph setup (used by both)
  data/
    facilities.csv                        # 10 facilities (id, name, type, region)
    connections.csv                       # 15 directed connections with risk metrics
  README.md                               # this file
  runbook.md                              # step-by-step analyst walkthrough
  pyproject.toml                          # dependencies
```

**Start here**: run `python disease_outbreak_prevention_network.py` for the full ranking end to end, or follow `runbook.md` to rebuild it step by step.

## Sample data

The bundled data is small and illustrative — a 10-facility regional health network, sized to teach the weighted-centrality flow, not to match a specific jurisdiction's network.

- **`data/facilities.csv`** (10 rows) — one row per facility, with `id`, `name`, `type` (hospital, clinic, testing center, government, emergency services), and `region`.
- **`data/connections.csv`** (15 rows) — one row per directed connection, with `from_facility_id`, `to_facility_id`, `transfer_volume`, and `contact_intensity`. The model derives each connection's `risk_weight` as `transfer_volume x contact_intensity`. Every id must reference a valid facility in `facilities.csv`.

## Model overview

The model is a directed, weighted graph with one node concept and one edge concept.

- **Key entities**: `Facility` (graph node) and `FacilityConnection` (graph edge).
- **Primary identifiers**: `Facility.id` (integer); `FacilityConnection` is identified by its `(from_facility, to_facility)` pair.
- **Important invariants**: `transfer_volume` and `contact_intensity` are non-negative; `risk_weight` is derived, not loaded (`transfer_volume x contact_intensity`); every connection endpoint references an existing `Facility`.

### Concepts

**`Facility`** — a healthcare facility, testing center, or community organization; the graph's node concept.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | Integer | Yes | `id` from `data/facilities.csv` |
| `name` | String | No | Human-readable name |
| `type` | String | No | Hospital / clinic / testing center / government / emergency services |
| `region` | String | No | Used for grouping and layout |

**`FacilityConnection`** — a directed transfer link between two facilities; the graph's edge concept, weighted by transmission risk.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `from_facility` | Relationship | Yes | Source `Facility` (part of identity) |
| `to_facility` | Relationship | Yes | Destination `Facility` (part of identity) |
| `transfer_volume` | Float | No | Patient transfer volume from `data/connections.csv` |
| `contact_intensity` | Float | No | Contact intensity from `data/connections.csv` |
| `risk_weight` | Float | No | Derived: `transfer_volume x contact_intensity`; the graph edge weight |

### Relationships

- `FacilityConnection.from_facility -> Facility` and `FacilityConnection.to_facility -> Facility` — the directed transfer edge; `risk_weight` is its weight in the graph.

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

Focus on the first changes most users will make.

### Use your own data

- Replace the CSV files in `data/` with your own network, keeping the same column names (or update the loading logic in `model_setup.py`).
- Make sure every facility referenced in `connections.csv` is a valid id in `facilities.csv`.
- For Snowflake-backed runs, swap the `pd.read_csv(...)` calls in `model_setup.py` for `model.data(snowflake_table)` calls.

### Tune parameters

- The risk formula is `risk_weight = transfer_volume x contact_intensity`, defined in `model_setup.py`. Change how the two factors combine (for example, a weighted average) to reweight what "risk" means.
- Switch the graph's centrality metric if you want a different notion of importance (for example, betweenness or eigenvector centrality) in place of weighted degree.

### Extend the model

- Add more risk factors to `FacilityConnection` (for example, disease prevalence or facility bed capacity) and fold them into `risk_weight`.
- Add temporal aspects (for example, seasonal variation in transmission rates) as additional edge properties.

### Scale up / productionize

- Replace the CSV bundle with CDC ingestion from your health-network systems; the graph shape is independent of the load pipeline.
- Pin `relationalai` (this template targets `1.11.0`) and schedule the run as a pipeline step for reproducible re-runs.

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
  <summary>Why is the Streamlit app missing dependencies?</summary>

- Install the visualization extra: `python -m pip install .[visualization]` (adds `streamlit`, `plotly`, `numpy`).

</details>

## Learn more

### Core concepts

- [PyRel v1 query language](https://docs.relational.ai/) — `where(...)` / `select(...)` and result extraction.
- [Concepts and relationships](https://docs.relational.ai/) — modeling entities and edges like `Facility` and `FacilityConnection`.

### Reasoner reference

- [Graph reasoner](https://docs.relational.ai/) — node-concept and edge-concept patterns, degree centrality, and other graph algorithms.

### CLI / SDK guides

- [RelationalAI setup](https://docs.relational.ai/) — `rai init`, profiles, and `raiconfig.yaml`.

## Support

- File issues at the RelationalAI templates repository.