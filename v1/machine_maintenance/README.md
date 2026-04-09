---
title: "Machine Maintenance"
description: "A multi-reasoner template that chains querying, graph analysis, rules-based classification, and prescriptive optimization to schedule preventive maintenance, surface hidden operational risk, and recommend cross-training to eliminate concentration vulnerabilities."
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
  - Assignment
  - OEE
  - Sensor Anomalies
  - Risk Classification
---

# Machine Maintenance

## What this template is for

Manufacturing facilities must schedule preventive maintenance for machines with ML-predicted failure probabilities. The challenge is that surface-level metrics (like OEE) can mask structural vulnerabilities -- a plant that looks mid-tier on performance may actually carry the highest concentration risk, discoverable only by chaining multiple analytical layers.

This template uses RelationalAI's **querying**, **graph analysis**, **rules-based classification**, and **prescriptive reasoning (optimization)** capabilities in a five-stage multi-reasoner workflow:

1. **Querying** computes OEE by facility, surfaces sensor anomalies, and identifies machines with the steepest failure degradation trajectories. Plant_B looks worst at 61.4% OEE -- but Plant_A, at 68.2%, has 7 of 9 sensor anomalies and the 3 steepest degradation curves.
2. **Graph analysis** builds a machine dependency graph from shared-technician qualifications. All 30 machines form a single connected cluster, and Pump-type machines score highest on betweenness centrality (24.0) as the most constrained scheduling bottlenecks.
3. **Rules** derive seven compliance flags and chain three of them (chronic downtime, high-risk, overdue) into a composite risk tier. M013 (Pump, Plant_A) is the only Critical-tier machine -- it triggers all three flags.
4. **Prescriptive optimization** schedules 20 maintenance jobs across 4 periods at $605K total cost, assigning qualified technicians. The optimizer consumes per-period failure predictions from Stage 0, betweenness centrality from Stage 1, and overdue-maintenance flags from Stage 2.
5. **Resilience analysis** reveals that all 3 Turbine-qualified technicians are in Houston_TX, forcing 67% of scheduled Turbine jobs to require travel. Cross-training T006 (Senior, Chicago_IL) for $3,200 over 5 weeks eliminates this geographic concentration risk.

Each stage enriches the shared ontology, and downstream stages consume those enrichments -- this is the **accretive ontology enrichment** pattern. No Python dicts carry state between stages; the ontology is the single source of truth:

- **Stage 0 writes** `Machine.performance_ratio`, `Machine.quality_ratio`, `Machine.anomaly_count`, `MachinePeriod.predicted_fp` -- consumed by Stage 2's rules AND Stage 3's objective. Both downstream reasoners see the same derived signals.
- **Stage 1 writes** `Machine.betweenness` (normalized centrality) -- consumed by Stage 3's failure cost term. Bottleneck machines are more expensive to leave vulnerable.
- **Stage 2 writes** `Machine.is_overdue_maintenance`, `Machine.is_high_risk`, `Machine.is_chronic_downtime`, `Machine.risk_tier` -- the overdue flag feeds a hard scheduling constraint in Stage 3 (overdue machines must be maintained by period 2).
- **Stage 3 writes** `x_maintain`, `x_vulnerable`, `x_assigned` (decision variables) -- parsed in Stage 4 to analyze technician utilization and concentration risk.

### Reasoner overview

