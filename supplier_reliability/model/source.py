"""Load the sample suppliers, products, and supply options into the supplier reliability model."""

from pathlib import Path

from pandas import read_csv

from .schema import Product, Supplier, SupplyOption, model

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

supplier_csv = read_csv(DATA_DIR / "suppliers.csv")
model.define(Supplier.new(model.data(supplier_csv).to_schema()))

product_csv = read_csv(DATA_DIR / "products.csv")
model.define(Product.new(model.data(product_csv).to_schema()))

options_csv = read_csv(DATA_DIR / "supply_options.csv")
options_data = model.data(options_csv)
model.define(
    SupplyOption.new(
        id=options_data.id,
        supplier=Supplier,
        product=Product,
        cost_per_unit=options_data.cost_per_unit,
    )
).where(Supplier.id == options_data.supplier_id, Product.id == options_data.product_id)
