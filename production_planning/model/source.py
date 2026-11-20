"""Load the sample products, machines, production rates, and scenarios into the production planning model."""

from pathlib import Path

from pandas import read_csv

from .schema import Machine, Product, Rate, Scenario, model

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

product_csv = read_csv(DATA_DIR / "products.csv")
model.define(Product.new(model.data(product_csv).to_schema()))

machine_csv = read_csv(DATA_DIR / "machines.csv")
model.define(Machine.new(model.data(machine_csv).to_schema()))

rates_csv = read_csv(DATA_DIR / "production_rates.csv")
rates_data = model.data(rates_csv)
model.define(
    r := Rate.new(machine=Machine, product=Product, hours_per_unit=rates_data.hours_per_unit)
).where(Machine.id == rates_data.machine_id, Product.id == rates_data.product_id)

scenario_data = model.data(
    [("low_demand", 0.8), ("baseline", 1.0), ("high_demand", 1.1)],
    columns=["name", "demand_multiplier"],
)
model.define(Scenario.new(scenario_data.to_schema()))
