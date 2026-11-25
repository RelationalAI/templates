---
title: "Supply Chain Resilience"
description: "Chain blast-radius reachability, network analysis, and rule-based risk classification into a risk-adjusted minimum-cost network flow for supply-chain routing."
featured: false
experience_level: intermediate
industry: "Supply Chain & Logistics"
reasoning_types:
    - Graph
    - Rules-based
    - Prescriptive
tags:
  - Multi-Reasoner
  - Chained Reasoning
  - Supply Chain
  - Network Flow
  - Risk Management
  - Scenario Analysis
---

## What this template is for

Supply chain networks route goods from suppliers through factories and distribution centers to customers -- but not all routes carry equal risk. Cost-optimal routes tend to concentrate flow through a few critical hubs, creating fragility that cost-minimization alone never surfaces. Unreliable suppliers, predicted delays, and over-reliance on bottleneck sites all threaten fulfillment, yet each is a different kind of signal: structural risk, supplier reliability, and routing cost are interdependent, and no single analysis reveals how they compound. When a critical warehouse goes offline, the network must absorb the shock through costlier alternatives or unmet demand -- and planners need to know that cost before it happens.

**This template chains RelationalAI's Graph, Rules-based, and Prescriptive reasoners on one shared ontology, so structural criticality and supplier risk flow directly into a risk-adjusted minimum-cost network flow, then re-solves under disruption scenarios to price resilience.**

## Who this is for

- Supply chain and logistics managers evaluating network resilience.
- Operations researchers exploring multi-reasoner pipelines in RelationalAI.
- Developers learning how to chain graph, rules, and optimization in a single model.
- **Assumed knowledge**: comfortable reading Python; the graph, rules, and optimization terms are explained as they come up. No prior RelationalAI experience is required to run it, though following a single-reasoner template first makes the chained flow easier to follow.

## What you'll build

- A risk-adjusted routing plan that meets demand at minimum cost while penalizing flow through bottleneck sites and risky suppliers, produced by the **prescriptive** reasoner (continuous flow and unmet-demand decision variables).
- Per-site criticality scores (`Site.centrality`) from **graph analysis** -- weakly connected components plus normalized eigenvector centrality -- that feed the routing objective as a bottleneck penalty.
- Supplier risk classifications (`Business.is_unreliable`, `is_watch_level`, `is_avoid`) and escalated-demand flags from **rules-based** reasoning, wired into the optimizer as hard constraints and surcharges.
- An upstream blast-radius view: for each high-priority customer, the set of suppliers it transitively depends on, computed by **graph reachability** before any optimization runs.
- A scenario comparison that re-solves the same formulation with a critical site offline and with watch suppliers downgraded to avoid, quantifying the cost of each disruption.

## What's included

