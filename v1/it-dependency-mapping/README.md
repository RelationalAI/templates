---
title: "IT Dependency Mapping"
description: "Map the downstream dependency structure of a software and data-pipeline estate by enumerating variable-length paths over an acyclic dependency graph. Surface the longest end-to-end chains and the owners along them to see a change or outage's full blast radius."
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

This template demonstrates **Graph** reasoning -- specifically variable-length path traversal -- over a dependency directed acyclic graph (DAG):

1. **Path enumeration** (`model.path(Feature.contributes_to.repeat(1, N)).all_paths()`) -- Walk every downstream dependency path of every length. Because the estate is acyclic, each enumerated path is a simple chain.
2. **Maximal-chain reduction** -- Collapse the full path set down to the longest non-extendable chains, dropping the shorter sub-chains contained inside them, so the end-to-end propagation paths stand out.

## Who this is for

- **Intermediate users** who want to learn variable-length path traversal on a directed acyclic graph
- **Platform and data engineers** assessing the downstream impact of a pipeline change or outage
- **Reliability owners** who need to know which chains, and which people, sit between a root component and its consumers
- **Assumed knowledge**: comfortable reading Python; graph and dependency-mapping terms are explained as they come up, so no prior RelationalAI experience is required to follow along

## What you'll build

- The full set of downstream dependency paths across a 14-feature, 15-edge estate (raw sources, pipelines, feature jobs, services, dashboards), reduced to the maximal chains -- the longest non-extendable end-to-end propagation paths.
- A per-feature reach summary: how many downstream paths each feature has and how deep its longest chain runs.
- `Feature.max_downstream_depth` persisted back to the ontology, so downstream queries can rank features by reach without re-enumerating paths.
- The owners along the single longest chain -- the worst-case change/incident blast radius.

Built using RelationalAI's **variable-length path enumeration** (`model.path(...).all_paths()`) over an acyclic dependency graph.

## What's included

- **Self-contained script**: `it_dependency_mapping.py` -- Runs the full analysis end-to-end
- **Runbook**: `runbook.md` — a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the script itself.
- **Data**: `data/features.csv` (14 features across tiers) and `data/dependencies.csv` (15 dependency edges)

## Prerequisites

### Access

- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools

- Python >= 3.10
- `relationalai >= 1.15` -- the path-traversal API is a preview capability.
- The `rai` CLI (ships with the `relationalai` SDK) for configuring your connection.

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

6. **Expected output** (a few lines confirm success):

   ```text
   Total downstream dependency paths (1-8 hops): 46
   === Maximal dependency chains (6 of 46 paths) ===
     5 hops: Clickstream Ingest -> Events Enrichment Pipeline -> Session Feature Job -> Churn Feature Store -> Churn Scoring API -> Retention Dashboard
   === Longest dependency chain: 5 hops ===
   ```

   The full printout -- per-feature reach, all six maximal chains, and the owners along the longest chain -- is in the `## Expected output` section below.

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

**Start here**: run `python it_dependency_mapping.py` for the full analysis end to end, or follow `runbook.md` to rebuild it step by step.

## Sample data

`data/features.csv` holds 14 features that make up a small software and data-pipeline estate -- raw sources, ingestion pipelines, feature jobs, services, and dashboards. Each row carries an `id`, a human-readable `name`, an `owner`, and a `deploy_tier` (`critical`, `high`, or `standard`).

| Column | Description |
|---|---|
| `id` | Stable identifier for the feature (e.g. `clickstream-ingest`) |
| `name` | Human-readable name (e.g. `Clickstream Ingest`) |
| `owner` | Person responsible for the feature |
| `deploy_tier` | Criticality tier: `critical`, `high`, or `standard` |

`data/dependencies.csv` holds 15 dependency edges. Each row is a directed `from_feature -> to_feature` pair, where the upstream feature feeds (contributes to) the downstream one.

| Column | Description |
|---|---|
| `from_feature` | `id` of the upstream feature |
| `to_feature` | `id` of the downstream feature it feeds |

The estate is **acyclic** (a dependency DAG): no feature transitively depends on itself, so every enumerated traversal path is a simple end-to-end chain.

## Model overview

A single concept, `Feature`, represents every node in the estate, and one self-relationship, `contributes_to`, records the directed dependency edges between features.

