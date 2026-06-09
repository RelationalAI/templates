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

# Supply Chain Resilience

## What this template is for

Supply chain networks must route goods from suppliers through factories and distribution centers to customers -- but not all routes carry equal risk. Unreliable suppliers, ML-predicted delays, and over-reliance on bottleneck sites can all disrupt fulfillment. This template shows how to combine multiple analytical signals into a single routing decision.

This template uses RelationalAI's **Graph** analysis, **Rules-based** classification, and **Prescriptive** optimization capabilities in a chained multi-reasoner workflow:

0. **Blast-radius pre-analysis** builds a directed Business graph from shipment data and traces every supplier each high-priority demand customer transitively depends on -- making the exposure footprint explicit before any optimization runs.
1. **Graph analysis** builds a site dependency graph from shipping operations and computes eigenvector centrality to identify critical warehouses and bridges between supply chain regions.
2. **Rules** classify suppliers by risk level (avoid / watch / reliable) using reliability scores and ML delay predictions, and flag escalated demand orders.
3. **Prescriptive optimization** solves a minimum-cost network flow that routes supply to meet demand. Graph centrality feeds a bottleneck penalty in the objective, and supplier risk flags feed hard constraints (no flow from "avoid" suppliers) and surcharges (extra cost for "watch" suppliers).
4. **Scenario analysis** re-solves with disruptions -- taking a critical site offline (+88.5% cost) and downgrading watch suppliers to avoid (+0.0% cost, because the optimizer had already routed around them) -- to quantify resilience costs.

Each stage enriches the shared ontology, and downstream stages consume those enrichments -- this is the **accretive ontology enrichment** pattern:

- **Stage 1 writes** `Site.centrality` (normalized eigenvector centrality) -- consumed by Stage 3's bottleneck penalty in the objective. High-centrality sites incur a `CENTRALITY_WEIGHT` surcharge per unit of flow.
- **Stage 2 writes** `Business.is_unreliable`, `Business.has_high_delay_risk`, `Business.is_watch_level` -- consumed by Stage 3 as hard constraints (avoid suppliers get zero flow) and cost surcharges (watch suppliers get `RISK_SURCHARGE` per unit of flow).
- **Stage 3 writes** `Operation.x_flow` and `Demand.x_unmet` decision variables, re-solved per scenario with modified constraints.

### Reasoner overview

| Stage | Reasoner | Reads from ontology | Writes to ontology | Role |
|-------|----------|---------------------|--------------------|------|
| 1 | Graph | Site, Operation (SHIP edges) | Site.centrality (normalized eigenvector) | 2 connected components. Top hubs: S004 TechAssembly (0.50), S006 West Coast DC (0.39), S003 PowerCell (0.37). Centrality feeds the bottleneck penalty in Stage 3. |
| 2 | Rules | Business.reliability_score, DelayPrediction | Business.is_unreliable, Business.has_high_delay_risk, Business.is_watch_level, Demand.is_escalated | 37 of 262 shipments late (14%). B003 classified as watch (reliability=0.81). 9 escalated demands. Watch/avoid flags feed constraints and surcharges in Stage 3. |
| 3 | Prescriptive | Site.centrality (Stage 1), Business.is_watch_level (Stage 2), Operation capacity/cost | Operation.x_flow, Demand.x_unmet | Baseline: $1,865 optimal cost, 8 active flows, all demand satisfied. |
| 3+ | Scenario Analysis | Same + exclude_site_id / block_business_ids | Re-solved x_flow, x_unmet per scenario | S004 offline: +88.5% cost ($3,515). Watch→Avoid: +0.0% ($1,865 -- watch suppliers were not on optimal routes). |

## Why this problem matters

Supply chain routing decisions are typically made with cost and capacity data alone. But cost-optimal routes can concentrate flow through a small number of critical hubs, creating fragility invisible to cost-minimization alone. When a critical warehouse goes offline -- due to weather, labor disruption, or infrastructure failure -- the network must absorb the disruption through costlier alternatives or unmet demand.

The multi-reasoner approach is necessary because structural risk (graph), supplier reliability (rules), and routing cost (optimization) are interdependent signals. A cost-optimal route through a high-centrality hub served by a watch-level supplier compounds risk in a way no single analysis reveals. Scenario analysis then quantifies the cost of disruption: taking the highest-centrality site offline increases total cost by 88.5%, while downgrading watch suppliers to avoid has no impact -- because the optimizer already routed around them. This asymmetry is the key insight.