| Stage | Reasoner | Reads from ontology | Writes to ontology | Role |
|-------|----------|---------------------|--------------------|------|
| 0 | Querying | ProductionRun, SensorReading, FailurePrediction | Machine.performance_ratio, Machine.quality_ratio, Machine.anomaly_count, MachinePeriod.predicted_fp | Plant_C leads at 79.8% OEE; Plant_A mid at 68.2% but has 7 of 9 sensor anomalies and the 3 steepest failure trajectories (M001 +0.230, M013 +0.228, M016 +0.219). |
| 1 | Graph | Qualification, Machine | Machine.betweenness (normalized centrality) | All 30 machines form 1 connected cluster. Pump-type machines are the top bottlenecks (betweenness=24.0). Centrality scores feed the failure cost multiplier in Stage 3. |
| 2 | Rules | Machine (all derived properties from Stages 0-1) | Machine.is_overdue_maintenance, Machine.is_high_risk, Machine.is_chronic_downtime, Machine.risk_tier | 6 overdue, 1 high-risk, 3 chronic downtime. Composite tier: M013 is Critical (all 3 flags), M016 is Elevated (2 of 3). Overdue flag becomes a hard constraint in Stage 3. |
| 3 | Prescriptive | MachinePeriod.predicted_fp, Machine.betweenness, Machine.is_overdue_maintenance | x_maintain, x_vulnerable, x_assigned (decision variables) | 20 jobs across 4 periods at $605K total cost. Per-period failure predictions (not static probability) weight the objective. Overdue machines scheduled by period 2. |
| 4 | Analysis | Solution variables, Qualification, TrainingOption | (terminal -- prints recommendations) | All 3 Turbine techs in Houston_TX -- 67% of Turbine jobs require travel. Best cross-training: T006 (Chicago_IL, Senior) at $3,200 / 5 weeks. |

## Why this problem matters

OEE dashboards and failure-probability rankings are how most plants prioritize maintenance today. But these metrics evaluate machines in isolation -- they miss structural dependencies between machines, technicians, and locations that create cascading risk. A plant where all Turbine-qualified technicians happen to work from the same office looks fine on every individual metric. The concentration risk is invisible until someone leaves, a certification expires, or a weather event disrupts the location -- at which point multiple machines lose coverage simultaneously.

The multi-reasoner approach is necessary because no single analytical technique surfaces this risk. Querying reveals sensor anomalies that OEE masks. Graph analysis exposes which machines share technician pools. Rules chain individual flags into composite risk tiers. Optimization produces a schedule, and resilience analysis stress-tests that schedule against the qualification structure. Each layer reveals something the previous one missed.

### Key design patterns demonstrated

- **Accretive ontology enrichment** -- each stage writes derived properties (betweenness, risk_tier, predicted_fp) that downstream stages consume, building a progressively richer model
- **Rules chaining** -- three boolean flags (is_chronic_downtime, is_high_risk, is_overdue_maintenance) are composed into a single risk_tier property using exhaustive enumeration with `model.not_()`
- **Graph-only concept for dependencies** -- a `GraphMachine` concept mirrors Machine nodes for the Graph reasoner, with betweenness centrality normalized and enriched back to the main ontology via rules
- **Per-period failure predictions** -- the optimization objective uses `MachinePeriod.predicted_fp` (period-specific) rather than static `Machine.failure_probability`, giving the solver time-varying cost information
- **Post-solve resilience analysis** -- Stage 4 inspects the solution and qualification structure to identify concentration risk, producing actionable cross-training recommendations without re-solving

## Who this is for

- Manufacturing and plant managers scheduling preventive maintenance
- Operations researchers exploring multi-reasoner pipelines in RelationalAI
- Developers learning how to chain querying, graph, rules, and optimization in a single model

## What you'll build

- Machine-level production aggregates, OEE components, and anomaly counts as derived properties
- A machine dependency graph with cluster detection and centrality scoring
- Seven compliance rules as derived Relationships and Properties, including a composite risk tier that chains three boolean flags
- Binary decision variables for maintenance timing, vulnerability tracking, and technician assignment
- Cumulative coverage, capacity, and overdue-deadline constraints
- A cost minimization objective that incorporates per-period failure predictions and graph centrality
- Geographic concentration risk analysis with cross-training recommendations

## What's included

