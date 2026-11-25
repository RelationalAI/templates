"""Bundled Favorita-shaped CSVs."""

from pathlib import Path

import pandas as pd

from .schema import Item, ItemFamily, Sale, Store, model

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "favorita_mini"

stores_df = pd.read_csv(DATA_DIR / "stores.csv")
items_df = pd.read_csv(DATA_DIR / "items.csv")
sales_df = pd.read_csv(DATA_DIR / "sales.csv", parse_dates=["date"])

model.define(Store.new(model.data(stores_df).to_schema()))
model.define(Item.new(model.data(items_df).to_schema()))
model.define(ItemFamily.new(family=Item.family))
model.define(Sale.new(model.data(sales_df).to_schema()))
