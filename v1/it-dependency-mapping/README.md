---
title: "IT Dependency Mapping"
description: "Map the downstream dependency structure of a software and data-pipeline estate by enumerating variable-length traversal paths over an acyclic dependency graph, then surface the longest end-to-end chains and the owners along them."
experience_level: intermediate
industry: "Technology & Telecom"
featured: false
reasoning_types:
  - Graph
tags:
  - graph-analytics
  - paths
  - variable-length-traversal
  - dependency-mapping
  - data-lineage
  - technology
sidebar:
  order: 6
---

## What this template is for

Modern software estates are webs of dependencies: raw data sources feed ingestion pipelines, pipelines feed feature jobs, jobs back services and APIs, and services power dashboards. When someone proposes changing a pipeline -- or one goes down at 2am -- the question is always the same: what is downstream of this, and how far does the blast radius reach? Direct dependencies are easy to list; the full transitive chains are not.

This template demonstrates **Graph** reasoning -- specifically variable-length path traversal -- over a dependency DAG:

1. **Path enumeration** (`model.path(Feature.contributes_to.repeat(1, N)).all_paths()`) -- Walk every downstream dependency path of every length. Because the estate is acyclic, each enumerated path is a simple chain.
2. **Maximal-chain reduction** -- Collapse the full path set down to the longest non-extendable chains, dropping the shorter sub-chains contained inside them, so the end-to-end propagation paths stand out.

## Who this is for

- **Intermediate users** who want to learn variable-length path traversal on a directed acyclic graph
- **Platform and data engineers** assessing the downstream impact of a pipeline change or outage
- **Reliability owners** who need to know which chains, and which people, sit between a root component and its consumers

## What you'll build

- Load a 14-feature, 15-edge dependency estate from CSV (raw sources, pipelines, feature jobs, services, dashboards)
- Define a `contributes_to` self-relationship forming an acyclic dependency DAG
- Enumerate every downstream dependency path with `model.path(...).all_paths()`
- Report per-feature path counts and longest downstream depth
- Reduce the path set to its maximal chains (longest non-extendable dependency chains)
- Persist each feature's longest downstream depth back to the ontology as `Feature.max_downstream_depth`
- Trace the owners along the single longest chain -- the worst-case change/incident blast radius

## What's included

- **Self-contained script**: `it_dependency_mapping.py` -- Runs the full analysis end-to-end
- **Data**: `data/features.csv` (14 features across tiers) and `data/dependencies.csv` (15 dependency edges)

## Prerequisites

- Python >= 3.10
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.
- `relationalai >= 1.15` -- the path-traversal API is a preview capability (introduced in 1.13, validated on 1.15).

## Quickstart

1. Download and extract this template:

   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/it-dependency-mapping.zip
   unzip it-dependency-mapping.zip
   cd it-dependency-mapping
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
   python it_dependency_mapping.py
   ```

## Template structure

```text
it-dependency-mapping/
├── it_dependency_mapping.py    # Self-contained analysis script
├── pyproject.toml              # Dependencies and project metadata
├── README.md                   # This file
└── data/
    ├── features.csv            # 14 features (id, name, owner, deploy_tier)
    └── dependencies.csv        # 15 dependency edges (from_feature, to_feature)
```

## How it works

```text
CSV files --> Define Feature + contributes_to --> Enumerate downstream paths --> Reduce to maximal chains --> Trace owners along longest chain
```

### 1. Load Ontology

A `Feature` is any node in the estate -- a raw source, pipeline, feature job, service, or dashboard. The `contributes_to` self-relationship records that an upstream feature feeds a downstream one, forming the dependency DAG:

```python
Feature = model.Concept("Feature", identify_by={"id": String})
Feature.name = model.Property(f"{Feature} has {String:name}")
Feature.owner = model.Property(f"{Feature} owned by {String:owner}")
Feature.deploy_tier = model.Property(f"{Feature} has deploy tier {String:deploy_tier}")

