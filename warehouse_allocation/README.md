---
title: "Warehouse Allocation"
description: "Allocate inventory across a distribution network using centrality, weakly-connected components, and bridge-route detection to prioritize critical hubs."
featured: false
experience_level: intermediate
industry: "Supply Chain & Logistics"
reasoning_types:
  - Graph
  - Prescriptive
tags:
  - Chained Reasoning
  - Eigenvector Centrality
  - Weakly Connected Components
  - Bridge Detection
  - Network Flow
  - Inventory Optimization
---

## What this template is for

Distribution networks have critical hub warehouses that connect many downstream sites. When a hub runs short of inventory, the disruption cascades across every site it feeds — so identifying which warehouses are structurally critical, and making sure they carry adequate stock, is essential for supply chain resilience. Judging importance by throughput alone misses hubs that are critical because of where they sit in the network, not how much moves through them.

This template chains graph analysis and prescriptive optimization so that the allocation plan respects network structure: the graph reasoner scores each site's importance, and the optimizer holds more inventory where it matters most.

**The graph reasoner writes centrality scores as properties on the `Site` concept, and the prescriptive reasoner reads those same properties directly in its constraints — the shared ontology carries the enrichment forward with no manual data transfer between stages.**

## Who this is for

- Data scientists learning to chain multiple RAI reasoner types
- Supply chain teams wanting network-aware inventory planning
- Anyone interested in combining graph analytics with optimization

## What you'll build

- A distribution-network graph enriched with eigenvector-centrality scores, weakly-connected-component labels, and cross-region bridge routes — all written back onto the ontology as queryable `Site` and `Route` properties.
- An inventory-allocation plan that satisfies demand and budget while holding buffer stock at critical hubs proportional to their centrality.
- A two-stage chain where the graph reasoner's centrality output becomes a direct input to the prescriptive reasoner's constraints — no DataFrame hand-off between stages.

Built using **graph analysis** (eigenvector centrality, weakly connected components, bridge detection) and **prescriptive reasoning** (linear program over continuous allocation variables).

## What's included

