---
title: "Machine Maintenance"
description: "A multi-reasoner template that chains querying, graph analysis, rules-based classification, and prescriptive optimization to diagnose plant performance, surface producibility bottlenecks, classify machine risk, and schedule preventive maintenance under technician-coverage constraints."
featured: false
experience_level: intermediate
industry: "Manufacturing"
reasoning_types:
  - Graph
  - Rules-based
  - Prescriptive
tags:
  - Multi-Reasoner
  - Chained Reasoning
  - Scheduling
  - Maintenance
  - Manufacturing
  - OEE
  - Risk Classification
  - Bottleneck Analysis
---

## What this template is for

Manufacturing reliability teams have to decide **which machines to maintain, when, and with which technician** — under a fixed maintenance-bay limit and a thin bench of qualified technicians. Get it wrong and a critical machine fails unplanned, or a plant's only on-site specialist becomes a single point of failure. The hard part is that no single view answers the question: plant OEE shows where output is lost but not what will fail next, failure predictions rank risk but ignore who can do the work, and a feasible schedule can still hide a concentration risk that one resignation would expose.

This template works the problem end to end on a 50-machine, 3-plant, 12-period operation. **It chains four RelationalAI reasoners over one ontology — querying to diagnose plant performance, rules to classify machine risk, graph analysis to find producibility bottlenecks, and prescriptive optimization to schedule maintenance and stress-test it.** Each stage writes its findings back to the model, so the next stage builds on what the last one learned.

## Who this is for

- Data scientists and analysts learning to chain multiple RelationalAI reasoners over one ontology
- Manufacturing and reliability teams building preventive-maintenance and risk-classification workflows
- Anyone wanting a worked multi-reasoner example on a realistic operational dataset

Readers are assumed comfortable reading Python; domain terms (OEE, betweenness centrality, the maintenance horizon) are explained inline.

## What you'll build

- An ontology over machines, technicians, qualifications, products, production runs, downtime events, failure predictions, and machine-product capabilities
- Querying-stage metrics: OEE by plant, downtime by fault and plant, failure ranking, waste rates, technician coverage
- A betweenness-centrality bottleneck ranking over the machine-product graph
- A per-machine `risk_tier` derived from business rules
- A preventive-maintenance schedule plus a technician-availability what-if

## What's included

- `machine_maintenance.py` — the four-stage multi-reasoner script
- `runbook.md` — a prompt-by-prompt walkthrough mapped to 13 reasoner questions, with the real figures each stage produces
- `data/` — the bundled `MANUFACTURING.PUBLIC` sample (15 CSVs)
- `pyproject.toml` — package configuration and dependencies

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools
- Python >= 3.10

## Quickstart

1. Download ZIP:
   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/machine_maintenance.zip
   unzip machine_maintenance.zip
   cd machine_maintenance
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
   python machine_maintenance.py
   ```

   Each stage prints its findings. The first lines look like:

   ```text
   -- Q1: OEE by plant --
      Plant_C: availability 97.7%  performance 81.7%  quality 98.2%  OEE 78.3%
   ```

   See `runbook.md` for the full walkthrough and output.

## Template structure

```text
.
├── README.md
├── runbook.md
├── pyproject.toml
├── machine_maintenance.py
└── data/
    ├── machines.csv
    ├── technicians.csv
    ├── qualifications.csv
    ├── products.csv
    ├── production_runs.csv
    ├── machine_product_capabilities.csv
    ├── downtime_events.csv
    ├── fault_types.csv
    ├── failure_predictions.csv
    ├── sensors.csv
    ├── sensor_readings.csv
    ├── travel.csv
    ├── training_options.csv
    ├── availability.csv
    └── degradation.csv