- `machine_maintenance.py` -- Main script with five chained reasoning stages
- `data/machines.csv` -- 30 machines with failure probability, criticality (1-5), duration, and parts cost
- `data/technicians.csv` -- 10 technicians with skill levels, certifications, hourly rates, and locations
- `data/availability.csv` -- Technician availability across the 4-period planning horizon
- `data/qualifications.csv` -- Mapping of which technicians can service which machine types
- `data/parts_inventory.csv` -- Spare parts stock levels at each facility
- `data/certification_expiry.csv` -- Days remaining on technician certifications per machine type
- `data/sensors.csv` -- 60 sensors (2 per machine) with warning and critical thresholds
- `data/sensor_readings.csv` -- 240 periodic sensor measurements with anomaly flags
- `data/failure_predictions.csv` -- 120 per-period failure probability trajectories with predicted failure modes
- `data/downtime_events.csv` -- 129 downtime events with fault categories and durations
- `data/production_runs.csv` -- 120 production runs with planned, actual, and good quantities
- `data/training_options.csv` -- 13 cross-training options with costs and durations
- `pyproject.toml` -- Python project configuration with dependencies

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools
- Python >= 3.10
- RelationalAI Python SDK (`relationalai`) >= 1.0.13

## Quickstart

1. Download the ZIP file for this template and extract it:

   ```bash
   curl -O https://private.relational.ai/templates/zips/v1/machine_maintenance.zip
   unzip machine_maintenance.zip
   cd machine_maintenance
   ```

   > [!TIP]
   > You can also download the template ZIP using the "Download ZIP" button at the top of this page.

