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

**Start here**: run `python supply_chain_resilience.py` for the full chain end to end -- blast-radius pre-analysis, the three reasoning stages, and the scenario comparison.

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

### Concepts

**`Site`** -- a physical location. Stage 1 enriches it with a normalized centrality score.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | String | Yes | `ID` from `data/site.csv` |
| `name`, `site_type`, `region`, `country` | String | No | Loaded from CSV |
| `centrality` | Float | No | **Stage 1** normalized eigenvector centrality |

**`Business`** -- a supplier, manufacturer, warehouse, or buyer that operates at a site. Stage 2 enriches it with risk flags.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | String | Yes | `ID` from `data/business.csv` |
| `name`, `business_type` | String | No | Loaded from CSV |
| `reliability_score` | Float | No | `[0, 1]` supplier reliability |
| `site` | Relationship | -- | Business operates at a `Site` |
| `ships_to` | Relationship | -- | Derived supplier-to-customer edge (collapses shipments); the blast-radius graph edge |
| `is_high_priority_customer` | Relationship | -- | Pre-analysis flag; seeds upstream reachability |
| `is_unreliable`, `has_high_delay_risk`, `is_watch_level`, `is_avoid` | Relationship | -- | **Stage 2** risk classifications |

**`Operation`** -- a shipping or transfer route between sites. The flow decision space.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | String | Yes | `ID` from `data/operation.csv` |
| `op_type` | String | No | `SHIP` / transfer; SHIP operations form the site graph edges |
| `cost_per_unit` | Float | No | Base transport cost |
| `capacity_per_day` | Integer | No | Upper bound on `x_flow` |
| `transit_time_days` | Integer | No | Loaded from CSV |
| `source_site`, `output_site`, `output_sku` | Relationship | -- | Route endpoints and produced SKU |
| `source_business` | Relationship | -- | Derived by matching `source_site` to `Business.site` |
| `x_flow` | Float | No | **Stage 3** flow decision variable (0 to capacity) |

**`Demand`** -- a customer order. Stage 2 flags escalations; Stage 3 tracks unmet slack.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | String | Yes | `ID` from `data/demand.csv` |
| `quantity` | Integer | No | Units ordered |
| `priority` | String | No | `HIGH` triggers escalation |
| `business`, `sku` | Relationship | -- | Placing customer and demanded SKU |
| `is_escalated` | Relationship | -- | **Stage 2** flag for `priority == "HIGH"` |
| `x_unmet` | Float | No | **Stage 3** unmet-demand slack |

**`SKU`** -- a stock-keeping unit (raw material, component, or finished good).

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | String | Yes | `ID` from `data/sku.csv` |
| `name`, `sku_type` | String | No | Loaded from CSV |

**`Shipment`** -- a historical shipment; the source for late-shipment rates and the blast-radius supplier graph.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | String | Yes | `ID` from `data/shipment.csv` |
| `sku_id` | String | No | Shipped SKU |
| `quantity` | Integer | No | Units shipped |
| `supplier`, `customer` | Relationship | -- | Supplier and customer `Business` endpoints |

**`DelayPrediction`** -- a predicted delay probability per supplier per fiscal quarter.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | String | Yes | `ID` from `data/delay_prediction.csv` |
| `fiscal_quarter` | String | No | E.g. `Q1-2025` |
| `predicted_delay_prob` | Float | No | `[0, 1]` predicted delay probability |
| `risk_tier` | String | No | Loaded from CSV |
| `supplier_business` | Relationship | -- | Links the prediction to a `Business` |

### Relationships

- `Business.site` -- each business operates at a `Site`.
- `Operation.source_site` / `output_site` / `output_sku` -- route endpoints and the SKU produced.
- `Operation.source_business` -- derived by matching `Operation.source_site` to `Business.site`, avoiding an explicit join table.
- `Business.ships_to` -- derived supplier-to-customer edge collapsing many shipments; the directed edge the blast-radius reachability traverses.
- `Demand.business` / `sku` -- the customer placing the order and the SKU demanded.
- `Shipment.supplier` / `customer` and `DelayPrediction.supplier_business` -- link history and predictions back to `Business`.

## How it works

This section walks through the highlights in `supply_chain_resilience.py`.

