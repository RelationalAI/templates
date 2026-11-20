---
title: "Retail Planning"
description: "Predict article sales and customer churn with graph neural networks (GNNs), then optimize markdown pricing and inventory planning to maximize revenue and minimize costs."
featured: true
experience_level: advanced
industry: "Retail & Consumer"
reasoning_types:
  - Predictive
  - Prescriptive
tags:
  - Graph Neural Network (GNN)
  - Predict-then-Optimize
  - Markdown Optimization
  - Demand Planning
  - Multi-Reasoner
  - Retail
---

## What this template is for

Retailers face interconnected decisions: which items will sell, what discounts to offer, and how much inventory to stock. Traditionally these are solved in isolation -- demand forecasting in one silo, pricing optimization in another, supply planning a third. Solved separately, they pull against each other: a markdown plan that ignores the demand forecast, or an inventory plan that ignores the markdowns, leaves revenue on the table. This template unifies them so predicted demand flows straight into the pricing and inventory decisions that depend on it.

**A graph neural network predicts article demand, and those predictions become the parameters of a markdown-pricing and inventory optimization** -- a single predict-then-optimize pipeline on one deployed model with one shared ontology, so the optimizers price and plan against learned demand rather than static estimates.

The bundled H&M dataset is the worked example; the structure -- graph concepts, then GNN tasks, then an aggregation bridge, then prescriptive constraints -- is what carries over to your own retail, pricing, or demand-planning data (see the *Pipeline stages* diagram under *Model overview*).

## Who this is for

- Data scientists building end-to-end ML-to-optimization pipelines
- Retail analysts combining demand forecasting with pricing and inventory decisions
- ML engineers exploring GNN-based prediction on relational/graph data
- Operations researchers interested in predict-then-optimize patterns

Assumes familiarity with Python, basic ML concepts (classification, regression, link prediction), and linear programming.

## What you'll build

- A sales-regression graph neural network (GNN) on the H&M knowledge graph (Customer, Article, Transaction) that predicts per-transaction sales, trained on the predictive reasoner
- A bridge that aggregates the GNN's predicted sales into adjusted demand per planning article
- A markdown optimization (MILP) that selects discount schedules to maximize revenue + salvage
- A demand/inventory planning (LP) that minimizes production, holding, and unmet demand costs
- A deployed model whose GNN predictions replace static parameters in both optimizers, with every result queryable from the deployed ontology

## What's included

- `model/` -- the deployed model: `schema.py` declares the concepts and the sales task relationships, `source.py` loads the bundled CSVs, `reasoning.py` states the graph, the GNN, the demand bridge, and the markdown and planning problems with the rules that publish their solutions
- `train.py` -- trains the sales GNN over the deployed splits and registers its version
- `queries/retail_report.py` -- prints the sales target profile, the adjusted demand, both solve results, and the selected discounts from the deployed model
- `retail_planning.py` -- a separate script-mode reference for the full three-GNN pipeline (sales, churn, purchase) against H&M tables in Snowflake. It is not part of the deployed model, and the Quickstart does not run it
- `runbook.md` -- a paste-testable walkthrough that reproduces the template step by step with the RAI skills
- Sample data:
  - `data/hm_mini/` -- bundled H&M subset (~10K customers / 5K articles / 9.6K transactions) with sales task splits, the 12-article planning inventory, and its production capacity
  - `data/discounts.csv`, `data/weeks.csv` -- the discount tiers and planning weeks
- Outputs: the adjusted demand, the optimal discount schedule, and the cost and revenue summaries

## Prerequisites

### Access