2. Create a virtual environment and activate it:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   ```

3. Install dependencies:

   ```bash
   python -m pip install .
   ```

4. Configure your RAI connection:

   ```bash
   rai init
   ```

5. Run the template:

   ```bash
   python machine_maintenance.py
   ```

6. Expected output:
   ```text
   ======================================================================
   STAGE 0: Querying -- Operational Intelligence
   ======================================================================

   OEE proxy by facility (Performance x Quality):
     Plant_C: Perf=81.3%, Qual=98.1%, OEE=79.8%
     Plant_A: Perf=69.8%, Qual=97.8%, OEE=68.2%
     Plant_B: Perf=62.6%, Qual=98.1%, OEE=61.4%

   Sensor anomalies (9 readings across 5 machines):
     M013 (Pump, Plant_A): 3 anomalies
     M001 (Turbine, Plant_A): 2 anomalies
     M016 (Turbine, Plant_A): 2 anomalies
     M002 (Compressor, Plant_B): 1 anomalies
     M006 (Turbine, Plant_C): 1 anomalies
     By facility: {'Plant_A': 7, 'Plant_B': 1, 'Plant_C': 1}

   Steepest failure trajectories (period 1 -> 4):
     M001 (Turbine, Plant_A): 0.102 -> 0.332 (+0.230) [bearing_wear]
     M013 (Pump, Plant_A): 0.435 -> 0.663 (+0.228) [impeller_erosion]
     M016 (Turbine, Plant_A): 0.263 -> 0.482 (+0.219) [bearing_wear]
     ...

   ======================================================================
   STAGE 1: Graph Analysis -- Dependency Clusters & Centrality
   ======================================================================

   Dependency clusters found: 1

   Top bottleneck machines (betweenness centrality):
     M003 (Pump, Plant_C): betweenness=24.0000, failure_prob=0.089
     M008 (Pump, Plant_B): betweenness=24.0000, failure_prob=0.076
     M013 (Pump, Plant_A): betweenness=24.0000, failure_prob=0.435
     ...

   ======================================================================
   STAGE 2: Rules -- Compliance Flags & Composite Risk Tier
   ======================================================================

   Overdue maintenance (6 machines):
     M002 (Compressor_Beta_1): RUL=3.7h < duration=6h
     M006 (Turbine_Alpha_2): RUL=3.4h < duration=8h
     M013 (Pump_Gamma_3): RUL=2.3h < duration=4h
     ...

   High-risk machines (1):
     M013 (Pump_Gamma_3): prob=0.435, crit=4

   Anomalous machines (5):
     M013 (Pump_Gamma_3, Plant_A): 3 anomalies
     M001 (Turbine_Alpha_1, Plant_A): 2 anomalies
     M016 (Turbine_Alpha_4, Plant_A): 2 anomalies
     ...

   Chronic downtime machines (>8 events, 3 machines):
     M001 (Turbine_Alpha_1, Plant_A): 12 events, 1635 min total downtime
     M016 (Turbine_Alpha_4, Plant_A): 11 events, 1314 min total downtime
     M013 (Pump_Gamma_3, Plant_A): 10 events, 1272 min total downtime

   Composite risk tier:
     Critical (1): M013
     Elevated (1): M016
     Standard (28): M001, M002, ...

   Parts needing reorder (4):
     P001 (Spindle Bearings, Plant_A): stock=25 <= min_order=50
     ...

   Expiring certifications (5):
     T001 (Alice_Johnson): Compressor -- 22 days remaining
     T004 (Diana_Chen): Pump -- 8 days remaining
     ...

   ======================================================================
   STAGE 3: Prescriptive -- Maintenance Scheduling
   ======================================================================

   Status: OPTIMAL
   Objective value: 605240.61

   Maintenance schedule (20 jobs):
     Period 1:
       M002 (Compressor, Plant_B, crit=5)
       M006 (Turbine, Plant_C, crit=5)
       M013 (Pump, Plant_A, crit=4)
       M016 (Turbine, Plant_A, crit=3)
       ...
     Period 2: ...
     Period 3: ...
     Period 4: ...

   Technician assignments (20):
     Period 1:
       M002: T003 (6h x $65/h = $390) [TRAVEL]
       M013: T006 (4h x $88/h = $352) [TRAVEL]
       ...

   ======================================================================
   STAGE 4: Resilience -- Concentration Risk Analysis
   ======================================================================

   Technician utilization in optimal schedule:
     T003 (Charlie_Brown, Junior, Houston_TX): 5 assignments (25%)
     T004 (Diana_Chen, Junior, Chicago_IL): 5 assignments (25%)
     ...

   Qualification coverage by machine type:
     Compressor: 3 techs in Chicago_IL, Houston_TX -- gaps at Phoenix_AZ
     Generator: 3 techs in Chicago_IL, Phoenix_AZ -- gaps at Houston_TX
     Motor: 4 techs in Chicago_IL, Phoenix_AZ -- gaps at Houston_TX
     Pump: 3 techs in Chicago_IL, Phoenix_AZ -- gaps at Houston_TX
     Turbine: 3 techs in Houston_TX -- CONCENTRATED

   Concentration risk detail:

     Turbine: 6 machines across 3 facilities, all 3 qualified techs in Houston_TX
       Local machines (Houston_TX): 2
       Remote machines (require travel): 4
       Scheduled Turbine jobs: 3, of which 2 require travel (67%)
       Qualified techs (all Houston_TX):
         T001 (Alice_Johnson, Senior)
         T002 (Bob_Martinez, Senior)
         T003 (Charlie_Brown, Junior)

   ======================================================================
   RECOMMENDATION: Cross-Training to Eliminate Concentration Risk
   ======================================================================

     Turbine -- add coverage outside Houston_TX:
       Best candidate: T006 (Fiona_Garcia, Senior, Chicago_IL)
       Cost: $3,200, Duration: 5 weeks
       All candidates:
         T006 (Fiona_Garcia, Chicago_IL): $3,200, 5 weeks
         T005 (Edward_Smith, Chicago_IL): $3,500, 6 weeks
         T008 (Hannah_Wilson, Phoenix_AZ): $3,800, 6 weeks
         T009 (Ian_Taylor, Phoenix_AZ): $4,200, 8 weeks
         T004 (Diana_Chen, Chicago_IL): $5,500, 10 weeks
   ```

## Template structure

```text
.
├── README.md
├── pyproject.toml
├── machine_maintenance.py
└── data/
    ├── machines.csv
    ├── technicians.csv
    ├── availability.csv
    ├── qualifications.csv
    ├── parts_inventory.csv
    ├── certification_expiry.csv
    ├── sensors.csv
    ├── sensor_readings.csv
    ├── failure_predictions.csv
    ├── downtime_events.csv
    ├── production_runs.csv
    └── training_options.csv
