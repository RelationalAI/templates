---
title: "Retail Planning"
description: "Predict article sales and customer churn with GNNs, then optimize markdown pricing and inventory planning to maximize revenue and minimize costs."
featured: true
experience_level: advanced
industry: "Retail"
reasoning_types:
  - Predictive
  - Prescriptive
tags:
  - GNN
  - Predict-then-Optimize
  - Markdown Optimization
  - Demand Planning
  - Multi-Reasoner
  - Retail
---

## What this template is for

Retailers face interconnected decisions: which items will sell, which customers are at risk of leaving, what discounts to offer, and how much inventory to stock. Traditionally these are solved in isolation -- demand forecasting in one silo, pricing optimization in another, supply planning in a third. This template shows how to unify them in a single predict-then-optimize pipeline using RelationalAI.

Three GNN models learn directly from the H&M transaction graph: one predicts article-level sales, another predicts customer churn, and a third predicts which articles each customer will purchase. All three predictions are aggregated into adjusted demand estimates -- churn risk discounts demand while purchase propensity uplifts it -- that feed two downstream optimization problems: a markdown optimizer that chooses weekly discount schedules to maximize revenue, and a demand planner that sets production quantities to minimize cost. The entire pipeline runs on one semantic model, with GNN outputs flowing seamlessly into prescriptive constraints and objectives.

## Who this is for

- Data scientists building end-to-end ML-to-optimization pipelines
- Retail analysts combining demand forecasting with pricing and inventory decisions
- ML engineers exploring GNN-based prediction on relational/graph data
- Operations researchers interested in predict-then-optimize patterns

Assumes familiarity with Python, basic ML concepts (classification, regression, link prediction), and linear programming.

## What you'll build

- Three GNN predictive models on the H&M knowledge graph (item-sales, user-churn, user-item-purchase)
- A bridge layer that aggregates all three GNN outputs into adjusted demand per article
- A markdown optimization (MILP) that selects discount schedules to maximize revenue + salvage
- A demand/inventory planning (LP) that minimizes production, holding, and unmet demand costs
- A unified pipeline where GNN predictions replace static parameters in both optimizers

## What's included

- **Model**: Three GNN tasks on the H&M knowledge graph (Customer, Article, Transaction), two prescriptive problems consuming their output
- **Runner**: `retail_planning.py` -- single script executing the full pipeline
- **Sample data**: CSV files for optimization parameters (discounts, weeks, article inventory, production capacity)
- **Outputs**: GNN evaluation metrics, optimal discount schedules, production plans, cost/revenue summaries

## Prerequisites

### Access

