# Runbook: Machine Maintenance — Multi-Reasoner Walkthrough

Walk-through of the chained-reasoner pattern this template is built on. One realistic plant-floor thread — **scheduling preventive maintenance for a 30-machine, 3-plant operation** — traced across querying, graph, rules, and prescriptive reasoners, each stage writing properties back to the same ontology that downstream stages consume.

The template's combined script (`machine_maintenance.py`) implements all five stages directly; this runbook expands the surrounding narrative — what each prompt asks, what shape of output to expect, and how each enrichment feeds the next — so a reader can follow the reasoning thread end-to-end without re-running the script.

---

## TL;DR — the chain in one screen

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

A single-reasoner approach can't surface this. OEE alone says Plant_B is the problem. Sensor counts alone don't quantify forward risk. Rules alone flag machines but don't allocate scarce technician time. The optimizer alone produces a feasible schedule — but doesn't know that a single weather event in Houston blocks all on-site Turbine work.

---

## How to read this runbook

This runbook serves two audiences:

- **Reading top-to-bottom**: the narrative + ASCII visualizations show what the chain produces stage-by-stage, with the same business framing the stakeholder would see.
- **Per-stage skill blocks**: the boxed `Skill / Prompt` callout at the start of each stage is the recipe — load that RAI agent skill, give it that prompt against the bundled demo data, and the agent will reproduce the stage.

---

## Step 0 — Scope the question with `rai-discovery`

> **Skill:** `rai-discovery` ·
> **Prompt:** "We need to schedule preventive maintenance for 30 machines across 3 plants. Where does OEE alone mislead us, and what structural risks won't a pure optimizer surface?"

Discovery classifies the question by reasoner family and tells you which downstream skills to load:

| Sub-question | Reasoner | Skill |
|---|---|---|
| Where does the operation actually hurt — OEE, anomalies, failure trajectories? | Querying / Descriptive | `rai-querying` |
| Which machines are scheduling bottlenecks given shared technician pools? | Graph | `rai-graph-analysis` |
| Which machines are overdue, high-risk, chronic, or composite-Critical? | Rules | `rai-rules-authoring` |
| What's the optimal maintain-and-assign plan across 4 periods? | Prescriptive | `rai-prescriptive-problem-formulation` |
| Where is the schedule structurally fragile, and what cross-training fixes it? | Prescriptive (re-solve / interpretation) | `rai-prescriptive-solver-management` + `rai-prescriptive-results-interpretation` |

Discovery's output is a *plan*, not code. Everything that follows materializes that plan.

---

## Setup

See the template's main `README.md` for installation, RAI connection setup, and how to run the script. The narrative below follows the actual stage outputs of `machine_maintenance.py`.

**Prerequisites**

- Template's `data/` CSVs available (or your own Snowflake schema with equivalent tables — `machines`, `technicians`, `qualifications`, `availability`, `parts_inventory`, `certification_expiry`, `sensors`, `sensor_readings`, `failure_predictions`, `downtime_events`, `production_runs`, `training_options`)
- `raiconfig.yaml` pointing at your RAI engine
- Python ≥ 3.10 with `relationalai >= 1.0.14`

---

## Workflow

The runbook walks the same chain stage-by-stage, prompt-by-prompt, in agent-skill order. Each row maps to a section of the script.

