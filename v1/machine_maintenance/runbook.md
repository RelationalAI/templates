# Runbook: Machine Maintenance — Multi-Reasoner Walkthrough

Schedules preventive maintenance for a **50-machine, 3-plant, 12-period** manufacturing operation. OEE alone misranks the plants; downtime totals don't say what will fail next; rules flag risky machines but don't allocate scarce technician time; the optimizer produces a feasible schedule but can't see that all on-site Turbine coverage funnels through a single technician per plant. The chain threads querying, graph, rules, and prescriptive reasoners through one ontology so each stage's enrichments feed the next.

> **Data provenance.** Every figure below is computed from the bundled `data/*.csv`, which is the real `MANUFACTURING.PUBLIC` dataset (50 machines, 20 technicians, 8 products, 12 weekly periods across Plant_A/Plant_B/Plant_C). The same dataset backs the reasoner-workflow eval suite, so the walkthrough doubles as a reproducibility check against 13 known-answer questions.
>
> **Status (draft).** Querying (Q1–Q5, Q7) and Rules (Q9) below are verified against the real data and reproduce the eval's expected answers exactly. Graph (Q8), Predictive (Q6, Q13), and Prescriptive (Q10–Q12) are wired in the script and their numbers will be filled from the live engine run — they are marked _pending live run_ until then.

## The chain

```
  ─────────────────────────────────────────────────────────────────
  STAGE 1  Querying     ──►  OEE by plant, downtime drivers, failure
   /rai-querying              ranking, waste rates, tech coverage
                              Plant_C 78.3% > Plant_A 68.0% > Plant_B 63.3%
                              Bearing Failure = 19.4% of all downtime.
                              Turbines have only 3 qualified technicians.
  ─────────────────────────────────────────────────────────────────
  STAGE 2  Rules        ──►  Machine.risk_tier  (50)
   /rai-rules-authoring       3 Critical · 6 Elevated · 41 Standard
                              Critical: M001, M006 (Turbine/Plant_A), M011.
  ─────────────────────────────────────────────────────────────────
  STAGE 3  Graph        ──►  Machine producibility bottlenecks
   /rai-graph-analysis        (pending live run)
  ─────────────────────────────────────────────────────────────────
  STAGE 4  Predictive   ──►  Per-machine failure risk & mode, 12 periods
   /rai-predictive-modeling   (pre-computed predictions; GNN pending)
  ─────────────────────────────────────────────────────────────────
  STAGE 5  Prescriptive ──►  Preventive-maintenance schedule + what-if
   /rai-prescriptive-*        (pending live run)
  ─────────────────────────────────────────────────────────────────
```

## Workflow

> **How to use this walkthrough.** Each section is a Prompt you paste into a single RAI session; state accumulates across steps so later reasoners read the properties earlier ones wrote. Responses show what the template produces against the bundled real data.

### 1. Build ontology

**Prompt**

```
/rai-build-starter-ontology Build a manufacturing maintenance ontology from the CSVs in data/. Scope it for preventive-maintenance scheduling over a multi-period horizon — introduce a Period concept (1..12 from the `period` column) alongside the source-bound concepts (machines, technicians, qualifications, products, production runs, downtime events, failure predictions, sensors, machine-product capabilities).
```

**Response**

Concepts bound to the bundled CSVs: `Machine` (50, across Plant_A/B/C × Turbine/Generator/Pump/Compressor/Motor), `Technician` (20), `Qualification` (32), `Product` (8), `ProductionRun` (844), `DowntimeEvent` (353), `FailurePrediction` (600), `Sensor` (200), `SensorReading` (2400), `MachineProductCapability` (120), and a generated `Period` (1..12). Junction concepts (`MachinePeriod`, `TechnicianMachinePeriod`) are deferred to the prescriptive stage.

### 2. Diagnose plant operations — OEE  _(eval Q1)_

**Prompt**

```
/rai-querying What's the OEE by plant, broken into Availability (planned time = production runs × 480 min per run; downtime = unplanned events only, is_planned = 0), Performance (avg of actual_speed / target_speed per run), and Quality (good_quantity / actual_quantity)? Compute OEE from the unrounded components, then round to one decimal.
```

**Response** _(verified)_

| Plant | Availability | Performance | Quality | OEE |
|---|---|---|---|---|
| Plant_C | 97.7% | 81.7% | 98.2% | **78.3%** |
| Plant_A | 96.4% | 71.8% | 98.3% | **68.0%** |
| Plant_B | 92.5% | 69.8% | 98.1% | **63.3%** |

Plant_C leads; Plant_B trails — driven by its low Availability (most unplanned downtime) and Performance.

### 3. Find the downtime drivers  _(eval Q2, Q3)_