```

## How it works

This section walks through the highlights in `machine_maintenance.py`.

### Define concepts and load CSV data

The model defines concepts for machines (with ML-predicted failure probability and numeric criticality), technicians (with skills and hourly rates), qualifications linking technicians to machine types, parts inventory, certification expiry, sensors, sensor readings, failure predictions, downtime events, and production runs. All data is loaded from CSV files:

```python
Machine = model.Concept("Machine", identify_by={"machine_id": String})
Machine.failure_probability = model.Property(
    f"{Machine} has failure probability {Float:failure_probability}")
Machine.criticality = model.Property(f"{Machine} has criticality {Integer:criticality}")

Technician = model.Concept("Technician", identify_by={"technician_id": String})
Qualification = model.Concept(
    "Qualification", identify_by={"technician_id": String, "machine_type": String})

Sensor = model.Concept("Sensor", identify_by={"sensor_id": String})
SensorReading = model.Concept(
    "SensorReading",
    identify_by={"sensor_id": String, "machine_id": String, "pid": Integer})
FailurePrediction = model.Concept(
    "FailurePrediction", identify_by={"prediction_id": String})
DowntimeEvent = model.Concept("DowntimeEvent", identify_by={"event_id": String})
ProductionRun = model.Concept("ProductionRun", identify_by={"run_id": String})
```

Machine-level derived aggregates are computed from the loaded data using `aggs.sum` and `aggs.count`, providing production ratios, downtime counts, and anomaly counts as derived properties:

```python
Machine.total_planned_qty = model.Property(
    f"{Machine} has total planned qty {Float:total_planned_qty}")
model.define(Machine.total_planned_qty(
    aggs.sum(ProductionRun.planned_quantity).per(Machine)
    .where(ProductionRun.machine(Machine)) | 0
))

model.where(Machine.total_planned_qty > 0).define(
    Machine.performance_ratio(
        floats.float(Machine.total_actual_qty)
        / floats.float(Machine.total_planned_qty)
    )
)
```

Cross-product concepts define the scheduling decision space. `MachinePeriod` pairs each machine with each planning period and stores per-period failure predictions. `TechnicianMachinePeriod` is restricted to qualified pairs -- technicians can only be assigned to machine types they are certified for:

```python
MachinePeriod.predicted_fp = model.Property(
    f"{MachinePeriod} has predicted failure probability {Float:predicted_fp}")
FPJoin = FailurePrediction.ref()
model.where(
    MachinePeriod.machine_id == FPJoin.machine_id_str,
    MachinePeriod.pid == FPJoin.period_int,
).define(MachinePeriod.predicted_fp(FPJoin.failure_probability))
```

### Stage 0: Querying -- operational intelligence

The querying stage computes OEE proxy (Performance x Quality) by facility, surfaces machines with above-threshold sensor readings, and identifies the steepest failure degradation trajectories. All queries use `model.select` with derived properties:

```python
oee_df = (
    model.select(
        Machine.machine_id.alias("machine_id"),
        Machine.facility.alias("facility"),
        Machine.performance_ratio.alias("performance"),
        Machine.quality_ratio.alias("quality"),
    )
    .to_df()
)
```

### Stage 1: Graph -- dependency clusters and centrality

A `GraphMachine` concept mirrors Machine nodes for graph analysis. Edges connect machines when at least one technician is qualified for both machine types. The graph runs in the main model, so results can be enriched back via rules without a pandas round-trip:

```python
dep_graph = Graph(
    model, directed=False, weighted=False, node_concept=GMachine, aggregator="sum"
)
```

Weakly connected components identify dependency clusters (groups of machines that compete for the same technicians). Betweenness centrality scores bottleneck machines -- those whose maintenance blocks the most scheduling options. The scores are normalized in-model and enriched onto `Machine`:

```python
Machine.betweenness = model.Property(
    f"{Machine} has betweenness centrality {Float:betweenness}")
