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
- Demand-planning teams who need a per-(store, family) weekly forecast that aggregates from per-Sale predictions
- ML engineers exploring GNN regression over heterogeneous retail graphs
- Teams already querying RelationalAI on a Store/Item/Sale ontology who want to layer a predictive head onto it

Assumes familiarity with Python, basic ML concepts (regression, RMSE), and time-series forecasting fundamentals.

## What you'll build

- **Predictive**: a regression GNN on a heterogeneous Sale → Store, Sale → Item, Item → ItemFamily graph, predicting `Sale.unit_sales` per (store, item, day) in a forward-looking 60-day test window
- **Reporting**: weekly aggregate forecast per (store-city, item-family) with absolute error per week, plus per-Sale and per-(city, family, week) RMSE metrics
- The whole pipeline runs end-to-end on a small bundled synthetic Favorita-shaped dataset (3 stores × 25 items × 365 days = ~27K daily rows); no Snowflake source data setup, no GPU

## What's included

- **Runner**: `demand_forecasting.py` — runs the full pipeline (graph build, GNN training, predictions, weekly aggregation) on the bundled CSVs
- **Runbook**: `runbook.md` — a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the script itself.
- **Synthetic data generator**: `data/generate_favorita_mini.py` — reproducible Favorita-shaped data generator (run once if you need to regenerate; output is committed under `data/favorita_mini/`)
- **Model**: `Store`, `Item`, `ItemFamily`, `Sale`, plus three task-table concepts (`TrainTable`, `ValTable`, `TestTable`) carrying the unit-sales targets
- **Sample data**: bundled synthetic Favorita-shaped dataset (3 stores × 25 items × 365 days); see [Sample data](#sample-data)
- **Outputs**: store/item counts, temporal split summary, GNN training/prediction metrics, weekly per-(city, family) forecast table, per-Sale and per-week RMSE

## Prerequisites

### Access

Any Snowflake account with the **RelationalAI Native App** installed. The bundled CSVs ship with the template; there is no source-table setup. The GNN trains on CPU.

The predictive reasoner needs a writable Snowflake schema where it can create experiments and models. The script defaults to `FAVORITA_MINI.EXPERIMENTS` (configurable via `EXP_DATABASE` / `EXP_SCHEMA` near the top of the script). One-time setup, run as `ACCOUNTADMIN`, or any role with privileges to run the commands below:

```sql
-- Use a database you own (FAVORITA_MINI shown; pick anything writable)
CREATE DATABASE IF NOT EXISTS FAVORITA_MINI;
CREATE SCHEMA IF NOT EXISTS FAVORITA_MINI.EXPERIMENTS;

GRANT USAGE ON DATABASE FAVORITA_MINI TO APPLICATION RELATIONALAI;
GRANT USAGE ON SCHEMA FAVORITA_MINI.EXPERIMENTS TO APPLICATION RELATIONALAI;
GRANT CREATE EXPERIMENT ON SCHEMA FAVORITA_MINI.EXPERIMENTS TO APPLICATION RELATIONALAI;
GRANT CREATE MODEL ON SCHEMA FAVORITA_MINI.EXPERIMENTS TO APPLICATION RELATIONALAI;
```

### Tools

- Python >= 3.10
- RelationalAI Python SDK (`relationalai[gnn] == 1.8`)

## Quickstart

1. Download ZIP:
   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/demand_forecasting.zip
   unzip demand_forecasting.zip
   cd demand_forecasting
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

   After `rai init` generates the config file, add the following to your `raiconfig.yaml`:

   ```yaml
   data:
       ensure_change_tracking: true
   ```

5. Run the experiments-schema setup DDL above (one-time per Snowflake account).

6. Run:
   ```bash
   python demand_forecasting.py
   ```

### Expected output (abbreviated)

Real numbers from a verified end-to-end run on the bundled subset (CPU). Exact predicted values shift slightly with numerical noise.

```text
Stores: 3  Items: 25  Sales: 27,375
Splits (temporal): train=18,375  val=4,500  test=4,500
Train: < 2024-11-02; Val: 2024-11-02 -- 2025-01-01; Test: >= 2025-01-01
unit_sales: min=0 mean=15.30 max=92

============================================================
Predictive: demand-forecasting regression GNN (CPU)
============================================================
=== Start GNN Training ===
  ✓ Step 1 completed (~5s)    # prepare dataset + GNN tables
  ✓ Step 2 completed (~2s)    # trainer config
  ✓ Step 3 completed (~6s)    # submit training job
=== Start GNN Prediction ===
  ✓ GNN Prediction Complete (~221s)

============================================================
Forecast (test window) -- weekly aggregate per (store, item family)
============================================================
  city    family week_start  actual  predicted    abs_err
Cuenca    BAKERY 2024-10-28   173.0     189.28      16.28
Cuenca    BAKERY 2024-11-25   335.0     378.79      43.79
Cuenca    BAKERY 2024-12-02   494.0     349.67     144.33
Cuenca BEVERAGES 2024-12-02   658.0     483.66     174.34
Cuenca BEVERAGES 2024-12-30    75.0      63.16      11.84
... (one row per (city, family, week))

Test-set RMSE (per-Sale):                  7.2792
Test-set RMSE (per (city, family, week)): 150.8997
```

> [!NOTE]
> The GNN learns base-level demand and weekday/weekend seasonality cleanly. The December holiday spike is partially captured but under-shot — Sale.date is exposed as a flat datetime feature, not a temporal index, so the GNN doesn't aggregate over time windows. The pandas-level temporal split is preserved (we still train on the past and evaluate on the future). To trade simplicity for tighter spike capture, see the "Use temporal indexing" variant in [Customize this template](#customize-this-template).

## Template structure

```text
.
├── README.md                       # this file
├── pyproject.toml                  # dependencies
├── demand_forecasting.py           # GNN regression pipeline on bundled CSVs (CPU)
└── data/
    ├── generate_favorita_mini.py   # reproducible synthetic-data generator
    └── favorita_mini/
        ├── stores.csv              # 3 stores × city, state, type, cluster
        ├── items.csv               # 25 items × family, class, perishable
        └── sales.csv               # ~27K daily (store, item, date) rows with unit_sales + onpromotion
```

**Start here**: run `python demand_forecasting.py` for the full pipeline — graph build, GNN training, predictions, and weekly aggregation — end to end on the bundled CSVs, or follow `runbook.md` to reproduce it step by step with the RAI skills.

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

For the full concept and property definitions — including the GNN edges (`Sale → Store`, `Sale → Item`, `Item → ItemFamily`) and the Train/Val/Test task relationships — see `demand_forecasting.py`; `runbook.md` builds them step by step with the RAI skills.

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

**Train and predict.** The GNN runs a regression task with `has_time_column=False`, a deliberate simplicity choice (the temporal split is preserved at the pandas level above; the GNN just doesn't use the date as a temporal index inside the graph — see [Customize this template](#customize-this-template) for the temporal-indexing variant). Predictions are attached back to each Sale.

**Aggregate to a weekly forecast.** A single declarative query pulls the per-Sale predictions and joins them to store and item metadata; pandas then rolls them up into weekly per-(city, family) buckets against the actuals.

See `demand_forecasting.py` for the implementation and `runbook.md` to reproduce it step by step with the RAI skills.

## Customize this template

### Use your own data

- **Repoint to your own retail data** — replace the CSVs under `data/favorita_mini/` with your real store / item / sales exports (matching column names) and re-run.
- **Add weather, promotions calendar, holiday flags** — extend `Sale` with extra columns and add them to `PropertyTransformer.category` or `.continuous` as appropriate. The same hierarchical-graph plus GNN scaffold absorbs new features without restructuring.

### Tune parameters

- **Forecast different granularity** — change `TEST_DAYS` / `VAL_DAYS` at the top of the script. Default is a 60-day test window after a 60-day val window.
- **Use temporal indexing instead** — for tighter holiday/seasonal spike capture, set `has_time_column=True`, restore `time_col=[Sale.date]` in the PropertyTransformer, restore the date arg in the Train/Val/Test relationships (`f"{Sale} at {Any:date} has {Any:value}"`), and add `temporal_strategy="last"` to the `GNN(...)` constructor. Trades simplicity for the GNN aggregating over time windows.

### Extend the model

- **Bring more hierarchy in** — the bundled data has Item → ItemFamily. Real Favorita data has Item → Class → Family → Department. Define a `Class` and `Department` concept the same way `ItemFamily` is defined, add `Class → Family` and `Family → Department` edges, and the GNN propagates through deeper product hierarchies.

### Scale up / productionize

- **Run on the full public Favorita dataset** — the bundled `favorita_mini` is intentionally tiny so the template runs in minutes on CPU. See the walkthrough below to point the pipeline at the full Kaggle corpus on a GPU-backed engine.

### Run on the full public Favorita dataset

The bundled `favorita_mini` is intentionally tiny so the template runs in minutes on CPU. To run on the full Kaggle Favorita corpus (~125M sales rows across 54 stores × 4,100 items × ~5 years):

1. Download the dataset from [Kaggle: Corporación Favorita Grocery Sales Forecasting](https://www.kaggle.com/c/favorita-grocery-sales-forecasting). License is "Subject to Competition Rules" — review before redistributing.
2. Load the CSVs into Snowflake (`stores.csv`, `items.csv`, `train.csv` is the sales table). Rename `train.csv → sales.csv` to match the template.
3. Replace the `pd.read_csv(...)` calls at the top of the script with Snowpark queries against your loaded tables (or use `model.Table("<DB>.<SCHEMA>.<TABLE>")` per `rai-pyrel-coding` skill's data-loading guidance):
   ```python
   from relationalai.config import SnowflakeConnection, create_config
   from snowflake import snowpark
   session = create_config().get_session(SnowflakeConnection)
   stores_df = session.sql("SELECT * FROM YOUR_DB.FAVORITA.STORES").to_pandas()
   items_df = session.sql("SELECT * FROM YOUR_DB.FAVORITA.ITEMS").to_pandas()
   sales_df = session.sql(
       "SELECT * FROM YOUR_DB.FAVORITA.SALES WHERE date >= '2017-01-01'"
   ).to_pandas(parse_dates=["date"])
   ```
4. Switch `device="cpu"` to `device="cuda"` and a GPU-backed RAI engine — full Favorita on CPU will take many hours.
5. Trim the date window in the SQL `WHERE` clause if you don't need the full 5 years; the template's `TEST_DAYS` / `VAL_DAYS` parameters control the temporal split inside that window.
6. Real Favorita has additional tables (`oil.csv`, `holidays_events.csv`, `transactions.csv`) you may want to fold in as features — see [Customize this template](#customize-this-template) above for the pattern.

## Troubleshooting

<details>
<summary><code>Schema does not exist or the GNN RelationalAI Native App lacks permissions</code> on first run</summary>

The GNN training service writes experiment artifacts to a Snowflake schema, and the `RELATIONALAI` native app must have write access. If the run fails with a message like *"The experiment is configured to use database 'X' and schema 'EXPERIMENTS' ... grant the necessary permissions ..."*, run the [setup DDL](#access) as `ACCOUNTADMIN`.

The error also fires if you've changed `EXP_DATABASE` to a database you own but haven't granted USAGE on the database itself; both grants (USAGE on database + ALL on schema) are required.
</details>

<details>
<summary>Re-running with a stale experiment causes <code>training job failed</code> at the prediction step</summary>

The SDK matches submitted training jobs to existing experiments by `Model("...")` name. If a previous failed run left a model_run_id behind, a re-run can match the stale model and fail trying to predict against incompatible artifacts (or hang at "Step 2/4: Preparing model for prediction" indefinitely). Bump the model name to force a fresh experiment:

```python
model = Model("demand_forecasting_local_v2")  # bump on each re-run if needed
```
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

- [Setup and configuration](https://docs.relational.ai/) — `rai init`, `raiconfig.yaml`, and granting the Native App access to an experiments schema.

## Support

- File issues at the RelationalAI templates repository.