| # | Step | Skill | Prompt | Expected Output |
|---|------|-------|--------|-----------------|
| 1 | Build ontology | `/rai-build-starter-ontology` | "Build a RAI ontology for a manufacturing maintenance scheduling problem from the CSVs in `data/`. Concepts: Machine, Technician, Qualification, Period, MachinePeriod, TechnicianPeriod, TechnicianMachinePeriod, PartsInventory, CertificationExpiry, Sensor, SensorReading, FailurePrediction, DowntimeEvent, ProductionRun." | Model `machine_maintenance` with 14 user-facing concepts. 30 Machine rows (3 plants × 10 machines, 5 types × 6). 10 Technician rows (4 Chicago_IL, 3 Houston_TX, 3 Phoenix_AZ). 16 Qualification rows. 4 Period rows. |
| 2 | Discovery | `/rai-discovery` | "What questions can we answer with this ontology? We want to schedule preventive maintenance and surface hidden operational risk." | Querying: OEE by facility, anomaly counts, failure trajectory deltas. Graph: machine dependency clusters, bottleneck centrality on shared-technician edges. Rules: overdue, high-risk, chronic-downtime flags chained to a composite risk tier. Prescriptive: maintain × period × technician assignment minimizing failure + labor + travel cost. Resilience: post-solve concentration analysis. |
| 3 | Stage 0 — OEE proxy | `/rai-querying` | "Compute OEE proxy (Performance × Quality) by facility. Performance is total_actual / total_planned across ProductionRuns; Quality is total_good / total_actual." | Plant_C: Perf 81.3%, Qual 98.1%, OEE 79.8%. Plant_A: Perf 69.8%, Qual 97.8%, OEE 68.2%. Plant_B: Perf 62.6%, Qual 98.1%, OEE 61.4%. Quality is uniform; Performance is the differentiator. |
| 4 | Stage 0 — Sensor anomalies | `/rai-querying` | "List machines with above-threshold sensor readings (`SensorReading.is_anomaly == 1`), grouped by facility." | 9 anomaly readings across 5 machines. Plant_A: 7 (M013 Pump:3, M001 Turbine:2, M016 Turbine:2). Plant_B: 1 (M002 Compressor). Plant_C: 1 (M006 Turbine). Plant_A's anomaly load is 7× Plant_B's despite Plant_A's higher OEE. |
| 5 | Stage 0 — Failure trajectories | `/rai-querying` | "For each machine, compute the failure-probability delta from period 1 to period 4 from `FailurePrediction`. Show the steepest 6." | M001 (Turbine, Plant_A): 0.102 → 0.332 (+0.230, bearing_wear). M013 (Pump, Plant_A): 0.435 → 0.663 (+0.228, impeller_erosion). M016 (Turbine, Plant_A): 0.263 → 0.482 (+0.219, bearing_wear). All three steepest curves are Plant_A. Stored back as `MachinePeriod.predicted_fp` (120 rows) for Stage 3's objective. |
| 6 | Stage 1 — Dependency graph | `/rai-graph-analysis` | "Build a graph with `Machine` as `node_concept`. Two machines are adjacent when at least one technician is qualified for both machine types. Run weakly connected components." | 30 nodes, edges joined via `Qualification`. WCC: 1 cluster of 30 — every machine is reachable from every other through shared qualifications. No isolated subgraphs. |
| 7 | Stage 1 — Bottleneck centrality | `/rai-graph-analysis` | "Compute betweenness centrality on the dependency graph. Normalize and store as `Machine.betweenness`." | Pump-type machines tie at the top (raw betweenness 24.0 → normalized 1.0): M003 (Plant_C), M008 (Plant_B), M013 (Plant_A). Turbines, Generators, Motors, Compressors lower. `Machine.betweenness` written back for all 30 machines and consumed by Stage 3's failure-cost multiplier. |
| 8 | Stage 2 — Compliance flags | `/rai-rules-authoring` | "Define seven derived flags: overdue (`remaining_useful_life < maintenance_duration_hours`), high-risk (`failure_probability > 0.3 AND criticality >= 4`), anomalous (`anomaly_count > 0`), chronic-downtime (`downtime_event_count > 8`), parts-reorder (`stock_level <= min_order_qty`), expiring-cert (`days_remaining < 30`). Use `model.where(...).define(...)`." | Overdue (6): M002, M006, M013, M016, M022, M025 (RUL below required maintenance hours). High-risk (1): M013 (fp=0.435, crit=4). Anomalous (5): M013, M001, M016, M002, M006. Chronic downtime (3, threshold > 8 events): M001 (12 events), M016 (11), M013 (10). Parts reorder (4): P001, P003, P004, P006. Expiring certs (5): T001 Compressor 22d, T004 Pump 8d, T003 Compressor 15d, T006 Motor 25d, T009 Motor 12d. |
| 9 | Stage 2 — Composite risk tier | `/rai-rules-authoring` | "Chain `is_chronic_downtime`, `is_high_risk`, `is_overdue_maintenance` into `Machine.risk_tier`: Critical if all three, Elevated if exactly two, Standard otherwise. Enumerate all 8 combinations using `model.not_()` for negation." | Critical (1): M013 (Pump, Plant_A) — chronic + high-risk + overdue. Elevated (1): M016 (Turbine, Plant_A) — chronic + overdue, not high-risk. Standard (28): rest. Plant_A holds the only Critical and the only Elevated machine despite ranking second on OEE. |
| 10 | Stage 3 — Formulation | `/rai-prescriptive-problem-formulation` | "Formulate the maintenance schedule. Decision variables: `MachinePeriod.x_maintain` (bin), `MachinePeriod.x_vulnerable` (bin), `TechnicianMachinePeriod.x_assigned` (bin) — restricted to qualified pairs. Constraints: cumulative coverage (`Σ x_maintain[m,1..τ] + x_vulnerable[m,τ] = 1` per machine and period), assignment-maintenance linkage (`Σ x_assigned over techs = x_maintain` per (m,τ)), technician hour capacity (`Σ x_assigned · duration ≤ available_hours`), parts/bay capacity (`≤ 5 jobs per period`), and overdue deadline (`Σ x_maintain[m, τ ≤ 2] ≥ 1` for every overdue machine — feeds from Stage 2). Objective: minimize failure_cost + labor_cost + travel_cost." | 120 `x_maintain` binaries (30 machines × 4 periods). 120 `x_vulnerable` binaries. ~250 `x_assigned` binaries (qualification-restricted). 5 constraint families. Failure cost uses `MachinePeriod.predicted_fp` (Stage 0) × `Machine.criticality` × `(1 + 2.0 × Machine.betweenness)` (Stage 1). |
| 11 | Stage 3 — Solve | `/rai-prescriptive-solver-management` | "Solve with HiGHS, time limit 120s, assert OPTIMAL." | OPTIMAL. Objective = $605,240.61. 20 maintenance jobs scheduled across 4 periods (capacity-binding at 5 jobs/period). Both Plant_A overdue Turbines (M016 plus the rest of the overdue list) maintained by period 2 — overdue constraint satisfied. |
| 12 | Stage 3 — Schedule readout | `/rai-prescriptive-results-interpretation` | "Show the period-by-period schedule and technician assignments. Flag any travel (`base_location != machine.location`)." | Period 1 includes M002 (Plant_B), M006 (Plant_C), M013 (Plant_A), M016 (Plant_A) — high-priority overdue/critical machines. Periods 2–4 cover the remaining 16 jobs. Multiple Turbine assignments require travel because all 3 Turbine-qualified techs (T001, T002, T003) are based in Houston_TX while Turbines exist at all 3 plants. Travel cost is paid at $50/hr × duration. |
| 13 | Stage 4 — Concentration analysis | `/rai-graph-analysis`, `/rai-querying` | "From the qualification table, find machine types whose qualified technicians are all in one location. For each concentrated type, count how many scheduled jobs require travel." | Compressor: techs in Chicago_IL, Houston_TX (gap: Phoenix_AZ). Generator: Chicago_IL, Phoenix_AZ (gap: Houston_TX). Motor: Chicago_IL, Phoenix_AZ (gap: Houston_TX). Pump: Chicago_IL, Phoenix_AZ (gap: Houston_TX). **Turbine: all 3 techs in Houston_TX — CONCENTRATED.** Of 3 scheduled Turbine jobs, 2 require travel (67%). 4 of 6 Turbines are at remote plants. The optimizer found the cheapest plan but cannot fix the structural fragility — losing T001's Compressor cert (22 days remaining) doesn't break Turbines, but losing any of T001/T002/T003 from Houston shrinks Turbine coverage by a third. |
| 14 | Stage 4 — Cross-training recommendation | `/rai-prescriptive-results-interpretation` | "From `training_options.csv`, find the cheapest Turbine-cross-training candidate based outside Houston_TX." | Best candidate: **T006 (Fiona_Garcia, Senior, Chicago_IL) — $3,200 / 5 weeks.** Other non-Houston options: T005 ($3,500/6w, Chicago), T008 ($3,800/6w, Phoenix), T009 ($4,200/8w, Phoenix), T004 ($5,500/10w, Chicago). Training T006 adds the first non-Houston Turbine tech, eliminates the single-point-of-failure for Plant_B and Plant_C Turbines, and pays back the first time travel or a cert lapse would have idled a Turbine job. The prescriptive reasoner produced the schedule; the resilience layer produced the structural action item. |

