---
title: "Defect Root-Cause Analysis"
description: "Diagnose a final-test defect spike on an electronics assembly line: trace each unit's genealogy backward through the bill of materials, contrast-score candidate factors against good units, then solve a minimal set-cover MILP for the smallest, most specific set of root causes."
experience_level: advanced
industry: "Manufacturing"
featured: false
reasoning_types:
  - Graph
  - Rules-based
  - Prescriptive
tags:
  - root-cause-analysis
  - reachability
  - genealogy
  - bill-of-materials
  - set-cover
  - minimal-diagnosis
  - multi-reasoner
  - manufacturing
sidebar:
  order: 6
---

## What this template is for

Final-test failures on a discrete manufacturing line have spiked from a ~1.2% baseline to 6.3%. The genealogy is all there -- every serialized unit records which material lots it consumed (transitively, through a multi-tier bill of materials) and which machine and shift ran each operation -- but a naive "what's common to the failures?" scan points at whatever touches the most units: a near-universal housing lot, the busiest placement line. Those are red herrings. The real causes are specific and upstream.

This template works *backward* from the failures to the smallest, most specific set of causes that explains them, chaining three reasoners on one ontology:

- **Graph** reasoning closes the lot genealogy transitively, so each unit is linked to every lot consumed anywhere beneath it -- the inverse of forward BOM dependency tracing. This is what surfaces a contaminated component lot sitting two tiers below the finished unit.
- **Rules-based** reasoning contrast-scores each candidate factor by how concentrated defects are among the units it touches versus the plant-wide baseline, screening out high-coverage / low-lift factors before optimization.
- **Prescriptive** reasoning solves a minimal-diagnosis set-cover MILP: the smallest, least-collateral set of suspect factors that together explain the failures, preferring the specific deep root over the proximate sub-assemblies that merely carry it.

The result is a defensible, ranked root-cause diagnosis -- not a correlation table.

## Who this is for

- **Quality and process engineers** investigating a yield drop or warranty spike who need to move from "here are 40 things the bad units have in common" to "here are the 2 root causes."
- **Manufacturing analysts** who want to learn backward reachability, contrast scoring, and minimal-diagnosis optimization on a realistic genealogy.
- **Advanced users** combining graph, rules, and prescriptive reasoning in a single accretive-enrichment pipeline.

## What you'll build

- Load a serialized electronics-assembly corpus (2,500 finished units, a four-tier BOM, 105 material lots, process history, and final-test results) from CSV.
- Build a directed lot-genealogy graph and compute transitive backward reachability, linking each unit to its full upstream lot set (`Unit.touches_lot`).
- Contrast-score every candidate factor -- lot, machine, or shift -- by defect lift versus baseline, and flag suspects (`Factor.lift`, `Factor.is_suspect`).
- Solve a set-cover MILP for the minimal set of root causes (`Factor.is_root_cause`) and persist a queryable headline (`DiagnosisResult`).

## What's included

- **Self-contained pipeline**: `defect_root_cause.py` -- runs the full three-stage analysis end-to-end.
- **Data generator**: `generate_data.py` -- regenerates the corpus (seeded) with the planted root causes and decoys. The generated CSVs are already included, so you do not need to run it to use the template.
- **Data**: ten CSVs under `data/` -- the SKU structure, bill of materials, suppliers, machines, lots, lot genealogy, units, unit-to-lot consumption, unit process history, and the candidate-factor universe.

## Prerequisites

- Python >= 3.10
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.
- A prescriptive engine for the Stage 3 MILP. The template solves with the open-source HiGHS solver, which requires no additional license.

## Quickstart

1. Download and extract this template:

   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/defect_root_cause.zip
   unzip defect_root_cause.zip
   cd defect_root_cause
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

   ```bash
   python -m pip install .
   ```

4. **Configure Snowflake connection and RAI profile**

   ```bash
   rai init
   ```

5. **Run the template**

   ```bash
   python defect_root_cause.py
   ```

## Template structure

```text
defect_root_cause/
├── README.md
├── runbook.md                # analyst-facing, paste-testable walkthrough
├── pyproject.toml
├── defect_root_cause.py      # the three-stage pipeline
├── generate_data.py          # regenerates the corpus (CSVs already included)
└── data/
    ├── skus.csv              # 20 SKUs across four tiers
    ├── bill_of_materials.csv # 26 BOM edges (output SKU requires input SKU)
    ├── suppliers.csv
    ├── machines.csv          # placement / reflow / assembly / test equipment
    ├── lots.csv              # 105 received or produced batches
    ├── lot_genealogy.csv     # 162 parent -> child lot edges
    ├── units.csv             # 2,500 serialized units + final-test result
    ├── unit_lots.csv         # top-tier lots each unit consumes
    ├── unit_process.csv      # which machine/shift ran each operation
    └── factors.csv           # 118 candidate factors (lots + machines + shifts)
```

