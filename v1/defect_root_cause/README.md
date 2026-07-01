---
title: "Defect Root-Cause Analysis"
description: "Diagnose a spike in final-test failures on an electronics assembly line by tracing each unit's history back through the bill of materials and the production line, then identifying the smallest set of causes that explains the failures."
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

When final-test failures suddenly climb on a manufacturing line, the cost adds up quickly: scrap, rework, held shipments, and the risk of defective product reaching customers. The hard part is rarely noticing that something broke. It is finding what broke, quickly, among thousands of units, hundreds of material lots, and dozens of machines and shifts. The instinctive first move, listing everything the failing units have in common, tends to backfire, because the things they share most are the things every unit shares: the same common materials and the busiest production lines. Those high-volume commonalities are not causes. They are noise that hides the real signal.

This template shows how to cut through that noise and produce a defensible, ranked root-cause diagnosis instead of a long list of coincidences. It uses RelationalAI's **Graph**, **Rules-based**, and **Prescriptive** reasoning together: it traces each unit's full material and process history, measures how strongly defects concentrate around each candidate cause relative to a normal baseline, and then identifies the smallest, most specific set of causes that actually explains the failures, separating a true upstream culprit from the many innocent factors that merely travel alongside it.

## Who this is for

- **Quality and process engineers** running a yield or warranty investigation who want to move from "here is everything the failures have in common" to "here are the few real causes."
- **Manufacturing and operations analysts** learning how to combine traceability data, statistical contrast, and optimization in a single workflow.

**Assumed knowledge:** comfort reading Python, a basic understanding of a bill of materials and shop-floor traceability (the idea of material lots, machines, and shifts), and familiarity with running a script against a configured RelationalAI engine. No optimization background is required; the template explains each step as it goes.

## What you'll build

- A timeline view that pinpoints the week the failure rate jumped, so the investigation starts from the right window.
- A genealogy graph that links every finished unit to every material lot it consumed, even several assembly tiers down.
- A contrast score for each candidate cause (a lot, a machine, or a shift) that separates genuine signals from high-volume noise.
- A minimal root-cause diagnosis that names the fewest, most specific causes explaining the failures, each reported with the evidence an engineer would confirm next.

At a high level, this exercises three RelationalAI capabilities on one shared model: **graph reachability** to close the genealogy, **rules and derived properties** to score the candidates, and **prescriptive optimization** to select the minimal diagnosis.

## What's included

- **Model and pipeline** (`defect_root_cause.py`): a single script that defines the ontology and runs all three reasoning stages end to end.
- **Data generator** (`generate_data.py`): rebuilds the sample corpus deterministically from a fixed seed. The generated files are already included, so you do not need to run it to use the template.
- **Sample data** (`data/`): ten CSV files describing the product structure, the material lots and their genealogy, the finished units and their test results, the process history, and the list of candidate causes.
- **Outputs**: the diagnosis is printed to the console and written back into the model as a `DiagnosisResult` summary and an `is_root_cause` flag on each named factor, so the result can be queried after the run rather than only read from the console.

## Prerequisites

### Access

- A Snowflake account with the RelationalAI Native App installed.
- A Snowflake user with permission to access the RelationalAI Native App.
- A prescriptive engine for the optimization step. The template solves with the open-source HiGHS solver, so no additional solver license is required.

### Tools

- Python 3.10 or later.
- The RelationalAI Python library, installed with the steps below and configured with `rai init`.

## Quickstart

1. Download and extract this template:

   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/defect_root_cause.zip
   unzip defect_root_cause.zip
   cd defect_root_cause
   ```

   > [!TIP]
   > You can also download the template ZIP using the "Download ZIP" button at the top of this page.

2. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install -U pip
   ```

3. Install dependencies:

   ```bash
   python -m pip install .
   ```

4. Configure your Snowflake connection and RelationalAI profile:

   ```bash
   rai init
   ```

5. Run the template:

   ```bash
   python defect_root_cause.py
   ```

