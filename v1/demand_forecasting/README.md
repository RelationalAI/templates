---
title: "Demand Forecasting"
description: "Forecast next-period unit sales per (store, item, day) with a regression GNN over a heterogeneous retail knowledge graph: sales transactions linked to stores, items, and item families so the GNN propagates signal through the store and product hierarchies."
featured: false
private: true
experience_level: advanced
industry: "Retail"
reasoning_types:
  - Predictive
tags:
  - GNN
  - Regression
  - Demand Forecasting
  - Time Series
  - Retail
---

# Demand Forecasting

## What this template is for

Retail planners forecast unit sales at fine granularity — per store, per item, per day — to drive replenishment, promotions, and labour planning. Classical demand-forecasting models score one (store, item) series in isolation; they miss the fact that store A's sales of bread move with bakery sales across the chain, and that bakery sells through similarly to dairy. This template wires those hierarchies into a **Predictive** reasoner: a regression GNN trained over a heterogeneous Sale → Store, Sale → Item, Item → ItemFamily graph, so the model propagates signal through the store and product hierarchies while predicting per-Sale unit sales.

> [!IMPORTANT]
> The RelationalAI **predictive reasoner (GNN)** used in this template is in early access. The API surface (`GNN`, `PropertyTransformer`, task relationships) may still change between releases; check the `rai-predictive-modeling` and `rai-predictive-training` skills for current guidance before adapting to production data.

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
- **Synthetic data generator**: `data/generate_favorita_mini.py` — reproducible Favorita-shaped data generator (run once if you need to regenerate; output is committed under `data/favorita_mini/`)
- **Model**: `Store`, `Item`, `ItemFamily`, `Sale`, plus three task-table concepts (`TrainTable`, `ValTable`, `TestTable`) carrying the unit-sales targets
- **Sample data**: bundled synthetic Favorita-shaped dataset (3 stores × 25 items × 365 days); see [Sample data](#sample-data)
- **Outputs**: store/item counts, temporal split summary, GNN training/prediction metrics, weekly per-(city, family) forecast table, per-Sale and per-week RMSE

## Prerequisites

### Access

Any Snowflake account with the **RelationalAI Native App** installed. The bundled CSVs ship with the template; there is no source-table setup. The GNN trains on CPU.

The predictive reasoner needs a writable Snowflake schema where it can create experiments and models. The script defaults to `FAVORITA_MINI.EXPERIMENTS` (configurable via `EXP_DATABASE` / `EXP_SCHEMA` near the top of the script). One-time setup, run as `ACCOUNTADMIN`:

```sql
-- Use a database you own (FAVORITA_MINI shown; pick anything writable)
CREATE DATABASE IF NOT EXISTS FAVORITA_MINI;
CREATE SCHEMA IF NOT EXISTS FAVORITA_MINI.EXPERIMENTS;

GRANT USAGE ON DATABASE FAVORITA_MINI TO APPLICATION RELATIONALAI;
GRANT ALL PRIVILEGES ON SCHEMA FAVORITA_MINI.EXPERIMENTS TO APPLICATION RELATIONALAI;
```

### Tools

- Python >= 3.10
- RelationalAI Python SDK (`relationalai`)

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
> The GNN learns base-level demand and weekday/weekend seasonality cleanly. The December holiday spike is partially captured but under-shot — that's because the SDK's `has_time_column=True` temporal indexing is currently disabled in this template (see [Customize this template](#customize-this-template) and the troubleshooting note below). The pandas-level temporal split is preserved (we still train on the past and evaluate on the future), but the GNN itself sees the date as a flat datetime feature rather than a temporal index. When the SDK's time-aware mode is stable for this dataset shape, re-enabling it should improve the December-spike capture.

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

### Key entities

- **Store** (`store_id`): one physical retail store with city, state, store type, and a cluster identifier
- **Item** (`item_id`): one SKU with family, item-class, and a perishable flag
- **ItemFamily** (`family`): derived from the unique `Item.family` values; gives the GNN a hierarchical edge structure (Item → ItemFamily) that lets signal propagate across items within a family
- **Sale** (`sale_id`): one row per (store, item, date) with `unit_sales` target and an `onpromotion` flag

### Pipeline stages

```text
Stores + Items + Sales (bundled CSVs)
  → Build heterogeneous graph: Sale → Store, Sale → Item, Item → ItemFamily
  → Temporal train/val/test split in pandas (last 60 days = test, previous 60 = val)
  → Predictive: GNN regression on Sale.unit_sales
  → Reporting: aggregate per-Sale predictions to weekly per-(city, family) forecasts
```

## How it works

### 1. Build the heterogeneous graph

Each Sale connects to its Store and its Item; each Item connects to its ItemFamily. The GNN aggregates over these neighborhoods so signal propagates: e.g., a Cuenca BAKERY sale's prediction is influenced by other Cuenca sales (via Store), by other items in the BAKERY family (via Item → ItemFamily), and by the broader BAKERY family base rate.

```python
gnn_graph = Graph(model, directed=True, weighted=False)
Edge = gnn_graph.Edge
model.define(Edge.new(src=Sale, dst=Store)).where(Sale.store_id == Store.store_id)
model.define(Edge.new(src=Sale, dst=Item)).where(Sale.item_id == Item.item_id)
model.define(Edge.new(src=Item, dst=ItemFamily)).where(Item.family == ItemFamily.family)
```

### 2. Declare features and target (PropertyTransformer)

PKs / FKs are dropped (the graph carries identity). `Sale.unit_sales` is dropped from features (it's the target — keeping it would leak). Categorical, continuous, integer, and datetime feature types are declared explicitly.

```python
pt = PropertyTransformer(
    drop=[
        Sale.sale_id, Sale.store_id, Sale.item_id,
        Store.store_id, Item.item_id,
        Sale.unit_sales,   # target — drop to prevent leakage
    ],
    category=[Store.city, Store.state, Store.store_type,
              Item.family, Item.perishable, Sale.onpromotion],
    continuous=[Store.cluster],
    integer=[Item.item_class],
    datetime=[Sale.date],
)
```

### 3. Temporal train / val / test split

Forecasting requires a temporal split: training on the past, evaluating on the future. Random splits leak future signal into training. The split is done in pandas before the task tables are built:

```python
max_date = sales_df["date"].max()
test_start = max_date - pd.Timedelta(days=TEST_DAYS - 1)
val_start = test_start - pd.Timedelta(days=VAL_DAYS)

train_mask = sales_df["date"] < val_start
val_mask = (sales_df["date"] >= val_start) & (sales_df["date"] < test_start)
test_mask = sales_df["date"] >= test_start
```

### 4. Train and predict (GNN regression)

```python
gnn = GNN(
    exp_database=EXP_DATABASE,
    exp_schema=EXP_SCHEMA,
    graph=gnn_graph,
    property_transformer=pt,
    train=Train,
    validation=Val,
    task_type="regression",
    eval_metric="rmse",
    has_time_column=False,
    seed=SEED,
    device="cpu",
    n_epochs=20,
    lr=0.005,
)
gnn.fit()
Sale.predictions = gnn.predictions(domain=Test)
```

`has_time_column=False` is a deliberate choice — see [Customize this template](#customize-this-template). The temporal split is still preserved at the pandas level above; the GNN just doesn't use the date as a temporal index inside the graph.

### 5. Aggregate to weekly per-(city, family) forecast

A single declarative query pulls per-Sale predictions and joins them back to store/item metadata; pandas then aggregates to weekly buckets:

```python
sale_ref = Sale.ref()
predicted_value_ref = Float.ref()
results_df = (
    select(
        sale_ref.sale_id.alias("sale_id"),
        sale_ref.date.alias("date"),
        sale_ref.store_id.alias("store_id"),
        sale_ref.item_id.alias("item_id"),
        sale_ref.unit_sales.alias("actual"),
        predicted_value_ref.alias("predicted"),
    )
    .where(sale_ref.predictions.predicted_value(predicted_value_ref))
    .to_df()
)

# join store + item metadata
# week_start = results_df["date"].dt.to_period("W").dt.start_time
# weekly = results_df.groupby(["city", "family", "week_start"])[...].sum()
```

## Customize this template

- **Re-enable temporal indexing** when the SDK ships a stable fix — set `has_time_column=True`, restore `time_col=[Sale.date]` in the PropertyTransformer, restore the date arg in the Train/Val/Test relationships (`f"{Sale} at {Any:date} has {Any:value}"`), and add `temporal_strategy="last"` to the `GNN(...)` constructor. The December holiday spike should predict better.
- **Forecast different granularity** — change `TEST_DAYS` / `VAL_DAYS` at the top of the script. Default is a 60-day test window after a 60-day val window.
- **Add weather, promotions calendar, holiday flags** — extend `Sale` with extra columns and add them to `PropertyTransformer.category` or `.continuous` as appropriate. The same hierarchical-graph + GNN scaffold absorbs new features without restructuring.
- **Bring more hierarchy in** — the bundled data has Item → ItemFamily. Real Favorita data has Item → Class → Family → Department. Define a `Class` and `Department` concept the same way `ItemFamily` is defined, add `Class → Family` and `Family → Department` edges, and the GNN propagates through deeper product hierarchies.
- **Repoint to your own retail data** — replace the CSVs under `data/favorita_mini/` with your real store / item / sales exports (matching column names) and re-run.

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
<summary><code>worker is not ready to accept jobs - please retry the job later</code></summary>

The predictive reasoner can show `STATUS='READY'` while its in-pod worker is still coming up; train submissions hit a 400 error in this state. Recover by suspend / resume on the predictive reasoner, then wait for `READY` again before retrying:

```sql
CALL RELATIONALAI.API.SUSPEND_REASONER('predictive', '<reasoner_name>');
CALL RELATIONALAI.API.RESUME_REASONER_ASYNC('predictive', '<reasoner_name>');
-- poll until STATUS=READY:
CALL RELATIONALAI.API.GET_REASONER('predictive', '<reasoner_name>');
```

If you're driving the reasoner via the SDK and saw an earlier-in-the-day successful run for a smaller template (e.g. `subscriber_retention`), running that template once *primes* the worker — chaining a smaller run before this one is a reliable way to avoid the cold-worker hit.
</details>

<details>
<summary>Re-running with a stale experiment causes <code>training job failed</code> at the prediction step</summary>

The SDK matches submitted training jobs to existing experiments by `Model("...")` name. If a previous failed run left a model_run_id behind, a re-run can match the stale model and fail trying to predict against incompatible artifacts (or hang at "Step 2/4: Preparing model for prediction" indefinitely). Bump the model name to force a fresh experiment:

```python
model = Model("demand_forecasting_local_v2")  # bump on each re-run if needed
```
</details>

<details>
<summary>Train job failures with date columns at scale (<code>has_time_column=True</code>)</summary>

PyRel 1.0.x has a server-side `DateTime/VString` signature mismatch when `has_time_column=True` is paired with a date column at non-trivial dataset sizes. Symptoms include train jobs that hang at "Step 2/4: Preparing model for prediction" with no JOBS row, or fail with a SQL signature error.

Workaround (used as the default in this template): keep the date as a plain `datetime` feature in `PropertyTransformer`, but set `has_time_column=False` and drop `time_col` / `temporal_strategy`. Preserve the temporal split in pandas before building task tables. See [Customize this template](#customize-this-template) for the instructions to re-enable temporal indexing once the SDK fix lands.
</details>

## Related templates

- **`subscriber_retention`** — sibling Predictive template using a regression GNN on a homogeneous call graph (no time column); useful as a comparison for the simpler-graph case
- **`fraud-detection`** — the canonical multi-reasoner GNN template (Graph + Rules + Predictive + Prescriptive); use as the reference for adding a Prescriptive optimization stage on top of forecasting predictions (e.g., truck-routing or replenishment optimization driven by predicted demand)
