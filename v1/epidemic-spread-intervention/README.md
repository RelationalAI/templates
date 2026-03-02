---
title: "Epidemic Spread Intervention"
description: "Use multi-layer graph reasoning to identify super-spreaders, bridge individuals, and transmission clusters in a population contact network, prioritizing people for vaccination and isolation to contain epidemic spread."
experience_level: intermediate
industry: Public Health
reasoning_types:
  - Graph
tags:
  - graph-analytics
  - eigenvector-centrality
  - betweenness-centrality
  - community-detection
  - public-health
---

## What this template is for

During an epidemic, public health officials face a critical challenge: limited resources (vaccines, isolation capacity, contact tracers) must be deployed where they will have the greatest impact on slowing spread. This template demonstrates how to use **three complementary graph algorithms** — Eigenvector Centrality, Betweenness Centrality, and Louvain Community Detection — to identify the highest-priority individuals for intervention.

What makes this template distinctive is its **multi-layer exposure graph**: rather than modeling only direct person-to-person contacts, it also captures indirect co-location risk (people who visit the same places) and fuses both layers into a single weighted network. Edge weights incorporate individual susceptibility (vaccination level and comorbidity), so the graph reflects real-world transmission potential rather than just social proximity.

By analyzing this fused exposure network, this template helps you:
- **Identify super-spreaders** whose connections are themselves highly connected, amplifying their influence across multiple social layers (Eigenvector Centrality)
- **Find bridge individuals** who sit on the shortest paths between otherwise-separate communities — removing or vaccinating them fractures spread routes (Betweenness Centrality)
- **Discover tight-knit transmission clusters** where disease can circulate rapidly before spilling over to the broader population (Louvain Community Detection)

## Who this is for

- **Intermediate users** ready to learn multi-metric graph analysis with a realistic epidemiological model
- **Data scientists** working with public health, contact tracing, or network epidemiology
- **Epidemiologists and public health analysts** prioritizing vaccine deployment and isolation strategies
- **Healthcare researchers** studying how disease spreads through multi-layer social networks

## What you'll build

- Load a contact network with 22 people, 10 locations, 42 direct contacts, and 48 location visits from CSV files
- Derive individual susceptibility from vaccination level and comorbidity score
- Build a two-layer exposure network: Layer 1 (direct contacts with transmission risk) and Layer 2 (co-location contacts derived from shared venue visits)
- Fuse both layers into a single weighted exposure graph, discounting co-location risk relative to direct contact
- Apply Eigenvector Centrality to rank super-spreaders with amplified multi-layer influence
- Apply Betweenness Centrality to rank bridge individuals whose removal fractures spread pathways
- Apply Louvain Community Detection to identify tight-knit transmission clusters for targeted intervention
- Generate ranked tables for each metric to guide resource deployment decisions

This template uses **RelationalAI's advanced graph algorithms** including Eigenvector Centrality (iterative power-method algorithm), Betweenness Centrality (all-pairs shortest path analysis), and Louvain Community Detection (modularity-optimizing clustering).

## What's included

- **Shared model setup**: `model_setup.py` — Multi-layer model configuration, concept definitions, and exposure graph construction (used by both scripts)
- **Command-line script**: `epidemic-spread-intervention.py` — CLI analysis script with three ranked result tables
- **Interactive app**: `app.py` — Streamlit web application with network visualization and interactive priority analysis
- **Data**: `data/people.csv`, `data/locations.csv`, `data/direct_contacts.csv`, `data/visits.csv`

## Prerequisites

- Python >= 3.10
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

## Quickstart

Follow these steps to run the template with the included sample data.
You can customize the data and model as needed after you have it running end-to-end.

1. Download the ZIP file for this template and extract it:

   ```bash
   curl -O https://private.relational.ai/templates/zips/v1/epidemic-spread-intervention.zip
   unzip epidemic-spread-intervention.zip
   cd epidemic-spread-intervention
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
   python epidemic-spread-intervention.py
   ```

   **Option B: Interactive Streamlit app**

   ```bash
   # Install additional dependencies for visualization
   python -m pip install .[visualization]

   # Launch the interactive app
   streamlit run app.py
   ```

   The Streamlit app provides:
   - Interactive exposure network visualization with nodes colored by Louvain community
   - Ranked super-spreader table (Eigenvector Centrality)
   - Ranked bridge individual table (Betweenness Centrality)
   - Transmission cluster breakdown by community
   - CSV export functionality

## How it works

The template follows this flow:

```text
CSV files → model_setup.create_model() → Build exposure graph → Run graph algorithms → Rank & display results
```

### 1. Shared Model Setup

Both the CLI script and Streamlit app use the same model setup from `model_setup.py`:

```python
from model_setup import create_model

# Create the model, all concepts, and the fused exposure graph
*_, exposure_graph = create_model()
```

The `create_model()` function handles:
- Creating the RelationalAI model container
- Defining `Person`, `Location`, `DirectContact`, and `Visit` concepts with all properties
- Loading all four CSV files
- Deriving individual `base_susceptibility` from vaccination level and comorbidity score
- Computing `DirectContact.transmission_risk` (Layer 1) and `ColocationContact.transmission_risk` (Layer 2)
- Fusing both layers into `ExposureEdge` with combined weights
- Building the weighted, undirected `exposure_graph`
- Returning all components for use in analysis

