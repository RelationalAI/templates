"""Demand Forecasting (Snowflake source variant) -- predict per-(store, item, date)
unit sales with a GNN, against real Corporación Favorita data in Snowflake.

Identical ontology, splits, PropertyTransformer, and GNN config as the shipped
`demand_forecasting.py`. Differences:
  - Source data loads from FAVORITA.PUBLIC.{STORES, ITEMS, SALES} Snowflake
    tables (real Kaggle Favorita: 54 stores, 4100 items, 125M sale rows).
  - Subset materialized as Snowflake tables (FAVORITA.PREDICTIVE.*) so train /
    val / test splits flow through `Table(...).to_schema()` -- avoids the
    16MB LQP code-length cap that `model.data(df).to_schema()` hits at scale.
  - Subset knobs (TOP_N_STORES / TOP_M_ITEMS / RECENT_DAYS) control scale.

Run:
    python demand_forecasting_sf.py
"""

import os
import datetime as _dt

import numpy as np
import pandas as pd
import snowflake.connector
from cryptography.hazmat.primitives import serialization

from relationalai.semantics import Any, Float, Integer, Model, String, Table as _StubTable, select
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.predictive import GNN, PropertyTransformer

SEED = 42
STREAM_LOGS = False

TEST_DAYS = 60
VAL_DAYS = 60

# Subset over the full 125M-row Favorita SALES. With splits materialized in
# Snowflake (not packed inline), the only constraint is GPU training time.
TOP_N_STORES: int | None = 5
TOP_M_ITEMS: int | None = 50
RECENT_DAYS: int | None = 180

EXP_DATABASE = "FAVORITA"
EXP_SCHEMA = "EXPERIMENTS"

SOURCE_DATABASE = "FAVORITA"
SOURCE_SCHEMA = "PUBLIC"

PRED_DATABASE = "FAVORITA"
PRED_SCHEMA = "PREDICTIVE"


def _sf_conn():
    pk_path = os.path.expanduser("~/.snowflake/rai_private_key_new.p8")
    with open(pk_path, "rb") as f:
        pk = serialization.load_pem_private_key(f.read(), password=None)
    pkb = pk.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return snowflake.connector.connect(
        account="jqb21724",
        user="cameron.afzal@relational.ai",
        private_key=pkb,
        warehouse="DEMOWAREHOUSE",
        role="ACCOUNTADMIN",
        database=SOURCE_DATABASE,
        schema=SOURCE_SCHEMA,
    )


def _exec_sf(*sqls: str) -> None:
    with _sf_conn() as conn:
        cur = conn.cursor()
        for s in sqls:
            cur.execute(s)


def _scalar(sql: str):
    with _sf_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql)
        row = cur.fetchone()
    return row[0] if row else None


# ---------------------------------------------------------------------------
# Phase 1: materialize subset + train/val/test split tables in Snowflake
# ---------------------------------------------------------------------------
print("=== Phase 1: materializing subset tables in FAVORITA.PREDICTIVE ===")

_exec_sf(
    f"CREATE SCHEMA IF NOT EXISTS {PRED_DATABASE}.{PRED_SCHEMA}",
    f"GRANT USAGE ON SCHEMA {PRED_DATABASE}.{PRED_SCHEMA} TO APPLICATION RELATIONALAI",
)

# Subset SALES filtered to recent window + top-N stores + top-M items
date_filter = ""
if RECENT_DAYS is not None:
    date_filter = (
        f'WHERE TO_DATE("date") >= '
        f'(SELECT DATEADD(day, -{RECENT_DAYS}, MAX(TO_DATE("date"))) FROM {SOURCE_DATABASE}.{SOURCE_SCHEMA}.SALES)'
    )

extras = []
if TOP_N_STORES is not None:
    extras.append(
        f'"store_nbr" IN (SELECT "store_nbr" FROM {SOURCE_DATABASE}.{SOURCE_SCHEMA}.SALES '
        f'{date_filter} GROUP BY "store_nbr" ORDER BY SUM("unit_sales") DESC NULLS LAST LIMIT {TOP_N_STORES})'
    )
if TOP_M_ITEMS is not None:
    extras.append(
        f'"item_nbr" IN (SELECT "item_nbr" FROM {SOURCE_DATABASE}.{SOURCE_SCHEMA}.SALES '
        f'{date_filter} GROUP BY "item_nbr" ORDER BY SUM("unit_sales") DESC NULLS LAST LIMIT {TOP_M_ITEMS})'
    )
where_clause = date_filter
if extras:
    where_clause = (date_filter + (" AND " if date_filter else "WHERE ") + " AND ".join(extras))

