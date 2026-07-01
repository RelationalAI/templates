# Runbook: Retail Planning — Multi-Reasoner Walkthrough

A retail planner wants demand-aware pricing and production plans: first learn how each article actually sells, then use that learned demand to set markdowns and to plan production and inventory. This chain trains a sales-regression graph neural network (GNN) on transaction history, turns its predictions into per-article demand, and feeds that demand into two optimizers — a markdown schedule that maximizes revenue plus salvage, and a demand/inventory plan that minimizes production, holding, and shortfall cost. Predict-then-optimize across a predictive and two prescriptive stages.

## The chain

```
An H&M retail subset — 5,000 articles, 10,000 customers, ~9,600 transactions — plus a
12-article planning set with inventory, 4 weeks, and 5 discount tiers. The chain learns
per-article demand with a GNN, then runs two optimizers on it.

  ─────────────────────────────────────────────────────────────────
  STAGE 1  Predictive   ──►  Article demand (from sales GNN)
                  (GNN)      Sales-regression GNN over the customer-article
                             transaction graph; baseline RMSE ~0.0212.
                             Adjusted demand aggregated per article.
  ─────────────────────────────────────────────────────────────────
  STAGE 2  Prescriptive ──►  Markdown schedule (discount per article-week)
                             Maximize revenue + salvage. OPTIMAL, $62,038.94.
  ─────────────────────────────────────────────────────────────────
  STAGE 3  Prescriptive ──►  Production / inventory plan
                             Minimize production + holding + unmet penalty.
                             OPTIMAL, $8,761.30.
  ─────────────────────────────────────────────────────────────────
```

## Workflow

> **How to use this walkthrough.** Each section below is a Prompt that an analyst pastes into a fresh agent session loaded with the named `/rai-*` skill. Prompts are designed to run **in order, in a single session** — every step relies on enrichments the previous steps wrote back to the shared ontology, so the agent inherits accumulated model state across prompts. This template trains a GNN on the RelationalAI engine.

### 1. Build ontology

**Prompt**

```
/rai-build-starter-ontology Build an ontology from the bundled H&M subset in data/hm_mini/: articles (products), customers, and transactions (a customer bought an article), with train / validation / test sales splits for the demand model. Also load the planning inputs: the planning articles' inventory, the weeks, and the discount tiers. Model a transaction as a relationship linking a customer and an article.
```

**Response**

Loads `Article` (5,000), `Customer` (10,000), and `Transaction` (~9,601, linking customer and article) with sales splits (7,648 train / 1,147 validation / 806 test), plus the planning inputs — a 12-article inventory set, 4 `Week`s, and 5 `Discount` tiers for the optimizers.

### 2. Examine ontology

**Prompt**

```
/rai-querying What concepts and relationships does the ontology have, and how many rows are in each?
```

**Response**

`Article` (5,000), `Customer` (10,000), `Transaction` (~9,601) with train/val/test sales splits, plus the planning layer — 12 articles with inventory, 4 weeks, 5 discount tiers. The transactions feed the demand model; the small planning set feeds the optimizers.

### 3. Discover reasoner questions

**Prompt**

```
/rai-discovery We want to learn per-article demand from sales history, then use it to set markdowns and to plan production and inventory. How should we break this down?
```

**Response**

Routes to a predictive step (a sales-regression GNN producing per-article demand) feeding two prescriptive steps — a markdown optimizer and a demand/inventory planner — that both consume the learned demand.

### 4. Learn per-article demand

**Prompt**

```
/rai-predictive-modeling + /rai-predictive-training Train a sales-regression graph neural network over the customer-article transaction graph to predict article sales, training on the sales splits. Aggregate the predictions into an adjusted demand per article for the planning set, and write it back to the ontology.
```

**Response**

A sales-regression GNN trains over the transaction graph (beating the predict-the-mean baseline RMSE of ~0.0212) and its predictions are aggregated into an adjusted demand per planning article, written back for the optimizers to read.

### 5. Optimize markdowns

**Prompt**

```
/rai-prescriptive-problem-formulation + /rai-prescriptive-solver-management Using the learned demand, choose a discount tier for each planning article in each week to maximize total revenue plus salvage value of leftover stock, respecting inventory. Persist the chosen discounts.
```

**Response**

OPTIMAL (HiGHS), total revenue plus salvage **$62,038.94**. The markdown decision picks a discount per article-week against the GNN-derived demand and is written back. (The dollar figure tracks the learned demand, so it shifts with model training; the OPTIMAL plan and its structure are stable.)

### 6. Plan production and inventory

**Prompt**

```
/rai-prescriptive-problem-formulation + /rai-prescriptive-solver-management Using the learned demand, plan weekly production and inventory for the planning articles to minimize total cost — production plus holding plus an unmet-demand penalty — within production capacity. Persist the plan.
```

**Response**

OPTIMAL (HiGHS), total cost **$8,761.30** (production + holding + unmet penalty). The production/inventory plan meets the GNN-derived demand within capacity at least cost and is written back.

### 7. Read the plans

**Prompt**

```
/rai-prescriptive-results-interpretation What do the two plans recommend, and how does the learned demand drive them?

```

**Response**

The markdown plan sets per-article-week discounts that lift revenue to ~$62,039 (sales plus salvage), while the production plan meets demand for ~$8,761 of production, holding, and shortfall cost. Both are driven by the same GNN-learned demand — higher predicted demand pulls articles toward shallower markdowns and more production — so improving the demand model directly reshapes both plans.

## Data

Bundled CSVs in `data/hm_mini/` (articles, customers, transactions, sales splits) plus `data/` planning inputs (article inventory, weeks, discount tiers). `retail_planning_local.py` is the primary runnable (real GNN on the bundled subset, both optimizers); `retail_planning.py` is the Snowflake-tables reference. Full chain in `retail_planning_local.py`.
