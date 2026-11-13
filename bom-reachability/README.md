---
title: "BOM Reachability"
description: "Trace transitive dependencies through a bill of materials to identify which raw materials each finished product depends on and which components are structural bottlenecks."
experience_level: intermediate
industry: "Manufacturing"
featured: false
reasoning_types:
  - Graph
tags:
  - graph-analytics
  - reachability
  - betweenness-centrality
  - bill-of-materials
  - manufacturing
sidebar:
  order: 5
---

## What this template is for

A bill of materials (BOM) defines how finished products are built from components and raw materials through multiple assembly stages. When a supplier slips, a plant goes down, or a part is recalled, the pressing question is not "what does this product use directly?" but "which finished goods ultimately depend on this part, and how far up the chain does the damage travel?" Direct inputs are easy to read off a spreadsheet; the full transitive dependency tree — and the shared components that quietly sit on everyone's critical path — are not.

This template turns a BOM into a dependency graph so you can trace those transitive dependencies, pinpoint the components that are structural bottlenecks across product lines, and enumerate the end-to-end assembly chains that build each finished good. **It runs on RelationalAI's graph reasoner, using reachability, betweenness centrality, and path enumeration directly over the ontology.**

## Who this is for

- **Intermediate users** who want to learn reachability analysis on directed graphs
- **Supply chain analysts** assessing multi-tier dependency exposure
- **Manufacturing engineers** identifying single-source risks in their BOM
- **Assumed knowledge**: comfortable reading Python and familiar with basic graph and dependency concepts (nodes, directed edges, reachability); BOM, betweenness centrality, and the RelationalAI features are explained as they come up

## What you'll build

- A directed dependency graph over the BOM (SKU nodes, output-to-input "depends on" edges) built with the graph reasoner's `Graph` construction.
- A full transitive dependency tree per finished good, broken down by type (component vs raw material), from all-pairs `reachable(full=True)`.
- A most-depended-on ranking of SKUs and a betweenness-centrality ranking that flags the structural bottleneck components.
- An enumeration of the end-to-end assembly chains that build each finished good, reduced to the maximal (non-extendable) chains via path enumeration.
- Each finished good's assembly depth: the length of the longest chain that builds it.

Built on RelationalAI's graph reasoner: **reachability** for transitive dependencies, **betweenness centrality** for bottlenecks, and **path enumeration** for assembly chains.

## What's included

- **Model**: two concepts (`SKU` and `BillOfMaterials`) wired into a directed dependency graph, plus a derived `feeds` self-relationship on `SKU`.
- **Runner**: `bom_reachability.py` — a single self-contained Python script that deploys the model to your Snowflake account and prints the reachability, betweenness centrality, and assembly-path report from the deployed model.
- **Runbook**: `runbook.md` — a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the script itself.
- **Sample data**: `data/skus.csv` (9 SKUs across 3 tiers) and `data/bill_of_materials.csv` (14 BOM entries with site-specific assembly). See *Sample data* below.
- **Outputs**: printed transitive-dependency lists per finished good, a most-depended-on and betweenness ranking, the maximal assembly chains, and each finished good's assembly depth.

## Prerequisites

### Access