6. Confirm success. The run ends with the diagnosis; the final lines should look like this:

   ```text
   Root-cause diagnosis: 2 factors explain 120/142 defective units (85% coverage)
            factor                  label    kind defects_on_factor     lift
      LOT::SP-0423   CP-PASTE lot SP-0423     LOT                62 4.230811
   MACHINE::REF-02 Reflow oven 2 (REFLOW) MACHINE                73 2.167304
   ```

   The full annotated output appears in the [Sample output](#sample-output) section below.

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
    ├── bill_of_materials.csv # 26 bill-of-materials edges (output SKU requires input SKU)
    ├── suppliers.csv
    ├── machines.csv          # placement, reflow, assembly, and test equipment
    ├── lots.csv              # 105 received or produced batches
    ├── lot_genealogy.csv     # 162 parent-to-child lot edges
    ├── units.csv             # 2,500 serialized units, test results, and build week
    ├── unit_lots.csv         # top-tier lots each unit consumes
    ├── unit_process.csv      # which machine and shift ran each operation
    └── factors.csv           # 118 candidate causes (lots, machines, and shifts)
```

**Start here:** `python defect_root_cause.py` runs the whole pipeline end to end.

## Sample data

The bundled corpus is a serialized-unit manufacturing genealogy for a consumer-electronics line that builds smartphones and a tablet. It covers 2,500 finished units over a three-week window. Each unit records the material lots it consumed (traceable through a four-tier bill of materials) and the machine and shift that ran each operation. The data is generated with two planted root causes that share a single incident at the start of week two: a contaminated solder-paste lot that arrives then, and a reflow oven that drifts out of calibration then. Several decoys are planted alongside them (a near-universal housing lot, a high-volume placement line, and the day shift) so the analysis has to distinguish real causes from things that simply touch most of production. Because contaminated boards reach only units built on or after the incident, the failure timeline is a genuine signal rather than an artifact.

## Model overview

The model represents a manufacturing genealogy: finished units built from material lots through a multi-tier bill of materials, each with a full process history.

The genealogy is the backbone: a built `Lot` consumes its input lots, so following those links from a finished unit reaches every material beneath it. The sections below document the model concept by concept.

### SKU

An item in the product structure. SKUs, and the bill of materials between them, define the product's type-level structure that the lot genealogy instantiates.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | string | Yes | Loaded from `data/skus.csv` |
| `name` | string | No | Human-readable name |
| `tier` | string | No | One of `FINISHED`, `SUBASSEMBLY`, `COMPONENT`, or `RAW` |

### Lot

A specific received or produced batch of a SKU. Lots form the genealogy the diagnosis traces backward.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | string | Yes | Loaded from `data/lots.csv` |
| `sku` | SKU | No | Which SKU this lot is a batch of |
| `supplier` | Supplier | No | Who supplied the lot |
| `received_date` | string | No | When the lot was received; corroborating evidence |

### Unit

A serialized finished unit and its final-test outcome. Defective units are the symptoms the diagnosis must explain.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | string | Yes | Loaded from `data/units.csv` |
| `sku` | SKU | No | The finished product built |
| `defective` | int | No | 1 if the unit failed final test, otherwise 0 |
| `defect_type` | string | No | Failure signature, for example `COLD_SOLDER` |
| `build_week` | int | No | Week index used by the timeline step |
| `shift` | string | No | Shift that built the unit |

### Machine

A piece of process equipment. Calibration age corroborates a machine-as-cause finding.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | string | Yes | Loaded from `data/machines.csv` |
| `machine_type` | string | No | The operation it performs (placement, reflow, assembly, test) |
| `calibration_age_days` | int | No | Days since last calibration |

### Factor

A candidate root cause: any lot, machine, or shift, put on a common footing so the diagnosis can range over all three. The rules and optimization stages enrich each factor with derived properties.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | string | Yes | Loaded from `data/factors.csv`, for example `LOT::SP-0423` |
| `kind` | string | No | `LOT`, `MACHINE`, or `SHIFT` |
| `lift` | float | No | Derived: defect rate among touched units versus the plant baseline |
| `is_root_cause` | float (binary) | No | Decision variable: named in the diagnosis |

### Relationships

The reasoning relies on a few relations beyond concept properties:

| Relationship | Reading | Notes |
|---|---|---|
| `Lot consumes Lot` | parent lot, child lot | The genealogy; closed transitively in the graph stage |
| `Unit consumes Lot` | unit, lot | Top-tier lots the unit consumed directly |
| `Unit ran on Machine` | unit, machine | Process history (one per operation) |
| `Factor touches Unit` | factor, unit | Derived incidence the diagnosis ranges over |

## How it works

This section walks through the highlights in `defect_root_cause.py`. The pipeline moves from the failure timeline to a ranked diagnosis:

```text
failure timeline -> genealogy graph -> contrast scoring -> minimal-diagnosis optimization -> ranked root causes
```

### Locate the spike onset

First, a real investigation starts on the timeline rather than the genealogy. Rolling failures up by build week locates the onset, the first week whose rate runs well above the opening baseline, which tells the rest of the chain which window to interrogate. Here the rate steps from 1.9 percent in week one to 6.6 percent in week two, so the onset is week two:

```python
wk = model.select(Unit.build_week.alias("week"), Unit.defective.alias("defective")).to_df()
wk["defective"] = wk["defective"].astype(int)
timeline = wk.groupby("week").agg(units=("defective", "size"), defects=("defective", "sum"))
timeline["rate"] = timeline["defects"] / timeline["units"]
opening = timeline["rate"].iloc[0]
onset = next((int(w) for w, r in timeline["rate"].items() if r > 2 * opening), None)
```

### Trace the genealogy backward (Graph)

Next, the lot genealogy is a directed parent-to-child graph: a built lot consumes its input lots. Closing it transitively with `reachable(full=True)` links each unit to every lot beneath the top-tier lots it consumed, so a contaminated component lot two tiers down is still attributed to every finished unit that carries it:

```python
graph = Graph(model, directed=True, weighted=False, node_concept=Lot)
parent, child = Lot.ref(), Lot.ref()
model.where(parent.consumes(child)).define(graph.Edge.new(src=parent, dst=child))

reach = graph.reachable(full=True)

Unit.touches_lot = model.Relationship(f"{Unit} touches {Lot:lot}")
model.where((u := Unit.ref()).consumes_lot(top := Lot.ref())).define(Unit.touches_lot(u, top))
model.where(
    (u := Unit.ref()).consumes_lot(top := Lot.ref()),
    reach(top, deep := Lot.ref())
).define(Unit.touches_lot(u, deep))
```

A unified `Factor.touches` relationship then puts lots, machines, and shifts on the same footing: lot factors inherit the genealogy closure, while machine and shift factors come straight from process history.

### Score the candidates (Rules)

Then each candidate is scored by how concentrated defects are among the units it touches. The `lift` is the candidate's defect rate divided by the plant-wide baseline, and a candidate becomes a suspect only when its lift, its support, and its defect count all clear a threshold. This is what screens out the high-coverage, low-lift factors that dominate a raw count but explain nothing:

```python
model.define(Factor.touched_count(aggs.count(Unit).per(Factor).where(Factor.touches(Unit))))
model.define(Factor.defect_count(aggs.count(Unit).per(Factor).where(Factor.touches(Unit), Unit.is_defective())))
model.where(Factor.defect_count > 0).define(
    Factor.lift((floats.float(Factor.defect_count) / floats.float(Factor.touched_count)) / BASELINE_RATE)
)
model.where(
    Factor.lift >= LIFT_THRESHOLD,
    Factor.touched_count >= MIN_SUPPORT,
    Factor.defect_count >= MIN_DEFECTS
).define(Factor.is_suspect(Factor))
```

### Find the minimal diagnosis (Prescriptive)

Finally, a binary decision variable names each suspect a root cause, and a binary slack lets a defective unit be left unexplained. The coverage constraint requires every defective unit to be explained by a named cause it touches or else marked unexplained. The objective trades off three things: a cost for each named cause (so the diagnosis stays small), a penalty for naming a cause that also touches many good units (so it stays specific), and a cost for leaving a defect unexplained. Together these make the optimizer prefer the single deep root over the several proximate sub-assemblies that merely carry it:

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

The naive raw-count view ranks high-volume trunk factors first, none of which is a cause. Contrast scoring flips the ranking, and the optimization resolves the suspects to the two real roots, each reported with corroborating evidence.

```text
Loaded 2500 units, 142 defective (5.68% final-test failure rate)
When did the spike start? Final-test failure rate by build week:
  week 1:  795 units    1.9%
  week 2:  852 units    6.6%  <- spike onset
  week 3:  853 units    8.3%
Spike onset at week 2: the chain interrogates what entered the line then.
Genealogy graph: 105 lot nodes, 162 parent->child edges
Backward reachability built 57,133 (factor, unit) incidence facts.
Top candidate factors by RAW defective units touched (pre-contrast -- note the high-volume bias):
           factor    kind  units  defects
 LOT::RM-POLY-L01     LOT   2500      142
 LOT::CP-HOUS-L01     LOT   2197      126
LOT::RM-RESIN-L02     LOT   1550      110
   LOT::RM-SI-L04     LOT   2012      104
   LOT::RM-LI-L01     LOT   1788      103
  MACHINE::SMT-01 MACHINE   1761       98

Contrast scoring: 10 suspect factors (baseline failure rate 5.68%, lift>=1.5, support>=30, defects>=5)
          factor    kind units defects     rate     lift
LOT::SA-PCBA-L05     LOT    82      23 0.280488 4.938166
LOT::SA-PCBA-L09     LOT    83      23 0.277108 4.878670
    LOT::SP-0423     LOT   258      62 0.240310 4.230811
 LOT::CP-PCB-L08     LOT    93      16 0.172043 3.028926
LOT::SA-PCBA-L15     LOT    93      16 0.172043 3.028926
 LOT::CP-SOC-L04     LOT   226      29 0.128319 2.259130
  LOT::RM-SI-L03     LOT   226      29 0.128319 2.259130
 MACHINE::REF-02 MACHINE   593      73 0.123103 2.167304
 LOT::CP-PCB-L03     LOT   332      31 0.093373 1.643900
  LOT::RM-CU-L02     LOT   803      71 0.088418 1.556663

Pre-solve audit: 142 coverage constraints grounded (one per defective unit).
Diagnosis solve: OPTIMAL   objective=46.32
Root-cause diagnosis: 2 factors explain 120/142 defective units (85% coverage)
         factor                  label    kind defects_on_factor     lift
   LOT::SP-0423   CP-PASTE lot SP-0423     LOT                62 4.230811
MACHINE::REF-02 Reflow oven 2 (REFLOW) MACHINE                73 2.167304

Corroborating evidence per root cause:
  CP-PASTE lot SP-0423       84% COLD_SOLDER    supplier Meridian Components, received 2026-02-09
  Reflow oven 2 (REFLOW)     81% SOLDER_BRIDGE  168 days since last calibration
```

The diagnosis names a contaminated solder-paste lot (`SP-0423`) and a reflow oven (`REF-02`). The optimization is what makes the result useful: three populated-board lots (`SA-PCBA-L05`, `SA-PCBA-L09`, and `SA-PCBA-L15`) carry the contaminated paste and so score high on lift, but the optimizer prefers the single deep paste lot that explains all of them, and it ignores the correlated bystanders (`CP-SOC-L04` and `RM-SI-L03`) whose defects are already covered. Each named cause is reported with the evidence an engineer would confirm physically: the failures on `SP-0423` are overwhelmingly cold solder (the paste signature) and the lot arrived exactly at the week-two onset, while the failures on `REF-02` are solder bridges and it is 168 days past calibration. The diagnosis is the prioritized hypothesis; the evidence is what you check next.

## Customize this template

### Use your own data

- Replace the CSVs in `data/` with your own genealogy, keeping the same column names. The genealogy can be any depth, because backward reachability handles arbitrary bill-of-materials tiers.
- To add another kind of candidate cause (an operator, a work order, or a supplier site), append rows to `factors.csv` with the new kind, add a matching back-pointer property, and add one `Factor.touches` rule, mirroring the existing lot, machine, and shift pattern.

### Tune parameters

- `LIFT_THRESHOLD`, `MIN_SUPPORT`, and `MIN_DEFECTS` set how aggressively the contrast stage admits suspects.
- `W_SELECT`, `W_GOOD`, and `W_UNEXPLAINED` trade off how small, how specific, and how complete the diagnosis is. The named causes are robust to the exact values; what drives the result is the balance between parsimony and the good-unit penalty, not the specific numbers.

### Extend the model

- Run `python generate_data.py` to rebuild the sample corpus. Edit the planted causes, decoys, and volumes near the top of the file to author your own scenario.
- The timeline step is a natural place to add a more formal change-point test; the contrast step is where you would add a statistical significance test alongside the lift threshold.

## Troubleshooting

<details>
  <summary>Why does the diagnosis leave some defects unexplained?</summary>

- The optimization includes a per-unit slack so that a handful of scattered baseline failures (units whose only shared factors are low-lift) are left unexplained rather than forcing in a spurious cause.
- Lower `W_UNEXPLAINED` to tolerate more unexplained defects, or raise it to push the optimizer toward fuller coverage.

</details>

<details>
  <summary>Why are the top raw-count factors not the diagnosis?</summary>

- High-volume factors such as a near-universal raw-material lot or the busiest line touch almost every unit, so they touch many defective units too, but only at the baseline rate.
- Their lift is close to 1.0, so the contrast stage screens them out before the optimization ever sees them. This is the central lesson of the template: coverage is not causation.

</details>

<details>
  <summary>Why does authentication or configuration fail?</summary>

- Run <code>rai init</code> to create or update <code>raiconfig.yaml</code>.
- If you have multiple profiles, set <code>RAI_PROFILE</code> or switch profiles in your configuration.

</details>
