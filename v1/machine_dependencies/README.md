---
title: "Machine Dependencies"
description: "Analyze machine dependency networks through shared technician qualifications to identify clusters and bottleneck machines."
featured: false
experience_level: intermediate
industry: Manufacturing
reasoning_types:
  - Graph
tags:
  - graph-analytics
  - connected-components
  - betweenness-centrality
  - manufacturing
  - maintenance
---

# Machine Dependencies

## What this template is for

This template uses **graph analysis** to analyze machine dependency networks through shared technician qualifications, identifying clusters and bottleneck machines.

Manufacturing facilities rely on specialized technicians to maintain equipment. When the same technician is qualified for multiple machines, those machines share a maintenance dependency -- if the technician is unavailable, all dependent machines are affected. Understanding these hidden dependency chains is critical for risk management.

This template uses RelationalAI's graph reasoner to build an undirected dependency graph where machines are connected if they share a qualified technician. Two graph algorithms reveal the dependency structure:

1. **Weakly Connected Components** -- Identify clusters of machines that are transitively linked through shared technicians. A failure or scheduling conflict in one cluster cannot propagate to another.
2. **Betweenness Centrality** -- Rank machines by how many dependency paths pass through them. High-betweenness machines are bottlenecks whose disruption affects the most other machines.

## Who this is for

- **Intermediate users** who want to learn graph analysis on relational data
- **Manufacturing operations teams** assessing technician-dependency risk
- **Maintenance planners** identifying scheduling bottlenecks

## What you'll build

- A data model with machines, technicians, and qualifications loaded from CSV
- An undirected graph connecting machines through shared technician qualifications (self-join pattern)
- Weakly connected component analysis to identify dependency clusters
- Betweenness centrality ranking to find bottleneck machines
- A critical machine report combining graph position with failure probability

## What's included

- `machine_dependencies.py` -- Main script defining the model, graph, and analysis
- `data/machines.csv` -- 8 machines across 3 facilities with failure probability and criticality
- `data/technicians.csv` -- 5 technicians with skill levels
- `data/qualifications.csv` -- 12 technician-to-machine qualification links
- `pyproject.toml` -- Python package configuration with dependencies

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools
- Python >= 3.10

## Quickstart

1. Download ZIP:
   ```bash
   curl -O https://private.relational.ai/templates/zips/v1/machine_dependencies.zip
   unzip machine_dependencies.zip
   cd machine_dependencies
   ```
   > [!TIP]
   > You can also download the template ZIP using the "Download ZIP" button at the top of this page.

2. Create venv:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   ```

3. Install:
   ```bash
   python -m pip install .
   ```

4. Configure:
   ```bash
   rai init
   ```

5. Run:
   ```bash
   python machine_dependencies.py
   ```

## Template structure

```text
.
├── README.md
├── pyproject.toml
├── machine_dependencies.py
└── data/
    ├── machines.csv
    ├── technicians.csv
    └── qualifications.csv
```

## How it works

This section walks through the highlights in `machine_dependencies.py`.

```text
CSV files --> Define Machine + Technician + Qualification concepts --> Build undirected graph --> WCC clusters --> Betweenness centrality --> Display results
```

### 1. Load Ontology

Machine, Technician, and Qualification concepts are loaded from CSV. Each qualification links a technician to a specific machine:

```python
Machine = model.Concept("Machine", identify_by={"id": String})
Qualification = model.Concept("Qualification", identify_by={"id": String})
Qualification.technician = model.Relationship(f"{Qualification} for {Technician}")
Qualification.machine = model.Relationship(f"{Qualification} covers {Machine}")
```

### 2. Build Graph via Self-Join

The graph connects machines that share a qualified technician. This uses a self-join on qualifications where two different qualification records reference the same technician but different machines:

```python
dep_graph = Graph(model, directed=False, weighted=False, node_concept=Machine, aggregator="sum")

m1, m2 = Machine.ref(), Machine.ref()
q1, q2 = Qualification.ref(), Qualification.ref()
tech = Technician.ref()

model.where(
    q1.technician(tech), q2.technician(tech),
    q1.machine(m1), q2.machine(m2),
    m1.id < m2.id,
).define(dep_graph.Edge.new(src=m1, dst=m2))
```

### 3. Identify Clusters

`weakly_connected_component()` groups machines into dependency clusters. Machines in the same cluster are transitively linked through shared technicians.

### 4. Find Bottlenecks

`betweenness_centrality()` ranks each machine by how many shortest paths in the dependency network pass through it. High-betweenness machines are structural bottlenecks.

## Customize this template

- **Add edge types**: Include facility co-location or shared parts as additional edge criteria.
- **Weight edges**: Use the number of shared technicians as edge weight for weighted graph analysis.
- **Combine with rules**: Use the manufacturing_compliance template's rule flags (e.g., is_high_risk) to filter or annotate graph results.
- **Use your own data**: Replace CSVs in `data/` with your own machine and qualification data, keeping the same column names.

## Troubleshooting

<details>
<summary><code>ModuleNotFoundError</code></summary>

Make sure you activated the virtual environment and ran `python -m pip install .` to install all dependencies listed in `pyproject.toml`.
</details>

<details>
<summary>Connection or authentication errors</summary>

Run `rai init` to configure your Snowflake connection. Verify that the RAI Native App is installed and your user has the required permissions.
</details>
