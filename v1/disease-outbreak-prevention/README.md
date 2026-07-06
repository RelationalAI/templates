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
- **Runbook**: `runbook.md` — a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the script itself.
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

For the full concept and property definitions, see `model_setup.py`; `runbook.md` builds them step by step with the RAI skills.

## How it works

Both runners share one model builder, then compute weighted centrality on the resulting graph and rank facilities:

```text
CSV files → model_setup.create_model() → weighted centrality + degree metrics → rank facilities → display / export
```

1. **Shared model setup.** `model_setup.create_model()` builds everything both runners need in one call: the RelationalAI model, the `Facility` node concept, the `FacilityConnection` edge concept, the CSV loads, the derived `risk_weight` (`transfer_volume x contact_intensity`), and the directed, weighted graph that uses `risk_weight` as its edge weight.

2. **Calculate graph metrics.** The Graph API computes weighted degree centrality (summing risk-weighted edges, so the score reflects cumulative transmission risk rather than a raw connection count) alongside indegree and outdegree counts.

3. **Query and rank.** A single query pulls each facility's identity, type, region, centrality score, and in/out connection counts, then sorts descending by centrality to produce the ranked shortlist.

4. **Present results.** The CLI script prints the ranked table, a top-priority breakdown, network summary statistics, and response recommendations. The optional Streamlit app renders the same ranking as an interactive network graph with a filterable table and CSV export.

See `model_setup.py` and `disease_outbreak_prevention_network.py` for the implementation and `runbook.md` for the skill-driven reproduction.

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