---

## Stage 0 — Querying: operational intelligence

> **Skill:** `rai-querying` ·
> **Prompt:** "What's the OEE by plant? Which machines have the most sensor anomalies, and which are most likely to fail by the end of the planning horizon?"

This stage establishes the operational baseline. Plant_C leads at 79.8% OEE; Plant_B trails at 61.4%. But Plant_A — middle of the OEE pack at 68.2% — owns 7 of 9 sensor anomalies and the three steepest failure trajectories (M001, M013, M016). The querying stage writes nine derived properties on `Machine` plus `MachinePeriod.predicted_fp` (120 rows), and Stage 3 reads `predicted_fp` directly into the failure-cost objective term.

## Stage 1 — Graph: dependency clusters and bottleneck centrality

> **Skill:** `rai-graph-analysis` ·
> **Prompt:** "Which machines share qualified technicians, and which are bottlenecks in the qualification network? Compute centrality and write it back to each machine so the optimizer can weight critical machines."

The 30 machines form a single connected component — every machine is reachable through shared qualifications. Pump-type machines tie at the top of betweenness (raw 24.0, normalized 1.0): M003 (Plant_C), M008 (Plant_B), M013 (Plant_A). The normalized centrality is consumed by Stage 3's failure-cost multiplier `(1 + 2.0 × betweenness)`, so leaving a bottleneck Pump vulnerable is markedly more expensive than leaving a peripheral Motor vulnerable.

