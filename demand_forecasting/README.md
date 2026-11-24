---
title: "Demand Forecasting"
description: "Forecast next-period unit sales per store, item, and day with a regression graph neural network (GNN) over a heterogeneous retail graph linking sales to stores, items, and item families."
featured: false
experience_level: advanced
industry: "Retail & Consumer"
reasoning_types:
  - Predictive
tags:
  - GNN (graph neural network)
  - Regression
  - Demand Forecasting
  - Time Series
  - Retail
---

## What this template is for

Retail planners forecast unit sales at fine granularity — per store, per item, per day — to drive replenishment, promotions, and labour planning. Classical demand-forecasting models score one (store, item) series in isolation; they miss the fact that store A's sales of bread move with bakery sales across the chain, and that bakery sells through similarly to dairy. This template wires those hierarchies into a **Predictive** reasoner: a regression GNN trained over a heterogeneous Sale → Store, Sale → Item, Item → ItemFamily graph, so the model propagates signal through the store and product hierarchies while predicting per-Sale unit sales.

## Who this is for

- Retail data scientists building per-(store, item, day) demand-forecasting pipelines who want to add hierarchical signal (item family, store cluster) without manually engineering features
- Demand-planning teams who need a per-(city, family) weekly forecast that aggregates from per-Sale predictions
- ML engineers exploring GNN regression over heterogeneous retail graphs
- Teams already querying RelationalAI on a Store/Item/Sale ontology who want to layer a predictive head onto it

Assumes familiarity with Python, basic ML concepts (regression, RMSE), and time-series forecasting fundamentals.

## What you'll build

- **Predictive**: a regression GNN on a heterogeneous Sale → Store, Sale → Item, Item → ItemFamily graph, predicting `Sale.unit_sales` per (store, item, day) in a forward-looking 60-day test window
- **Reporting**: weekly aggregate forecast per (store-city, item-family) with absolute error per week, plus per-Sale and per-(city, family, week) RMSE metrics
- The whole pipeline runs end-to-end on a small bundled synthetic Favorita-shaped dataset (3 stores × 25 items × 365 days = ~27K daily rows); no Snowflake source data setup, no GPU

## What's included

