"""Load the sample products, discounts, and weeks into the retail markdown model."""

from pathlib import Path

from pandas import read_csv

from .schema import Discount, Product, Week, model

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

product_csv = read_csv(DATA_DIR / "products.csv")
model.define(Product.new(model.data(product_csv).to_schema()))

discount_csv = read_csv(DATA_DIR / "discounts.csv")
model.define(Discount.new(model.data(discount_csv).to_schema()))

week_csv = read_csv(DATA_DIR / "weeks.csv")
model.define(Week.new(model.data(week_csv).to_schema()))