## Stage 2 — Rules: compliance flags and composite risk tier

> **Skill:** `rai-rules-authoring` ·
> **Prompt:** "Rate each machine's risk: chronic if >8 downtime events, high-risk if failure prob >0.3 AND criticality 4+, plus overdue for maintenance. All three flags = Critical, two = Elevated, otherwise Standard."

Six machines overdue, one high-risk (M013), three chronic-downtime, four parts-reorder, five expiring certs. The composite tier surfaces a single Critical machine — M013 (Pump, Plant_A) — and a single Elevated machine — M016 (Turbine, Plant_A). The overdue flag is consumed by Stage 3 as a hard constraint: every overdue machine must be scheduled by period 2.

## Stage 3 — Prescriptive: maintenance schedule

> **Skill:** `rai-prescriptive-problem-formulation` ·
> **Prompt:** "Schedule preventive maintenance for all 30 machines across 4 periods, capped at 5 jobs per period. Every overdue machine gets maintained by period 2, and Turbines need an on-site qualified technician. Minimize expected failure cost weighted by criticality and centrality, plus labor and travel."

The solver returns OPTIMAL with objective $605,240.61 and 20 maintenance jobs across the four periods (capacity-binding at 5 jobs/period). M013 and M016 — Plant_A's Critical and Elevated machines — are both scheduled by period 1, satisfying the overdue deadline. Several Turbine assignments require travel because all three Turbine-qualified techs are based in Houston_TX while four of six Turbines sit at Plant_A and Plant_C. The optimizer pays the travel cost; it cannot restructure the qualification pool.

## Stage 4 — Resilience: concentration sweep and cross-training

> **Skill:** `rai-prescriptive-solver-management` + `rai-prescriptive-results-interpretation` ·
> **Prompt:** "For each machine type, are all qualified technicians concentrated in one location? How many scheduled jobs required travel, and what's the cheapest cross-training option to eliminate the single-point-of-failure?"

