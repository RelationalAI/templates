# Runbook: Machine Maintenance — Multi-Reasoner Walkthrough

Schedules preventive maintenance for a **50-machine, 3-plant, 12-period** manufacturing operation. OEE alone misranks the plants; downtime totals don't say what will fail next; rules flag risky machines but don't allocate scarce technician time; the optimizer produces a feasible schedule but can't see that all on-site Turbine coverage funnels through a single technician per plant. The chain threads querying, rules, graph, predictive, and prescriptive reasoners through one ontology so each stage's enrichments feed the next.

> **Data provenance.** Every figure below is computed from the bundled `data/*.csv` — the real `MANUFACTURING.PUBLIC` sample: 50 machines, 20 technicians, 8 products, and 12 weekly periods across Plant_A, Plant_B, and Plant_C.
>
> **Status.** Every figure below comes from a real run of `machine_maintenance.py` against the bundled data — no predicted numbers. Querying and rules are deterministic; the graph and prescriptive stages use the template's own sound formulations. The predictive stage reads the bundled pre-loaded failure predictions by default (no training step); a live GNN is the opt-in alternative.

## The chain

```
  ─────────────────────────────────────────────────────────────────
  STAGE 1  Querying     ──►  OEE by plant, downtime drivers, waste
   /rai-querying              rates, technician coverage
                              Plant_C 78.3% > Plant_A 68.0% > Plant_B 63.3%
                              Bearing Failure = 19.4% of all downtime.
                              Turbines have only 3 qualified technicians.
  ─────────────────────────────────────────────────────────────────
  STAGE 2  Rules        ──►  Machine.risk_tier  (50)
   /rai-rules-authoring       3 Critical · 6 Elevated · 41 Standard
                              Critical: M001, M006 (Turbine/Plant_A), M011.
  ─────────────────────────────────────────────────────────────────
  STAGE 3  Graph        ──►  Machine.bottleneck  (50)
   /rai-graph-analysis        Pumps & Motors bridge the most product lines.
  ─────────────────────────────────────────────────────────────────
  STAGE 4  Predictive   ──►  Forward failure risk & mode, 12 periods
   /rai-predictive-modeling   Pre-loaded by default; live GNN optional.
                              M016 / M028 / M011 ≈ 42% by period 12.
  ─────────────────────────────────────────────────────────────────
  STAGE 5  Prescriptive ──►  Maintenance schedule + technician what-if
   /rai-prescriptive-*        All 50 scheduled (5/period, P1–10); drop T001
                              and 4 Plant_A Turbines lose coverage.
  ─────────────────────────────────────────────────────────────────
```

## Workflow

> **How to use this walkthrough.** Each section is a Prompt you paste into a single RAI session; state accumulates across steps, so later reasoners read the properties earlier ones wrote. Responses show what the template produces against the bundled real data.

### 1. Build ontology

**Prompt**

```
/rai-build-starter-ontology Build a manufacturing maintenance ontology from the CSVs in data/. Scope it for preventive-maintenance scheduling over a multi-period horizon — introduce a Period concept (1..12 from the `period` column) alongside the source-bound concepts (machines, technicians, qualifications, products, production runs, downtime events, failure predictions, machine-product capabilities).
```

**Response**

Concepts bound to the bundled CSVs: `Machine` (50, across Plant_A/B/C × Turbine/Generator/Pump/Compressor/Motor), `Technician` (20), `Qualification` (32), `Product` (8), `ProductionRun` (844), `DowntimeEvent` (353), `FailurePrediction` (600), `MachineProductCapability` (120), and a generated `Period` (1..12). The `MachinePeriod` decision space is added later, in the prescriptive stage.

### 2. Examine the ontology

**Prompt**

```
/rai-querying What concepts and relationships does the ontology have, and how many rows are in each?
```

**Response**

50 `Machine`, 20 `Technician`, 32 `Qualification`, 8 `Product`, 844 `ProductionRun`, 353 `DowntimeEvent`, 600 `FailurePrediction`, 120 `MachineProductCapability`, and 12 `Period`. Machines relate to production runs, downtime events, failure predictions, and product capabilities; technicians relate to qualifications.

### 3. Discover reasoner questions

**Prompt**

```
/rai-discovery We run a 50-machine, 3-plant operation and want to keep it healthy: where are we losing output, what is likely to fail next, where are the structural single points of failure, and how should we schedule preventive maintenance under a thin bench of qualified technicians? Which of these are querying, rules, graph, predictive, and prescriptive questions?
```

**Response**

Routes the work across reasoner families: descriptive querying (OEE, downtime drivers, waste rates, technician coverage), rules (per-machine risk tiers), graph (producibility bottlenecks), predictive (forward failure risk), and prescriptive (preventive-maintenance scheduling with a technician what-if). These map to the stages below, in order.

### 4. Diagnose plant operations — OEE

**Prompt**

```
/rai-querying What's the OEE by plant, broken into Availability (planned time = production runs × 480 min per run; downtime = unplanned events only, is_planned = 0), Performance (avg of actual_speed / target_speed per run), and Quality (good_quantity / actual_quantity)? Compute OEE from the unrounded components, then round to one decimal.
```

**Response**