Feature.contributes_to = model.Relationship(
    f"{Feature} contributes to {Feature}", short_name="contributes_to"
)
```

### 2. Enumerate Downstream Paths

`model.path(Feature.contributes_to.repeat(1, MAX_DEPTH))` describes a variable-length traversal of 1 to `MAX_DEPTH` `contributes_to` edges. `all_paths()` enumerates every such path. Each result is a `PathTraversal`; project `p.nodes` to get the ordered features it visits. Do not also select `p.length` alongside `p.nodes` -- that fans the node rows out; derive the hop count from the maximum node index instead:

```python
p_pattern = model.path(Feature.contributes_to.repeat(1, MAX_DEPTH))
paths_df = (
    model.where(p := p_pattern.all_paths())
    .select(
        p.alias("path_id"),
        p.nodes["index"].alias("step"),
        Feature(p.nodes).id.alias("feature_id"),
        Feature(p.nodes).name.alias("feature_name"),
    )
    .to_df()
)
paths_df["step"] = paths_df["step"].astype(int)
# Projecting p.nodes can emit duplicate (path, step) rows -- dedupe before reassembly.
paths_df = paths_df.drop_duplicates(["path_id", "step"]).sort_values(["path_id", "step"])
```

Each path arrives as one row per visited node. Grouping on the path-id column reassembles the ordered chain; the hop count is the maximum node index:

```python
chains = (
    paths_df.groupby("path_id")
    .agg(
        hops=("step", "max"),
        node_ids=("feature_id", lambda s: tuple(s)),
        chain=("feature_name", lambda s: " -> ".join(s)),
    )
    .reset_index()
)
```

### 3. Persist Longest Downstream Depth

The longest path starting at each feature is its downstream depth. Writing it back as a first-class property lets a downstream query rank features by reach without re-enumerating paths:

```python
Feature.max_downstream_depth = model.Property(
    f"{Feature} has {Integer:max_downstream_depth}"
)
depth_data = model.data(depth_rows)
model.define(
    Feature.max_downstream_depth(depth_data.max_downstream_depth)
).where(Feature.id == depth_data.feature_id)
```

### 4. Reduce to Maximal Chains

The full path set contains every sub-chain. A path is *maximal* when its node sequence is not a contiguous sub-chain of any other enumerated path -- it cannot be extended upstream or downstream. Filtering to maximal chains leaves only the end-to-end propagation paths:

```python
maximal = chains[
    chains["node_ids"].apply(
        lambda seq: not any(
            is_sub_chain(seq, other) for other in all_sequences if other != seq
        )
    )
].copy()
```

The single longest maximal chain is the worst-case blast radius: joining owner metadata onto its features shows every person a change at the root would have to clear before it reaches the final consumer.

## Expected output

The deepest chain runs five hops from a raw source all the way to a downstream dashboard, crossing several owners:

```text
=== Maximal dependency chains (6 of 46 paths) ===
  5 hops: Clickstream Ingest -> Events Enrichment Pipeline -> Session Feature Job -> Churn Feature Store -> Churn Scoring API -> Retention Dashboard
  4 hops: CRM Sync -> Customer 360 Build -> Churn Feature Store -> Churn Scoring API -> Retention Dashboard
  4 hops: Clickstream Ingest -> Events Enrichment Pipeline -> Session Feature Job -> Recommendation Service -> Retention Dashboard
  4 hops: Transaction CDC Stream -> Customer 360 Build -> Churn Feature Store -> Churn Scoring API -> Retention Dashboard
  4 hops: Transaction CDC Stream -> Ledger Normalizer -> Revenue Rollup -> Billing API -> Executive Revenue Dashboard
  3 hops: Transaction CDC Stream -> Ledger Normalizer -> Revenue Rollup -> Executive Revenue Dashboard

=== Longest dependency chain: 5 hops ===
  Chain: Clickstream Ingest -> Events Enrichment Pipeline -> Session Feature Job -> Churn Feature Store -> Churn Scoring API -> Retention Dashboard
  Spans 6 features and 5 owners:
    - Clickstream Ingest             owner=Maya Chen      tier=critical
    - Events Enrichment Pipeline     owner=Sofia Rossi    tier=high
    - Session Feature Job            owner=Liang Wu       tier=high
    - Churn Feature Store            owner=Liang Wu       tier=high
    - Churn Scoring API              owner=Priya Nair     tier=high
    - Retention Dashboard            owner=Hana Kim       tier=standard

  A change at 'Clickstream Ingest' propagates through 5 downstream feature(s) before reaching 'Retention Dashboard'.
```

## Customize this template

**Use your own data:**
- Replace the CSVs in `data/` with your own features and dependency edges, keeping the same column names.
- `deploy_tier` is illustrative metadata; swap in your own (criticality, environment, SLA class) and group the output by it.

**Extend the analysis:**
- Raise `MAX_DEPTH` if your estate has longer chains than the sample.
- Filter the enumerated paths to those that end at a `critical`-tier feature to find the chains that matter most.
- Add edge attributes (latency, freshness SLA) and sum them along each path to rank chains by cumulative risk, not just length.

## Troubleshooting

<details>
  <summary>Why does <code>model.path(...)</code> raise an <code>AttributeError</code> or <code>ImportError</code>?</summary>

- The path-traversal API is a preview capability introduced in `relationalai` 1.13 and validated on 1.15. Confirm your installed version (>= 1.15) with `python -c "import relationalai; print(relationalai.__version__)"` and upgrade if it is older.

</details>

<details>
  <summary>Why does path enumeration hang or return far more paths than expected?</summary>

- `all_paths()` enumerates walks. On an acyclic estate every walk is a simple chain, but if you add an edge that introduces a cycle the enumeration can explode. Keep `contributes_to` acyclic, and use `MAX_DEPTH` to bound traversal.

</details>

<details>
  <summary>Why does authentication/configuration fail?</summary>

- Run `rai init` to create/update `raiconfig.toml`.
- If you have multiple profiles, set `RAI_PROFILE` or switch profiles in your config.

</details>