- A Snowflake account that has the RAI Native App installed.
- The one-time model deployment setup on that account, done by an account administrator: follow [Set up model deployment](https://private.relational.ai/early-access/model-deploy-setup) through **Governed setup**, **PAT authentication**, and steps 1-2 of **Additional setup for the prescriptive reasoner** (the Quickstart covers this template's own schemas). It gives you a model role, a programmatic access token (PAT) stored as a secret, an external access integration, a PAT user, and a warehouse.
- A Snowflake user that holds the model role.
- The predictive reasoner's compute pool added to the compute-pool network rule that admits the PAT user (the rule from the prescriptive reasoner setup), because the deployed model runs this template's GNN training, scoring, and registration jobs as the PAT user. Check the pool names in your account with `SHOW COMPUTE POOLS` (for example `RELATIONAL_AI_HIGHMEM_X64_S_ML`), and have an administrator run `ALTER NETWORK RULE <PAT_POOL_NETWORK_RULE> SET VALUE_LIST = (...)`, listing the pools already in the rule plus the predictive one.

Those jobs need grants for the PAT user's role (`<PAT_ROLE>`) and matching caller grants for the RAI Native App. Once the Quickstart's first step has created this template's schemas, have an administrator run:

```sql
GRANT USAGE ON WAREHOUSE <PAT_WAREHOUSE> TO ROLE <PAT_ROLE>;
GRANT USAGE ON DATABASE <DB> TO ROLE <PAT_ROLE>;
GRANT USAGE ON SCHEMA <DB>.RETAIL_PLANNING_META TO ROLE <PAT_ROLE>;
GRANT SELECT ON ALL VIEWS IN SCHEMA <DB>.RETAIL_PLANNING_META TO ROLE <PAT_ROLE>;
GRANT SELECT ON FUTURE VIEWS IN SCHEMA <DB>.RETAIL_PLANNING_META TO ROLE <PAT_ROLE>;
GRANT USAGE, CREATE TABLE, CREATE STAGE, CREATE FILE FORMAT ON SCHEMA <DB>.RETAIL_PLANNING TO ROLE <PAT_ROLE>;
GRANT CREATE EXPERIMENT, CREATE MODEL ON SCHEMA <DB>.RETAIL_PLANNING TO ROLE <PAT_ROLE>;
GRANT CALLER USAGE, CREATE TABLE, CREATE STAGE, CREATE FILE FORMAT ON SCHEMA <DB>.RETAIL_PLANNING TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT, INSERT ON ALL TABLES IN SCHEMA <DB>.RETAIL_PLANNING TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER READ, WRITE ON ALL STAGES IN SCHEMA <DB>.RETAIL_PLANNING TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER USAGE ON ALL FILE FORMATS IN SCHEMA <DB>.RETAIL_PLANNING TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER CREATE EXPERIMENT, CREATE MODEL ON SCHEMA <DB>.RETAIL_PLANNING TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER USAGE, MODIFY ON ALL EXPERIMENTS IN SCHEMA <DB>.RETAIL_PLANNING TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER OWNERSHIP ON ALL MODELS IN SCHEMA <DB>.RETAIL_PLANNING TO APPLICATION <RAI_APP_NAME>;
```

The bundled CSVs ship with the template; there is no source-table setup and no GPU requirement. The GNN trains on the predictive reasoner and stores its experiments and registered versions in the template's public schema.

### Tools

- Python >= 3.10.
- The `relationalai[gnn]` SDK and the `rai` CLI (installed by the Quickstart's `python -m pip install .`).

## Quickstart

Before you start, install Python 3.10 or later and complete the access prerequisites above: a Snowflake account with the RAI Native App, the one-time model deployment setup, and a Snowflake user that holds the model role.

Before the first deploy, create this template's two schemas as the model role, and have an administrator grant the RAI Native App access to them. The GNN keeps its experiments and registered versions in the public schema, and the internal schema holds only this model's objects, so the grants cover all of it, including the solver's result tables that the deploy creates:

```sql
-- as the model role
CREATE SCHEMA IF NOT EXISTS <DB>.RETAIL_PLANNING;
CREATE SCHEMA IF NOT EXISTS <DB>.RETAIL_PLANNING_META;

-- as an administrator
GRANT USAGE ON DATABASE <DB> TO APPLICATION <RAI_APP_NAME>;
GRANT USAGE ON SCHEMA <DB>.RETAIL_PLANNING TO APPLICATION <RAI_APP_NAME>;
GRANT CREATE EXPERIMENT ON SCHEMA <DB>.RETAIL_PLANNING TO APPLICATION <RAI_APP_NAME>;
GRANT CREATE MODEL ON SCHEMA <DB>.RETAIL_PLANNING TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON DATABASE <DB> TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON SCHEMA <DB>.RETAIL_PLANNING_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON WAREHOUSE <PAT_WAREHOUSE> TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL TABLES IN SCHEMA <DB>.RETAIL_PLANNING_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL DYNAMIC TABLES IN SCHEMA <DB>.RETAIL_PLANNING_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL VIEWS IN SCHEMA <DB>.RETAIL_PLANNING_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER INSERT, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA <DB>.RETAIL_PLANNING_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER CREATE TABLE, CREATE STAGE ON SCHEMA <DB>.RETAIL_PLANNING_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER READ, WRITE ON ALL STAGES IN SCHEMA <DB>.RETAIL_PLANNING_META TO APPLICATION <RAI_APP_NAME>;

```

Use this sequence to deploy the model, train the GNN, and query the markdown and production plans:

1. **Download the template**

   [Download the ZIP](https://docs.relational.ai/templates/zips/v1/retail_planning.zip), unzip it, and enter the template directory:

   ```bash
   unzip retail_planning.zip
   cd retail_planning
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

   Set the connection `role` to the model role, then add the predictive and prescriptive reasoners, the registered version the GNN predicts with, and a `deployment` section. Give each template its own schema pair so two deployed templates never share one:

   ```yaml
   reasoners:
     predictive:
       name: retail_sales_gnn          # created on first use if it doesn't exist
       gnns:
         sales_regression:             # the GNN's name in model/reasoning.py
           registry: <DB>.RETAIL_PLANNING
           model: SALES_REGRESSION
           version: V1                  # train.py registers this version
     prescriptive:
       name: retail_planning_solver      # created on first deploy if it doesn't exist
   deployment:
     role: <MODEL_ROLE>
     public_schema: <DB>.RETAIL_PLANNING          # published views and tables
     identity:
       internal_schema: <DB>.RETAIL_PLANNING_META # solver inputs, results, refresh procedures
     schedules:
       standard:
         interval_s: 0                  # refresh only on deploy or on demand
     schedule: standard
     pat_secret: <PAT_SECRET>           # these four come from the setup page
     pat_eai: <PAT_EAI>
     pat_user: <PAT_USER>
     pat_warehouse: <PAT_WAREHOUSE>
   ```

5. **Deploy the model**

   Deploy the model in `model/` to the schemas in `raiconfig.yaml`:

   ```bash
   rai models deploy --path model
   ```

   The deploy creates the reasoners and the public schema named in `raiconfig.yaml` if they don't exist and waits for the model's first refresh, which loads the data and sets up both problems. No version of the GNN is registered yet, so this refresh makes no sales predictions and the plans have no demand to act on.

6. **Train the GNN**

   Train the GNN over the deployed splits and register it as the version named in `raiconfig.yaml`:

   ```bash
   python train.py
   ```

   Then refresh the deployed model so it predicts sales with this version and solves both problems over the adjusted demand: `CALL DB.RETAIL_PLANNING_META._INTERNAL_REFRESH_MODEL('standard', NULL);` with your database in place of `DB`. The registry refuses to overwrite a version, so to retrain, set a new `version` in `raiconfig.yaml` first.

7. **Query the results**

   Print the diagnostics and the plans from the deployed model:

   ```bash
   python -m queries.retail_report
   ```

   ```text
   === Sales target profile (train split) ===
     n=7648  min=0.0004237  max=0.5915  mean=0.0286  stddev=0.02121
     Baseline RMSE (predict-the-mean) ~= stddev = 0.02121

   === Adjusted Demand per Article (from sales GNN, aggregated) ===
    article_id                     name  adjusted_demand
            74         3p Sneaker Socks            22.25
         53892 Jade HW Skinny Denim TRS           153.27
         57700      Pour It Up Push Bra            37.08
         64286      Maggie high support            77.34
         66518        Rose thong 7-pack            33.06
         84950                  Nirvana            38.33
         93584 SPEED ELLA BELTED BLOUSE            53.05
     ...

   Markdown Status: OPTIMAL
   Total revenue (sales + salvage): $65,535.59

   === Markdown: Selected Discounts by Article-Week ===
                    article  week  discount_pct
           3p Sneaker Socks     1          30.0
           3p Sneaker Socks     2          30.0
           3p Sneaker Socks     3          30.0
           3p Sneaker Socks     4          30.0
   Jade HW Skinny Denim TRS     1           0.0
     ...

   Demand Planning Status: OPTIMAL
   Total cost (production + holding + unmet penalty): $9,318.44
   ```

   The report prints more lines than shown here: all 12 planning articles and every selected discount. The GNN's predictions, and with them the demand and both objectives, shift from one training run to the next; the structural outcome is stable: status OPTIMAL for the markdown and the planning problems. Alternative optimal discount schedules can differ between refreshes at the same revenue.

   To predict and solve again without changing the model, refresh the deployed model, then run the query again:

   ```sql
   CALL <DB>.RETAIL_PLANNING_META._INTERNAL_REFRESH_MODEL('standard', NULL);
   ```

8. **Tear down the deployment**

   Preview what the teardown removes, then remove it:

   ```bash
   rai models teardown
   rai models teardown --force
   ```

   The teardown removes the deployed objects and keeps the two schemas, with the GNN's experiments and registered versions in the public schema.

## Template structure

```text
retail_planning/
  model/
    __init__.py                   # exports for train.py and the query
    schema.py                     # concepts, sales task relationships
    source.py                     # bundled CSVs and base facts
    reasoning.py                  # graph, GNN, demand bridge, markdown MILP, planning LP
  train.py                        # trains the GNN and registers its version
  queries/
    retail_report.py              # target profile, adjusted demand, both plans
  retail_planning.py              # script-mode reference: three GNNs against Snowflake tables
  data/
    discounts.csv                 # discount levels with demand lifts
    weeks.csv                     # planning weeks with seasonal multipliers
    hm_mini/                      # HM_MINI subset the model loads
      customers.csv               #   10K customers from H&M Kaggle
      articles.csv                #   5K articles
      transactions.csv            #   9.6K transactions
      train_sales.csv             #   RelBench sales task: 7.6K train rows
      val_sales.csv               #   1.1K val rows
      test_sales.csv              #   806 test rows
      articles_inventory.csv      #   12-article optimizer scope (real HM_MINI IDs)
      production_capacity.csv     #   matching production parameters
  README.md                       # this file
  runbook.md                      # multi-reasoner agent-skill walkthrough
  pyproject.toml                  # dependencies
```

**Start here**: follow the [Quickstart](#quickstart) to deploy the model, train the GNN, and print the report, or follow `runbook.md` to rebuild it step by step.

## Sample data

The H&M core data (customers, articles, transactions) and the sales task splits are a bundled subset of the [RelBench rel-hm dataset](https://relbench.stanford.edu/datasets/rel-hm/) in `data/hm_mini/`. The planning inputs are CSV files too:

- **discounts.csv** -- Five discount tiers (0% to 50%) with demand lift multipliers
- **weeks.csv** -- Four-week planning horizon with seasonal demand multipliers
- **hm_mini/customers.csv** and **hm_mini/articles.csv** -- the model loads only the columns the GNN reads (customers: id, fn, active, club status, fashion news frequency, age; articles: id, name, product group, colour group, index group, garment group). The deploy writes each loaded table inline into a view, and Snowflake rejects a view definition past about 1 MB; the full files are 1.2 MB and 2 MB inline
- **hm_mini/articles_inventory.csv** -- 12 articles with initial price, cost, inventory, and salvage rate
- **hm_mini/production_capacity.csv** -- Per-article production limits, costs, and holding costs

## Model overview

### Key entities

- **Customer** (`c_customer_id`): H&M shoppers with demographics (age, club status, fashion news frequency)
- **Article** (`a_article_id`): Products with metadata (name, product group, colour group, index group, garment group)
- **Transaction** (`transaction_id`): Purchase events linking customers to articles with sales channel, date, and price (the sales label)
- **ArticleDemand** (`article_id`): the adjusted demand that the GNN's predictions aggregate to, one per article with test-period transactions
- **OptArticle** (`opt_article_id`) and **ProdCapacity** (`pc_article_id`): the 12 planning articles with pricing, inventory, and production parameters
- **Discount** (`level`) and **Week** (`num`): the markdown tiers and the planning weeks

**Important invariants**: `opt_article_id` and `pc_article_id` must match real `a_article_id` values that carry test-period transactions, since an article's adjusted demand sums its predicted sales; the discount tiers include a 0% level (feasible starting point) and only increase across weeks (price ladder); prices, costs, inventory, and demand are non-negative.

### Pipeline stages

```text
Customer / Article / Transaction data (bundled CSVs)
  → GNN sales regression (per transaction)
  → Bridge: adjusted demand per article
  → Markdown optimization (MILP, maximize revenue)
  → Demand/inventory planning (LP, minimize cost)
```

The deployed model trains only the sales GNN (the most demonstrative task): HM_MINI does not ship churn or purchase splits, so the aggregation step uses the sales predictions alone. `retail_planning.py` is the script-mode reference that adds the churn and purchase GNNs against the full H&M tables.

For the full concept and property definitions, see `model/schema.py` and `model/reasoning.py`; `runbook.md` builds them step by step with the RAI skills.

## How it works

The pipeline trains a GNN on the H&M knowledge graph, aggregates its predictions into an adjusted-demand estimate per article, and feeds that estimate into two optimizers -- one for markdown pricing, one for production/inventory planning. The same demand number flows into both, so pricing and planning stay consistent with the learned forecast rather than static estimates (see the *Pipeline stages* diagram above).

1. **Train the GNN.** The graph is Customer-Transaction-Article, with the sales-regression task defined by the train, validation, and test relationships over transactions. `Transaction.price` is the label, so it is not a feature. `train.py` fits it on the predictive reasoner and registers the version that the deployed model predicts with.
2. **Bridge to optimizer inputs.** Each article's `ArticleDemand.adjusted_demand` is the sum of the predicted sales of its test-period transactions, scaled by `DEMAND_SCALE` so the figure is comparable to the inventory units. The optimizers read it for the planning articles.
3. **Markdown optimization (maximize revenue).** A mixed-integer program selects one discount per article per week under a price ladder and inventory limits, bounding sales by the *GNN-predicted* adjusted demand rather than a static estimate, and maximizes sales revenue plus salvage.
4. **Demand/inventory planning (minimize cost).** A linear program decides production quantities per article per week, tracks inventory with flow conservation against adjusted demand, and minimizes production cost plus holding cost plus an unmet-demand penalty.

Both problems are solved by HiGHS on each refresh of the deployed model, and their statuses, objectives, and selected discounts are published as relationships the report reads.

## Customize this template

### Use your own data

- Edit the CSV files in `data/` to change the article subset, pricing, inventory levels, discount tiers, or planning horizon. A table loaded this way must stay under about 1 MB of inline rows; larger tables need the Snowflake source tables that `retail_planning.py` reads.
- The `article_id` values in `articles_inventory.csv` and `production_capacity.csv` must match article IDs that have test-period transactions in `hm_mini/`.
- To work from your own Snowflake tables, use `retail_planning.py` as the reference for the source-table wiring and the full three-GNN pipeline.

### Tune parameters

- **Demand scale** (`DEMAND_SCALE` in `model/reasoning.py`): scales the aggregated predictions into demand units.
- **Unmet demand penalty** (`UNMET_PENALTY`): higher values force the demand planner to fulfill more demand at the cost of higher production.
- **Solve time limits** (`time_limit_sec` in the `configure` calls): the longest each solve may run on a refresh.
- **Discount tiers and demand lifts**: edit `discounts.csv` for finer or coarser pricing granularity.

### Extend the model

- **Add minimum-margin constraints**: ensure discounted prices always exceed cost (`OptArticle.initial_price * (1 - discount_pct/100) >= OptArticle.cost`).
- **Category-level budgets**: group articles by department and limit total discount exposure per category.
- **Multi-site planning**: extend `ProdCapacity` with a site dimension and add cross-site transfer variables.
- **Scenario analysis**: wrap the demand planner in a loop over different planning horizons (see `demand_planning_temporal` template for the pattern).

### Scale up / productionize

- Move from the bundled `data/hm_mini/` CSVs to Snowflake source tables by reading them in `model/source.py`, as `retail_planning.py` does.
- Churn and purchase GNNs need their own task relationships; add them to `model/schema.py` and `model/reasoning.py` and register each under its own name in `raiconfig.yaml`.
- Pin `relationalai` (see Prerequisites) and keep the GNN `seed` fixed so training stays reproducible across environments.
- Set `interval_s` in the deployment `schedules` to refresh the model on a schedule once the registered version is settled.

## Troubleshooting

<details>
<summary>GNN training fails or is very slow</summary>

- Check that the deploy finished: the train, validation, and test relationships must be populated in the deployed model.
- The bundled subset trains on the predictive reasoner in a few minutes; a larger dataset needs a GPU-enabled predictive reasoner size.
</details>

<details>
<summary>The report prints no adjusted demand</summary>

- Run `python train.py`, then refresh the deployed model: the first deploy registers no GNN version, so it makes no predictions.
- Check that `raiconfig.yaml` names the same model and version that `train.py` registered.
</details>

<details>
<summary>Markdown optimization is infeasible</summary>

- Verify that `discounts.csv` includes a 0% discount level (the model needs a feasible starting point).
- Check that initial inventory in `articles_inventory.csv` is sufficient for at least one week of base demand.
- Ensure the article IDs in the CSVs match articles that have predictions (they appear in the sales test set).
</details>

<details>
<summary>Demand planner shows large unmet demand</summary>

- Increase `max_production_per_week` in `production_capacity.csv` or lower `DEMAND_SCALE`.
- Reduce `UNMET_PENALTY` if you want the optimizer to tolerate some shortfall rather than over-producing.
</details>

<details>
<summary>Predictions are all NaN or empty</summary>

- Ensure the GNN training completed successfully (check for `fit()` errors).
- Verify that the test relationship has rows and that the keys link to the core entities.
- If the validation RMSE is at or above the `stddev` that the report prints for the target, the regression model has collapsed to the mean; revisit the PropertyTransformer and task setup.
</details>

<details>
<summary>The model registry refuses to overwrite a version</summary>

Set a new `version` in `raiconfig.yaml`, then run `python train.py` again.
</details>

<details>
<summary>rai init fails or connection errors</summary>

Ensure your Snowflake credentials are configured correctly and that the RAI Native App is installed on your account. Run `rai init` again and verify the connection settings.
</details>

## Learn more

### Core concepts

- [Multi-reasoner workflows](https://docs.relational.ai/) — chaining predictive output into prescriptive optimization on a shared ontology.
- [PyRel v1 query language](https://docs.relational.ai/) — `model.where(...)`, aggregations, and `model.select(...)`.

### Reasoner reference

- [Predictive reasoner (GNN)](https://docs.relational.ai/) — the Graph / Relationship / PropertyTransformer API, task types, and training configuration.
- [Prescriptive reasoner](https://docs.relational.ai/) — the `Problem` API, decision variables, constraints, and objectives.

### Deeper dives

- [Predict-then-optimize patterns](https://docs.relational.ai/) — using model predictions as parameters inside an optimizer, via an aggregation bridge concept.

## Support

- File issues at the RelationalAI templates repository.