## How it works

```text
CSV genealogy corpus
  --> Stage 1 (Graph):        backward reachability over lot genealogy  --> Unit.touches_lot
  --> Stage 2 (Rules):        contrast scoring vs. baseline             --> Factor.lift, Factor.is_suspect
  --> Stage 3 (Prescriptive): minimal set-cover MILP                    --> Factor.is_root_cause, DiagnosisResult
```

### Stage 1 -- Graph: backward reachability over the lot genealogy

The lot genealogy is a directed parent -> child graph: a built lot consumes its input lots. Closing it transitively links each unit to every lot beneath the top-tier lots it consumed -- so a contaminated component lot two tiers down is attributed to every finished unit that carries it.

```python
graph = Graph(model, directed=True, weighted=False, node_concept=Lot)
parent, child = Lot.ref(), Lot.ref()
model.where(parent.consumes(child)).define(graph.Edge.new(src=parent, dst=child))

reach = graph.reachable(full=True)

Unit.touches_lot = model.Relationship(f"{Unit} touches {Lot:lot}")
model.where((u := Unit.ref()).consumes_lot(top := Lot.ref())).define(Unit.touches_lot(u, top))
model.where(
    (u := Unit.ref()).consumes_lot(top := Lot.ref()),
    reach(top, deep := Lot.ref()),
).define(Unit.touches_lot(u, deep))
```

A unified `Factor.touches` incidence then puts lots, machines, and shifts on the same footing: lot factors inherit the genealogy closure, while machine and shift factors come straight from process history.

### Stage 2 -- Rules: contrast scoring

Each candidate factor is scored by how concentrated defects are among the units it touches. `lift` is the factor's defect rate divided by the plant-wide baseline; a factor becomes a suspect only when its lift, support, and defect count all clear threshold. This is what screens out the high-coverage, low-lift trunk factors that dominate a raw count.

```python
model.define(Factor.touched_count(aggs.count(Unit).per(Factor).where(Factor.touches(Unit))))
model.define(Factor.defect_count(aggs.count(Unit).per(Factor).where(Factor.touches(Unit), Unit.is_defective())))
model.where(Factor.defect_count > 0).define(
    Factor.lift((floats.float(Factor.defect_count) / floats.float(Factor.touched_count)) / BASELINE_RATE)
)
model.where(
    Factor.lift >= LIFT_THRESHOLD,
    Factor.touched_count >= MIN_SUPPORT,
    Factor.defect_count >= MIN_DEFECTS,
).define(Factor.is_suspect(Factor))
```

### Stage 3 -- Prescriptive: minimal-diagnosis set-cover MILP

A binary variable names each suspect factor a root cause; a binary slack lets a defective unit be left unexplained. The coverage constraint requires every defective unit to be explained by a named factor it touches or marked unexplained. The objective minimizes a parsimony cost (per named factor), a specificity penalty (per good unit a named factor also touches), and the count of unexplained defects -- so the diagnosis prefers the single deep root over the several proximate sub-assembly lots that carry it.

```python
problem = Problem(model, Float)
problem.solve_for(Factor.is_root_cause, where=[Factor.is_suspect()], type="bin", name=["pick", Factor.id])
problem.solve_for(Unit.unexplained, where=[Unit.is_defective()], type="bin", name=["slack", Unit.id])

cover = problem.satisfy(
    model.where(Unit.is_defective()).require(
        (aggs.sum(Factor.is_root_cause).per(Unit).where(Factor.touches(Unit)) | 0) + Unit.unexplained >= 1.0
    ),
    name=["cover", Unit.id],
)
problem.minimize(
    aggs.sum(Factor.is_root_cause * Factor.select_cost) + W_UNEXPLAINED * aggs.sum(Unit.unexplained)
)
problem.solve("highs", time_limit_sec=120)
```

## Sample output

The naive raw-count view ranks high-volume trunk factors first -- none of which is a cause. Contrast scoring flips the ranking, and set cover resolves the suspects to the two real roots.

