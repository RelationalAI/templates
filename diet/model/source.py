"""Load the sample foods, nutrients, and scenarios into the diet model."""

from pathlib import Path

from pandas import read_csv

from .schema import Food, Nutrient, Scenario, model

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# Map nutrients data from CSV.
nutrient_csv = read_csv(DATA_DIR / "nutrients.csv")
model.define(Nutrient.new(model.data(nutrient_csv).to_schema()))

# Map foods data from CSV (one column per nutrient name).
food_csv = read_csv(DATA_DIR / "foods.csv")
food_data = model.data(food_csv)
model.define(food := Food.new(name=food_data.name), food.cost(food_data.cost))
for nutrient_name in nutrient_csv.name:
    model.define(food.contains(Nutrient, getattr(food_data, nutrient_name))).where(
        Nutrient.name == nutrient_name
    )

# Scenarios scale every nutrient bound by their factor.
scenario_data = model.data(
    [("scaling_80pct", 0.8), ("baseline", 1.0), ("scaling_120pct", 1.2)],
    columns=["scenario_name", "nutrient_scaling"],
)
model.define(Scenario.new(scenario_data.to_schema()))
