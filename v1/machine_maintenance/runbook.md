# Runbook: Machine Maintenance — Multi-Reasoner Walkthrough

Schedules preventive maintenance for a 30-machine, 3-plant operation. OEE alone misranks the plants; sensor counts don't quantify forward risk; rules flag machines but don't allocate scarce technician time; the optimizer produces a feasible schedule but can't see that all Turbine techs sit in one city. The chain threads querying, graph, rules, and prescriptive reasoners through one ontology so each stage's enrichments feed the next.

## The chain

```
Plant_B looks worst on OEE (61.4%). Plant_A looks mid-tier (68.2%).
The chain shows Plant_A is actually the highest-risk plant — and that
all 3 Turbine techs sit in one city, a $3,200 fix away from resolved.

  ─────────────────────────────────────────────────────────────────
  STAGE 0  Querying     ──►  Machine.performance_ratio  (30)
                              Machine.quality_ratio  (30)
                              Machine.anomaly_count  (30)
                              MachinePeriod.predicted_fp  (120)
                              Plant_C 79.8% > Plant_A 68.2% > Plant_B 61.4%
                              7 of 9 sensor anomalies are at Plant_A.
  ─────────────────────────────────────────────────────────────────
  STAGE 1  Graph        ──►  Machine.betweenness  (30)
                              30 machines → 1 connected component.
                              Pumps tie for top centrality (24.0).
  ─────────────────────────────────────────────────────────────────
  STAGE 2  Rules        ──►  Machine.is_overdue_maintenance  (6)
                              Machine.is_high_risk  (1)
                              Machine.is_chronic_downtime  (3)
                              Machine.risk_tier  (30)
                              M013 (Pump, Plant_A) = Critical (3 of 3).
  ─────────────────────────────────────────────────────────────────
  STAGE 3  Prescriptive ──►  MachinePeriod.x_maintain  (120 binary)
                              MachinePeriod.x_vulnerable  (120 binary)
                              TechnicianMachinePeriod.x_assigned
                              OPTIMAL · 20 jobs · 4 periods · $605,241
  ─────────────────────────────────────────────────────────────────
  STAGE 4  Resilience   ──►  Concentration analysis on the solve
                              Turbine: all 3 techs in Houston_TX.
                              67% of scheduled Turbine jobs travel.
                              Cross-train T006 (Chicago) — $3,200 / 5 wks.
  ─────────────────────────────────────────────────────────────────
```

## Workflow

### 1. Build ontology

- Prompt: `/rai-build-starter-ontology Build a manufacturing maintenance ontology from the CSVs in data/ covering machines, technicians, qualifications, periods, sensor readings, failure predictions, downtime events, production runs, parts inventory, and certification expiry.`
- Response: Concepts: `Machine`, `Technician`, `Qualification`, `Period`, `MachinePeriod`, `TechnicianPeriod`, `TechnicianMachinePeriod`, `Sensor`, `SensorReading`, `FailurePrediction`, `DowntimeEvent`, `ProductionRun`, `PartsInventory`, `CertificationExpiry` — bound to the bundled CSVs (30 machines × 3 plants, 10 technicians, 4 periods). `training_options.csv` is loaded as a DataFrame (read in Stage 4), not modeled as a concept.

### 2. Examine ontology

- Prompt: `/rai-querying Show the ontology as a concept-relationship diagram and report row counts per concept.`
- Response: Concepts wired to the bundled CSVs: 30 `Machine` (3 plants × 5 types), 10 `Technician` (3 cities), 16 `Qualification`, 4 `Period`, 120 `MachinePeriod`, 60 `Sensor` and 240 `SensorReading`, 120 `FailurePrediction`, 129 `DowntimeEvent`, 120 `ProductionRun`, plus parts inventory and certification-expiry rows.

### 3. Discover reasoner questions

- Prompt: `/rai-discovery We need to schedule preventive maintenance for 30 machines across 3 plants. Where does OEE alone mislead us, and what structural risks won't a pure optimizer surface?`
- Response: Plan routing sub-questions to querying, graph, rules, prescriptive, and resilience skills.

### 4. Diagnose plant operations

- Prompt: `/rai-querying What's the OEE by plant? Which machines have the most sensor anomalies, and which are most likely to fail by the end of the planning horizon?`
- Response: Plant_C 79.8% > Plant_A 68.2% > Plant_B 61.4%; 7 of 9 anomalies at Plant_A; `MachinePeriod.predicted_fp` written for 120 rows.

### 5. Find scheduling bottlenecks

- Prompt: `/rai-graph-analysis Which machines share qualified technicians, and which are bottlenecks in the qualification network? Compute centrality and write it back to each machine so the optimizer can weight critical machines.`
- Response: 30 machines → 1 connected component; Pumps tie at top betweenness (24.0 raw, 1.0 normalized); `Machine.betweenness` stored.

### 6. Classify machine risk

- Prompt: `/rai-rules-authoring Rate each machine's risk: chronic if >8 downtime events, high-risk if failure prob >0.3 AND criticality 4+, plus overdue for maintenance. All three flags = Critical, two = Elevated, otherwise Standard.`
- Response: 6 overdue, 1 high-risk, 3 chronic; M013 (Pump, Plant_A) = Critical; M016 (Turbine, Plant_A) = Elevated.

### 7. Schedule maintenance

- Prompt: `/rai-prescriptive-problem-formulation Schedule preventive maintenance for all 30 machines across 4 periods, capped at 5 jobs per period. Every overdue machine gets maintained by period 2, and each maintained machine needs a qualified technician. Minimize expected failure cost (weighted by criticality and centrality) plus labor and travel.`
- Response: 120 `x_maintain` + 120 `x_vulnerable` + 384 `x_assigned` binaries (96 qualified tech×machine pairs × 4 periods); 5 constraint families (cumulative coverage, assignment-maintenance linkage, technician hours, parts/bay capacity, overdue deadline); failure cost uses `x_vulnerable × predicted_fp × parts_cost × criticality × (1 + 2.0 × betweenness)`.

### 8. Stress-test concentration

- Prompt: `/rai-prescriptive-solver-management + /rai-prescriptive-results-interpretation For each machine type, check whether all qualified technicians sit in one location and recommend the cheapest cross-training fix.`
- Response: OPTIMAL · 20 jobs · $605,241; Turbine concentrated in Houston_TX (67% of jobs travel); cross-train T006 (Chicago_IL, Senior) for $3,200 / 5 weeks.

### 9. Persist the chain into the ontology

- Prompt: `/rai-ontology-design Promote the per-stage enrichments to first-class ontology state: OEE-proxy properties, betweenness, the seven per-machine risk flags, the composite risk tier. Add a `MaintenancePlan` concept (one row per maintained `(machine, period, technician)` triple) and a `CrossTrainingRecommendation` concept so the optimizer's outputs persist as ontology.`
- Response: Ontology now carries `Machine.performance_ratio / quality_ratio / anomaly_count / betweenness / is_overdue_maintenance / is_high_risk / is_chronic_downtime / risk_tier`, plus a `MaintenancePlan` concept holding the 20 scheduled jobs and a `CrossTrainingRecommendation` concept for T006 / Chicago_IL / $3,200 / 5 weeks.

## Data

Bundled CSVs in `data/`: 30 machines (3 plants × 5 types), 10 technicians (3 cities), 16 qualifications, 4 periods, 60 sensors / 240 readings, 120 failure predictions, 129 downtime events, 120 production runs, 13 training options. All five stages run in `machine_maintenance.py`.