max_betweenness = max(GMachine.betweenness_raw)
model.where(
    Machine.machine_id == gm_norm.machine_id,
    max_betweenness > 0,
).define(
    Machine.betweenness(gm_norm.betweenness_raw / max_betweenness)
)
```

### Stage 2: Rules -- compliance flags and composite risk tier

Seven derived Relationships and Properties flag compliance issues. Each rule is a pure logic derivation using `model.where(...).define(...)`:

```python
Machine.is_overdue_maintenance = model.Relationship(
    f"{Machine} is overdue maintenance")
model.where(
    Machine.remaining_useful_life < floats.float(Machine.maintenance_duration_hours)
).define(Machine.is_overdue_maintenance())

Machine.is_chronic_downtime = model.Relationship(f"{Machine} has chronic downtime")
model.where(
    Machine.downtime_event_count > CHRONIC_DOWNTIME_THRESHOLD
).define(Machine.is_chronic_downtime())
```

Individual flags are chained into a composite risk tier using `model.not_()` for negation. This exhaustively enumerates all eight combinations of three boolean flags:

```python
Machine.risk_tier = model.Property(f"{Machine} has risk tier {String:risk_tier}")

# Critical: all 3 flags.
model.where(
    Machine.is_chronic_downtime(),
    Machine.is_high_risk(),
    Machine.is_overdue_maintenance(),
).define(Machine.risk_tier("Critical"))

# Elevated: exactly 2 of 3 flags.
model.where(
    Machine.is_chronic_downtime(),
    Machine.is_high_risk(),
    model.not_(Machine.is_overdue_maintenance()),
).define(Machine.risk_tier("Elevated"))
```

### Stage 3: Define decision variables, constraints, and objective

Three binary decision variables control the schedule: whether to maintain a machine in a period, whether it remains vulnerable, and whether a technician is assigned. The formulation includes four standard constraints (cumulative coverage, assignment linkage, technician capacity, parts/bay capacity) plus a hard constraint from Stage 2's overdue flag:

```python
maintained_by_deadline = (
    sum(MachinePeriod_overdue.x_maintain)
    .where(
        MachinePeriod_overdue.machine(Machine_overdue),
        MachinePeriod_overdue.period(Period_overdue),
        Period_overdue.pid <= OVERDUE_DEADLINE,
    )
    .per(Machine_overdue)
)
p.satisfy(
    model.require(maintained_by_deadline >= 1).where(
        Machine_overdue.is_overdue_maintenance()
    )
)
```

The objective minimizes expected total cost with three components. The failure cost term incorporates per-period failure predictions from Stage 0 and betweenness centrality from Stage 1, making it more expensive to leave bottleneck machines vulnerable in periods where their predicted failure probability is highest:

```python
failure_cost = sum(
    MachinePeriod_outer.x_vulnerable
    * MachinePeriod_outer.predicted_fp
    * Machine_obj.estimated_parts_cost
    * Machine_obj.criticality
    * (1 + CENTRALITY_WEIGHT * Machine_obj.betweenness)
).where(
    MachinePeriod_outer.machine(Machine_obj), MachinePeriod_outer.period(Period_outer)
)
```

### Solve and extract results

The model is solved using the HiGHS solver with a two-minute time limit. Assignment decisions are parsed from the solution to build the maintenance schedule:

```python
p.solve("highs", time_limit_sec=120)
si = p.solve_info()
assert si.termination_status == "OPTIMAL"
```

### Stage 4: Resilience analysis and cross-training

After solving, the script analyzes qualification coverage by machine type and location. For each machine type, it checks whether all qualified technicians are concentrated in a single location -- a geographic single-point-of-failure invisible to the optimizer:

```python
for mtype in machine_types:
    qual_techs = qualifications_df[
        qualifications_df["machine_type"] == mtype
    ]["technician_id"].tolist()
    tech_info = technicians_df[technicians_df["technician_id"].isin(qual_techs)]
    locations = tech_info["base_location"].unique().tolist()
    if len(locations) == 1:
        concentrated_types.append((mtype, locations[0], len(qual_techs)))
