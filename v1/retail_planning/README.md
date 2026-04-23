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
- **Runners**: `retail_planning_local.py` (zero-setup demo on bundled HM_MINI CSVs) and `retail_planning.py` (full pipeline against HM_PYREL in Snowflake)
- **Sample data**: optimizer-parameter CSVs (discounts, weeks, article inventory, production capacity), plus `data/hm_mini/` — a bundled H&M subset (~10K customers / 5K articles / 9.6K transactions) with sales task splits so the local runner can train a real GNN
- **Outputs**: GNN evaluation metrics, optimal discount schedules, production plans, cost/revenue summaries

## Prerequisites

### Access

**For the local runner (`retail_planning_local.py`):** any Snowflake account
with the RAI Native App -- no H&M Snowflake data required, no GPU required.
The bundled `data/hm_mini/` CSVs are loaded via `model.data()`, and the
sales-regression GNN trains on CPU in a few minutes. Start here.

**For the full pipeline (`retail_planning.py`):**

- A Snowflake account with the RAI Native App installed
- The H&M Personalized Fashion Recommendations dataset
  ([Kaggle](https://www.kaggle.com/competitions/h-and-m-personalized-fashion-recommendations/data))
  loaded into Snowflake, plus RelBench-style task splits
  ([rel-hm](https://relbench.stanford.edu/datasets/rel-hm/)):
  - Core tables: `CUSTOMERS`, `ARTICLES`, `TRANSACTIONS`
  - Task tables: churn (`TRAIN`, `VAL`, `TEST`), sales (`TRAIN`, `VAL`, `TEST`),
    purchase (`TRAIN_EXPLODED`, `VALIDATION_EXPLODED`, `TEST_EXPLODED`)
- A GPU-enabled engine for GNN training

### Tools

- Python >= 3.10
- RelationalAI Python SDK (`relationalai`) >= 1.0.14

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

5. (Option B only) Update Snowflake settings in `retail_planning.py` to point at
   your loaded H&M database. Skip this step if you're running
   `retail_planning_local.py` on the bundled CSVs.
   ```python
   DATABASE = "HM_DB"           # your Snowflake database
   SCHEMA = "HM_SCHEMA"         # schema with core H&M tables
   TASK_CHURN_SCHEMA = "HM_CHURN"
   TASK_SALES_SCHEMA = "HM_SALES"
   TASK_PURCHASE_SCHEMA = "HM_PURCHASE"
   ```

6. Run:
   ```bash
   # Option A: local demo. Trains a real sales-regression GNN on the bundled
   # HM_MINI CSV subset (CPU, ~5-10 min), then runs both optimizers. No
   # external data or GPU required.
   python retail_planning_local.py

   # Option B: full pipeline. Trains all 3 GNNs (sales, churn, purchase) on
   # the full Kaggle H&M + RelBench data in Snowflake, then runs both
   # optimizers. Requires HM_PYREL loaded in Snowflake and a GPU-enabled
   # RAI engine.
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
├── retail_planning.py           # full pipeline (needs HM_PYREL in Snowflake + GPU)
├── retail_planning_local.py     # local demo: real GNN on HM_MINI CSVs + optimizers
└── data/
    ├── discounts.csv            # discount levels with demand lifts
    ├── weeks.csv                # planning weeks with seasonal multipliers
    ├── articles_inventory.csv   # article pricing/inventory (full-pipeline scope)
    ├── production_capacity.csv  # production caps/costs (full-pipeline scope)
    └── hm_mini/                 # HM_MINI subset used by retail_planning_local.py
        ├── customers.csv        #   10K customers from H&M Kaggle
        ├── articles.csv         #   5K articles
        ├── transactions.csv     #   9.6K transactions
        ├── train_sales.csv      #   RelBench sales task: 7.6K train rows
        ├── val_sales.csv        #   1.1K val rows
        ├── test_sales.csv       #   806 test rows
        ├── articles_inventory.csv     # 12-article optimizer scope (real HM_MINI IDs)
        └── production_capacity.csv    # matching production params
```

**Start here**: `retail_planning_local.py` for a zero-setup demo (CPU only),
or `retail_planning.py` for the full pipeline against HM_PYREL.

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
Customer / Article / Transaction data (Snowflake tables or bundled CSVs)
  → GNN item-sales (regression on Article)
  → GNN user-churn (classification on Customer)     [full pipeline only]
  → GNN user-item-purchase (link prediction)        [full pipeline only]
  → Bridge: adjusted demand per article
  → Markdown optimization (MILP, maximize revenue)
  → Demand/inventory planning (LP, minimize cost)
```

`retail_planning_local.py` trains only the sales GNN (the most demonstrative
task) on the bundled HM_MINI CSVs — HM_MINI does not ship churn or purchase
splits. Churn and purchase are omitted from the local aggregation step.
`retail_planning.py` runs all three GNNs against the full HM_PYREL data.

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

Three separate GNN models are trained using the Graph / Relationship / PropertyTransformer API. All three share the same graph and feature configuration; only the task relationships and task-type differ:

```python
# Item-sales regression
SalesTrain = Relationship(f"{Article} at {Any:timestamp} has {Any:sales}")
sales_gnn = GNN(
    exp_database=GNN_EXP_DATABASE, exp_schema=GNN_EXP_SCHEMA,
    graph=graph, property_transformer=pt,
    train=SalesTrain, validation=SalesVal,
    task_type="regression", eval_metric="rmse",
    has_time_column=True, stream_logs=STREAM_LOGS, seed=SEED,
    device="cuda", n_epochs=20, train_batch_size=256, lr=0.005, head_layers=2,
    temporal_strategy="last", max_iters=500,
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
problem.satisfy(model.where(...).require(
    sales_ref <= OptArticle.adjusted_demand
    * Discount_ref.demand_lift * Week_ref.demand_multiplier * selection_ref
))
problem.maximize(revenue + salvage)
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
- For regression (sales): the rai-predictive-training skill flags that 5 epochs
  is a smoke test; regression usually needs 20–50 epochs. If val-RMSE is at or
  above `stddev(target)`, the model collapsed to the mean — increase `n_epochs`
  or reduce text features.
</details>

<details>
<summary><code>has_time_column=True</code> fails validation</summary>

Known limitation flagged in the rai-predictive-training skill: when the concept
carrying `time_col` (here, `Transaction`) is used only as an edge intermediary,
validation can fail with "no time column defined in data tables." Workaround:
set `has_time_column=False` on the affected GNN and remove the `"at"` clause
from its Relationship templates until the GNN team resolves this.
</details>

<details>
<summary>Sales regression R² is low or negative</summary>

R² < 0 early in training is normal — it means the model is doing worse than
predicting the target mean. See the "Sales target profile (train split)" block
printed before training: if val-RMSE prints below the target's stddev, the
GNN is learning signal. If it plateaus at or above the stddev, increase
`n_epochs` or re-check the PropertyTransformer.
</details>

<details>
<summary>Spinner floods the log when running in CI / non-TTY</summary>

Set `STREAM_LOGS = False` at the top of the script (the default). The GNN
continues training server-side; only the client-side log stream is suppressed.
</details>


<details>
<summary>rai init fails or connection errors</summary>

Ensure your Snowflake credentials are configured correctly and that the RAI Native App is installed on your account. Run `rai init` again and verify the connection settings.
</details>
