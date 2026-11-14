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

- **Model**: `model/__init__.py` — the `Facility` concept, the `FacilityConnection` edge concept (with `transfer_volume`, `contact_intensity`, and a derived `risk_weight`), the directed weighted `Graph` built from them, and the weighted degree centrality, indegree, and outdegree metrics. `rai models deploy --path model` deploys it to your Snowflake account, where each refresh computes the metrics.
- **Query**: `queries/facility_ranking.py` — prints the ranked report from the deployed model.
- **App**: `app.py` — an optional Streamlit web app that queries the deployed model.
- **Runbook**: `runbook.md` — a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the script itself.
- **Sample data**: `data/facilities.csv` and `data/connections.csv`.
- **Outputs**: a ranked facility table, a top-priority breakdown, and network summary statistics printed to stdout; the Streamlit app adds an interactive network graph and CSV export.

## Prerequisites

### Access

- A Snowflake account that has the RAI Native App installed.
- A role that can deploy models, set up once by an account administrator: follow [Set up model deployment](https://private.relational.ai/early-access/model-deploy-setup) (**Try it out**, or **Governed setup** for a shared account). This template has no prescriptive solve, so it needs no PAT setup.
- A Snowflake user that holds that role.

### Tools

- Python >= 3.10
- RelationalAI Python SDK (`relationalai == 2.1.1`).
- Optional: `streamlit`, `plotly`, `numpy` for the interactive app (installed via the `visualization` extra).

## Quickstart

Before you start, install Python 3.10 or later and get a Snowflake role that can deploy models, as described under Access. This template has no prescriptive solve, so it needs no setup beyond that role.

Run these steps from a terminal:

1. **Download the template**

   [Download the ZIP](https://docs.relational.ai/templates/zips/v1/disease-outbreak-prevention.zip), unzip it, and enter the template directory:

   ```bash
   unzip disease-outbreak-prevention.zip
   cd disease-outbreak-prevention
   ```

2. **Create a Python environment**

   Create and activate a virtual environment, then update pip:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   ```

3. **Install the template**

   Install the dependencies pinned in `pyproject.toml`:

   ```bash
   python -m pip install .
   ```

4. **Configure your project**

   Use the configuration builder in [Install and run PyRel](https://docs.relational.ai/get-started/install-and-run-pyrel/#configure-your-project) to create `raiconfig.yaml` in the template directory, with the model role as the connection `role`.

   Then add a `deployment` section. Give each template its own schema pair so two deployed templates never share one; the deploy creates both schemas if they don't exist:

   ```yaml
   deployment:
     role: <MODEL_ROLE>
     public_schema: <DB>.DISEASE_OUTBREAK_PREVENTION              # published views and tables
     identity:
       internal_schema: <DB>.DISEASE_OUTBREAK_PREVENTION_META     # refresh procedures and metadata
     schedules:
       standard:
         interval_s: 0           # refresh only on deploy or on demand
     schedule: standard
   ```

5. **Deploy the model**

   Deploy the model in `model/` to the schemas in `raiconfig.yaml`:

   ```bash
   rai models deploy --path model
   ```

   The deploy waits for the model's first refresh, which computes the weighted degree centrality and the incoming and outgoing connection counts.

   Deploying again without changing the model applies no updates and does not refresh it again; the query reports the latest refresh.

6. **Query the results**

   Print the report from the deployed model:

   ```bash
   python -m queries.facility_ranking
   ```

   ```text
   DISEASE OUTBREAK PREVENTION NETWORK - DEGREE CENTRALITY ANALYSIS
   ...
    rank                    name               type   region  degree_centrality  incoming_connections  outgoing_connections  total_connections
       1        Central Hospital           Hospital Downtown              28.89                     0                     4                  4
       2      Public Health Dept         Government Downtown              28.89                     2                     2                  4
       3    Regional Testing Lab     Testing Center Downtown              24.22                     1                     2                  3
       4  Emergency Response Hub Emergency Services Downtown              20.89                     3                     0                  3
       5         Westside Clinic             Clinic     West              15.78                     2                     2                  4
       6   North Valley Hospital           Hospital    North              12.67                     2                     1                  3
       7 Community Health Center      Community Org    North              11.33                     2                     1                  3
       8     Mobile Testing Unit     Testing Center     West               4.44                     1                     1                  2
       9        Eastside Medical             Clinic     East               2.67                     1                     1                  2
      10  South Community Clinic             Clinic    South               2.67                     1                     1                  2
   ...
     #1 - Central Hospital
          Type: Hospital
          Region: Downtown
          Weighted Degree Centrality: 28.89
          Total Connections: 4 (0 incoming, 4 outgoing)
   ...
     • Total facilities analyzed: 10
     • Average degree centrality: 15.2444
     • Average connections per facility: 3.0
     • Most connected facility: Central Hospital (4 connections)
   ```

   The report ranks every facility, lists the top three priority facilities with their connection breakdown, and prints network summary statistics. The full ranked table and a step-by-step walkthrough are in `runbook.md`.

7. **Tear down the deployment**

   Preview what the teardown removes, then remove it:

   ```bash
   rai models teardown
   rai models teardown --force
   ```

   The first command lists the model's objects without dropping anything; the second drops them and keeps the two schemas.

## Run the Streamlit app

The Streamlit app is an optional interactive view of the same ranking. It only queries the deployed model, so run it after the deploy step of the Quickstart, from the template directory and with the same `raiconfig.yaml`:

```bash
python -m pip install ".[visualization]"
streamlit run app.py
```

The Streamlit app provides:

- Interactive network visualization with directional arrows
- Filterable facility rankings table
- Detailed priority facility analysis
- CSV export functionality

## Template structure

```text
disease-outbreak-prevention/
  model/
    __init__.py                           # deployed model: graph and metrics
  queries/
    facility_ranking.py                   # report from the deployed model
  app.py                                  # optional Streamlit app (queries the deployed model)
  data/
    facilities.csv                        # 10 facilities (id, name, type, region)
    connections.csv                       # 15 directed connections with risk metrics
  README.md                               # this file
  runbook.md                              # step-by-step analyst walkthrough
  pyproject.toml                          # dependencies
```

**Start here**: deploy with `rai models deploy --path model` and run `python -m queries.facility_ranking` for the full ranking end to end, or follow `runbook.md` to rebuild it step by step.

## Sample data

The bundled data is small and illustrative — a 10-facility regional health network, sized to teach the weighted-centrality flow, not to match a specific jurisdiction's network.

- **`data/facilities.csv`** (10 rows) — one row per facility, with `id`, `name`, `type` (hospital, clinic, testing center, government, emergency services), and `region`.
- **`data/connections.csv`** (15 rows) — one row per directed connection, with `from_facility_id`, `to_facility_id`, `transfer_volume`, and `contact_intensity`. The model derives each connection's `risk_weight` as `transfer_volume x contact_intensity`. Every id must reference a valid facility in `facilities.csv`.

## Model overview

The model is a directed, weighted graph with one node concept and one edge concept.

- **Key entities**: `Facility` — a healthcare facility, testing center, or community organization (the graph's node); `FacilityConnection` — a directed transfer link between two facilities, weighted by transmission risk (the graph's edge).
- **Primary identifiers**: `Facility.id` (integer); `FacilityConnection` is identified by its `(from_facility, to_facility)` pair.
- **Important invariants**: `transfer_volume` and `contact_intensity` are non-negative; `risk_weight` is derived, not loaded (`transfer_volume x contact_intensity`); every connection endpoint references an existing `Facility`.

For the full concept and property definitions, see `model/__init__.py`; `runbook.md` builds them step by step with the RAI skills.

## How it works

The deployed model computes weighted centrality on the graph; the report and the app query it and rank facilities:

```text
CSV files → model/ (deployed) → weighted centrality + degree metrics → rank facilities → display / export
```

1. **Deployed model.** `model/__init__.py` declares everything the report and the app need and `rai models deploy --path model` deploys it: the RelationalAI model, the `Facility` node concept, the `FacilityConnection` edge concept, the CSV loads, the derived `risk_weight` (`transfer_volume x contact_intensity`), and the directed, weighted graph that uses `risk_weight` as its edge weight.

2. **Calculate graph metrics.** Each refresh of the deployed model runs the Graph API, which computes weighted degree centrality (summing risk-weighted edges, so the score reflects cumulative transmission risk rather than a raw connection count) alongside indegree and outdegree counts.

3. **Query and rank.** A single query pulls each facility's identity, type, region, centrality score, and in/out connection counts, then sorts descending by centrality to produce the ranked shortlist.

4. **Present results.** `queries/facility_ranking.py` prints the ranked table, a top-priority breakdown, network summary statistics, and response recommendations from the deployed model. The optional Streamlit app queries the same deployed model and renders the ranking as an interactive network graph with a filterable table and CSV export.

See `model/__init__.py` and `queries/facility_ranking.py` for the implementation and `runbook.md` for the skill-driven reproduction.

## Customize this template

Focus on the first changes most users will make.

### Use your own data

- Replace the CSV files in `data/` with your own network, keeping the same column names (or update the loading logic in `model/__init__.py`).
- Make sure every facility referenced in `connections.csv` is a valid id in `facilities.csv`.
- For Snowflake-backed runs, swap the `pd.read_csv(...)` calls in `model/__init__.py` for `model.data(snowflake_table)` calls.

### Tune parameters

- The risk formula is `risk_weight = transfer_volume x contact_intensity`, defined in `model/__init__.py`. Change how the two factors combine (for example, a weighted average) to reweight what "risk" means.
- Switch the graph's centrality metric if you want a different notion of importance (for example, betweenness or eigenvector centrality) in place of weighted degree.

### Extend the model

- Add more risk factors to `FacilityConnection` (for example, disease prevalence or facility bed capacity) and fold them into `risk_weight`.
- Add temporal aspects (for example, seasonal variation in transmission rates) as additional edge properties.

### Scale up / productionize

- Replace the CSV bundle with CDC ingestion from your health-network systems; the graph shape is independent of the load pipeline.
- Pin `relationalai` (this template targets `2.1.1`) and schedule the run as a pipeline step for reproducible re-runs.

## Troubleshooting

<details>
  <summary>Why does authentication/configuration fail?</summary>

- Re-create `raiconfig.yaml` with the configuration builder (Quickstart step 4).
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