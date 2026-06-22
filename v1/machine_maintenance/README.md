---
title: "Machine Maintenance"
description: "A multi-reasoner template that chains querying, graph analysis, rules-based classification, and prescriptive optimization to diagnose plant performance, surface producibility bottlenecks, classify machine risk, and schedule preventive maintenance under technician-coverage constraints."
featured: false
experience_level: intermediate
industry: "Manufacturing"
reasoning_types:
  - Querying
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

# Machine Maintenance

## What this template is for

This template models a **50-machine, 3-plant, 12-period** manufacturing operation and threads four RelationalAI reasoners through a single ontology, with each stage's enrichments feeding the next:

1. **Querying** — diagnose plant performance: OEE (availability × performance × quality), downtime drivers, forward failure risk, waste rates, and technician coverage.
2. **Graph** — build a machine-product bipartite graph and rank machines by betweenness centrality to find producibility bottlenecks.
3. **Rules** — classify each machine into a risk tier (Critical / Elevated / Standard) from chronic-downtime, high-risk, and maintenance-overdue flags.
4. **Prescriptive** — schedule preventive maintenance across machines and periods under a per-period bay limit and technician-coverage feasibility (Turbine work needs an on-site qualified technician), then stress-test the schedule against the loss of a key technician.

The point is the chain: OEE alone misranks the plants, downtime totals don't say what will fail next, rules flag risky machines but don't allocate scarce technician time, and the optimizer produces a feasible schedule but can't see that on-site Turbine coverage funnels through a single technician per plant.

## Who this is for

- Data scientists and analysts learning to chain multiple RelationalAI reasoners over one ontology
- Manufacturing and reliability teams building preventive-maintenance and risk-classification workflows
- Anyone wanting a worked multi-reasoner example on a realistic operational dataset

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

   Each stage prints its findings — OEE by plant, downtime drivers, the bottleneck ranking, risk tiers, and the maintenance schedule with its what-if.

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
| `machines.csv` | 50 | Machines across 3 plants × 5 types (Turbine, Generator, Pump, Compressor, Motor) |
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

Core concepts: `Machine`, `Technician`, `Qualification`, `Product`, `ProductionRun`, `DowntimeEvent`, `FailurePrediction`, `MachineProductCapability`, and a generated `Period` (1..12). The prescriptive stage adds a `MachinePeriod` decision space (machine × period).

## How it works

### 1. Querying
Per-plant OEE is built from production runs (performance = avg of actual/target speed; quality = good/actual quantity) and downtime events (availability from unplanned downtime against an 480-minute-per-run planned base). Additional queries rank downtime by fault and plant, surface the highest forward failure risk, compute waste rates by machine-product, and count qualified technicians per machine type.

### 2. Graph
A bipartite machine-product graph is built from `machine_product_capabilities` (edge = machine can produce product). `betweenness_centrality()` ranks machines by how much production-routing flows through them — the producibility bottlenecks.

### 3. Rules
Three boolean flags — chronic downtime (> 15 events), high-risk (failure probability > 0.20 **and** criticality ≥ 4), and maintenance-overdue (remaining useful life ≤ 9) — combine into `Machine.risk_tier`: all three → Critical, exactly two → Elevated, otherwise Standard.

### 4. Prescriptive
A binary `MachinePeriod.x_maintain` decides which machine is maintained in which period. Each machine gets at most one slot and only if coverage is feasible (Turbine work requires an on-site qualified technician); each period is capped at 5 jobs. The objective prioritizes high failure-probability × criticality work in earlier periods. A second solve removes a key technician (T001) to show which machines lose coverage.

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
