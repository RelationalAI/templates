"""Bundled Favorita-shaped CSVs and the temporal train / validation / test split."""

from pathlib import Path

import pandas as pd

from .schema import (
    Item,
    ItemFamily,
    Sale,
    Store,
    Test,
    TestTable,
    Train,
    TrainTable,
    Val,
    ValTable,
    model,
)

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "favorita_mini"

TEST_DAYS = 60  # last 60 days as test window
VAL_DAYS = 60  # 60 days before test as validation

stores_df = pd.read_csv(DATA_DIR / "stores.csv")
items_df = pd.read_csv(DATA_DIR / "items.csv")
sales_df = pd.read_csv(DATA_DIR / "sales.csv", parse_dates=["date"])

model.define(Store.new(model.data(stores_df).to_schema()))
model.define(Item.new(model.data(items_df).to_schema()))
model.define(ItemFamily.new(family=Item.family))
model.define(Sale.new(model.data(sales_df).to_schema()))

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

train_df = sales_df.loc[train_mask, ["sale_id", "date", "unit_sales"]].reset_index(drop=True)
val_df = sales_df.loc[val_mask, ["sale_id", "date", "unit_sales"]].reset_index(drop=True)
test_df = sales_df.loc[test_mask, ["sale_id", "date"]].reset_index(drop=True)

model.define(TrainTable.new(model.data(train_df).to_schema()))
model.define(ValTable.new(model.data(val_df).to_schema()))
model.define(TestTable.new(model.data(test_df).to_schema()))

# The split was done temporally in pandas above (train < val_start,
# val < test_start, test >= test_start), so the GNN trains on the past and
# evaluates on the future.
model.define(Train(Sale, TrainTable.date, TrainTable.unit_sales)).where(
    Sale.sale_id == TrainTable.sale_id,
)
model.define(Val(Sale, ValTable.date, ValTable.unit_sales)).where(
    Sale.sale_id == ValTable.sale_id,
)
model.define(Test(Sale, TestTable.date)).where(
    Sale.sale_id == TestTable.sale_id,
)