_exec_sf(
    f"""
    CREATE OR REPLACE TABLE {PRED_DATABASE}.{PRED_SCHEMA}.SALES AS
    SELECT
      "id"           AS sale_id,
      TO_DATE("date") AS date,
      "store_nbr"    AS store_id,
      "item_nbr"     AS item_id,
      GREATEST(CAST("unit_sales" AS FLOAT), 0.0) AS unit_sales,
      COALESCE("onpromotion", FALSE)              AS onpromotion
    FROM {SOURCE_DATABASE}.{SOURCE_SCHEMA}.SALES
    {where_clause}
    """,
    f"""
    CREATE OR REPLACE TABLE {PRED_DATABASE}.{PRED_SCHEMA}.STORES AS
    SELECT "store_nbr" AS store_id, "city" AS city, "state" AS state, "type" AS store_type, "cluster" AS cluster
    FROM {SOURCE_DATABASE}.{SOURCE_SCHEMA}.STORES
    WHERE "store_nbr" IN (SELECT DISTINCT store_id FROM {PRED_DATABASE}.{PRED_SCHEMA}.SALES)
    """,
    f"""
    CREATE OR REPLACE TABLE {PRED_DATABASE}.{PRED_SCHEMA}.ITEMS AS
    SELECT "item_nbr" AS item_id, "family" AS family, "class" AS item_class, "perishable" AS perishable
    FROM {SOURCE_DATABASE}.{SOURCE_SCHEMA}.ITEMS
    WHERE "item_nbr" IN (SELECT DISTINCT item_id FROM {PRED_DATABASE}.{PRED_SCHEMA}.SALES)
    """,
)

n_sales = _scalar(f"SELECT COUNT(*) FROM {PRED_DATABASE}.{PRED_SCHEMA}.SALES")
n_stores = _scalar(f"SELECT COUNT(*) FROM {PRED_DATABASE}.{PRED_SCHEMA}.STORES")
n_items = _scalar(f"SELECT COUNT(*) FROM {PRED_DATABASE}.{PRED_SCHEMA}.ITEMS")
max_date = _scalar(f"SELECT MAX(date) FROM {PRED_DATABASE}.{PRED_SCHEMA}.SALES")
print(f"Subset: stores={n_stores}  items={n_items}  sales={n_sales:,}  max_date={max_date}")

if isinstance(max_date, _dt.date):
    test_start = max_date - _dt.timedelta(days=TEST_DAYS - 1)
    val_start = test_start - _dt.timedelta(days=VAL_DAYS)
else:
    raise RuntimeError(f"unexpected max_date type {type(max_date)}: {max_date!r}")

_exec_sf(
    f"""
    CREATE OR REPLACE TABLE {PRED_DATABASE}.{PRED_SCHEMA}.SALES_TRAIN AS
    SELECT sale_id, unit_sales FROM {PRED_DATABASE}.{PRED_SCHEMA}.SALES
    WHERE date < '{val_start.isoformat()}'
    """,
    f"""
    CREATE OR REPLACE TABLE {PRED_DATABASE}.{PRED_SCHEMA}.SALES_VAL AS
    SELECT sale_id, unit_sales FROM {PRED_DATABASE}.{PRED_SCHEMA}.SALES
    WHERE date >= '{val_start.isoformat()}' AND date < '{test_start.isoformat()}'
    """,
    f"""
    CREATE OR REPLACE TABLE {PRED_DATABASE}.{PRED_SCHEMA}.SALES_TEST AS
    SELECT sale_id FROM {PRED_DATABASE}.{PRED_SCHEMA}.SALES
    WHERE date >= '{test_start.isoformat()}'
    """,
    f"GRANT SELECT ON ALL TABLES IN SCHEMA {PRED_DATABASE}.{PRED_SCHEMA} TO APPLICATION RELATIONALAI",
    f"ALTER TABLE {PRED_DATABASE}.{PRED_SCHEMA}.STORES SET CHANGE_TRACKING = TRUE",
    f"ALTER TABLE {PRED_DATABASE}.{PRED_SCHEMA}.ITEMS SET CHANGE_TRACKING = TRUE",
    f"ALTER TABLE {PRED_DATABASE}.{PRED_SCHEMA}.SALES SET CHANGE_TRACKING = TRUE",
    f"ALTER TABLE {PRED_DATABASE}.{PRED_SCHEMA}.SALES_TRAIN SET CHANGE_TRACKING = TRUE",
    f"ALTER TABLE {PRED_DATABASE}.{PRED_SCHEMA}.SALES_VAL SET CHANGE_TRACKING = TRUE",
    f"ALTER TABLE {PRED_DATABASE}.{PRED_SCHEMA}.SALES_TEST SET CHANGE_TRACKING = TRUE",
)