### 2. Derive Individual Susceptibility

Before building the graph, each person's susceptibility is computed from their clinical profile:

```python
# base_susceptibility = (1 - vaccination_level) * (1 + comorbidity_score)
define(Person.base_susceptibility == (1 - Person.vaccination_level) * (1 + Person.comorbidity_score))
```

A fully vaccinated person (`vaccination_level=1.0`) has susceptibility 0 and cannot be infected. Higher comorbidity amplifies susceptibility, scaling every incoming edge weight.

### 3. Build the Multi-Layer Exposure Graph

**Layer 1 — Direct Contact:**

```python
# transmission_risk = weekly_frequency * (duration_hours) * recipient_susceptibility
define(DirectContact.transmission_risk ==
       DirectContact.frequency * (DirectContact.duration / 60) * DirectContact.person_b.base_susceptibility)
```

**Layer 2 — Co-location Contact:**

Co-location contacts are derived automatically from shared venue visits (a 2-hop join: Person → Location → Person):

```python
# transmission_risk = sum over shared locations of:
#   weekly_visits[p1,loc] * weekly_visits[p2,loc] * density_score[loc] * (1 - ventilation_score[loc])
```

**Fused Exposure Edge:**

Both layers are merged into a single edge weight using a 0.6 discount factor for co-location risk:

```text
weight = direct_transmission_risk + 0.6 × colocation_transmission_risk
```

Only edges with `weight > 0.0` are included in the graph.

### 4. Run Graph Algorithms

```python
# Eigenvector Centrality: super-spreaders with multi-layer influence
eigenvector_centrality = exposure_graph.eigenvector_centrality()

# Betweenness Centrality: bridge individuals connecting separate communities
betweenness_centrality = exposure_graph.betweenness_centrality()

# Louvain Community Detection: tight-knit transmission clusters
louvain_communities = exposure_graph.louvain()
```

### 5. Query and Display Results

```python
from relationalai.semantics import where, Integer, Float

person = exposure_graph.Node.ref("person")
eig_score = Float.ref("eig_score")

eig_df = where(
    eigenvector_centrality(person, eig_score)
).select(
    person.person_id,
    eig_score.alias("eigenvector_score")
).to_df().sort_values("eigenvector_score", ascending=False)
```

## Customize this template

**Use your own data:**

- Replace the CSV files in the `data/` directory with your own contact network, keeping the same column names (or update `model_setup.py` to match).
- `people.csv` must include `person_id`, `vaccination_level` (0–1), and `comorbidity_score` (0+).
- `locations.csv` must include `location_id`, `density_score`, and `ventilation_score` (0–1, where 1.0 = perfect ventilation).
- `direct_contacts.csv` must include `person_a`, `person_b`, `weekly_frequency`, and `duration_minutes`.
- `visits.csv` must include `person_id`, `location_id`, and `weekly_visits`.

**Extend the model:**

- **Adjust the co-location discount factor**: Change the `0.6` multiplier in `model_setup.py` to weight co-location risk more or less relative to direct contact.

- **Modify the susceptibility formula**: Add additional clinical factors (e.g., age, immune status) to `base_susceptibility`.

- **Try additional algorithms**:

  - `graph.pagerank()` — Identify individuals where spread naturally concentrates over many iterations
  - `graph.degree_centrality()` — Find individuals with the highest total exposure weight across all connections
  - `graph.weakly_connected_components()` — Identify disconnected sub-populations that require separate containment strategies

- **Model directed spread**: Switch to `Graph(..., directed=True)` to model asymmetric transmission (e.g., supershedder → susceptible only, not the reverse).

**Add temporal analysis**: Include date ranges or time-varying contact frequencies to model outbreak dynamics across phases.

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
  <summary>Why does Eigenvector Centrality not converge?</summary>

- Your exposure graph might have disconnected components or an unusual structure.
- Check that your graph has valid edges (weight > 0.0) and nodes.
- Ensure vaccination levels are between 0 and 1 so susceptibility values are non-negative.

</details>

<details>
  <summary>How do I choose which metric to act on first?</summary>

- **Eigenvector Centrality**: Prioritize for vaccination — stops spread at the most influential nodes in the network
- **Betweenness Centrality**: Prioritize for isolation/quarantine — cutting these individuals fragments the spread network fastest
- **Louvain Communities**: Prioritize for cluster-level interventions (localized quarantine zones, targeted testing campaigns)
- For maximum impact, cross-reference all three: individuals who rank highly across multiple metrics are the highest-priority intervention targets

</details>

<details>
  <summary>Why are some people missing from results?</summary>

- Individuals with no exposure edges (weight = 0 for all connections) are excluded from the graph.
- This happens when a person is fully vaccinated (`vaccination_level=1.0`) and has susceptibility 0, removing them as a transmission target.
- They may also be missing from `direct_contacts.csv` and `visits.csv`.

</details>
