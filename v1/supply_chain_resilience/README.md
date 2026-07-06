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

- `supply_chain_resilience.py` -- Main script: a blast-radius pre-analysis, three chained reasoning stages (graph, rules, prescriptive), and scenario analysis
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
- A Snowflake user with permissions to access the RAI Native App.

### Tools
- Python >= 3.10
- RelationalAI Python SDK (`relationalai`) == 1.11.0

## Quickstart

1. Download the ZIP file for this template and extract it:

   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/supply_chain_resilience.zip
   unzip supply_chain_resilience.zip
   cd supply_chain_resilience
   ```

   > [!TIP]
   > You can also download the template ZIP using the "Download ZIP" button at the top of this page.

2. Create a virtual environment and activate it:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   ```

3. Install dependencies:

   ```bash
   python -m pip install .
   ```

4. Configure your RAI connection:

   ```bash
   rai init
   ```

5. Run the template:

   ```bash
   python supply_chain_resilience.py
   ```

6. Expected output:
   ```text
   STAGE 1: Graph -- Network Criticality        (top critical sites ranked)
   STAGE 2: Rules -- Supplier Risk Classification (late shipments, risk classes)
   STAGE 3: Prescriptive -- Risk-Adjusted Network Flow
     Status: OPTIMAL   Total cost: 1,865.00   All demand satisfied
   SCENARIO COMPARISON: Baseline vs. Site S004 offline vs. Watch->Avoid
   ```

## Template structure

```text
.
├── README.md
├── pyproject.toml
├── supply_chain_resilience.py
└── data/
    ├── site.csv
    ├── business.csv
    ├── operation.csv
    ├── sku.csv
    ├── demand.csv
    ├── shipment.csv
    └── delay_prediction.csv
```

**Start here**: run `python supply_chain_resilience.py` for the full chain end to end -- blast-radius pre-analysis, the three reasoning stages, and the scenario comparison -- or follow `runbook.md` to reproduce it step by step with the RAI skills.

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

- **Key entities**: `Site`, `Business`, `Operation`, `SKU`, `Demand`, `Shipment`, `DelayPrediction`.
- **Primary identifiers**: string `id` on every concept.
- **Important invariants**: `reliability_score` and `predicted_delay_prob` are fractions in `[0, 1]`; `capacity_per_day`, `cost_per_unit`, and `quantity` are non-negative; the flow decision variable `x_flow` is bounded by each operation's capacity; unmet-demand slack `x_unmet` is non-negative.

For the full concept and property definitions, see `supply_chain_resilience.py`; `runbook.md` builds them step by step with the RAI skills.

## How it works

One shared ontology threads a pre-analysis and three chained reasoning stages -- each stage reads what earlier stages wrote and enriches the model for the next.

```text
CSV inputs → blast-radius reachability → Graph criticality → Rules risk classification → Prescriptive risk-adjusted flow → scenario re-solves
```

**Configure inputs.** A handful of parameters at the top control the run: risk thresholds (`RELIABILITY_THRESHOLD`, `DELAY_PROB_THRESHOLD`), objective penalties (`UNMET_PENALTY`, `RISK_SURCHARGE`, `CENTRALITY_WEIGHT`), and which quarter's delay predictions to use (`PREDICTION_QUARTER`).

**Define concepts and load data.** The seven source concepts load from CSV. A derived `Operation.source_business` relationship links each operation to its source business by matching the operation's source site to the business's site, avoiding an explicit join table.

**Stage 0 -- blast-radius pre-analysis.** A directed `Business` graph is built from the derived supplier-to-customer `ships_to` edges. Upstream reachability from each high-priority customer traces every supplier it transitively depends on, making the exposure footprint explicit so the later scenario results can be read in context.

**Stage 1 -- Graph, network criticality.** An undirected graph with sites as nodes and SHIP operations as edges captures the physical shipping network. Weakly connected components reveal whether the network is fragmented or unified; eigenvector centrality scores each site by its structural influence. Scores are normalized and stored as `Site.centrality` for the optimizer to penalize.

**Stage 2 -- Rules, supplier risk classification.** Derived relationships flag suppliers below the reliability threshold and suppliers with high predicted delay probability. Suppliers with both flags are classified "avoid" (blocked from flow); suppliers with either flag are "watch" (allowed but surcharged). A further rule flags `HIGH`-priority demand as escalated. These classifications feed the optimizer as hard constraints and cost surcharges.

**Stage 3 -- Prescriptive, risk-adjusted network flow.** Two continuous decision variables drive the solve: `x_flow` per operation (bounded by capacity) and `x_unmet` slack per order. A demand-satisfaction constraint requires inbound flow at each customer's site for the demanded SKU, plus slack, to cover the order. Operations from "avoid" suppliers are pinned to zero flow. The objective minimizes four components: base transport cost, a surcharge on flow through "watch" suppliers, a centrality penalty that discourages over-reliance on bottleneck sites, and a high penalty on unmet demand.

**Solve and run scenarios.** The baseline solves with HiGHS. Two disruption scenarios then re-solve with modified constraints -- taking the highest-centrality site offline, and downgrading all "watch" suppliers to "avoid" -- and the cost increase across scenarios quantifies the network's resilience to each type of disruption.

For the implementation, see `supply_chain_resilience.py`; to reproduce it step by step with the RAI skills, follow `runbook.md`.

## Customize this template

Focus on the first changes most users will make.

### Use your own data

- Replace the CSVs in `data/` with your own; keep the column names listed in *Sample data* above.
- For Snowflake-backed runs, swap the `pd.read_csv(...)` calls for `model.data(snowflake_table)` calls.
- The `source_business` link is derived by matching `Operation.source_site` to `Business.site` -- ensure those IDs align across `operation.csv` and `business.csv` (the script prints a populated count on startup).

### Tune parameters

- **Risk thresholds** -- `RELIABILITY_THRESHOLD` and `DELAY_PROB_THRESHOLD` control which suppliers are flagged as unreliable or high-delay-risk.
- **Prediction quarter** -- `PREDICTION_QUARTER` selects which quarter's delay predictions to use.
- **Centrality weight** -- `CENTRALITY_WEIGHT` controls how strongly bottleneck penalties influence routing.
- **Risk surcharge** -- `RISK_SURCHARGE` sets the cost penalty for "watch" suppliers.
- **Unmet-demand penalty** -- `UNMET_PENALTY` controls the trade-off between routing cost and demand fulfillment.

### Extend the model

- Add new scenarios by calling `solve_flow()` with different `exclude_site_id` or `block_business_ids` parameters.
- Add rows to the CSV files -- more sites, operations, or demand orders scale the network flow problem.
- Swap eigenvector centrality for another graph algorithm (e.g. betweenness) to surface a different notion of structural criticality without changing the optimizer.

### Scale up / productionize

- Replace the `data/` CSV bundle with change-data-capture ingestion from the operator's upstream systems.
- The formulation scales to whatever fits the prescriptive engine's solve budget; the reusable `solve_flow()` function makes scheduled re-solves and new disruption scenarios cheap to add.

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
- Ensure the `source_business` derived relationship is populating (the script prints a count on startup).
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

- Run `rai init` to configure your Snowflake connection.
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