Turbine is the concentrated type — all three qualified techs (T001, T002, T003) sit in Houston_TX, and 67% of scheduled Turbine jobs already require travel. The recommended fix: cross-train T006 (Senior, Chicago_IL) for $3,200 over 5 weeks. That single addition eliminates the Houston single-point-of-failure for Turbine work at Plant_B and Plant_C, and pays back the first time a weather event, illness, or expiring cert would have idled a Turbine job that the optimizer would otherwise have left uncovered.

---

## Stage outputs — what each reasoner contributes back

```
ONTOLOGY ENRICHMENT — what each stage wrote back

  Stage 0 (querying)      Machine.total_planned_qty               [30]
                          Machine.total_actual_qty                [30]
                          Machine.total_good_qty                  [30]
                          Machine.performance_ratio               [30]
                          Machine.quality_ratio                   [30]
                          Machine.total_downtime_minutes          [30]
                          Machine.downtime_event_count            [30]
                          Machine.anomaly_count                   [30]
                          MachinePeriod.predicted_fp              [120]

  Stage 1 (graph)         Machine.betweenness_raw                 [30]
                          Machine.betweenness   (normalized)      [30]

  Stage 2 (rules)         Machine.is_overdue_maintenance          [6]
                          Machine.is_high_risk                    [1]
                          Machine.is_anomalous                    [5]
                          Machine.is_chronic_downtime             [3]
                          Machine.risk_tier                       [30]
                          PartsInventory.needs_reorder            [4]
                          CertificationExpiry.is_expiring         [5]

  Stage 3 (prescriptive)  MachinePeriod.x_maintain                [120 binary]
                          MachinePeriod.x_vulnerable              [120 binary]
                          TechnicianMachinePeriod.x_assigned

  Stage 4 (analysis)      (terminal — prints concentration risk and
                           costed cross-training recommendation)

  ──────────────────────────────────────────────────────────────────
  Each stage reads what the previous stage wrote.
  Re-running any downstream stage automatically picks up enrichments.
  No glue code, no DataFrame round-trip — same ontology throughout.
  ──────────────────────────────────────────────────────────────────
```

---

## The chain — accretive ontology enrichment

```
THE MACHINE-MAINTENANCE CHAIN

  STAGE 0  QUERYING
  "Where does the operation actually hurt?"
  reads:   ProductionRun, SensorReading, FailurePrediction
  writes:  Machine.performance_ratio / quality_ratio
           Machine.anomaly_count
           Machine.downtime_event_count / total_downtime_minutes
           MachinePeriod.predicted_fp
                         │
                         ▼
  STAGE 1  GRAPH (betweenness centrality)
  "Which machines are scheduling bottlenecks?"
  reads:   Qualification, Machine (as node_concept)
  writes:  Machine.betweenness        ── normalized 0..1
                         │
                         ▼
  STAGE 2  RULES
  "Which machines violate which compliance flags?"
  reads:   Machine.failure_probability, Machine.criticality,
           Machine.remaining_useful_life, Machine.maintenance_duration_hours,
           Machine.anomaly_count, Machine.downtime_event_count,
           PartsInventory.stock_level, CertificationExpiry.days_remaining
  writes:  Machine.is_overdue_maintenance / is_high_risk /
           is_chronic_downtime / is_anomalous
           Machine.risk_tier            ── Critical / Elevated / Standard
           PartsInventory.needs_reorder
           CertificationExpiry.is_expiring
                         │
                         ▼
  STAGE 3  PRESCRIPTIVE (HiGHS MIP)
  "What's the optimal maintain-and-assign plan?"
  reads:   MachinePeriod.predicted_fp        ──►  failure cost (period-specific)
           Machine.betweenness               ──►  failure cost multiplier
           Machine.is_overdue_maintenance    ──►  hard deadline constraint
           Qualification (assignment scope), TechnicianPeriod.capacity_hours
  writes:  MachinePeriod.x_maintain          ── 20 jobs flagged
           MachinePeriod.x_vulnerable
           TechnicianMachinePeriod.x_assigned
                         │
                         ▼
  STAGE 4  RESILIENCE
  "Where is the schedule structurally fragile?"
  reads:   Solution variables, Qualification, Technician, TrainingOption
  writes:  (terminal — concentration risk + cross-training recommendation)

  ──────────────────────────────────────────────────────────────────
  No glue. No DataFrame ping-pong. No re-derivation per-reasoner.
  Five reasoners, one ontology, one accretive thread.
  ──────────────────────────────────────────────────────────────────
```