n_train = _scalar(f"SELECT COUNT(*) FROM {PRED_DATABASE}.{PRED_SCHEMA}.SALES_TRAIN")
n_val = _scalar(f"SELECT COUNT(*) FROM {PRED_DATABASE}.{PRED_SCHEMA}.SALES_VAL")
n_test = _scalar(f"SELECT COUNT(*) FROM {PRED_DATABASE}.{PRED_SCHEMA}.SALES_TEST")
print(f"Splits: train={n_train:,}  val={n_val:,}  test={n_test:,}")
print(f"Train: < {val_start}; Val: {val_start} -- {test_start}; Test: >= {test_start}")

# ---------------------------------------------------------------------------
# Phase 2: define model + GNN
# ---------------------------------------------------------------------------
print("\n=== Phase 2: defining model + GNN ===")

model = Model("demand_forecasting_sf_v1")
Concept, Table, Relationship = model.Concept, model.Table, model.Relationship

Store = Concept("Store", identify_by={"store_id": Integer})
Item = Concept("Item", identify_by={"item_id": Integer})
ItemFamily = Concept("ItemFamily", identify_by={"family": String})
Sale = Concept("Sale", identify_by={"sale_id": Integer})

model.define(Store.new(Table(f"{PRED_DATABASE}.{PRED_SCHEMA}.STORES").to_schema()))
model.define(Item.new(Table(f"{PRED_DATABASE}.{PRED_SCHEMA}.ITEMS").to_schema()))
model.define(ItemFamily.new(family=Item.family))
model.define(Sale.new(Table(f"{PRED_DATABASE}.{PRED_SCHEMA}.SALES").to_schema()))

gnn_graph = Graph(model, directed=True, weighted=False)
Edge = gnn_graph.Edge
model.define(Edge.new(src=Sale, dst=Store)).where(Sale.store_id == Store.store_id)
model.define(Edge.new(src=Sale, dst=Item)).where(Sale.item_id == Item.item_id)
model.define(Edge.new(src=Item, dst=ItemFamily)).where(Item.family == ItemFamily.family)

pt = PropertyTransformer(
    drop=[
        Sale.sale_id,
        Sale.store_id,
        Sale.item_id,
        Store.store_id,
        Item.item_id,
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
)

TrainTable = Concept("TrainTable")
ValTable = Concept("ValTable")
TestTable = Concept("TestTable")
model.define(TrainTable.new(Table(f"{PRED_DATABASE}.{PRED_SCHEMA}.SALES_TRAIN").to_schema()))
model.define(ValTable.new(Table(f"{PRED_DATABASE}.{PRED_SCHEMA}.SALES_VAL").to_schema()))
model.define(TestTable.new(Table(f"{PRED_DATABASE}.{PRED_SCHEMA}.SALES_TEST").to_schema()))

Train = Relationship(f"{Sale} has {Any:value}")
model.define(Train(Sale, TrainTable.unit_sales)).where(Sale.sale_id == TrainTable.sale_id)
Val = Relationship(f"{Sale} has {Any:value}")
model.define(Val(Sale, ValTable.unit_sales)).where(Sale.sale_id == ValTable.sale_id)
Test = Relationship(f"{Sale}")
model.define(Test(Sale)).where(Sale.sale_id == TestTable.sale_id)

print("\n" + "=" * 60)
print("Predictive: demand-forecasting regression GNN (SF source, GPU)")
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

print("\n" + "=" * 60)
print("Forecast (test window) -- weekly aggregate per (city, family)")
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

    with _sf_conn() as _c:
        _cur = _c.cursor()
        _cur.execute(f"SELECT store_id, city FROM {PRED_DATABASE}.{PRED_SCHEMA}.STORES")
        stores_meta = _cur.fetch_pandas_all()
        _cur.execute(f"SELECT item_id, family FROM {PRED_DATABASE}.{PRED_SCHEMA}.ITEMS")
        items_meta = _cur.fetch_pandas_all()
    stores_meta.columns = stores_meta.columns.str.lower()
    items_meta.columns = items_meta.columns.str.lower()
    results_df = results_df.merge(stores_meta, on="store_id", how="left").merge(
        items_meta, on="item_id", how="left"
    )
    results_df["week_start"] = results_df["date"].dt.to_period("W").dt.start_time
    weekly = (
        results_df.groupby(["city", "family", "week_start"])[["actual", "predicted"]]
        .sum()
        .reset_index()
        .sort_values(["city", "family", "week_start"])
    )
    weekly["abs_err"] = (weekly["predicted"] - weekly["actual"]).abs()
    print(weekly.head(20).to_string(index=False))

    test_rmse = float(np.sqrt(((results_df["predicted"] - results_df["actual"]) ** 2).mean()))
    weekly_rmse = float(np.sqrt(((weekly["predicted"] - weekly["actual"]) ** 2).mean()))
    print(f"\nTest-set RMSE (per-Sale):           {test_rmse:.4f}")
    print(f"Test-set RMSE (per (city, family, week)): {weekly_rmse:.4f}")

print("\n" + "=" * 60)
print("Run complete.")
print("=" * 60)
