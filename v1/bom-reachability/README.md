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

A bill of materials (BOM) defines how finished products are built from components and raw materials through multiple assembly stages. Understanding the full transitive dependency tree -- not just direct inputs -- is critical for supply chain risk management. This template demonstrates two graph analysis techniques on a BOM structure:

1. **Reachability** (`reachable(full=True)`) -- Trace all transitive dependencies to answer "What does Product X ultimately depend on?" across multiple assembly tiers.
2. **Betweenness Centrality** -- Identify structural bottleneck components that sit on the most dependency paths between finished goods and raw materials.

## Who this is for

- **Intermediate users** who want to learn reachability analysis on directed graphs
- **Supply chain analysts** assessing multi-tier dependency exposure
- **Manufacturing engineers** identifying single-source risks in their BOM
- **Assumed knowledge**: comfortable reading Python and familiar with basic graph and dependency concepts (nodes, directed edges, reachability); BOM, betweenness centrality, and the RelationalAI features are explained as they come up

## What you'll build

- Load a 9-SKU, 14-BOM-entry product structure from CSV (consumer electronics: smartphones, tablets, components, raw materials)
- Construct a directed dependency graph where edges point from output SKU to input SKU ("depends on")
- Compute all-pairs reachability to map full transitive dependency trees
- List dependencies per finished good, broken down by type (COMPONENT vs RAW_MATERIAL)
- Rank components by how many other SKUs depend on them
- Compute betweenness centrality to identify structural bottlenecks
- Enumerate the end-to-end assembly chains that build each finished good and persist each one's assembly depth

Built on RelationalAI's graph reasoner: **reachability** for transitive dependencies, **betweenness centrality** for bottlenecks, and **path enumeration** for assembly chains.

## What's included

- **Self-contained script**: `bom_reachability.py` -- Runs the full analysis end-to-end
- **Data**: `data/skus.csv` (9 SKUs across 3 tiers) and `data/bill_of_materials.csv` (14 BOM entries with site-specific assembly)

## Prerequisites

### Access

- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

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

4. **Configure Snowflake connection and RAI profile**

   ```bash
   rai init
   ```

5. **Run the template**

   ```bash
   python bom_reachability.py
   ```

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

**Start here**: run `python bom_reachability.py` for the full analysis end to end (reachability, betweenness centrality, and assembly-path enumeration), or follow `runbook.md` to rebuild it step by step with a coding agent.

## Sample data

`data/skus.csv` holds 9 SKUs spanning the three assembly tiers: 4 `RAW_MATERIAL` (silicon wafer, display glass, lithium-ion cells, NAND flash), 3 `COMPONENT` (mobile processor, OLED display, battery pack), and 2 `FINISHED_GOOD` (a smartphone and a tablet). Each row carries an `ID`, `NAME`, `TYPE`, `CATEGORY`, `UNIT_OF_MEASURE`, `LEAD_TIME_DAYS`, `UNIT_COST`, and `UNIT_PRICE`; the graph analysis uses `ID`, `NAME`, `TYPE`, and `CATEGORY`.

`data/bill_of_materials.csv` holds 14 BOM entries, each linking an `OUTPUT_SKU_ID` (what is produced) to an `INPUT_SKU_ID` (what it requires), with `ID`, `SITE_ID`, and `INPUT_QUANTITY`. The same output-to-input pair is recorded once per `SITE_ID`, so multi-site assemblies appear as duplicate edges (for example, `SKU001` is assembled at both `S001` and `S012`). The graph deduplicates these automatically -- see the multi-edges note under Troubleshooting.

## Model overview

