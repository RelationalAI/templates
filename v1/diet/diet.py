"""Diet optimization (prescriptive optimization) template.

This script demonstrates a classic diet linear optimization problem in RelationalAI:

- Load sample CSVs describing foods, nutrients, and per-food nutrient quantities.
- Model foods and nutrients as *concepts* with typed properties.
- Choose a non-negative amount of each food to satisfy nutrient bounds.
- Minimize total cost.
- Solve multiple scenarios scaling nutrient requirements using Scenario as a
  first-class Concept (single solve, all scenarios simultaneously).

Modeling approach:
- Scenario is a Concept with a nutrient_scaling parameter property.
- Decision variables are multi-argument Properties indexed by (Food, Scenario).
- Constraints use ref() bindings + .per(Scenario) to scope per-scenario.
- One solve handles all scaling levels; results extracted via model.select().

Run:
    `python diet.py`

Output:
    Prints per-scenario termination status, objective value, and a table of foods
    with non-trivial amounts, followed by a scenario analysis summary.
"""

from pathlib import Path

from pandas import read_csv

from relationalai.semantics import Float, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("diet")

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Concept: nutrients with min/max bounds
Nutrient = model.Concept("Nutrient", identify_by={"name": String})
Nutrient.min = model.Property(f"{Nutrient} has {Float:min}")
Nutrient.max = model.Property(f"{Nutrient} has {Float:max}")
nutrient_csv = read_csv(data_dir / "nutrients.csv")
model.define(Nutrient.new(model.data(nutrient_csv).to_schema()))

# Concept: foods with cost and nutrient content (ternary property)
Food = model.Concept("Food", identify_by={"name": String})
Food.cost = model.Property(f"{Food} has {Float:cost}")
Food.contains = model.Property(f"{Food} contains {Nutrient} in {Float:qty}")
food_csv = read_csv(data_dir / "foods.csv")
food_data = model.data(food_csv)
model.define(food := Food.new(name=food_data.name), food.cost(food_data.cost))
for nutrient_name in nutrient_csv.name:
    model.define(food.contains(Nutrient, getattr(food_data, nutrient_name))).where(
        Nutrient.name == nutrient_name
    )

# --------------------------------------------------
# Scenario Concept — nutrient_scaling parameter variations
# --------------------------------------------------

Scenario = model.Concept("Scenario", identify_by={"scenario_name": String})
Scenario.nutrient_scaling = model.Property(f"{Scenario} has {Float:nutrient_scaling}")
scenario_data = model.data(
    [("scaling_80pct", 0.8), ("baseline", 1.0), ("scaling_120pct", 1.2)],
    columns=["scenario_name", "nutrient_scaling"],
)
model.define(Scenario.new(scenario_data.to_schema()))

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

# Decision variable — indexed by Scenario (multi-argument Property)
Food.x_amount = model.Property(f"{Food} in {Scenario} has {Float:amount}")

# Ref for binding multi-arg variable in constraints
x_amt = Float.ref()

s = Problem(model, Float)

# Variable: amount of each food per scenario (non-negative)
s.solve_for(Food.x_amount(Scenario, x_amt), name=["amt", Scenario.scenario_name, Food.name], lower=0)

# Constraint: nutrient bounds scaled by scenario parameter (per nutrient, per scenario)
nutrient_qty = Float.ref()
s.satisfy(model.where(
    Food.x_amount(Scenario, x_amt),
    Food.contains(Nutrient, nutrient_qty),
).require(
    sum(nutrient_qty * x_amt).per(Nutrient, Scenario) >= Nutrient.min * Scenario.nutrient_scaling,
    sum(nutrient_qty * x_amt).per(Nutrient, Scenario) <= Nutrient.max * Scenario.nutrient_scaling,
))

# Objective: minimize total cost
s.minimize(
    sum(Food.cost * x_amt)
    .where(Food.x_amount(Scenario, x_amt))
)

# --------------------------------------------------
# Solve (single solve for all scenarios)
# --------------------------------------------------

s.display()
s.solve("highs", time_limit_sec=60)
s.display_solve_info()

# --------------------------------------------------
# Extract results per scenario
# --------------------------------------------------

print("\nDiet plan per scenario:")
model.select(
    Scenario.scenario_name.alias("scenario"),
    Food.name.alias("food"),
    Food.cost,
    x_amt.alias("amount"),
).where(
    Food.x_amount(Scenario, x_amt), x_amt > 0.001
).inspect()