```text
Loaded 2500 units, 157 defective (6.28% final-test failure rate)
Genealogy graph: 105 lot nodes, 162 parent->child edges
Backward reachability built 57,142 (factor, unit) incidence facts.
Top candidate factors by RAW defective units touched (pre-contrast -- note the high-volume bias):
           factor    kind  units  defects
 LOT::RM-POLY-L01     LOT   2500      157
 LOT::CP-HOUS-L01     LOT   2195      137
LOT::RM-RESIN-L02     LOT   1627      125
  MACHINE::SMT-01 MACHINE   1778      114
   LOT::RM-LI-L01     LOT   1795      110
   LOT::RM-SI-L04     LOT   1984      109

Contrast scoring: 9 suspect factors (baseline failure rate 6.28%, lift>=1.5, support>=30, defects>=5)
          factor    kind units defects     rate     lift
LOT::SA-PCBA-L05     LOT   132      31 0.234848 3.739626
LOT::SA-PCBA-L09     LOT   129      28 0.217054 3.456278
    LOT::SP-0423     LOT   371      78 0.210243 3.347812
 LOT::CP-PCB-L08     LOT   110      19 0.172727 2.750434
LOT::SA-PCBA-L15     LOT   110      19 0.172727 2.750434
 LOT::CP-SOC-L04     LOT   260      37 0.142308 2.266046
  LOT::RM-SI-L03     LOT   260      37 0.142308 2.266046
 MACHINE::REF-02 MACHINE   584      77 0.131849 2.099511
 LOT::CP-PCB-L03     LOT   375      36 0.096000 1.528662

Pre-solve audit: 157 coverage constraints grounded (one per defective unit).
Diagnosis solve: OPTIMAL   objective=42.0
Root-cause diagnosis: 2 factors explain 141/157 defective units (90% coverage)
         factor                  label    kind defects_on_factor     lift
   LOT::SP-0423   CP-PASTE lot SP-0423     LOT                78 3.347812
MACHINE::REF-02 Reflow oven 2 (REFLOW) MACHINE                77 2.099511

Corroborating evidence per root cause:
  CP-PASTE lot SP-0423       87% COLD_SOLDER    supplier Meridian Components, received 2026-02-09
  Reflow oven 2 (REFLOW)     84% SOLDER_BRIDGE  168 days since last calibration
```

The diagnosis names a contaminated solder-paste lot (`SP-0423`) and a reflow oven (`REF-02`). Note what the MILP did with the suspects: three populated-board lots (`SA-PCBA-L05/L09/L15`) carry the contaminated paste and so score high on lift, but the optimizer prefers the single deep paste lot that explains all of them -- and ignores the correlated bystanders (`CP-SOC-L04`, `RM-SI-L03`) whose defects are already covered. Each named cause is reported with the evidence an engineer would confirm physically: SP-0423's failures are overwhelmingly cold solder (the paste signature) and it arrived mid-window, while REF-02's are solder bridges and it is 168 days past calibration. The diagnosis is the prioritized hypothesis; the evidence is what you check next.

## Customize this template

**Use your own data:**
- Replace the CSVs in `data/` with your own genealogy, keeping the same column names. The genealogy can be any depth -- backward reachability handles arbitrary BOM tiers.
- Add factor kinds (operator, work order, supplier site) by appending rows to `factors.csv` and a back-pointer property plus one `Factor.touches` rule, mirroring the lot / machine / shift pattern.

**Tune the diagnosis:**
- `LIFT_THRESHOLD`, `MIN_SUPPORT`, `MIN_DEFECTS` set how aggressively the contrast stage admits suspects.
- `W_SELECT`, `W_GOOD`, `W_UNEXPLAINED` trade off parsimony, specificity, and coverage in the MILP objective.

**Regenerate the corpus:**
- Run `python generate_data.py` to rebuild the CSVs. Edit the planted causes, decoys, and volumes at the top of the file to author your own scenario.

## Troubleshooting

<details>
  <summary>Why does the diagnosis leave some defects unexplained?</summary>

- The MILP includes a per-unit <code>unexplained</code> slack so that a handful of scattered baseline failures -- units whose only common factors are low-lift -- are left unexplained rather than forcing a spurious root cause. Lower <code>W_UNEXPLAINED</code> to tolerate more unexplained defects, or raise it to push the optimizer toward fuller coverage.

</details>

<details>
  <summary>Why are the top RAW-count factors not the diagnosis?</summary>

- High-volume factors (a near-universal raw-material lot, the busiest line) touch almost every unit, so they touch many defective units too -- but at the baseline rate. Their lift is ~1.0, so the contrast stage screens them out before the MILP ever sees them. This is the central lesson of the template: coverage is not causation.

</details>

<details>
  <summary>Why does authentication/configuration fail?</summary>

- Run <code>rai init</code> to create/update <code>raiconfig.toml</code>.
- If you have multiple profiles, set <code>RAI_PROFILE</code> or switch profiles in your config.

</details>