| Plant | Availability | Performance | Quality | OEE |
|---|---|---|---|---|
| Plant_C | 97.7% | 81.7% | 98.2% | **78.3%** |
| Plant_A | 96.4% | 71.8% | 98.3% | **68.0%** |
| Plant_B | 92.5% | 69.8% | 98.1% | **63.3%** |

Plant_C leads; Plant_B trails — driven by its low Availability (most unplanned downtime) and Performance.

### 5. Find the downtime drivers

**Prompt**

```
/rai-querying What are the top causes of downtime by specific fault name and their percent of total downtime? And which plant carries the most downtime?
```

**Response**

Top fault names: **Bearing Failure 3,905 min (19.4%)**, Overheating 3,183 (15.8%), Motor Burnout 2,344 (11.7%), Seal Degradation 2,328 (11.6%), Shaft Misalignment 1,600 (8.0%). By plant: **Plant_B 10,494 min (52.2%)**, Plant_A 6,576 (32.7%), Plant_C 3,033 (15.1%). Total downtime = 20,103 min.

### 6. Surface the worst waste

**Prompt**

```
/rai-querying Which machine-product combinations have the worst waste rates (waste_quantity / actual_quantity), to one decimal?
```

**Response**

M025 + Hydraulic Seal Kit (3.8%), M005 + Turbine Blade Assembly (3.7%), M002 + Turbine Blade Assembly (3.6%), M049 + Motor Winding Set (3.6%), M045 + Control Panel Unit (3.5%).

### 7. Check technician coverage

**Prompt**

```
/rai-querying Which machine types have the fewest qualified technicians?
```

**Response**

Turbines are most constrained — only **3** qualified technicians (T001, T009, T017). Generators have 6; Pumps 7; Compressors and Motors 8 each. This concentration is what later makes Turbine coverage fragile in the schedule.

### 8. Classify machine risk

**Prompt**

```
/rai-rules-authoring Rate each machine's risk from three flags: chronic = more than 15 downtime events; high-risk = failure probability above 0.20 AND criticality 4 or higher; maintenance-overdue = remaining useful life of 9 or less. All three flags → Critical; exactly two → Elevated; otherwise Standard.
```

**Response**

**3 Critical** — M001 (Turbine, Plant_A), M006 (Turbine, Plant_A), M011 (Compressor, Plant_B); **6 Elevated**; **41 Standard**. The two Critical Turbines sit in the same plant the coverage query already flagged as thin on Turbine technicians.

### 9. Find producibility bottlenecks

**Prompt**

```
/rai-graph-analysis In a bipartite machine-product capability graph (machines and products as nodes), which machines are the biggest producibility bottlenecks — the machines that the most production routes flow through, so they bridge the most product lines?
```

**Response**

The bipartite graph has 58 nodes (50 machines + 8 products) and 120 edges. Betweenness centrality is highest for the **20 machines that each make three products — every Pump (M021–M030) and Motor (M041–M050)** — which tie at the top (46.7) because the most production routes flow through them; the two-product machines sit on no shortest paths. (A machine-machine co-occurrence projection over shared products surfaces the same 20.)

### 10. Predict forward failure risk

**Prompt**

```
/rai-predictive-modeling Which machines are most likely to fail over the next 12 periods, and what's the most likely failure mode for each? Use the bundled pre-loaded predictions, or train a live GNN over the sensor and downtime history.
```

**Response**

By default the template reads the bundled pre-loaded `failure_predictions` (no training step), so the answer is deterministic — by period 12 the highest-risk machines are M016 valve_stuck (42.0%), M028 seal_leak (42.0%), M011 valve_stuck (42.0%), M012 valve_stuck (41.5%), M047 motor_burnout (35.4%). To run it live instead, set `USE_PRELOADED_PREDICTIONS = False` and train a GNN over the sensor and downtime history (see _Customize_ in the README and the rai-predictive-modeling / rai-predictive-training skills).

### 11. Schedule preventive maintenance + stress-test

**Prompt**

```
/rai-prescriptive-problem-formulation What's the optimal preventive-maintenance schedule across the 50 machines and 12 periods — at most 5 jobs per period, each maintained machine assigned a qualified technician (Turbine work covered by an on-site technician at the same plant), prioritizing high failure-probability and high-criticality machines in earlier periods? And if technician T001 becomes unavailable, which machines lose coverage?
```

**Response**

Baseline solve is **OPTIMAL**: all **50 machines scheduled across periods 1–10** at 5 jobs/period (periods 11–12 absorb the slack), with the riskiest machines (M028, M016, M012, M006, M011) placed in period 1. Re-solving with **T001 unavailable** is still OPTIMAL but covers only **46 of 50** machines: the four Plant_A Turbines — **M001, M004, M006, M009** — lose coverage, because no on-site Turbine technician remains in Plant_A.

## Data

Bundled CSVs in `data/` (real `MANUFACTURING.PUBLIC`): 50 machines (3 plants, 5 types), 20 technicians, 32 qualifications, 8 products, 120 machine-product capabilities, 844 production runs, 353 downtime events, 600 failure predictions, 200 sensors / 2,400 sensor readings, plus travel, training options, availability, and degradation references. The five-stage script loads the first eight; the rest support the extensions in the README. All stages run in `machine_maintenance.py`.
