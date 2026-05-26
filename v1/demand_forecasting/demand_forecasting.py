"""Demand Forecasting -- predict per-(store, item, date) unit sales with a GNN.

Runs an end-to-end regression GNN pipeline on a bundled Favorita-shaped
dataset (3 stores x 25 items x 365 days = ~27K daily sales rows). All
source data loads from CSVs via `model.data()` -- no Snowflake source-data
loading and no GPU required. The GNN reasoner still uses Snowflake for
experiment artifacts (see README "Prerequisites" for the one-time
schema-permission DDL).

Pipeline:
  1. Load store / item / sale data and derive ItemFamily from Item.family.
  2. Build a heterogeneous Sale -> Store, Sale -> Item, Item -> ItemFamily
     graph so the GNN can propagate signal through the store and item
     hierarchies.
  3. Train a regression GNN predicting Sale.unit_sales. Sale.date is fed
     as a plain datetime feature, not as a temporal index; the temporal
     split is done in pandas before the task tables are built (see step 4).
  4. Generate per-Sale predictions on a forward-looking 60-day test window
     (temporal split done in pandas before the task tables are built) and
     aggregate to weekly per-(store, family) forecasts.

The bundled CSVs were generated synthetically by
data/generate_favorita_mini.py — promotional flags, weekday/weekend
seasonality, December holiday spike, and per-store/item base rates with
Poisson-style noise. Customers adapting this template would replace the
CSVs with a real Favorita subset (or any retail demand dataset matching
the schema) by overwriting the files under data/favorita_mini/.

Run:
    python demand_forecasting.py

Output:
    Data summary, GNN training metrics (RMSE on validation), test-set
    RMSE, and a weekly forecast table per (store, item family).
"""

from pathlib import Path

import numpy as np
import pandas as pd
from relationalai.semantics import Any, Float, Integer, Model, String, select
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.predictive import GNN, PropertyTransformer

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

SEED = 42
STREAM_LOGS = False
DATA_DIR = Path(__file__).parent / "data" / "favorita_mini"

TEST_DAYS = 60   # last 60 days as test window
VAL_DAYS = 60    # 60 days before test as validation

# RelationalAI's predictive reasoner writes GNN experiment artifacts to a
# Snowflake schema that the RELATIONALAI native app must have write access
# to. Set EXP_DATABASE to a database you own; the schema EXPERIMENTS will
# be created on first run. See README "Prerequisites" for the one-time
# setup DDL.
EXP_DATABASE = "FAVORITA_MINI"
EXP_SCHEMA = "EXPERIMENTS"

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

model = Model("demand_forecasting_local_v1")
Concept, Relationship = model.Concept, model.Relationship

stores_df = pd.read_csv(DATA_DIR / "stores.csv")
items_df = pd.read_csv(DATA_DIR / "items.csv")
sales_df = pd.read_csv(DATA_DIR / "sales.csv", parse_dates=["date"])

# Store concept: physical retail store with city, state, type, cluster.
Store = Concept("Store", identify_by={"store_id": Integer})
model.define(Store.new(model.data(stores_df).to_schema()))

# Item concept: SKU with family, class, perishability.
Item = Concept("Item", identify_by={"item_id": Integer})
model.define(Item.new(model.data(items_df).to_schema()))

# ItemFamily concept: derived from the unique Item.family values; gives the
# GNN a hierarchical edge structure (Item -> Family) that lets signal
# propagate across items within a family.
ItemFamily = Concept("ItemFamily", identify_by={"family": String})
model.define(ItemFamily.new(family=Item.family))

# Sale concept: one row per (store, item, date) with unit_sales target and
# onpromotion flag. The GNN target is Sale.unit_sales.
Sale = Concept("Sale", identify_by={"sale_id": Integer})
model.define(Sale.new(model.data(sales_df).to_schema()))

# --------------------------------------------------
# Build the GNN graph
# --------------------------------------------------
# Heterogeneous: each Sale connects to its Store and its Item; each Item
# connects to its ItemFamily. The GNN aggregates over these neighborhoods
# while the time column (Sale.date) drives temporal causality.

gnn_graph = Graph(model, directed=True, weighted=False)
Edge = gnn_graph.Edge
model.define(Edge.new(src=Sale, dst=Store)).where(Sale.store_id == Store.store_id)
model.define(Edge.new(src=Sale, dst=Item)).where(Sale.item_id == Item.item_id)
model.define(Edge.new(src=Item, dst=ItemFamily)).where(Item.family == ItemFamily.family)

# --------------------------------------------------
# PropertyTransformer -- declare feature types
# --------------------------------------------------

pt = PropertyTransformer(
    drop=[
        # PKs and FKs add noise; the graph carries identity.
        Sale.sale_id,
        Sale.store_id,
        Sale.item_id,
        Store.store_id,
        Item.item_id,
        # The GNN target is unit_sales — keeping it as a feature would leak.
        Sale.unit_sales,
    ],
    category=[
        Store.city,
        Store.state,
        Store.store_type,
        Item.family,
        Item.perishable,
        Sale.onpromotion,
    ],
    continuous=[Store.cluster],
    integer=[Item.item_class],
    datetime=[Sale.date],
    # Sale.date is exposed as a plain datetime feature above; we don't set
    # time_col here so the GNN treats it as a regular feature rather than a
    # temporal index. The split is still temporal — see the
    # train_mask / val_mask / test_mask assignments below — so we still
    # train on the past and evaluate on the future.
)