**Prompt**

```
/rai-querying What are the top causes of downtime by specific fault name and their percent of total downtime? And which plant carries the most downtime?
```

**Response** _(verified)_

Top fault names: **Bearing Failure 3,905 min (19.4%)**, Overheating 3,183 (15.8%), Motor Burnout 2,344 (11.7%), Seal Degradation 2,328 (11.6%), Shaft Misalignment 1,600 (8.0%). By plant: **Plant_B 10,494 min (52.2%)**, Plant_A 6,576 (32.7%), Plant_C 3,033 (15.1%). Total downtime = 20,103 min.

### 4. Rank forward failure risk  _(eval Q4)_

**Prompt**

```
/rai-querying Which machines are most likely to fail by the end of the planning horizon (period 12), and for what predicted reason?
```

**Response** _(verified)_

M016 valve_stuck (42.0%), M028 seal_leak (42.0%), M011 valve_stuck (42.0%), M012 valve_stuck (41.5%), M047 motor_burnout (35.4%).

### 5. Surface the worst waste  _(eval Q5)_

**Prompt**

```
/rai-querying Which machine-product combinations have the worst waste rates (waste_quantity / actual_quantity), to one decimal?
```

**Response** _(verified)_

M025 + Hydraulic Seal Kit (3.8%), M005 + Turbine Blade Assembly (3.7%), M002 + Turbine Blade Assembly (3.6%), M049 + Motor Winding Set (3.6%), M045 + Control Panel Unit (3.5%).

### 6. Check technician coverage  _(eval Q7)_

**Prompt**

```
/rai-querying Which machine types have the fewest qualified technicians?
```

**Response** _(verified)_

Turbines are most constrained — only **3** qualified technicians (T001, T009, T017). Generators have 6; Pumps 7; Compressors and Motors 8 each. This concentration is what later makes Turbine coverage fragile in the schedule.

### 7. Classify machine risk  _(eval Q9)_

**Prompt**

```
/rai-rules-authoring Rate each machine's risk from three flags: chronic = more than 15 downtime events; high-risk = failure probability above 0.20 AND criticality 4 or higher; maintenance-overdue = remaining useful life of 9 or less. All three flags → Critical; exactly two → Elevated; otherwise Standard.
```

**Response** _(verified)_

**3 Critical** — M001 (Turbine, Plant_A), M006 (Turbine, Plant_A), M011 (Compressor, Plant_B); **6 Elevated**; **41 Standard**. The two Critical Turbines sit in the same plant that the coverage query already flagged as thin on Turbine technicians.

### 8. Find producibility bottlenecks  _(eval Q8)_

**Prompt**

```
/rai-graph-analysis Build a machine-product bipartite graph from machine_product_capabilities and find the biggest connectivity bottlenecks — machines tied to products with the fewest alternative producers.
```

**Response** _(pending live run)_

Graph stage is wired in `machine_maintenance.py`; bottleneck centralities will be filled from the live engine run.

### 9. Predict failures  _(eval Q6, Q13)_

**Prompt**

```
/rai-predictive-modeling Which machines are most likely to fail over the next 12 periods, and what's the most likely failure mode for each, given sensor readings, downtime history, and machine attributes?
```

**Response** _(pre-computed; GNN pending)_

The bundled `failure_predictions` supply per-machine, per-period probabilities and predicted modes (the source of the step-4 ranking). A GNN formulation over sensor/downtime history is wired for the predictive reasoner; its trained-model results will be added from the live run.

### 10. Schedule preventive maintenance + stress-test  _(eval Q10, Q11, Q12)_

**Prompt**

```
/rai-prescriptive-problem-formulation Schedule preventive maintenance across the 50 machines and 12 periods: at most 5 jobs per period; each maintained machine needs a qualified technician, with Turbine work covered by an on-site technician at the same plant; prioritize high failure-probability × high-criticality and earlier periods for the riskiest. Then re-solve with T001 unavailable and report the coverage impact.
```

**Response** _(pending live run)_

Prescriptive formulation (decision variables, ≤5/period cap, qualified + on-site Turbine assignment, expected-failure-cost objective) and the T001-unavailable what-if are wired in `machine_maintenance.py`; the optimal schedule, objective, and concentration/cross-training findings will be filled from the live solve.

## Data

Bundled CSVs in `data/` (real `MANUFACTURING.PUBLIC`): 50 machines (3 plants × 5 types), 20 technicians, 32 qualifications, 8 products, 120 machine-product capabilities, 844 production runs, 353 downtime events, 600 failure predictions, 200 sensors / 2,400 sensor readings, plus travel, training options, availability, and degradation references. All stages run in `machine_maintenance.py`.