### Import libraries and configure inputs

First, the script imports the RAI SDK and configures key parameters that control risk thresholds, penalties, and the prediction quarter:

```python
from relationalai.semantics import Float, Integer, Model, String, select, sum, where
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.std import aggregates as aggs

model = Model("supply_chain_resilience")

UNMET_PENALTY = 100.0  # penalty for unmet demand (kept moderate so routing costs are visible)
RISK_SURCHARGE = 5.0  # cost multiplier for "watch" supplier operations
CENTRALITY_WEIGHT = 2.0  # multiplier for bottleneck site penalty
DELAY_PROB_THRESHOLD = 0.15  # above this = high delay risk
RELIABILITY_THRESHOLD = 0.80  # below this = unreliable supplier
PREDICTION_QUARTER = "Q1-2025"  # which quarter's predictions to use
```

### Define concepts and load CSV data

Next, the model defines concepts for the supply chain ontology. `Site` represents physical locations (factories, distribution centers, stores). `Business` represents entities (suppliers, manufacturers, buyers) with reliability scores. `Operation` defines shipping routes between sites with cost and capacity:

```python
Site = model.Concept("Site", identify_by={"id": String})
Site.name = model.Property(f"{Site} has {String:name}")
Site.site_type = model.Property(f"{Site} has type {String:site_type}")
Site.region = model.Property(f"{Site} in {String:region}")

Business = model.Concept("Business", identify_by={"id": String})
Business.reliability_score = model.Property(
    f"{Business} has reliability {Float:reliability_score}"
)
Business.site = model.Relationship(f"{Business} operates at {Site}")

Operation = model.Concept("Operation", identify_by={"id": String})
Operation.cost_per_unit = model.Property(
    f"{Operation} costs {Float:cost_per_unit} per unit"
)
Operation.capacity_per_day = model.Property(
    f"{Operation} has capacity {Integer:capacity_per_day} per day"
)
Operation.source_site = model.Relationship(f"{Operation} from {Site}")
Operation.output_site = model.Relationship(f"{Operation} to {Site}")
Operation.output_sku = model.Relationship(f"{Operation} produces {SKU}")
```

A derived relationship links each operation to its source business by matching the operation's source site to the business's site:

```python
Operation.source_business = model.Relationship(
    f"{Operation} sourced from {Business}"
)
model.define(Operation.source_business(Operation, Business)).where(
    Operation.source_site == Business.site
)
```

`DelayPrediction` captures ML-predicted delay probabilities per supplier per fiscal quarter:

```python
DelayPrediction = model.Concept("DelayPrediction", identify_by={"id": String})
DelayPrediction.predicted_delay_prob = model.Property(
    f"{DelayPrediction} has {Float:predicted_delay_prob}"
)
DelayPrediction.supplier_business = model.Relationship(
    f"{DelayPrediction} predicts for {Business}"
)
```

### Stage 0: Blast-radius pre-analysis

Before any optimization runs, a directed `Business` graph is built from the derived `ships_to` edges (supplier to customer). Upstream reachability from the high-priority customers traces every supplier each one transitively depends on, making the exposure footprint explicit so the later scenario results can be read in context:

```python
model.where(Business.ships_to(b_src, b_dst)).define(
    biz_graph.Edge.new(src=b_src, dst=b_dst)
)

target_customer = model.Relationship(f"target customer {Business}")
model.where(Business.is_high_priority_customer()).define(target_customer(Business))

reachable_to = biz_graph.reachable(to=target_customer)
```

### Stage 1: Graph -- network criticality

An undirected graph is built with sites as nodes and shipping operations as edges. This captures how sites are connected through the physical shipping network:

```python
graph = Graph(model, directed=False, weighted=False, node_concept=Site, aggregator="sum")

s1, s2, op_ref = Site.ref(), Site.ref(), Operation.ref()
model.define(
    graph.Edge.new(src=s1, dst=s2)
).where(
    op_ref.source_site(s1),
    op_ref.output_site(s2),
    op_ref.op_type == "SHIP",
)
```

Weakly connected components identify whether the network is fragmented or unified. Eigenvector centrality scores each site by its influence in the network -- high-centrality sites are critical hubs whose disruption would cascade through many routes. These scores are normalized and stored as a `Site.centrality` property for use in the optimization objective:

```python
eigenvector = graph.eigenvector_centrality()

Site.centrality = model.Property(f"{Site} has centrality {Float:centrality}")
eig_df["normalized"] = eig_df["centrality_score"] / max_centrality
cent_data = model.data(eig_df[["site_id", "normalized"]])
model.where(Site.id == cent_data["site_id"]).define(
    Site.centrality(cent_data["normalized"])
)
```

### Stage 2: Rules -- supplier risk classification

Two derived Relationships flag risky suppliers. The first marks businesses with reliability scores below the threshold. The second uses ML delay predictions to flag suppliers with high predicted delay probability:

```python
Business.is_unreliable = model.Relationship(f"{Business} is unreliable")
model.where(
    Business.reliability_score < RELIABILITY_THRESHOLD
).define(Business.is_unreliable())

Business.has_high_delay_risk = model.Relationship(
    f"{Business} has high delay risk"
)
dp_ref = DelayPrediction.ref()
model.where(
    dp_ref.supplier_business(Business),
    dp_ref.fiscal_quarter == PREDICTION_QUARTER,
    dp_ref.predicted_delay_prob > DELAY_PROB_THRESHOLD,
).define(Business.has_high_delay_risk())
```

Suppliers that are both unreliable and have high delay risk are classified as "avoid" (blocked from the network flow). Suppliers with either flag are "watch" (allowed but penalized). These classifications feed directly into the optimizer as hard constraints and cost surcharges.

A third rule flags escalated demand orders to surface high-priority fulfillment requirements:

```python
Demand.is_escalated = model.Relationship(f"{Demand} is escalated")
model.where(Demand.priority == "HIGH").define(Demand.is_escalated())
```

### Stage 3: Define decision variables, constraints, and objective

Two continuous decision variables control the network flow: `x_flow` is the flow on each operation (bounded by capacity), and `x_unmet` is unmet demand slack per order:

```python
problem = Problem(model, Float)

problem.solve_for(
    Operation.x_flow,
    name=["x_flow", Operation.id],
    lower=0,
    upper=Operation.capacity_per_day,
)

problem.solve_for(Demand.x_unmet, name=["x_unmet", Demand.id], lower=0, populate=False)
```

The demand satisfaction constraint requires that inbound flow at each customer's site for the demanded SKU, plus unmet slack, covers the order quantity:

```python
problem.satisfy(
    model.require(
        sum(Op.x_flow).per(D) + D.x_unmet >= D.quantity
    ).where(
        D.business(B),
        B.site == Op.output_site,
        D.sku == Op.output_sku,
    ),
    name=["demand_sat", D.id],
)
```

Operations sourced from "avoid" suppliers are blocked with zero-flow constraints. In scenario mode, operations from a specific site can also be disabled.

The objective minimizes four cost components. Transport cost is the base shipping cost. Risk surcharge penalizes flow through "watch"-level suppliers. The centrality penalty discourages over-reliance on bottleneck sites identified in Stage 1. Unmet demand incurs a high penalty:

```python
transport_cost = sum(Operation.cost_per_unit * Operation.x_flow)

risk_cost = RISK_SURCHARGE * sum(op_watch.x_flow).where(
    op_watch.source_business(biz_watch),
    biz_watch.is_watch_level(),
)

centrality_cost = CENTRALITY_WEIGHT * sum(
    op_cent.x_flow * cent_val
).where(
    op_cent.output_site(site_cent),
    site_cent.centrality(cent_val),
)

unmet_cost = UNMET_PENALTY * sum(Demand.x_unmet)

problem.minimize(
    sum(model.union(transport_cost, risk_cost, centrality_cost, unmet_cost))
)
```

### Solve and run scenario analysis

The model is solved using the HiGHS solver with a two-minute time limit. The `solve_flow` function encapsulates the full formulation and accepts optional parameters to disable a site or block additional suppliers:

```python
problem.solve("highs", time_limit_sec=120)
```

After the baseline solve, two disruption scenarios are evaluated by re-solving with modified constraints: taking the highest-centrality site offline, and downgrading all "watch" suppliers to "avoid". The cost increase across scenarios quantifies the network's resilience to each type of disruption.

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