```

For concentrated types, the script queries `training_options.csv` to recommend the cheapest candidate at a different location, producing a specific, costed action item (e.g., "Cross-train T006 for Turbine at $3,200 / 5 weeks").

## Customize this template

- **Adjust centrality weight** via `CENTRALITY_WEIGHT` to control how strongly graph bottleneck scores influence scheduling priority.
- **Change the overdue deadline** via `OVERDUE_DEADLINE` to give more or fewer periods for overdue machines.
- **Extend the planning horizon** by adding more periods to the availability and failure prediction data and increasing `PERIOD_HORIZON`.
- **Adjust capacity limits** via `PARTS_CAPACITY_PER_PERIOD` to see how tighter constraints shift scheduling priorities.
- **Tune travel cost** via `TRAVEL_COST_PER_HOUR` to control preference for local vs. cross-facility assignments.
- **Add rule thresholds** -- adjust `failure_probability > 0.3` or `criticality >= 4` in the high-risk rule to match your risk tolerance.
- **Change chronic downtime threshold** via `CHRONIC_DOWNTIME_THRESHOLD` to control which machines are flagged.
- **Add sensor types** -- extend `sensors.csv` with new sensor types and adjust `sensor_readings.csv` with corresponding measurements.
- **Add training options** -- extend `training_options.csv` to explore different cross-training strategies.

## Troubleshooting

<details>
<summary><code>Status: INFEASIBLE</code></summary>

- The overdue-maintenance constraint requires certain machines to be scheduled in early periods. If technician capacity is too tight, this can cause infeasibility.
- Try increasing `OVERDUE_DEADLINE` from 2 to 3, or increase `PARTS_CAPACITY_PER_PERIOD`.
- Check that technician hours capacity across all periods can accommodate all machines.
</details>

<details>
<summary>All machines maintained in period 1</summary>

- The solver minimizes total cost. If capacity allows, it may schedule all maintenance early to avoid vulnerability costs.
- Tighten `PARTS_CAPACITY_PER_PERIOD` to spread maintenance across periods.
</details>

<details>
<summary>Graph shows 0 edges</summary>

- This means no two machines share a qualified technician. Check that `qualifications.csv` has overlapping machine types across technicians.
- The graph edge construction uses type-based joins: two machines connect if any technician is qualified for both their `machine_type` values.
</details>

<details>
<summary><code>input definition is too large</code></summary>

- This occurs with large cross-products. The qualification-filtered assignment space avoids this issue for the default 30-machine dataset.
- If you scale up significantly, consider reducing data size or querying solver
  results via `Variable.values(...)` instead of broad `model.select(...)`
  patterns.
</details>

<details>
<summary><code>ModuleNotFoundError</code></summary>

- Make sure you activated the virtual environment and ran `python -m pip install .` from the template directory.
- The `pyproject.toml` declares the required dependencies.
</details>

<details>
<summary>Connection or authentication errors</summary>

- Run `rai init` to configure your Snowflake connection.
- Verify that the RAI Native App is installed and your user has the required permissions.
</details>

<details>
<summary>No concentration risk detected in Stage 4</summary>

- This means all machine types have qualified technicians in multiple locations. The resilience analysis examines geographic diversity of the qualification pool, not individual assignment redundancy.
- Try modifying `qualifications.csv` to concentrate a machine type's technicians in one location to see how the analysis surfaces this risk.
</details>