- A Snowflake account that has the RAI Native App installed.
- A role that can deploy models, set up once by an account administrator: follow [Set up model deployment](https://private.relational.ai/early-access/model-deploy-setup) (**Try it out**, or **Governed setup** for a shared account). This template has no prescriptive solve, so it needs no PAT setup.
- A Snowflake user that holds that role.

### Tools

- Python >= 3.10
- The `relationalai` SDK and the `rai` CLI (installed by the Quickstart's `python -m pip install .`).
- Assembly-path enumeration is a PREVIEW capability that requires `relationalai>=1.15`; reachability and betweenness run on earlier versions.

## Quickstart

1. Download and extract this template:

   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/bom-reachability.zip
   unzip bom-reachability.zip
   cd bom-reachability
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

4. **Configure the Snowflake connection and the deployment**

   Run `rai init` to create `raiconfig.yaml` with your Snowflake connection, set the connection `role` to the model role, then add a `deployment` section. Give each template its own schema pair so two deployed templates never share one; the deploy creates both schemas if they don't exist.

   ```yaml
   deployment:
     role: <MODEL_ROLE>
     public_schema: <DB>.BOM_REACHABILITY              # published views and tables
     identity:
       internal_schema: <DB>.BOM_REACHABILITY_META     # refresh procedures and metadata
     schedules:
       standard:
         interval_s: 0           # refresh only on deploy or on demand
     schedule: standard
   ```

   Without the `deployment` section, `python bom_reachability.py` stops with an error naming the missing setting.

5. **Run the template**

   ```bash
   python bom_reachability.py
   ```

   The script deploys the model, waits for its first refresh, and prints the report from the deployed model. `rai models deploy` deploys without printing the report. To remove the deployment, run `rai models teardown --force` from this directory; it keeps the two schemas.

6. **Expected output** (a few lines confirm success):

   ```text
   === BOM Dependency Graph ===
   9          # SKUs (nodes)
   10         # dependency edges (14 site-specific BOM rows deduplicated)
   Top bottleneck: Mobile Processor A15 (betweenness=4.0000)
   Enumerated 18 assembly path(s) (<= 4 hops).
   Maximal assembly chains (8 of 18, sub-paths suppressed):
   ```

   Both finished goods resolve to 7 transitive dependencies, the processor is the single most disruptive component, and each finished good lands at assembly depth 2. The full printout and a step-by-step walkthrough are in `runbook.md`.

## Template structure

```text
.
├── README.md
├── runbook.md                   # paste-able graph-analysis walkthrough (RAI skills)
├── pyproject.toml               # dependencies
├── bom_reachability.py          # self-contained runner (reachability + betweenness + assembly paths)
└── data/
    ├── skus.csv                 # 9 SKUs across 3 tiers (raw material / component / finished good)
    └── bill_of_materials.csv    # 14 site-specific BOM entries (output SKU requires input SKU)
```

**Start here**: run `python bom_reachability.py` for the full analysis end to end (reachability, betweenness centrality, and assembly-path enumeration), or follow `runbook.md` to reproduce it step by step with the RAI skills.

## Sample data

`data/skus.csv` holds 9 SKUs spanning the three assembly tiers: 4 `RAW_MATERIAL` (silicon wafer, display glass, lithium-ion cells, NAND flash), 3 `COMPONENT` (mobile processor, OLED display, battery pack), and 2 `FINISHED_GOOD` (a smartphone and a tablet). Each row carries an `ID`, `NAME`, `TYPE`, `CATEGORY`, `UNIT_OF_MEASURE`, `LEAD_TIME_DAYS`, `UNIT_COST`, and `UNIT_PRICE`; the graph analysis uses `ID`, `NAME`, `TYPE`, and `CATEGORY`.

`data/bill_of_materials.csv` holds 14 BOM entries, each linking an `OUTPUT_SKU_ID` (what is produced) to an `INPUT_SKU_ID` (what it requires), with `ID`, `SITE_ID`, and `INPUT_QUANTITY`. The same output-to-input pair is recorded once per `SITE_ID`, so multi-site assemblies appear as duplicate edges (for example, `SKU001` is assembled at both `S001` and `S012`). The graph deduplicates these automatically — see the multi-edges note under Troubleshooting.

## Model overview

- **Key entities**: `SKU` (one stock-keeping unit at any tier) and `BillOfMaterials` (one output-to-input link, used as the directed graph's edge concept).
- **Primary identifiers**: `SKU` by `id`; `BillOfMaterials` by `id`.
- **Important invariants**: each `BillOfMaterials` row points an output SKU at one input SKU ("depends on"); the BOM is acyclic (raw materials feed components feed finished goods, never back).

The model also derives a `feeds` self-relationship on `SKU` (input SKU feeds output SKU), built from the `BillOfMaterials` intermediary and used to enumerate assembly paths.

For the full concept and property definitions, see `bom_reachability.py`; `runbook.md` builds them step by step with the RAI skills.

## How it works

The pipeline loads the ontology, builds a directed graph, then runs three graph analyses over it:

```text
CSV files --> Define SKU + BOM concepts --> Build directed graph --> Reachability analysis --> Betweenness centrality --> Assembly-path enumeration --> Display results
```

### 1. Load ontology

The `SKU` and `BillOfMaterials` concepts load from CSV. Each BOM entry links an output SKU (what is produced) to an input SKU (what is required), which becomes the directed "depends on" edge.

### 2. Build directed graph

The graph uses `BillOfMaterials` as the edge concept, with edges pointing from output SKU to input SKU — so following an edge means following a dependency.

### 3. Trace dependencies

All-pairs reachability computes every source-and-destination pair where a directed path exists, giving the full transitive dependency tree behind each finished good rather than just its direct inputs.

### 4. Identify bottlenecks

Betweenness centrality ranks components by how many shortest dependency paths pass through them. Components with high betweenness are structural bottlenecks — disrupting them affects the most product lines.

### 5. Enumerate assembly paths (PREVIEW, requires `relationalai>=1.15`)

Where reachability returns dependency *pairs*, path enumeration returns the actual *build sequences*. It walks the derived `feeds` edge to enumerate every assembly path; because the BOM is acyclic, this yields exactly the simple paths with no cycle risk. A maximal-paths view keeps only the longest non-extendable chains, and the deepest chain ending at each finished good gives its assembly depth.

See `bom_reachability.py` for the implementation and `runbook.md` for the skill-driven reproduction.

## Customize this template

Focus on the first changes most users will make.

### Use your own data

- Replace the CSVs in `data/` with your own SKU and BOM data, keeping the same column names.
- The BOM data can include site-specific assembly (`SITE_ID` column) for multi-site manufacturing.

### Tune parameters

- **Assembly-path depth** — `MAX_ASSEMBLY_HOPS` (the `repeat(1, MAX_ASSEMBLY_HOPS)` bound) caps how many tiers `.all().paths()` enumerates. Raise it if your BOM is deeper than the bundled three tiers; lower it to keep path counts manageable on wide structures.

### Extend the model

- Use `reachable(from_=target)` to trace the downstream impact of a specific component disruption.
- Add cost or lead-time properties to quantify dependency exposure.
- Combine with supplier data to map component-to-supplier risk chains.

### Scale up / productionize

- Swap the CSV loads for `model.data(snowflake_table)` calls to run against Snowflake-backed tables instead of the bundled files.
- Size the engine to the graph: reachability and betweenness scale with node and edge counts, and path enumeration grows with assembly depth and branching, so wide or deep BOMs want a larger engine.
- Pin `relationalai` to a known-good version for reproducible runs, and schedule the script (cron, orchestrator, or Snowflake task) to refresh results as the BOM changes.

## Troubleshooting

<details>
  <summary>Why do I see a "multi-edges" warning?</summary>

- The BOM data includes site-specific entries (e.g., SKU001 is assembled at both S001 and S012). This creates duplicate edges between the same SKU pair. The warning is informational — the graph deduplicates automatically. To suppress it, add `aggregator="sum"` to the Graph constructor.

</details>

<details>
  <summary>Why does authentication/configuration fail?</summary>

- Run `rai init` to create/update `raiconfig.yaml`.
- If you have multiple profiles, set `RAI_PROFILE` or switch profiles in your config.

</details>

## Learn more

### Core concepts

- [RelationalAI documentation](https://docs.relational.ai/) — language, modeling, and reasoner reference.

### Reasoner reference

- [Graph reasoner](https://docs.relational.ai/) — node-concept and edge-concept graph construction, reachability, betweenness centrality, and path enumeration.

### More templates

- [Template gallery](https://docs.relational.ai/build/templates) — other runnable templates, including graph, rules, and prescriptive examples.

## Support

- Questions or issues: [support.relational.ai](https://support.relational.ai).
- File issues at the RelationalAI templates repository.