- **Model**: `model/` — the deployed model: concepts and splits (`schema.py`, `source.py`), the graph, the GNN and its predictions (`reasoning.py`)
- **Training**: `train.py` — trains the GNN over the deployed splits and registers its version
- **Query**: `queries/forecast_report.py` — prints the weekly forecast and test-set RMSE from the deployed model
- **Runbook**: `runbook.md` — a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the code itself.
- **Synthetic data generator**: `data/generate_favorita_mini.py` — reproducible Favorita-shaped data generator (run once if you need to regenerate; output is committed under `data/favorita_mini/`)
- **Model**: `Store`, `Item`, `ItemFamily`, `Sale`, plus three task-table concepts (`TrainTable`, `ValTable`, `TestTable`) carrying the unit-sales targets
- **Sample data**: bundled synthetic Favorita-shaped dataset (3 stores × 25 items × 365 days); see [Sample data](#sample-data)
- **Outputs**: store/item counts, temporal split summary, GNN training/prediction metrics, weekly per-(city, family) forecast table, per-Sale and per-week RMSE

## Prerequisites

### Access

- A Snowflake account that has the RAI Native App installed.
- A role that can deploy models, set up once by an account administrator: follow [Set up model deployment](https://private.relational.ai/early-access/model-deploy-setup) (**Try it out**, or **Governed setup** for a shared account). This template has no prescriptive solve, so it needs no PAT setup.
- A Snowflake user that holds that role.

The bundled CSVs ship with the template; there is no source-table setup. The GNN trains on the predictive reasoner and stores its experiments and registered versions in the template's public schema.

### Tools

- Python 3.10 through 3.14 (the range relationalai 2.3.0 supports)
- The `relationalai[gnn]` SDK and the `rai` CLI (installed by the Quickstart's `python -m pip install .`).

## Quickstart

Before you start, install Python 3.10 or later and complete the access prerequisites above: a Snowflake account with the RAI Native App, a role that can deploy models, and a Snowflake user that holds it.

Before the first deploy, create this template's two schemas as the model role, and have an administrator grant the RAI Native App access to them. The GNN keeps its experiments and registered versions in the public schema, and the internal schema holds only this model's objects, so the grants cover all of it:

```sql
-- as the model role
CREATE SCHEMA IF NOT EXISTS <DB>.DEMAND_FORECASTING;
CREATE SCHEMA IF NOT EXISTS <DB>.DEMAND_FORECASTING_META;

-- as an administrator
GRANT USAGE ON DATABASE <DB> TO APPLICATION <RAI_APP_NAME>;
GRANT USAGE ON SCHEMA <DB>.DEMAND_FORECASTING TO APPLICATION <RAI_APP_NAME>;
GRANT CREATE EXPERIMENT ON SCHEMA <DB>.DEMAND_FORECASTING TO APPLICATION <RAI_APP_NAME>;
GRANT CREATE MODEL ON SCHEMA <DB>.DEMAND_FORECASTING TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON DATABASE <DB> TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON SCHEMA <DB>.DEMAND_FORECASTING_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON WAREHOUSE <WAREHOUSE> TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL TABLES IN SCHEMA <DB>.DEMAND_FORECASTING_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL DYNAMIC TABLES IN SCHEMA <DB>.DEMAND_FORECASTING_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL VIEWS IN SCHEMA <DB>.DEMAND_FORECASTING_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER INSERT, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA <DB>.DEMAND_FORECASTING_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER CREATE TABLE, CREATE STAGE ON SCHEMA <DB>.DEMAND_FORECASTING_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER READ, WRITE ON ALL STAGES IN SCHEMA <DB>.DEMAND_FORECASTING_META TO APPLICATION <RAI_APP_NAME>;
```

Use this sequence to deploy the model, train the GNN, and query its forecast:

1. **Download the template**

   [Download the ZIP](https://docs.relational.ai/templates/zips/v1/demand_forecasting.zip), unzip it, and enter the template directory:

   ```bash
   unzip demand_forecasting.zip
   cd demand_forecasting
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

   Set the connection `role` to the model role, then add the predictive reasoner, the registered version the GNN predicts with, and a `deployment` section. Give each template its own schema pair so two deployed templates never share one:

   ```yaml
   reasoners:
     predictive:
       name: demand_forecasting_gnn     # created on first use if it doesn't exist
       gnns:
         demand_forecast:               # the GNN's name in model/reasoning.py
           registry: <DB>.DEMAND_FORECASTING
           model: DEMAND_FORECAST
           version: V1                  # train.py registers this version
   deployment:
     role: <MODEL_ROLE>
     public_schema: <DB>.DEMAND_FORECASTING
     identity:
       internal_schema: <DB>.DEMAND_FORECASTING_META
     schedules:
       standard:
         interval_s: 0                  # refresh only on deploy or on demand
     schedule: standard
   ```

5. **Deploy the model**

   Deploy the model in `model/` to the schemas in `raiconfig.yaml`:

   ```bash
   rai models deploy --path model
   ```

   The deploy waits for the model's first refresh, which loads the sales data and the train, validation, and test splits. No version of the GNN is registered yet, so this refresh makes no predictions.

   Deploying again without changing the model applies no updates and does not refresh.

6. **Train the GNN**

   Train the GNN over the deployed splits and register it as the version named in `raiconfig.yaml`:

   ```bash
   python train.py
   ```

   Then refresh the deployed model so it predicts with this version: `CALL <DB>.DEMAND_FORECASTING_META._INTERNAL_REFRESH_MODEL('standard', NULL);` with your database in place of `<DB>`. The registry refuses to overwrite a version, so to retrain, set a new `version` in `raiconfig.yaml` first.

7. **Query the results**

   Print the forecast from the deployed model:

   ```bash
   python -m queries.forecast_report
   ```

   ```text
   Stores: 3  Items: 25  Sales: 27,375
   Splits (temporal): train=18,375  val=4,500  test=4,500
   Train: < 2024-09-02; Val: 2024-09-02 -- 2024-11-01; Test: >= 2024-11-01
   unit_sales: min=0 mean=18.22 max=90

   ============================================================
   Forecast (test window) -- weekly aggregate per (city, item family)
   ============================================================
     city    family week_start  actual  predicted    abs_err
   Cuenca    BAKERY 2024-10-28   173.0 190.663560  17.663560
   Cuenca    BAKERY 2024-11-04   330.0 376.962092  46.962092
   Cuenca    BAKERY 2024-12-02   494.0 358.614115 135.385885
   Cuenca BEVERAGES 2024-12-02   658.0 483.350180 174.649820
   Cuenca BEVERAGES 2024-12-30    75.0  64.095143  10.904857

   Test-set RMSE (per-Sale):           7.3313
   Test-set RMSE (per (city, family, week)): 153.2000
   ```

   The forecast table is trimmed here: the report prints the first 20 (city, family, week) rows. The forecast follows the weekly swings, and its largest gaps fall in the December holiday weeks. Predicted values and the RMSE vary a little from one training run to the next; the data summary and actuals do not. See `runbook.md` for the step-by-step walkthrough.

   To predict again without changing the model, refresh the deployed model, then run the query again:

   ```sql
   CALL <DB>.DEMAND_FORECASTING_META._INTERNAL_REFRESH_MODEL('standard', NULL);
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
.
├── README.md                       # this file
├── pyproject.toml                  # dependencies
├── model/
│   ├── __init__.py                 # exports for train.py and the query
│   ├── schema.py                   # concepts and the Train/Val/Test task relationships
│   ├── source.py                   # bundled CSVs and the temporal split
│   └── reasoning.py                # graph, feature types, the GNN and its predictions
├── train.py                        # trains the GNN and registers its version
├── queries/
│   └── forecast_report.py          # weekly forecast and test-set RMSE
└── data/
    ├── generate_favorita_mini.py   # reproducible synthetic-data generator
    └── favorita_mini/
        ├── stores.csv              # 3 stores × city, state, type, cluster
        ├── items.csv               # 25 items × family, class, perishable
        └── sales.csv               # ~27K daily (store, item, date) rows with unit_sales + onpromotion
```

**Start here**: follow the [Quickstart](#quickstart) to deploy the model, train the GNN, and print the weekly forecast, or follow `runbook.md` to reproduce it step by step with the RAI skills.

## Sample data

Two ways to feed this template:

1. **Bundled (light)** — `data/favorita_mini/` ships with the template ZIP. 3 stores × 25 items × 365 days = ~27,375 rows. **Synthetic** (generated by `data/generate_favorita_mini.py`), Favorita-schema-shaped so it drops in as a Favorita stand-in. No external setup. **Quickstart uses this.**
2. **Full public dataset** — the original Corporación Favorita corpus is on Kaggle: [Corporación Favorita Grocery Sales Forecasting](https://www.kaggle.com/c/favorita-grocery-sales-forecasting) (~125M sales rows across 54 stores × 4,100 items × ~5 years; license: "Subject to Competition Rules"). See [Run on the full public Favorita dataset](#run-on-the-full-public-favorita-dataset) below for the GPU + Snowflake walkthrough.

About the bundled mini set, generated by `data/generate_favorita_mini.py`. The generator embeds:

- **3 stores** in Quito, Guayaquil, and Cuenca, each with a different per-store demand multiplier (Quito = highest volume city, Cuenca = lowest)
- **25 items** across five product families (`BEVERAGES`, `DAIRY`, `GROCERY`, `BAKERY`, `CLEANING`), each with its own family-level demand multiplier
- **365 days** of daily sales per (store, item) pair = 27,375 rows total
- **Weekly seasonality** (1.25× weekend boost), **monthly seasonality** (1.4× December holiday spike, 1.1× summer bump), and **promotional spikes** (~5% of (store, item, day) cells flagged on-promotion with a 1.6× lift)
- **Poisson-style noise** with overdispersion so the data isn't trivially predictable

Customers adapting this template would replace these CSVs with a real Favorita subset (or any retail demand dataset matching the schema) by overwriting the files under `data/favorita_mini/`. The original Favorita dataset is publicly available on Kaggle: [Corporación Favorita Grocery Sales Forecasting](https://www.kaggle.com/c/favorita-grocery-sales-forecasting).

## Model overview

The model is a small retail ontology whose only purpose is to give the graph neural network (GNN) a heterogeneous neighborhood: sales linked to their store and item, and items rolled up to a family.

- **Key entities**: `Store`, `Item`, `ItemFamily`, `Sale`, plus three task-table concepts (`TrainTable`, `ValTable`, `TestTable`) that carry the split targets into the trainer.
- **Primary identifiers**: `Store.store_id`, `Item.item_id`, `Sale.sale_id` (all integers); `ItemFamily.family` (the family string).
- **Important invariants**: `unit_sales` is a non-negative integer and is the regression target (dropped from features to prevent leakage); every `Sale` links to exactly one `Store` and one `Item`; every `Item` links to exactly one `ItemFamily`; `ItemFamily` is derived from the distinct `Item.family` values rather than loaded.

For the full concept and property definitions — including the GNN edges (`Sale → Store`, `Sale → Item`, `Item → ItemFamily`) and the Train/Val/Test task relationships — see `model/`; `runbook.md` builds them step by step with the RAI skills.

```text
Stores + Items + Sales (bundled CSVs)
  -> Build heterogeneous graph: Sale -> Store, Sale -> Item, Item -> ItemFamily
  -> Temporal train/val/test split in pandas (last 60 days = test, previous 60 = val)
  -> Predictive: GNN regression on Sale.unit_sales
  -> Reporting: aggregate per-Sale predictions to weekly per-(city, family) forecasts
```

## How it works

The pipeline builds a heterogeneous graph, trains a regression GNN over it, and aggregates the per-Sale predictions into a weekly forecast.

**Build the heterogeneous graph.** Each Sale connects to its Store and its Item; each Item connects to its ItemFamily. The GNN aggregates over these neighborhoods so signal propagates: a Cuenca BAKERY sale's prediction is influenced by other Cuenca sales (via Store), by other items in the BAKERY family (via Item → ItemFamily), and by the broader BAKERY family base rate.

**Declare features and target.** Primary and foreign keys are dropped because the graph carries identity, and `Sale.unit_sales` is dropped from the features because it is the regression target — keeping it would leak the answer. The remaining columns are declared explicitly as categorical, continuous, integer, or datetime features.

**Split temporally.** Forecasting requires training on the past and evaluating on the future; a random split would leak future signal into training. The split is done in pandas before the task tables are built — the last 60 days become the test window and the 60 before that the validation window.

**Train and predict.** The GNN runs a regression task with `has_time_column=True`: each Train, Val and Test row carries its sale date, and `Sale.date` is the property transformer's time column. Predictions are attached back to each Sale.

**Aggregate to a weekly forecast.** Two queries pull the per-Sale predictions and their store city and item family; pandas then rolls them up into weekly per-(city, family) buckets against the actuals, pooling stores that share a city.

See `model/reasoning.py` for the graph and the GNN, `queries/forecast_report.py` for the rollup, and `runbook.md` to reproduce it step by step with the RAI skills.

## Customize this template

### Use your own data

- **Repoint to your own retail data** — replace the CSVs under `data/favorita_mini/` with your real store / item / sales exports (matching column names), redeploy, and train a new version.
- **Add weather, promotions calendar, holiday flags** — extend `Sale` with extra columns and add them to `PropertyTransformer.category` or `.continuous` as appropriate. The same hierarchical-graph plus GNN scaffold absorbs new features without restructuring.

### Tune parameters

- **Forecast different granularity** — change `TEST_DAYS` / `VAL_DAYS` in `model/source.py`. Default is a 60-day test window after a 60-day val window.

### Extend the model

- **Bring more hierarchy in** — the bundled data has Item → ItemFamily. Real Favorita data has Item → Class → Family → Department. Define a `Class` and `Department` concept the same way `ItemFamily` is defined, add `Class → Family` and `Family → Department` edges, and the GNN propagates through deeper product hierarchies.

### Scale up / productionize

- **Run on the full public Favorita dataset** — the bundled `favorita_mini` is intentionally tiny so the template runs in minutes on CPU. The section below lists what changes to run it on the full Kaggle corpus on a GPU-backed engine.

### Run on the full public Favorita dataset

The bundled `favorita_mini` is intentionally tiny so the template runs in minutes on CPU. The template does not ship an adaptation for the full Kaggle Favorita corpus (~125M sales rows across 54 stores × 4,100 items × ~5 years); running on it takes these changes:

1. Download the dataset from [Kaggle: Corporación Favorita Grocery Sales Forecasting](https://www.kaggle.com/c/favorita-grocery-sales-forecasting). License is "Subject to Competition Rules" — review before redistributing.
2. Load `stores.csv`, `items.csv`, and `train.csv` (the sales table) into Snowflake, and map their columns to the ones the model reads: the Kaggle files name the keys `store_nbr`, `item_nbr`, and `id` (the model reads `store_id`, `item_id`, and `sale_id`), and the store and item types `type` and `class` (the model reads `store_type` and `item_class`). Raw `unit_sales` includes returns (negative values) and fractional quantities for items sold by weight, while the model's target is a non-negative integer, so decide how to filter or round them.
3. Read the tables through `model.Table("<db>.<schema>.<table>")` sources in `model/source.py` instead of pandas frames: the deployed model writes each pandas frame into its definition as inline rows, which does not scale to the full corpus. The temporal split in `model/source.py` works on pandas frames, so restate it as rules over `Sale.date`.
4. Size the predictive reasoner for the data with `reasoners.predictive.size` in `raiconfig.yaml` (a GPU size for the full corpus): a deployed GNN runs on the device that size provides.
5. Trim the date window in the tables you map if you don't need the full 5 years; `TEST_DAYS` / `VAL_DAYS` control the temporal split inside that window.
6. Real Favorita has additional tables (`oil.csv`, `holidays_events.csv`, `transactions.csv`) you may want to fold in as features — see [Customize this template](#customize-this-template) above for the pattern.

## Troubleshooting

<details>
<summary><code>Experiment tracking database ... does not exist or is not accessible</code> when training</summary>

The GNN keeps its experiments and registered versions in the public schema named in `raiconfig.yaml`, and the RAI Native App needs USAGE on its database and schema plus CREATE EXPERIMENT and CREATE MODEL on the schema. Run the setup grants from the [Quickstart](#quickstart) as an administrator, then run `python train.py` again.
</details>

<details>
<summary>The report prints <code>(no predictions returned)</code></summary>

The deployed model has not refreshed since a version was registered: the refresh that `rai models deploy` waits for runs before `python train.py`. Run `python train.py` if you haven't, then the refresh call from step 6 of the Quickstart, and query again.
</details>

## Related templates

- **`subscriber_retention`** — sibling Predictive template using a regression GNN on a homogeneous call graph (no time column); useful as a comparison for the simpler-graph case
- **`fraud-detection`** — the canonical multi-reasoner GNN template (Graph + Rules + Predictive + Prescriptive); use as the reference for adding a Prescriptive optimization stage on top of forecasting predictions (e.g., truck-routing or replenishment optimization driven by predicted demand)

## Learn more

### Core concepts

- [PyRel v1 query language](https://docs.relational.ai/) — `model.define(...)`, `.where(...)`, and `select(...)`, used to build the graph and pull predictions.
- [Graph construction](https://docs.relational.ai/) — building the heterogeneous `Graph` and its edges that the GNN aggregates over.

### Reasoner reference

- [Predictive reasoner (GNN)](https://docs.relational.ai/) — `GNN`, `PropertyTransformer`, regression tasks, and temporal handling.

### CLI / SDK guides

- [Setup and configuration](https://docs.relational.ai/) — `raiconfig.yaml`, deployment, and granting the Native App access to the template's schemas.

## Support

- File issues at the RelationalAI templates repository.