---

## Why the chain matters (vs. any single stage)

| Stage alone | What it tells you | What it doesn't |
|---|---|---|
| Querying | "Plant_B has worst OEE; Plant_A has the most anomalies" | Whether anomalies translate to scheduling priority |
| Graph alone | "Pumps are the most central machine type" | Which Pump matters most or what to do |
| Rules alone | "M013 is Critical-tier" | How to fit M013 plus 19 others into a 4-period horizon with 10 techs |
| Prescriptive alone | (won't run — no per-period failure curve, no centrality weight, no overdue flag) | Whole pipeline misses |
| Resilience alone | (won't run — no schedule to analyze) | — |

| Combined | Output |
|---|---|
| Querying → Graph | Per-machine signals plus structural bottleneck weight |
| + Rules | Composite risk tier + a hard "must maintain by period 2" constraint |
| + Prescriptive | $605K plan, 20 jobs, Plant_A's Critical machine handled in Period 1 |
| + Resilience | Cross-train T006 for $3,200 → eliminates Houston Turbine concentration |

**Multi-reasoner chaining grounded in (and contributing to) the ontology.**

---

## Adapting this recipe to a new domain

The chain pattern transfers cleanly. To rebuild for a different scheduling-with-resilience problem:

1. Re-run `rai-discovery` on the new business question — does it actually need all five reasoner families, or is one or two sufficient? A pure dispatch problem may only need querying + prescriptive; a pure compliance problem may only need rules.
2. Strip the demo ontology to the concepts the new chain needs (lean is better for type inference and solver compile time). Keep the cross-product concept (`MachinePeriod`-equivalent) — it's where most decision variables and per-period derived properties live.
3. Stage 1 (querying) is required scaffolding: the optimization objective leans on derived per-period signals, not raw inputs.
4. Stages 2–5 are the load-bearing chain: graph centrality writes a multiplier the cost objective consumes; rules write a hard deadline the optimizer must satisfy; the optimizer writes solution variables the resilience sweep reads; the resilience layer doesn't re-solve a new problem — it stress-tests the structure underneath the existing solve and recommends a structural fix.
5. Keep the validation checks at every stage: assert flagged-set size, betweenness top-N looks plausible, the OPTIMAL gate, the objective is not zero, and the resilience pass surfaces at least one actionable recommendation when concentration exists.

The shape this template demonstrates — *each reasoner writes a property the next reasoner reads* — is what makes the chain accretive rather than serial. The agent skills are how you reliably author each link.

---

## Optional extension — operator-shift assignment

A second optimization pass — assigning operators to line-shifts to maximize a skill-match bonus, subject to a same-facility constraint — is a natural follow-on but not part of this template's main script. It would consume the same `Machine` and facility ontology and add `Operator`, `Shift`, and `OperatorShift` concepts. Out of scope for this runbook.

---

## Data Reference

- **Source data**: bundled CSVs in `../data/` (30 machines across 3 plants × 5 machine types, 10 technicians across 3 cities, 16 qualifications, 4 planning periods, 60 sensors with 240 readings, 120 per-period failure predictions, 129 downtime events, 120 production runs, 13 cross-training options). To run against your own Snowflake schema instead, swap the `read_csv(...)` loads for `model.Table(...)` references in `machine_maintenance.py`; the rest of the pipeline is unchanged.
- **Stages**: implemented in `../machine_maintenance.py` as a single combined script with stage banners (Stage 0 → Stage 4).
- **Ontology**: 14 user-facing concepts. Run `inspect.schema(model)` after the pipeline (see template README) to dump the full concept/property/relationship surface, filtering out reasoner-owned concepts (`Variable`, `Constraint`, etc.) and the auto-generated `graph<id>_Edge` from Stage 1.