- **Model**: a two-stage pipeline (graph, then prescriptive) on a single shared ontology — `Site`, `Route`, and `Demand` concepts wired to the bundled CSVs, plus the centrality enrichment Stage 1 writes back — all in `model/__init__.py`, which `rai models deploy --path model` deploys to your Snowflake account, where each refresh runs both stages.
- **Query**: `queries/allocation_report.py`, which prints the report from the deployed model.
- **Runbook**: `runbook.md` — a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the script itself.
- **Sample data**: a small distribution network of warehouses and stores with routes and per-site demand. See *Sample data* below.
- **Outputs**: stdout diagnostics (centrality ranking, connected-component summary, bridge routes, solver status) plus the inventory allocation plan as queryable `Site.x_inventory`.

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- The one-time model deployment setup on that account, done by an account administrator: follow [Set up model deployment](https://private.relational.ai/early-access/model-deploy-setup) through **Governed setup**, **PAT authentication**, and steps 1-2 of **Additional setup for the prescriptive reasoner** (the Quickstart covers this template's own schema). It gives you a model role, a programmatic access token (PAT) stored as a secret, an external access integration, a PAT user, and a warehouse.
- A Snowflake user that holds the model role.

### Tools
- Python >= 3.10.
- RelationalAI Python SDK (`relationalai == 2.1.1`).

## Quickstart

Before you start, install Python 3.10 or later and complete the access prerequisites above: a Snowflake account with the RAI Native App, the one-time model deployment setup, and a Snowflake user that holds the model role.

Before the first deploy, create this template's internal schema as the model role, and have an administrator grant the RAI Native App caller access to it. The internal schema holds only this model's objects, so the grants cover all of it, including the solver's result tables that the deploy creates:

```sql
-- as the model role
CREATE SCHEMA IF NOT EXISTS <DB>.WAREHOUSE_ALLOCATION_META;

-- as an administrator
GRANT CALLER USAGE ON DATABASE <DB> TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON SCHEMA <DB>.WAREHOUSE_ALLOCATION_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON WAREHOUSE <PAT_WAREHOUSE> TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL TABLES IN SCHEMA <DB>.WAREHOUSE_ALLOCATION_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL DYNAMIC TABLES IN SCHEMA <DB>.WAREHOUSE_ALLOCATION_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL VIEWS IN SCHEMA <DB>.WAREHOUSE_ALLOCATION_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER INSERT, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA <DB>.WAREHOUSE_ALLOCATION_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER CREATE TABLE, CREATE STAGE ON SCHEMA <DB>.WAREHOUSE_ALLOCATION_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER READ, WRITE ON ALL STAGES IN SCHEMA <DB>.WAREHOUSE_ALLOCATION_META TO APPLICATION <RAI_APP_NAME>;
```

Use this sequence to deploy the model and query it:

1. **Download the template**

   [Download the ZIP](https://docs.relational.ai/templates/zips/v1/warehouse_allocation.zip), unzip it, and enter the template directory:

   ```bash
   unzip warehouse_allocation.zip
   cd warehouse_allocation
   ```

2. **Create a Python environment**

   Create and activate a virtual environment, then update pip:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   ```

3. **Install the template**

   Install the dependencies pinned in `pyproject.toml`:

   ```bash
   python -m pip install .
   ```

4. **Configure your project**

   Use the configuration builder in [Install and run PyRel](https://docs.relational.ai/get-started/install-and-run-pyrel/#configure-your-project) to create `raiconfig.yaml` in the template directory and verify your connection.

   Set the connection `role` to the model role, then add the prescriptive reasoner and a `deployment` section. Give each template its own schema pair so two deployed templates never share one:

   ```yaml
   reasoners:
     prescriptive:
       name: warehouse_allocation_solver            # created on first deploy if it doesn't exist
   deployment:
     role: <MODEL_ROLE>
     public_schema: <DB>.WAREHOUSE_ALLOCATION               # published views and tables
     identity:
       internal_schema: <DB>.WAREHOUSE_ALLOCATION_META      # solver inputs, results, refresh procedures
     schedules:
       standard:
         interval_s: 0              # refresh only on deploy or on demand
     schedule: standard
     pat_secret: <PAT_SECRET>       # these four come from the setup page
     pat_eai: <PAT_EAI>
     pat_user: <PAT_USER>
     pat_warehouse: <PAT_WAREHOUSE>
   ```

5. **Deploy the model**

   Deploy the model in `model/` to the schemas in `raiconfig.yaml`:

   ```bash
   rai models deploy --path model
   ```

   The deploy creates the public schema named in `raiconfig.yaml` if it doesn't exist and waits for the model's first refresh, which runs the graph analysis and the solve. Each refresh of the deployed model runs both again.

6. **Query the results**

   Print the report from the deployed model:

   ```bash
   python -m queries.allocation_report
   ```

   ```text
   ==================================================
   Stage 1a: Eigenvector Centrality
   ==================================================
               site       type   region  centrality
   0     Atlanta_DC  WAREHOUSE    SOUTH    0.321427
   1    Chicago_Hub  WAREHOUSE  MIDWEST    0.631380
   ...

   ==================================================
   Stage 1b: Connected Components
   ==================================================
   UNIFIED NETWORK: all 10 sites in a single component
   ...

   ==================================================
   Stage 2: Inventory Allocation
   ==================================================
   ...
   Status: OPTIMAL
   Total holding cost: $13713.29
   ```

   The report also prints the bridge routes, the formulation, and the allocation plan, and it stops unless the solve's termination status is OPTIMAL. The full printout and a step-by-step walkthrough are in `runbook.md`.

   To solve again without changing the model, refresh the deployed model, then run the query again:

   ```sql
   CALL <DB>.WAREHOUSE_ALLOCATION_META._INTERNAL_REFRESH_MODEL('standard', NULL);
   ```

7. **Tear down the deployment**

   Preview what the teardown removes, then remove it:

   ```bash
   rai models teardown
   rai models teardown --force
   ```

   The first command lists the model's objects without dropping anything; the second drops them and keeps the two schemas.

## Template structure

```text
warehouse_allocation/
  model/
    __init__.py             # the deployed model (Stage 1 graph + Stage 2 prescriptive)
  queries/
    allocation_report.py    # report from the deployed model
  data/
    sites.csv               # Warehouse and store locations with holding costs
    routes.csv              # Distribution routes with capacity and transport cost
    demands.csv             # Demand requirements per site
  README.md                 # this file
  runbook.md                # analyst-facing paste-testable walkthrough
  pyproject.toml            # dependencies
```

**Start here**: deploy with `rai models deploy --path model` and run `python -m queries.allocation_report` for both stages end to end, or follow `runbook.md` to rebuild it step by step.

## Sample data

The bundled data is a small, illustrative distribution network — designed to teach the graph-then-optimize flow on a Snowflake-connected RAI account, not to match a specific operator's network.

- **`sites.csv`** — distribution sites, each with a `region`, a `type` (`WAREHOUSE` or `STORE`), and a per-unit `holding_cost`.
- **`routes.csv`** — directed transport links between sites, each with a `capacity` (used as the undirected graph edge weight) and a `transport_cost`.
- **`demands.csv`** — the inventory `quantity` required at each site.

## Model overview

One shared ontology threads both stages. Stage 1 (graph) writes centrality onto `Site`; Stage 2 (prescriptive) reads it back as a constraint input.

- **Key entities**: `Site` (warehouses and stores), `Route` (transport links), `Demand` (per-site requirements).
- **Primary identifiers**: integer `id` on each of `Site`, `Route`, and `Demand`.
- **Important invariants**: `holding_cost`, `capacity`, and `quantity` are non-negative; the centrality floor applies only to `Site.type == "WAREHOUSE"`; allocation variables are continuous and non-negative.

For the full concept and property definitions, see `model/__init__.py`; `runbook.md` builds them step by step with the RAI skills.

## How it works

Stage 1 characterizes the route topology three ways, then Stage 2 allocates inventory using the results — all on the one shared ontology, so the graph reasoner's output is read directly by the optimizer with no data hand-off in between.

**Stage 1a — Eigenvector centrality.** The model builds an undirected weighted graph from the route network, using route capacity as the edge weight, and scores each site with eigenvector centrality. This surfaces sites that are structurally important because of where they sit in the network, not merely how much throughput passes through them. The scores are written back onto `Site.centrality`.

**Stage 1b — Weakly connected components.** The same graph is checked for fragmentation. Weakly connected components reveal whether every site is reachable from every other, or whether the network has split into isolated clusters that no route bridges. The report states whether the network is unified or fragmented and lists the size and regions of each component.

**Stage 1c — Bridge routes.** Cross-region routes are flagged as bridges: links whose two endpoints lie in different regions, so losing one fragments the corresponding inter-region flow.

**Stage 2 — Inventory allocation.** The optimizer allocates inventory across sites to minimize total holding cost, subject to a total budget, demand satisfaction at each site, and a centrality-based floor that requires each warehouse to hold buffer stock proportional to its centrality score. That floor reads the `Site.centrality` property Stage 1 wrote, so the more structurally critical a warehouse, the more stock the plan holds there.

```text
sites/routes/demands CSVs → graph (centrality, components, bridges) → Site.centrality → optimizer (budget, demand, centrality floor) → allocation plan
```

See `model/__init__.py` for the implementation, and `runbook.md` to reproduce it step by step with the RAI skills.

## Customize this template

Focus on the first changes most users will make.

### Use your own data

- Replace the CSVs in `data/` with your own; keep the column names shown in *Sample data* above (`sites.csv`, `routes.csv`, `demands.csv`). The graph and optimization adapt automatically to new topology.
- For Snowflake-backed runs, swap the `read_csv(...)` calls for `model.data(snowflake_table)` calls.
- Confirm `site_id` values in `routes.csv` and `demands.csv` match the `id` column in `sites.csv` — a mismatched key drops the route or demand silently.

### Tune parameters

- **Budget** — `TOTAL_BUDGET` (default `2000`) caps total units allocated across all sites.
- **Centrality floor** — `MIN_CENTRALITY_FACTOR` (default `200`) sets how much buffer stock a warehouse must hold per unit of centrality.

### Extend the model

- **Change the centrality algorithm** — replace `eigenvector_centrality()` with `pagerank()` or `betweenness_centrality()` for a different notion of importance; Stage 2 reads whatever `Site.centrality` holds.
- **Add a third stage** — use rule-based reasoning to flag sites that are both high-centrality and under-stocked, feeding into an alerting workflow.
- **Add a constraint or metric** — e.g., a per-region minimum-coverage floor, or fold `transport_cost` into the objective.

### Scale up / productionize

- Replace the `data/` CSV bundle with CDC ingestion from your upstream inventory and routing systems.
- The bundled network is small; the chain scales to whatever fits the prescriptive engine's solve budget. Pin dependencies via `pyproject.toml` for reproducible runs.

## Troubleshooting

<details>
<summary><code>ModuleNotFoundError</code></summary>

Make sure you activated the virtual environment and ran `python -m pip install .` to install all dependencies listed in `pyproject.toml`.
</details>

<details>
<summary>Connection or authentication errors</summary>

Re-create `raiconfig.yaml` with the configuration builder (Quickstart step 4) to configure your Snowflake connection. Verify that the RAI Native App is installed and your user has the required permissions.
</details>

## Learn more

### Core concepts

- [Multi-reasoner workflows](https://docs.relational.ai/) — chaining reasoners through a shared ontology, as this template does with graph then prescriptive.
- [PyRel v1 query language](https://docs.relational.ai/) — `model.where(...)` / `model.select(...)` / `aggs`.

### Reasoner reference

- [Graph reasoner](https://docs.relational.ai/) — building graphs from ontology patterns, eigenvector centrality, weakly connected components.
- [Prescriptive reasoner](https://docs.relational.ai/) — `Problem` API, decision variables, constraints, objective.

## Support

- File issues at the RelationalAI templates repository.