### Key design patterns demonstrated

- **Accretive ontology enrichment** -- Stage 1's `Site.centrality` feeds Stage 3's objective; Stage 2's risk flags feed Stage 3's constraints and surcharges
- **Single model composition** -- all three reasoners (Graph, Rules, Prescriptive) attach to one `Model` instance, unlike templates that require a separate graph model
- **Reusable solve function** -- `solve_flow(label, exclude_site_id, block_business_ids)` encapsulates the full formulation, enabling scenario analysis by re-solving with modified constraints
- **Derived relationship for business-to-operation linkage** -- `Operation.source_business` is derived by matching `source_site` to `Business.site`, avoiding an explicit join table
- **Scenario analysis via re-solve** -- disruptions are modeled as constraint modifications (site offline = zero flow, supplier downgrade = block), not separate models

## Who this is for

- Supply chain and logistics managers evaluating network resilience
- Operations researchers exploring multi-reasoner pipelines in RelationalAI
- Developers learning how to chain graph, rules, and optimization in a single model

## What you'll build

- A site dependency graph with connected component detection and eigenvector centrality scoring
- Supplier risk classification rules combining reliability scores and ML delay predictions
- Continuous decision variables for flow on each operation and unmet demand slack
- Demand satisfaction, supplier blocking, and site-offline constraints
- A cost minimization objective that incorporates transport cost, risk surcharges, centrality-based bottleneck penalties, and unmet demand penalties
- Scenario analysis comparing baseline, site-offline, and supplier-downgrade disruptions

## What's included

- `supply_chain_resilience.py` -- Main script with three chained reasoning stages and scenario analysis
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
- RelationalAI Python SDK (`relationalai`) >= 1.0.14

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
   ======================================================================
   STAGE 1: Graph -- Network Criticality
   ======================================================================

   Connected components: 2

   Top critical sites (eigenvector centrality):
     S004 TechAssembly Factory (FACTORY, APAC): centrality=0.5016
     S006 West Coast DC (DISTRIBUTION_CENTER, AMERICAS): centrality=0.3895
     S003 PowerCell Facility (FACTORY, APAC): centrality=0.3688
     ...

   ======================================================================
   STAGE 2: Rules -- Supplier Risk Classification
   ======================================================================

   Late shipments: 37 of 262 (14%)
     B006: 7 late shipments
     B007: 5 late shipments
     ...

   Supplier risk classification:
     [!] B003 PowerCell Ltd: reliability=0.81, class=watch
     [ ] B005 GlobalBuild Inc: reliability=0.85, class=reliable
     [ ] B001 ChipTech Industries: reliability=0.95, class=reliable
     ...

   Escalated demands (HIGH priority): 9

   ======================================================================
   STAGE 3: Prescriptive -- Risk-Adjusted Network Flow
   ======================================================================

     [Baseline]
     Status: OPTIMAL
     Total cost: 1,865.00
     Active flows: 8
     All demand satisfied

   ======================================================================
   SCENARIO ANALYSIS
   ======================================================================

   SCENARIO COMPARISON
     Scenario                  Status                Cost        Unmet
     -----------------------------------------------------------------
     Baseline                  OPTIMAL            1,865.00          0
     Site S004 offline         OPTIMAL            3,515.00 (+88.5%)          0
     Watch->Avoid              OPTIMAL            1,865.00 (0.0%)          0
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

- **Adjust risk thresholds** via `RELIABILITY_THRESHOLD` and `DELAY_PROB_THRESHOLD` to control which suppliers are flagged as unreliable or high-delay-risk.
- **Change the prediction quarter** via `PREDICTION_QUARTER` to use different ML delay predictions.
- **Tune the centrality weight** via `CENTRALITY_WEIGHT` to control how strongly bottleneck penalties influence routing.
- **Adjust the risk surcharge** via `RISK_SURCHARGE` to increase or decrease the cost penalty for "watch" suppliers.
- **Change the unmet demand penalty** via `UNMET_PENALTY` to control the trade-off between routing cost and demand fulfillment.
- **Add new scenarios** by calling `solve_flow()` with different `exclude_site_id` or `block_business_ids` parameters.
- **Extend the data** by adding rows to the CSV files -- more sites, operations, or demand orders will scale the network flow problem.

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