- **Key entities**: `SKU` (one stock-keeping unit at any tier) and `BillOfMaterials` (one output-to-input link, used as the directed graph's edge concept).
- **Primary identifiers**: `SKU` by `id`; `BillOfMaterials` by `id`.
- **Important invariants**: each `BillOfMaterials` row points an output SKU at one input SKU ("depends on"); the BOM is acyclic (raw materials feed components feed finished goods, never back).

### `SKU`

One stock-keeping unit at any assembly tier (raw material, component, or finished good).

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | string | Yes | Loaded from `data/skus.csv` (`ID`) |
| `name` | string | No | Human-readable name (`NAME`) |
| `type` | string | No | `RAW_MATERIAL`, `COMPONENT`, or `FINISHED_GOOD` (`TYPE`) |
| `category` | string | No | Used for grouping/filters (`CATEGORY`) |
| `assembly_depth` | int | No | Derived and persisted: longest assembly chain terminating at this SKU (PREVIEW stage) |

The model also derives a `feeds` self-relationship on `SKU` (`SKU feeds into SKU`): a binary input-feeds-output edge built from the `BillOfMaterials` intermediary and used to enumerate assembly paths.

### `BillOfMaterials`

One link in the bill of materials, recorded per assembly site and used as the graph's edge concept.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | string | Yes | Loaded from `data/bill_of_materials.csv` (`ID`) |

| Relationship | Schema | Notes |
|---|---|---|
| `output_sku` | `BillOfMaterials produces SKU` | The SKU this entry produces; graph edge source |
| `input_sku` | `BillOfMaterials requires SKU` | The SKU this entry requires; graph edge destination |

## How it works

```text
CSV files --> Define SKU + BOM concepts --> Build directed graph --> Reachability analysis --> Betweenness centrality --> Display results
```

### 1. Load Ontology

SKU and BillOfMaterials concepts are loaded from CSV. Each BOM entry links an output SKU (what is produced) to an input SKU (what is required):

```python
SKU = model.Concept("SKU", identify_by={"id": String})
BillOfMaterials = model.Concept("BillOfMaterials", identify_by={"id": String})
BillOfMaterials.output_sku = model.Relationship(f"{BillOfMaterials} produces {SKU}")
BillOfMaterials.input_sku = model.Relationship(f"{BillOfMaterials} requires {SKU}")
```

### 2. Build Directed Graph

The graph uses BillOfMaterials as the edge concept, with edges pointing from output to input ("depends on"):

```python
graph = Graph(
    model, directed=True, weighted=False,
    node_concept=SKU,
    edge_concept=BillOfMaterials,
    edge_src_relationship=BillOfMaterials.output_sku,
    edge_dst_relationship=BillOfMaterials.input_sku,
)
```

### 3. Trace Dependencies

`reachable(full=True)` computes all-pairs reachability -- every (source, destination) pair where a directed path exists:

```python
reachable = graph.reachable(full=True)

src, dst = graph.Node.ref("src"), graph.Node.ref("dst")
all_deps_df = where(reachable(src, dst)).select(
    src.id.alias("product_id"),
    dst.id.alias("dep_id"),
    ...
).to_df()
```

### 4. Identify Bottlenecks

Betweenness centrality ranks components by how many shortest dependency paths pass through them:

```python
betweenness = graph.betweenness_centrality()
```

Components with high betweenness are structural bottlenecks -- disrupting them affects the most product lines.

### 5. Enumerate Assembly Paths (PREVIEW, requires `relationalai>=1.15`)

Where reachability returns dependency *pairs*, path enumeration returns the actual *build sequences*. It derives a SKU-to-SKU `feeds` edge from the `BillOfMaterials` intermediary (input SKU feeds output SKU) and enumerates every assembly path; because the BOM is acyclic, `.all_paths()` yields exactly the simple paths -- no cycle risk. A maximal-paths view keeps only the longest non-extendable chains, and the longest assembly depth is persisted as `SKU.assembly_depth`.

```python
SKU.feeds = model.Relationship(f"{SKU} feeds into {SKU}", short_name="feeds")
p = model.path(SKU.feeds.repeat(1, MAX_ASSEMBLY_HOPS)).all_paths()
assembly_df = (
    model.where(p)
    .select(
        p.alias("path"),
        p.nodes["index"].alias("step"),
        SKU(p.nodes).id.alias("sku_id"),
        SKU(p.nodes).name.alias("sku_name"),
    )
    .to_df()
)
```

## Customize this template

**Use your own data:**
- Replace CSVs in `data/` with your own SKU and BOM data, keeping the same column names.
- The BOM data can include site-specific assembly (SITE_ID column) for multi-site manufacturing.

**Extend the analysis:**
- Use `reachable(from_=target)` to trace downstream impact of a specific component disruption
- Add cost or lead time properties to quantify dependency exposure
- Combine with supplier data to map component-to-supplier risk chains

## Troubleshooting

<details>
  <summary>Why do I see a "multi-edges" warning?</summary>

- The BOM data includes site-specific entries (e.g., SKU001 is assembled at both S001 and S012). This creates duplicate edges between the same SKU pair. The warning is informational -- the graph deduplicates automatically. To suppress it, add `aggregator="sum"` to the Graph constructor.

</details>

<details>
  <summary>Why does authentication/configuration fail?</summary>

- Run `rai init` to create/update `raiconfig.toml`.
- If you have multiple profiles, set `RAI_PROFILE` or switch profiles in your config.

</details>

## Learn more

- [RelationalAI documentation](https://docs.relational.ai/) — language, modeling, and reasoner reference.
- [Template gallery](https://docs.relational.ai/build/templates) — other runnable templates, including graph, rules, and prescriptive examples.

## Support

- Questions or issues: [support.relational.ai](https://support.relational.ai).