```

## Sample data

The bundled CSVs are the real `MANUFACTURING.PUBLIC` sample dataset:

| File | Rows | Description |
|---|---|---|
| `machines.csv` | 50 | Machines across 3 plants and 5 types (Turbine, Generator, Pump, Compressor, Motor) |
| `technicians.csv` | 20 | Technicians with skill level, base location, and rate |
| `qualifications.csv` | 32 | Which technicians are qualified for which machine type |
| `products.csv` | 8 | Products manufactured |
| `production_runs.csv` | 844 | Per-run planned/actual/good/waste quantities and speeds |
| `machine_product_capabilities.csv` | 120 | Which machines can produce which products |
| `downtime_events.csv` | 353 | Downtime events with fault name, duration, and planned flag |
| `fault_types.csv` | 15 | Fault catalog (name, category, MTTR/MTBF) |
| `failure_predictions.csv` | 600 | Per-machine, per-period failure probability and predicted mode |
| `sensors.csv` / `sensor_readings.csv` | 200 / 2,400 | Sensor catalog and readings with anomaly flags |
| `travel.csv` | 9 | Inter-location travel hours and cost |
| `training_options.csv` | 41 | Cross-training cost and duration per technician/type |
| `availability.csv` | 240 | Per-technician, per-period availability |
| `degradation.csv` | 5 | Per-type degradation rate and maintenance reset factor |

## Model overview

Core concepts: `Machine`, `Technician`, `Qualification`, `Product`, `ProductionRun`, `DowntimeEvent`, `FailurePrediction`, `MachineProductCapability`, and a generated `Period` (1..12). The prescriptive stage adds a `MachinePeriod` decision space (one entry per machine and period).

## How it works

The script runs four stages in order — querying, rules, graph, prescriptive — each writing its findings back to the shared model.

### 1. Querying
Per-plant OEE combines a performance leg (average of actual-versus-target speed) and a quality leg (good versus actual quantity) from production runs with an availability leg from unplanned downtime against a planned base of 480 minutes per run. The legs are aggregated per plant, then multiplied:

```python
oee["availability"] = (oee["n_runs"] * OEE_PLANNED_MIN_PER_RUN - oee["unplanned_dt"]) / (
    oee["n_runs"] * OEE_PLANNED_MIN_PER_RUN
)
oee["oee"] = oee["availability"] * oee["performance"] * oee["quality"]
```

Further queries rank downtime by fault and plant, surface the highest forward failure risk, compute waste rates by machine-product, and count qualified technicians per machine type.

### 2. Rules
Three boolean flags combine into a single `Machine.risk_tier`. Each flag is a derived relationship — for example, chronic downtime fires above the event threshold:

```python
Machine.is_chronic = model.Relationship(f"{Machine} has chronic downtime")
model.where(Machine.downtime_event_count > CHRONIC_DOWNTIME_THRESHOLD).define(Machine.is_chronic())
```

A machine with all three flags is Critical, exactly two is Elevated, otherwise Standard.

### 3. Graph
A bipartite machine-product graph is built from `machine_product_capabilities`, and betweenness centrality ranks machines by how much production routing flows through them — the producibility bottlenecks:

```python
prod_graph = Graph(model, directed=False, weighted=False)
model.where(
    MachineProductCapability.machine(_GM), MachineProductCapability.product(_GP)
).define(prod_graph.Edge.new(src=_GM, dst=_GP))
prod_graph.Node.bottleneck_raw = prod_graph.betweenness_centrality()
```

### 4. Prescriptive
A binary `MachinePeriod.x_maintain` decides which machine is maintained in which period. Each machine gets at most one slot and only if coverage is feasible (Turbine work requires an on-site qualified technician), and each period is capped at five jobs:

```python
prob.satisfy(
    model.require(
        aggs.sum(MachinePeriod.x_maintain).per(Period).where(MachinePeriod.period(Period)) <= 5
    ),
    name=["bay", Period.pid],
)
```

The objective prioritizes high failure-probability, high-criticality work in earlier periods. A second solve removes a key technician to show which machines lose coverage. The result is persisted as a `MaintenancePlan` headline so it stays queryable after the run.

## Customize this template

### Use your own data
Replace the CSVs in `data/` with your own machines, technicians, production, and downtime records (matching the column headers). Concept definitions bind directly to the CSV columns.

### Tune parameters
The thresholds at the top of `machine_maintenance.py` — period horizon, per-period bay limit, chronic/high-risk/overdue cutoffs — are constants you can adjust to your operation.

### Extend the model
Add reasoners or stages: cluster machines by shared technicians, train a GNN on the sensor/downtime history for failure prediction, or add cross-training recommendations from `training_options` to relieve the coverage bottlenecks the what-if surfaces.

## Troubleshooting

<details>
<summary><code>ModuleNotFoundError</code></summary>

Make sure you activated the virtual environment and ran `python -m pip install .` to install dependencies listed in `pyproject.toml`.
</details>

<details>
<summary>Connection or authentication errors</summary>

Run `rai init` to configure your Snowflake connection. Verify that the RAI Native App is installed and your user has the required permissions.
</details>
