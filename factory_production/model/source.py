"""Load the sample factories and products into the factory production model, and check the data."""

from pathlib import Path

from pandas import read_csv

from .schema import Factory, Product, model

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# Load factories from CSV.
factory_csv = read_csv(DATA_DIR / "factories.csv")
model.define(Factory.new(model.data(factory_csv).to_schema()))

# Load products from CSV and link each product to its factory.
product_csv = read_csv(DATA_DIR / "products.csv")
product_data = model.data(product_csv)
model.define(
    p := Product.new(name=product_data.name, factory_name=product_data.factory_name),
    p.rate(product_data.rate),
    p.profit(product_data.profit),
    p.demand(product_data.demand),
)
model.define(Product.factory(Factory)).where(
    Product.factory_name(product_data.factory_name),
    Factory.name(product_data.factory_name),
)

# Guard the reference data. Every sensitivity check in the report is gated by a hard-coded
# factory/product name, so if data/ is edited those checks could silently pass on zero
# rows. Fail loudly here instead, with a clear message, the moment the data drifts.
EXPECTED_FACTORIES = {"steel_factory", "amazing_brewery"}
EXPECTED_PRODUCTS = {"bands", "coils", "stouts", "ales"}
if set(factory_csv["name"]) != EXPECTED_FACTORIES:
    raise ValueError(f"factories.csv changed: {set(factory_csv['name'])} != {EXPECTED_FACTORIES}")
if set(product_csv["name"]) != EXPECTED_PRODUCTS:
    raise ValueError(f"products.csv changed: {set(product_csv['name'])} != {EXPECTED_PRODUCTS}")
# Product names are unique across factories, so the report keys the plan by name alone.
if not product_csv["name"].is_unique:
    raise ValueError(f"product names are not unique across factories: {list(product_csv['name'])}")