- **Key entities**: `Feature` — one node in the software and data-pipeline estate (raw source, ingestion pipeline, feature job, service, or dashboard).
- **Primary identifiers**: the string `id` on `Feature`.
- **Important invariants**: the `contributes_to` graph is acyclic — a feature does not depend on itself, so every enumerated traversal path is a simple chain.

For the full concept and property definitions, see `it_dependency_mapping.py`; `runbook.md` builds them step by step with the RAI skills.

## How it works

```text
CSV files --> Define Feature + contributes_to --> Enumerate downstream paths --> Reduce to maximal chains --> Trace owners along longest chain
```

**Load the ontology.** A `Feature` is any node in the estate -- a raw source, pipeline, feature job, service, or dashboard -- with `id`, `name`, `owner`, and `deploy_tier` loaded from `data/features.csv`. The `contributes_to` self-relationship records that an upstream feature feeds a downstream one, forming the dependency DAG from `data/dependencies.csv`.

**Enumerate downstream paths.** A variable-length traversal of 1 to `MAX_DEPTH` `contributes_to` edges, enumerated with `.all_paths()`, walks every downstream dependency path. Each path arrives as one row per visited node; grouping by path reassembles the ordered chain, and the hop count comes from the maximum node index. (Selecting the path length alongside the nodes would fan the rows out, so the code derives hops from the index and dedupes before reassembly.)

**Persist longest downstream depth.** The longest path starting at each feature is its downstream depth. RelationalAI computes it in PyRel — a max over path length per source endpoint — and defines it straight onto the feature as a first-class `max_downstream_depth` property, with no DataFrame round-trip, so later queries can rank features by reach without re-enumerating paths.

**Reduce to maximal chains.** The full path set contains every sub-chain. A path is *maximal* when its node sequence is not a contiguous sub-chain of any other enumerated path -- it cannot be extended upstream or downstream. Filtering to maximal chains leaves only the end-to-end propagation paths. The single longest maximal chain is the worst-case blast radius: joining owner metadata onto its features shows every person a change at the root would have to clear before it reaches the final consumer.

See `it_dependency_mapping.py` for the implementation, and `runbook.md` for the skill-driven reproduction.

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

### Use your own data

- Replace the CSVs in `data/` with your own features and dependency edges, keeping the same column names.
- `deploy_tier` is illustrative metadata; swap in your own (criticality, environment, SLA class) and group the output by it.

### Tune parameters

- `MAX_DEPTH` (default `8`, at the top of `it_dependency_mapping.py`) bounds the traversal length. Raise it if your estate has longer chains than the sample; lower it to cap enumeration on a denser graph.

### Extend the model

- Filter the enumerated paths to those that end at a `critical`-tier feature to find the chains that matter most.
- Add edge attributes (latency, freshness SLA) and sum them along each path to rank chains by cumulative risk, not just length.

### Scale up / productionize

- Size the RAI engine to the graph: path enumeration grows with the number of edges and `MAX_DEPTH`, so a larger estate warrants a larger engine.
- Schedule recurring runs (e.g. after each dependency-catalog refresh) so `Feature.max_downstream_depth` stays current for downstream queries.
- Pin `relationalai` to a known-good version for reproducible runs.

## Troubleshooting

<details>
  <summary>Why does <code>model.path(...)</code> raise an <code>AttributeError</code> or <code>ImportError</code>?</summary>

- The path-traversal API is a preview capability that requires `relationalai >= 1.15`. Confirm your installed version with `python -c "import relationalai; print(relationalai.__version__)"` and upgrade if it is older.

</details>

<details>
  <summary>Why does path enumeration hang or return far more paths than expected?</summary>

- `all_paths()` enumerates walks. On an acyclic estate every walk is a simple chain, but if you add an edge that introduces a cycle the enumeration can explode. Keep `contributes_to` acyclic, and use `MAX_DEPTH` to bound traversal.

</details>

<details>
  <summary>Why does authentication/configuration fail?</summary>

- Run `rai init` to create/update `raiconfig.yaml`.
- If you have multiple profiles, set `RAI_PROFILE` or switch profiles in your config.

</details>

## Learn more

- [RelationalAI documentation](https://docs.relational.ai/) — language, modeling, and reasoner reference.
- [Template gallery](https://docs.relational.ai/build/templates) — other runnable templates, including graph, rules, and prescriptive examples.

## Support

- Questions or issues: [support.relational.ai](https://support.relational.ai).