- A Snowflake account with the RAI Native App installed
- H&M dataset loaded in Snowflake (from [RelBench](https://relbench.stanford.edu/datasets/rel-hm/)):
  - Core tables: `CUSTOMERS`, `ARTICLES`, `TRANSACTIONS`
  - Task tables: churn (`TRAIN`, `VAL`, `TEST`), sales (`TRAIN`, `VAL`, `TEST`), purchase (`TRAIN_EXPLODED`, `VALIDATION_EXPLODED`, `TEST_EXPLODED`)
- A GPU-enabled engine for GNN training

### Tools

- Python >= 3.10
- RelationalAI SDK (`relationalai>=1.0`)

## Quickstart

1. Download ZIP:
   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/retail_planning.zip
   unzip retail_planning.zip
   cd retail_planning
   ```
   > [!TIP]
   > You can also download the template ZIP using the "Download ZIP" button at the top of this page.

2. Create venv:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   ```

3. Install:
   ```bash
   python -m pip install .
   ```

4. Configure:
   ```bash
   rai init
   ```

5. Update Snowflake settings in `retail_planning.py`:
   ```python
   DATABASE = "HM_DB"           # your Snowflake database
   SCHEMA = "HM_SCHEMA"         # schema with core H&M tables
   TASK_CHURN_SCHEMA = "HM_CHURN"
   TASK_SALES_SCHEMA = "HM_SALES"
   TASK_PURCHASE_SCHEMA = "HM_PURCHASE"
   ```

6. Run:
   ```bash
   python retail_planning.py
   ```

7. Expected output (abbreviated):
   ```text
   === Item Sales Predictions (sample) ===
    article_id  predicted_value
           100            12.45
          5000             8.73
    ...

   === Markdown: Selected Discounts by Article-Week ===
    article  week  discount_pct
    Rib Top     1           0.0
    Rib Top     2          10.0
    ...

   Pipeline Complete
   Predictive: 3 GNN models trained (item-sales, user-churn, user-item-purchase)
   Prescriptive A (Markdown): discount schedule optimized for revenue
   Prescriptive B (Demand Planning): production plan optimized for cost
   ```

## Template structure

```text
.
├── README.md                    # this file
├── pyproject.toml               # dependencies
├── retail_planning.py           # main runner (full pipeline)
└── data/
    ├── discounts.csv            # discount levels with demand lifts
    ├── weeks.csv                # planning weeks with seasonal multipliers
    ├── articles_inventory.csv   # article pricing/inventory for markdown
    └── production_capacity.csv  # production caps/costs for demand planning
```

**Start here**: `retail_planning.py` runs end-to-end.

## Sample data

The H&M core data (customers, articles, transactions) comes from Snowflake, sourced from the [RelBench rel-hm dataset](https://relbench.stanford.edu/datasets/rel-hm/). The local CSV files provide optimization parameters:

- **discounts.csv** -- Five discount tiers (0% to 50%) with demand lift multipliers
- **weeks.csv** -- Four-week planning horizon with seasonal demand multipliers
- **articles_inventory.csv** -- 12 articles with initial price, cost, inventory, and salvage rate
- **production_capacity.csv** -- Per-article production limits, costs, and holding costs

## Model overview

### Key entities

- **Customer** (`customer_id`): H&M shoppers with demographics (age, club status, postal code)
- **Article** (`article_id`): Products with rich metadata (category hierarchy, color, department, description)
- **Transaction**: Purchase events linking customers to articles with price and date

### Pipeline stages

```text
Snowflake tables
  → GNN item-sales (regression on Article)
  → GNN user-churn (classification on Customer)
  → GNN user-item-purchase (link prediction Customer→Article)
  → Bridge: adjusted demand per article (churn + purchase propensity)
  → Markdown optimization (MILP, maximize revenue)
  → Demand/inventory planning (LP, minimize cost)
```

### Concepts

**OptArticle** -- Articles in the optimizer's scope, linking GNN predictions to pricing/inventory data.

| Property | Type | Notes |
|---|---|---|
| `opt_article_id` | integer | Identifying; matches `article_id` |
| `name` | string | Human-readable product name |
| `initial_price` | float | Starting price before discounts |
| `cost` | float | Unit cost |
| `initial_inventory` | integer | Available stock |
| `salvage_rate` | float | Fraction of price recovered for unsold units |
| `predicted_sales` | float | From item-sales GNN |
| `avg_buyer_churn` | float | Average churn probability of recent buyers |
| `avg_purchase_score` | float | Average purchase prediction score across predicted buyers |
| `adjusted_demand` | float | `predicted_sales * (1 - churn_weight * churn) * (1 + purchase_weight * score)` |

**Discount** -- Markdown tiers with demand response.

| Property | Type | Notes |
|---|---|---|
| `level` | integer | Identifying; ordered tier (0 = no discount) |
| `discount_pct` | float | Percentage off initial price |
| `demand_lift` | float | Multiplier on base demand |

**Week** -- Planning periods with seasonality.

| Property | Type | Notes |
|---|---|---|
| `num` | integer | Identifying; week number |
| `demand_multiplier` | float | Seasonal adjustment factor |

**ProdCapacity** -- Per-article production parameters for demand planning.

| Property | Type | Notes |
|---|---|---|
| `pc_article_id` | integer | Identifying; matches `article_id` |
| `max_production_per_week` | integer | Production cap |
| `production_cost` | float | Cost per unit produced |
| `holding_cost_per_week` | float | Cost per unit in inventory per week |
| `pc_initial_inventory` | float | Starting stock for demand planner |

## How it works

### 1. Train GNN models on the H&M knowledge graph

Three separate GNN models are trained using the Graph/Relationship/PropertyTransformer API:

```python
# Item-sales regression
SalesTrain = Relationship(f"{Article} at {Any:timestamp} has {Any:target}")
sales_gnn = GNN(
    graph=sales_graph, pt=sales_pt,
    train=SalesTrain, validation=SalesVal,
    task_type="regression", eval_metric="rmse", ...
)
sales_gnn.fit()
Article.sales_predictions = sales_gnn.predictions(domain=SalesTest)
```

Each GNN learns from the same knowledge graph (Customer-Transaction-Article) but targets different labels: article sales (regression), customer churn (binary classification), and customer-article purchase links (link prediction).

### 2. Bridge: aggregate predictions into optimizer inputs

Predicted sales per article come directly from the item-sales GNN. Churn risk is aggregated per article by averaging the churn probability of each article's recent buyers. Purchase propensity is derived from the link prediction GNN by averaging prediction scores per article. All three signals combine into a single demand estimate:

```python
model.define(OptArticle.adjusted_demand(
    OptArticle.predicted_sales
    * (1 - CHURN_DISCOUNT_WEIGHT * OptArticle.avg_buyer_churn)
    * (1 + PURCHASE_PROPENSITY_WEIGHT * OptArticle.avg_purchase_score)
))
```

Articles bought primarily by high-churn-risk customers get reduced demand, while articles with high purchase propensity get an uplift.

### 3. Markdown optimization (maximize revenue)

A mixed-integer program selects one discount level per article per week. Constraints enforce a price ladder (discounts only increase) and inventory limits. The demand bound uses GNN-predicted demand instead of static estimates:

```python
p.satisfy(model.where(...).require(
    sales_ref <= OptArticle.adjusted_demand
    * Discount_ref.demand_lift * Week_ref.demand_multiplier * selection_ref
))
p.maximize(revenue + salvage)
```

### 4. Demand/inventory planning (minimize cost)

A linear program decides production quantities per article per week. Inventory flow conservation tracks stock levels. The objective balances production cost, holding cost, and a penalty for unmet demand:

```python
dp.satisfy(model.where(...).require(
    inv_curr == inv_prev + flow_prod_ref
    - OptArticle.adjusted_demand * flow_week_ref.demand_multiplier
    + flow_unmet_ref
))
dp.minimize(prod_cost_total + hold_cost_total + unmet_cost_total)
```

## Customize this template

### Use your own data

- Replace the Snowflake table references at the top of the script (`DATABASE`, `SCHEMA`, etc.) to point to your H&M dataset location.
- Edit the CSV files in `data/` to change the article subset, pricing, inventory levels, discount tiers, or planning horizon.
- The `article_id` values in the CSVs must match real article IDs in your Snowflake data.

### Tune parameters

- **GNN hyperparameters**: `n_epochs`, `lr`, `train_batch_size`, `head_layers` in each GNN constructor. More epochs improve accuracy but increase training time.
- **Churn discount weight** (`CHURN_DISCOUNT_WEIGHT`): controls how much churn risk reduces demand. 0 = ignore churn, 1 = full reduction.
- **Purchase propensity weight** (`PURCHASE_PROPENSITY_WEIGHT`): controls how much predicted purchase demand uplifts demand. 0 = ignore, higher = stronger uplift.
- **Unmet demand penalty** (`UNMET_PENALTY`): higher values force the demand planner to fulfill more demand at the cost of higher production.
- **Discount tiers and demand lifts**: edit `discounts.csv` for finer or coarser pricing granularity.

### Extend the model

- **Add minimum-margin constraints**: ensure discounted prices always exceed cost (`OptArticle.initial_price * (1 - discount_pct/100) >= OptArticle.cost`).
- **Category-level budgets**: group articles by department and limit total discount exposure per category.
- **Multi-site planning**: extend `ProdCapacity` with a site dimension and add cross-site transfer variables.
- **Scenario analysis**: wrap the demand planner in a loop over different planning horizons (see `demand_planning_temporal` template for the pattern).

## Troubleshooting

<details>
<summary>GNN training fails or is very slow</summary>

- Ensure a GPU-enabled engine is available. GNN training on CPU is significantly slower.
- Reduce `n_epochs` or `train_batch_size` for faster iteration during development.
- Check that the task tables (TRAIN, VAL, TEST) are populated and the foreign keys match the core tables.
</details>

<details>
<summary>Markdown optimization is infeasible</summary>

- Verify that `discounts.csv` includes a 0% discount level (the model needs a feasible starting point).
- Check that initial inventory in `articles_inventory.csv` is sufficient for at least one week of base demand.
- Ensure the article IDs in CSVs match articles that have GNN predictions (i.e., appear in the sales test set).
</details>

<details>
<summary>Demand planner shows large unmet demand</summary>

- Increase `max_production_per_week` in `production_capacity.csv` or lower the demand by adjusting `CHURN_DISCOUNT_WEIGHT`.
- Reduce `UNMET_PENALTY` if you want the optimizer to tolerate some shortfall rather than over-producing.
</details>

<details>
<summary>Predictions are all NaN or empty</summary>

- Ensure the GNN training completed successfully (check for fit() errors).
- Verify that the test set tables contain rows and that foreign keys link correctly to the core entity tables.
- Try increasing `n_epochs` -- very few epochs may not converge.
</details>

<details>
<summary>rai init fails or connection errors</summary>

Ensure your Snowflake credentials are configured correctly and that the RAI Native App is installed on your account. Run `rai init` again and verify the connection settings.
</details>