- **Model**: concepts for sites, businesses, SKUs, operations, demand, shipments, and delay predictions, the graph, rules, and risk-adjusted network flow problems, in the `model/` package (`schema.py` declares the concepts, `source.py` loads the sample data, `blast_radius.py`, `network_criticality.py`, `supplier_risk.py`, and `risk_adjusted_flows.py` state the graphs, rules, and decision problems, one module per stage), which `rai models deploy --path model` deploys to your Snowflake account, where each refresh runs the graph analysis and the solves.
- **Query**: `queries/resilience_report.py`, which prints the report from the deployed model.
- `runbook.md` -- a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the script itself
- `data/site.csv` -- 31 sites (factories, distribution centers, offices, stores) across multiple regions
- `data/business.csv` -- 31 businesses (suppliers, manufacturers, warehouses, buyers) with reliability scores
- `data/operation.csv` -- 70 shipping and transfer operations with cost, capacity, and transit time
- `data/sku.csv` -- 9 SKUs (raw materials, components, finished goods)
- `data/demand.csv` -- 20 customer demand orders with quantity and priority
- `data/shipment.csv` -- 262 historical shipments with delay data
- `data/delay_prediction.csv` -- 36 ML-predicted delay probabilities per supplier per quarter
- `pyproject.toml` -- Python project configuration with dependencies

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- The one-time model deployment setup on that account, done by an account administrator: follow [Set up model deployment](https://private.relational.ai/early-access/model-deploy-setup) through **Governed setup**, **PAT authentication**, and steps 1-2 of **Additional setup for the prescriptive reasoner** (the Quickstart covers this template's own schema). It gives you a model role, a programmatic access token (PAT) stored as a secret, an external access integration, a PAT user, and a warehouse.
- A Snowflake user that holds the model role.

### Tools
- Python 3.10 through 3.14 (the range relationalai 2.3.0 supports).
- RelationalAI Python SDK (`relationalai == 2.3.0`).

## Quickstart

Before you start, install Python 3.10 or later and complete the access prerequisites above: a Snowflake account with the RAI Native App, the one-time model deployment setup, and a Snowflake user that holds the model role.

Before the first deploy, create this template's internal schema as the model role, and have an administrator grant the RAI Native App caller access to it. The internal schema holds only this model's objects, so the grants cover all of it, including the solver's result tables that the deploy creates:

```sql
-- as the model role
CREATE SCHEMA IF NOT EXISTS <DB>.SUPPLY_CHAIN_RESILIENCE_META;

-- as an administrator
GRANT CALLER USAGE ON DATABASE <DB> TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON SCHEMA <DB>.SUPPLY_CHAIN_RESILIENCE_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON WAREHOUSE <PAT_WAREHOUSE> TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL TABLES IN SCHEMA <DB>.SUPPLY_CHAIN_RESILIENCE_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL DYNAMIC TABLES IN SCHEMA <DB>.SUPPLY_CHAIN_RESILIENCE_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL VIEWS IN SCHEMA <DB>.SUPPLY_CHAIN_RESILIENCE_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER INSERT, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA <DB>.SUPPLY_CHAIN_RESILIENCE_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER CREATE TABLE, CREATE STAGE ON SCHEMA <DB>.SUPPLY_CHAIN_RESILIENCE_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER READ, WRITE ON ALL STAGES IN SCHEMA <DB>.SUPPLY_CHAIN_RESILIENCE_META TO APPLICATION <RAI_APP_NAME>;
```

Use this sequence to deploy the model and query it:

1. **Download the template**

   [Download the ZIP](https://docs.relational.ai/templates/zips/v1/supply_chain_resilience.zip), unzip it, and enter the template directory:

   ```bash
   unzip supply_chain_resilience.zip
   cd supply_chain_resilience
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
       name: supply_chain_resilience_solver            # created on first deploy if it doesn't exist
   deployment:
     role: <MODEL_ROLE>
     public_schema: <DB>.SUPPLY_CHAIN_RESILIENCE               # published views and tables
     identity:
       internal_schema: <DB>.SUPPLY_CHAIN_RESILIENCE_META      # solver inputs, results, refresh procedures
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

   The deploy creates the public schema named in `raiconfig.yaml` if it doesn't exist and waits for the model's first refresh, which runs the graph analysis and the three solves. Each refresh of the deployed model runs them again.

6. **Query the results**

   Print the report from the deployed model:

   ```bash
   python -m queries.resilience_report
   ```

   ```text
   Source-business links: 70
   ...
   ======================================================================
   STAGE 1: Graph -- Network Criticality
   ======================================================================
   ...
   Connected components: 2
   ...
   Top critical sites (eigenvector centrality):
     S004 TechAssembly Factory (FACTORY, APAC): centrality=0.5016
     S006 West Coast DC (DISTRIBUTION_CENTER, AMERICAS): centrality=0.3895
     S003 PowerCell Facility (FACTORY, APAC): centrality=0.3688
   ...
   ======================================================================
   STAGE 2: Rules -- Supplier Risk Classification
   ======================================================================

   Late shipments: 37 of 262 (14%)
   ...
   Escalated demands (HIGH priority): 9

   ======================================================================
   STAGE 3: Prescriptive -- Risk-Adjusted Network Flow
   ======================================================================
   Solve result:
   • status: OPTIMAL
   • objective: 1865.0


     [Baseline]
     Status: OPTIMAL
     Total cost: 1,865.00
     Active flows: 8
     All demand satisfied
   ...
   ======================================================================
   SCENARIO COMPARISON
   ======================================================================
     Scenario                  Status                     Cost      Unmet
     -----------------------------------------------------------------
     Baseline                  OPTIMAL                1,865.00          0
     S004-offline              OPTIMAL                3,515.00 (+88.5%)          0
     Watch-Avoid               OPTIMAL                1,865.00 (0.0%)          0
   ```

   The report prints each stage and each problem's solve result (trimmed here). Taking the most critical site offline raises cost by 88.5%, while downgrading the watch suppliers to avoid leaves the baseline cost unchanged because the optimizer already routes around them. See `runbook.md` for the step-by-step walkthrough.

   To solve again without changing the model, refresh the deployed model, then run the query again:

   ```sql
   CALL <DB>.SUPPLY_CHAIN_RESILIENCE_META._INTERNAL_REFRESH_MODEL('standard', NULL);
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
.
├── README.md                     # this file
├── runbook.md                    # step-by-step analyst walkthrough
├── pyproject.toml                # dependencies
├── model/
│   ├── __init__.py               # exports of the deployed model
│   ├── schema.py                 # concepts and properties
│   ├── source.py                 # sample data
│   ├── blast_radius.py           # Stage 0: Business graph, high-priority customers, upstream suppliers
│   ├── network_criticality.py    # Stage 1: site graph, components, centrality
│   ├── supplier_risk.py          # Stage 2: risk flags and classes, late shipments, escalated demand
│   └── risk_adjusted_flows.py    # Stage 3: network flow problems and scenario cost change
├── queries/
│   └── resilience_report.py      # report from the deployed model
└── data/
    ├── site.csv
    ├── business.csv
    ├── operation.csv
    ├── sku.csv
    ├── demand.csv
    ├── shipment.csv
    └── delay_prediction.csv
```

**Start here**: deploy with `rai models deploy --path model` and run `python -m queries.resilience_report` for the full chain end to end -- blast-radius pre-analysis, the three reasoning stages, and the scenario comparison -- or follow `runbook.md` to reproduce it step by step with the RAI skills.

## Sample data

The bundled data is synthetic and illustrative -- designed to teach the reasoning flow on a Snowflake-connected RAI account, not to match a specific operator's network.

- **`site.csv`** (31 rows) -- physical locations (factories, distribution centers, offices, stores) with region and country.
- **`business.csv`** (31 rows) -- suppliers, manufacturers, warehouses, and buyers, each operating at a site, with a `RELIABILITY_SCORE` and value tier.
- **`operation.csv`** (70 rows) -- shipping and transfer routes between sites, each with `COST_PER_UNIT`, `CAPACITY_PER_DAY`, transit time, and output SKU.
- **`sku.csv`** (9 rows) -- raw materials, components, and finished goods with unit cost and price.
- **`demand.csv`** (20 rows) -- customer orders with quantity, priority, and due date.
- **`shipment.csv`** (262 rows) -- historical shipments with status and delay days; the source for the late-shipment rate and the blast-radius supplier graph.
- **`delay_prediction.csv`** (36 rows) -- predicted delay probabilities per supplier per fiscal quarter, with a risk tier.

## Model overview

One shared ontology threads the pre-analysis and all three stages. Each stage reads concepts and properties earlier stages wrote, and writes new ones for downstream stages.

- **Key entities**: `Site` — a physical location (Stage 1 enriches it with a centrality score); `Business` — a supplier, manufacturer, warehouse, or buyer operating at a site (Stage 2 enriches it with risk flags); `Operation` — a shipping or transfer route between sites, the flow decision space; `SKU` — a stock-keeping unit (raw material, component, or finished good); `Demand` — a customer order (Stage 2 flags escalations, Stage 3 tracks unmet slack); `Shipment` — a historical shipment, the source for late-shipment rates and the blast-radius supplier graph; `DelayPrediction` — a predicted delay probability per supplier per fiscal quarter.
- **Primary identifiers**: string `id` on every concept.
- **Important invariants**: `reliability_score` and `predicted_delay_prob` are fractions in `[0, 1]`; `capacity_per_day`, `cost_per_unit`, and `quantity` are non-negative; the flow decision variable `x_flow` is bounded by each operation's capacity; unmet-demand slack `x_unmet` is non-negative.

For the full concept and property definitions, see `model/schema.py`; `runbook.md` builds them step by step with the RAI skills.

## How it works

One shared ontology threads a pre-analysis and three chained reasoning stages -- each stage reads what earlier stages wrote and enriches the model for the next.

```text
CSV inputs → blast-radius reachability → Graph criticality → Rules risk classification → Prescriptive risk-adjusted flow → scenario re-solves
```

**Configure inputs.** A handful of parameters at the top of the module that uses them control the run: risk thresholds (`RELIABILITY_THRESHOLD`, `DELAY_PROB_THRESHOLD`) and which quarter's delay predictions to use (`PREDICTION_QUARTER`) in `model/supplier_risk.py`, and objective penalties (`UNMET_PENALTY`, `RISK_SURCHARGE`, `CENTRALITY_WEIGHT`) and the solver-noise cutoff `FLOW_TOLERANCE` in `model/risk_adjusted_flows.py`.

**Define concepts and load data.** The seven source concepts load from CSV (`model/schema.py` and `model/source.py`). A derived `Operation.source_business` relationship links each operation to its source business by matching the operation's source site to the business's site, avoiding an explicit join table.

**Stage 0 -- blast-radius pre-analysis.** A directed `Business` graph is built from the derived supplier-to-customer `ships_to` edges. Upstream reachability from each high-priority customer traces every supplier it transitively depends on, making the exposure footprint explicit so the later scenario results can be read in context. The `SUPPLIER`-type businesses a customer reaches are published as `Business.upstream_supplier`.

**Stage 1 -- Graph, network criticality.** An undirected graph with sites as nodes and SHIP operations as edges captures the physical shipping network. Weakly connected components reveal whether the network is fragmented or unified; eigenvector centrality scores each site by its structural influence. Scores are normalized by the largest score and stored as `Site.centrality` for the optimizer to penalize. Each site's rank by centrality (`Site.centrality_rank`, ties broken by site ID) is published, and the first-ranked site is flagged `Site.is_most_critical`. Each component's site count and regions (`SiteCluster`) are published too.

**Stage 2 -- Rules, supplier risk classification.** Derived relationships flag suppliers below the reliability threshold and suppliers with high predicted delay probability. Suppliers with both flags are classified "avoid" (blocked from flow); suppliers with either flag are "watch" (allowed but surcharged). Each business with a reliability score gets one risk class (`Business.risk_class`: avoid, watch, or reliable). A shipment with a recorded delay over zero days is late (`Shipment.is_late`), with late counts per supplier and in total, and a further rule flags `HIGH`-priority demand as escalated. These classifications feed the optimizer as hard constraints and cost surcharges.

**Stage 3 -- Prescriptive, risk-adjusted network flow.** Two continuous decision variables drive the solve: `x_flow` per operation (bounded by capacity) and `x_unmet` slack per order. A demand-satisfaction constraint requires inbound flow at each customer's site for the demanded SKU, plus slack, to cover the order. Each order is checked against the whole inbound flow for its site and SKU, so several orders for the same site and SKU can count the same units, and an order with no inbound operation for its site and SKU gets no constraint; "All demand satisfied" means every constrained order is covered by that inbound flow, not that the orders are fulfilled separately. Operations from "avoid" suppliers are pinned to zero flow. The objective minimizes four components: base transport cost, a surcharge on flow through "watch" suppliers, a centrality penalty that discourages over-reliance on bottleneck sites, and a high penalty on unmet demand.

**Solve and run scenarios.** The baseline solves with HiGHS. Two disruption scenarios are their own problems with modified constraints -- taking the most critical site offline, and downgrading all "watch" suppliers to "avoid" -- so one infeasible scenario never affects the others, and the cost increase across scenarios quantifies the network's resilience to each type of disruption. Each problem also publishes its count of active flows and unmet orders and units, and `CostChangePct` publishes each scenario's cost change against the baseline, so the report assembles the scenario comparison from published values.

For the implementation, see `model/blast_radius.py`, `model/network_criticality.py`, `model/supplier_risk.py`, and `model/risk_adjusted_flows.py`; to reproduce it step by step with the RAI skills, follow `runbook.md`.

## Customize this template

Focus on the first changes most users will make.

### Use your own data

- Replace the CSVs in `data/` with your own; keep the column names listed in *Sample data* above.
- For Snowflake-backed runs, swap the `read_csv(...)` calls in `model/source.py` for `model.data(snowflake_table)` calls.
- The `source_business` link is derived by matching `Operation.source_site` to `Business.site` -- ensure those IDs align across `operation.csv` and `business.csv` (the report prints a populated count first).

### Tune parameters

- **Risk thresholds** -- `RELIABILITY_THRESHOLD` and `DELAY_PROB_THRESHOLD` control which suppliers are flagged as unreliable or high-delay-risk.
- **Prediction quarter** -- `PREDICTION_QUARTER` selects which quarter's delay predictions to use.
- **Centrality weight** -- `CENTRALITY_WEIGHT` controls how strongly bottleneck penalties influence routing.
- **Risk surcharge** -- `RISK_SURCHARGE` sets the cost penalty for "watch" suppliers.
- **Unmet-demand penalty** -- `UNMET_PENALTY` controls the trade-off between routing cost and demand fulfillment.

### Extend the model

- Add new scenarios by calling `build_flow()` in `model/risk_adjusted_flows.py` with a new problem name and different `exclude_critical_site` or `block_watch_level` arguments, then report the new problem in `queries/resilience_report.py`.
- Add rows to the CSV files -- more sites, operations, or demand orders scale the network flow problem.
- Swap eigenvector centrality for another graph algorithm (e.g. betweenness) to surface a different notion of structural criticality without changing the optimizer.

### Scale up / productionize

- Replace the `data/` CSV bundle with change-data-capture ingestion from the operator's upstream systems.
- The formulation scales to whatever fits the prescriptive engine's solve budget; the reusable `build_flow()` function makes scheduled re-solves and new disruption scenarios cheap to add.

## Troubleshooting

<details>
<summary><code>Status: INFEASIBLE</code></summary>

- If too many suppliers are blocked (especially in the Watch->Avoid scenario), there may not be enough capacity to meet all demand. The unmet demand slack variable should prevent true infeasibility, but check that `UNMET_PENALTY` is set high enough that the solver prefers routing over leaving demand unmet.
- Verify that `operation.csv` has sufficient capacity on routes to cover total demand in `demand.csv`.
</details>

<details>
<summary>All demand shows as unmet</summary>

- Check that `operation.csv` routes connect supplier sites to customer sites for the correct SKUs.
- Verify that the demand satisfaction constraint joins on both site and SKU: inbound flow must match the demanded SKU at the customer's site.
- Ensure the `source_business` derived relationship is populating (the report prints a count first).
</details>

<details>
<summary>Graph shows 0 edges</summary>

- Edges are created from operations with `op_type == "SHIP"`. Verify that `operation.csv` contains SHIP-type operations.
- Check that source and output site IDs in `operation.csv` match IDs in `site.csv`.
</details>

<details>
<summary>No suppliers classified as "avoid" or "watch"</summary>

- The risk classification depends on both `RELIABILITY_THRESHOLD` (default 0.80) and `DELAY_PROB_THRESHOLD` (default 0.15). If all suppliers have high reliability and low delay predictions, none will be flagged.
- Check `business.csv` for reliability scores below the threshold and `delay_prediction.csv` for predictions above the threshold in the configured quarter.
</details>

<details>
<summary><code>ModuleNotFoundError</code></summary>

- Make sure you activated the virtual environment and ran `python -m pip install .` from the template directory.
- The `pyproject.toml` declares the required dependencies.
</details>

<details>
<summary>Connection or authentication errors</summary>

- Re-create `raiconfig.yaml` with the configuration builder (Quickstart step 4) and verify the connection settings.
- Verify that the RAI Native App is installed and your user has the required permissions.
</details>

## Learn more

### Core concepts

- [Multi-reasoner workflows](https://docs.relational.ai/) -- chained reasoner patterns and accretive ontology enrichment.
- [PyRel v1 query language](https://docs.relational.ai/) -- `model.where(...)` / `aggs` / `.define()`.

### Reasoner reference

- [Graph reasoner](https://docs.relational.ai/) -- connected components, eigenvector centrality, and reachability.
- [Rules-based reasoning](https://docs.relational.ai/) -- deriving classifications and flags as relationships.
- [Prescriptive reasoner](https://docs.relational.ai/) -- `Problem` API, decision variables, constraints, and objective.

## Support

- File issues at the RelationalAI templates repository.