# --------------------------------------------------
# Train / Val / Test split (temporal)
# --------------------------------------------------
# Forecast use cases require temporal splits: training on the past, evaluating
# on the future. Random splits leak future signal into training.

max_date = sales_df["date"].max()
test_start = max_date - pd.Timedelta(days=TEST_DAYS - 1)
val_start = test_start - pd.Timedelta(days=VAL_DAYS)

train_mask = sales_df["date"] < val_start
val_mask = (sales_df["date"] >= val_start) & (sales_df["date"] < test_start)
test_mask = sales_df["date"] >= test_start

train_df = sales_df.loc[train_mask, ["sale_id", "unit_sales"]].reset_index(drop=True)
val_df = sales_df.loc[val_mask, ["sale_id", "unit_sales"]].reset_index(drop=True)
test_df = sales_df.loc[test_mask, ["sale_id"]].reset_index(drop=True)

print(
    f"Stores: {len(stores_df)}  Items: {len(items_df)}  Sales: {len(sales_df):,}"
)
print(
    f"Splits (temporal): train={len(train_df):,}  val={len(val_df):,}  test={len(test_df):,}"
)
print(
    f"Train: < {val_start.date()}; Val: {val_start.date()} -- {test_start.date()}; "
    f"Test: >= {test_start.date()}"
)
print(
    f"unit_sales: min={sales_df['unit_sales'].min()} mean={sales_df['unit_sales'].mean():.2f} "
    f"max={sales_df['unit_sales'].max()}"
)

TrainTable = Concept("TrainTable")
ValTable = Concept("ValTable")
TestTable = Concept("TestTable")
model.define(TrainTable.new(model.data(train_df).to_schema()))
model.define(ValTable.new(model.data(val_df).to_schema()))
model.define(TestTable.new(model.data(test_df).to_schema()))

# Regression task relationships. The split was already done temporally in
# pandas above (train < val_start, val < test_start, test >= test_start), so
# the GNN trains on the past and evaluates on the future; we just don't pass
# the time column into the GNN itself due to the SDK limitation noted at
# `time_col=` above.
Train = Relationship(f"{Sale} has {Any:value}")
model.define(Train(Sale, TrainTable.unit_sales)).where(
    Sale.sale_id == TrainTable.sale_id,
)
Val = Relationship(f"{Sale} has {Any:value}")
model.define(Val(Sale, ValTable.unit_sales)).where(
    Sale.sale_id == ValTable.sale_id,
)
Test = Relationship(f"{Sale}")
model.define(Test(Sale)).where(
    Sale.sale_id == TestTable.sale_id,
)

# --------------------------------------------------
# Train the GNN
# --------------------------------------------------

print("\n" + "=" * 60)
print("Predictive: demand-forecasting regression GNN (CPU)")
print("=" * 60)

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
    stream_logs=STREAM_LOGS,
    seed=SEED,
    device="cpu",
    n_epochs=20,
    lr=0.005,
)
gnn.fit()
Sale.predictions = gnn.predictions(domain=Test)

# --------------------------------------------------
# Reporting -- weekly per-(store, family) forecast
# --------------------------------------------------

print("\n" + "=" * 60)
print("Forecast (test window) -- weekly aggregate per (store, item family)")
print("=" * 60)

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

if results_df.empty:
    print("(no predictions returned)")
else:
    results_df["date"] = pd.to_datetime(results_df["date"])
    results_df["predicted"] = results_df["predicted"].astype(float).clip(lower=0)
    results_df["actual"] = results_df["actual"].astype(float)

    # Join store + item metadata for the rollup.
    results_df = results_df.merge(
        stores_df[["store_id", "city"]], on="store_id", how="left"
    ).merge(items_df[["item_id", "family"]], on="item_id", how="left")
    results_df["week_start"] = results_df["date"].dt.to_period("W").dt.start_time

    weekly = (
        results_df.groupby(["city", "family", "week_start"])[["actual", "predicted"]]
        .sum()
        .reset_index()
        .sort_values(["city", "family", "week_start"])
    )
    weekly["abs_err"] = (weekly["predicted"] - weekly["actual"]).abs()

    print(weekly.head(20).to_string(index=False))

    test_rmse = float(
        np.sqrt(((results_df["predicted"] - results_df["actual"]) ** 2).mean())
    )
    weekly_rmse = float(
        np.sqrt(((weekly["predicted"] - weekly["actual"]) ** 2).mean())
    )
    print(f"\nTest-set RMSE (per-Sale):           {test_rmse:.4f}")
    print(f"Test-set RMSE (per (city, family, week)): {weekly_rmse:.4f}")

print("\n" + "=" * 60)
print("Local run complete.")
print("=" * 60)
