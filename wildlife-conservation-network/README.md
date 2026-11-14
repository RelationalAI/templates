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

- **Model**: a single shared ontology — `Organization` nodes and `Partnership` edges — plus the Louvain community and degree-centrality enrichment the graph reasoner writes back. Declared in `model/__init__.py`, which `rai models deploy --path model` deploys to your Snowflake account, where each refresh computes the metrics.
- **Query and app**: `queries/community_report.py` (CLI report) and `app.py` (interactive Streamlit visualization), both querying the deployed model.
- **Runbook**: `runbook.md` — a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the script itself.
- **Sample data**: a small network of conservation organizations and the partnerships between them. See *Sample data* below.
- **Outputs**: a per-organization table of community assignments and metrics, a per-community breakdown, and (in the app) an interactive network graph.

## Prerequisites

### Access

- A Snowflake account that has the RAI Native App installed.
- A role that can deploy models, set up once by an account administrator: follow [Set up model deployment](https://private.relational.ai/early-access/model-deploy-setup) (**Try it out**, or **Governed setup** for a shared account). This template has no prescriptive solve, so it needs no PAT setup.
- A Snowflake user that holds that role.

### Tools

- Python >= 3.10.
- RelationalAI Python SDK (`relationalai == 2.1.1`).
- Streamlit (installed via the optional `.[visualization]` extra) for the interactive app.

## Quickstart

Before you start, install Python 3.10 or later and get a Snowflake role that can deploy models, as described under Access. This template has no prescriptive solve, so it needs no setup beyond that role.

Run these steps from a terminal:

1. **Download the template**

   [Download the ZIP](https://docs.relational.ai/templates/zips/v1/wildlife-conservation-network.zip), unzip it, and enter the template directory:

   ```bash
   unzip wildlife-conservation-network.zip
   cd wildlife-conservation-network
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
     public_schema: <DB>.WILDLIFE_CONSERVATION_NETWORK              # published views and tables
     identity:
       internal_schema: <DB>.WILDLIFE_CONSERVATION_NETWORK_META     # refresh procedures and metadata
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

   The deploy waits for the model's first refresh, which computes the Louvain communities, degree centrality, and partnership counts.

6. **Query the results**

   Print the report from the deployed model:

   ```bash
   python -m queries.community_report
   ```

   ```text
   WILDLIFE CONSERVATION NETWORK - COMMUNITY DETECTION ANALYSIS (LOUVAIN ALGORITHM)
   ...
    community                           name      type          region    focus_species  degree_centrality  partnerships
            1       Serengeti Wildlife Trust       NGO     East Africa        Elephants             0.4545             5
            1  East African Research Station  Research     East Africa Multiple Species             0.3636             4
            1      Amboseli Elephant Project  Research     East Africa        Elephants             0.2727             3
            1    Wildlife Veterinary Network   Medical     East Africa Multiple Species             0.2727             3
            2    Rhino Conservation Alliance       NGO Southern Africa           Rhinos             0.2727             3
            2          Kruger Park Authority   Reserve Southern Africa Multiple Species             0.2727             3
            2   Southern Wildlife Foundation       NGO Southern Africa           Rhinos             0.2727             3
            2          Rhino Protection Unit  Security Southern Africa           Rhinos             0.2727             3
            2      Trans-Border Conservation       NGO Southern Africa Multiple Species             0.1818             2
            3            Big Cats Initiative       NGO     East Africa Lions & Leopards             0.2727             3
            3        Savanna Research Center  Research     East Africa Multiple Species             0.2727             3
            3 Community Conservation Program Community     East Africa Multiple Species             0.2727             3
   ...
     Community 1:
       Size: 4 organizations
       Primary Region: East Africa
       Species Focus: Elephants, Multiple Species
       Organization Types: Research (2), NGO (1), Medical (1)
       Hub Organization: Serengeti Wildlife Trust (centrality: 0.4545)
       Members: Serengeti Wildlife Trust, East African Research Station, Amboseli Elephant Project, Wildlife Veterinary Network
   ...
     • Total organizations: 12
     • Number of communities detected: 3
     • Average community size: 4.0 organizations
     • Average partnerships per organization: 3.2
     • Most connected organization: Serengeti Wildlife Trust (5 partnerships)
     • Total partnerships in network: 19
   ```

   The community ID numbers are arbitrary labels; what matters is which organizations group together. The full report and a step-by-step walkthrough are in `runbook.md`.

7. **Tear down the deployment**

   Preview what the teardown removes, then remove it:

   ```bash
   rai models teardown
   rai models teardown --force
   ```

   The first command lists the model's objects without dropping anything; the second drops them and keeps the two schemas.

## Run the Streamlit app

The Streamlit app is an optional interactive view of the same analysis. It only queries the deployed model, so run it after the deploy step of the Quickstart, from the template directory and with the same `raiconfig.yaml`:

```bash
python -m pip install ".[visualization]"
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
wildlife-conservation-network/
  model/
    __init__.py                      # Deployed model: concepts, graph, and metrics
  queries/
    community_report.py              # CLI report from the deployed model
  app.py                             # Optional Streamlit app (queries the deployed model)
  data/
    organizations.csv                # Conservation organizations (type, region, focus species)
    partnerships.csv                 # Undirected collaboration partnerships between organizations
  README.md                          # this file
  runbook.md                         # analyst-facing paste-testable walkthrough
  pyproject.toml                     # dependencies
```

**Start here**: deploy with `rai models deploy --path model` and run `python -m queries.community_report` for the full CLI analysis end to end, or follow `runbook.md` to rebuild it step by step. The Streamlit app is an optional visualization layer over the same model.

## Sample data

The bundled data is a small, illustrative conservation network — designed to teach community detection on a Snowflake-connected RAI account, not to match a specific program's partnerships.

- **`organizations.csv`** — 12 conservation organizations, each with a `type` (NGO, research station, reserve, and so on), a `region`, and a `focus_species`.
- **`partnerships.csv`** — 19 collaboration partnerships, one row each, given as a pair of organization ids. Partnerships are undirected, so ordering does not matter.

## Model overview

A single ontology (declared in `model/__init__.py`) backs both the report and the app. The graph reasoner writes community and centrality results back onto the network.

- **Key entities**: `Organization` (the network's nodes), `Partnership` (the collaboration edges).
- **Primary identifiers**: integer `id` on `Organization`; `Partnership` is identified by its two endpoint organizations.
- **Important invariants**: every `Partnership` endpoint must reference a valid `Organization` id; the graph is undirected and unweighted, so a partnership counts once regardless of row order.

For the full concept and property definitions, see `model/__init__.py`; `runbook.md` builds them step by step with the RAI skills.

## How it works

```text
CSV files → model/ (deployed) → apply Louvain + degree centrality → analyze communities → display results
```

Both the report and the app query one deployed model. `model/__init__.py` builds the RelationalAI model container, defines the `Organization` concept and loads it from CSV, defines the `Partnership` edges and loads them, constructs the undirected, unweighted graph, and declares the metrics, and `rai models deploy --path model` deploys it. This keeps the CLI report and the Streamlit app in sync, since neither declares or redefines anything.

The graph reasoner then runs two algorithms over that graph. Louvain community detection partitions the network into collaboration clusters by optimizing modularity — iteratively grouping organizations to maximize connections within a cluster and minimize connections between clusters — and writes a community label onto each organization. Degree centrality normalizes each organization's partnership count to a 0-to-1 scale, which makes hubs comparable across clusters of different sizes; the highest-centrality organization inside a community is the one best placed to broker coordination there.

Reading those results back is a query joining the community label, centrality score, and raw partnership count per organization. `queries/community_report.py` renders a per-organization table, a per-community breakdown (size, region, species focus, hub), and network-wide summary statistics. The optional Streamlit app is a visualization layer over the same query: an interactive network graph colored by community, expandable per-cluster detail, and cross-community connector analysis.

See `model/__init__.py` and `queries/community_report.py` for the implementation, and `runbook.md` to reproduce it step by step with the RAI skills.

## Customize this template

Focus on the first changes most users will make.

### Use your own data

- Replace the CSV files in `data/` with your own conservation network, keeping the same column names (or update the logic in `model/__init__.py`).
- Make sure organizations in `partnerships.csv` only reference valid organization ids from `organizations.csv`.
- For Snowflake-backed runs, swap the `pd.read_csv(...)` calls for `data(snowflake_table)` calls in `model/__init__.py`.

### Tune parameters

- The graph is built undirected and unweighted in `model/__init__.py`. Adding edge weights (see *Extend the model*) is the main lever on how the community detection partitions the network.

### Extend the model

- **Add organization properties** — budget, staff size, years active — by adding columns to `organizations.csv` and corresponding properties in `model/__init__.py`.
- **Add weighted partnerships** — weight edges by collaboration intensity (joint projects, shared funding, interaction frequency). Set `weighted=True` in the Graph definition and add weight values to edges.
- **Try different community-detection algorithms** — `graph.label_propagation()` (faster, less accurate on small networks) or `graph.weakly_connected_component()` (completely disconnected groups); experiment to see which best reveals your network's structure.
- **Add temporal analysis** — include partnership start dates to study how communities evolve over time.

### Scale up / productionize

- Replace the `data/` CSV bundle with ingestion from your partnership system of record.
- The bundled network is small; Louvain and degree centrality scale to much larger graphs. Pin dependencies via `pyproject.toml` for reproducible runs.

## Troubleshooting

<details>
  <summary>Why does authentication/configuration fail?</summary>

- Re-create `raiconfig.yaml` with the configuration builder (Quickstart step 4).
- If you have multiple profiles, set `RAI_PROFILE` or switch profiles in your config.

</details>

<details>
  <summary>Why does the deploy fail to connect to the RAI Native App?</summary>

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
  <summary>Why are community IDs different each time I run the report?</summary>

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
