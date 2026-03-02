"""Diet optimization (prescriptive optimization) template.

This script demonstrates a classic diet linear optimization problem in RelationalAI:

- Load sample CSVs describing foods, nutrients, and per-food nutrient quantities.
- Model foods and nutrients as *concepts*.
- Choose a non-negative amount of each food to satisfy nutrient bounds.
- Minimize total cost.

Run:
    `python diet.py`

Output:
    Prints the solver termination status, objective value, and a table of foods
    with non-trivial amounts.
"""

from pathlib import Path

import pandas
from pandas import read_csv

from relationalai.semantics import Model, data, define, require, select, sum
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

# --------------------------------------------------
# Configure inputs and create the model
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"

# Disable pandas inference of string types. This ensures that string columns
# in the CSVs are loaded as object dtype. This is only required when using
# relationalai versions prior to v1.0.
pandas.options.future.infer_string = False

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

# Create a Semantics model container.
model = Model("diet", config=globals().get("config", None), use_lqp=False)

# Nutrient concept: represents a nutrient with minimum and maximum daily requirements.
Nutrient = model.Concept("Nutrient")
Nutrient.name = model.Property("{Nutrient} is named {name:string}")
Nutrient.min = model.Property("{Nutrient} has minimum daily requirement {min:float}")
Nutrient.max = model.Property("{Nutrient} has maximum daily requirement {max:float}")

nutrient_csv = read_csv(DATA_DIR / "nutrients.csv")
data(nutrient_csv).into(Nutrient, keys=["name"])

# Food concept: foods have a cost and contain nutrients in some quantity.
Food = model.Concept("Food")
Food.nutrients = model.Relationship("{Food} contains {qty:float} of {Nutrient}")
Food.cost = model.Property("{Food} costs {cost:float}")

food_csv = read_csv(DATA_DIR / "foods.csv")
food_data = data(food_csv)

# Create one Food entity per row in the food data and define its cost.
food = Food.new(name=food_data.name)
define(food, food.cost(food_data.cost))

# Define nutrient quantities for each food by iterating the nutrient columns.
for nutrient_name in nutrient_csv.name:
    define(Food.nutrients(food, food_data[nutrient_name], Nutrient)).where(
        Nutrient.name == nutrient_name
    )

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

# Create a continuous optimization model.
s = SolverModel(model, "cont")

# Decision Variable: amount of each food (continuous, non-negative)
Food.x_amount = model.Property("{Food} has {x_amount:float}")
s.solve_for(Food.x_amount, name=Food.name, lower=0)

# Calculate total quantity of each nutrient across all foods: sum(qty * amount) per nutrient.
nutrient_total = sum(
    Food.nutrients["qty"] * Food.x_amount
).where(
    Food.nutrients == Nutrient
).per(Nutrient)

# Constraint: nutrient totals must be within specified bounds.
nutrient_bounds = require(
    nutrient_total >= Nutrient.min,
    nutrient_total <= Nutrient.max
)
s.satisfy(nutrient_bounds)

# Objective: minimize total cost
total_cost = sum(Food.cost * Food.x_amount)
s.minimize(total_cost)

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

# Solve the model with a time limit of 60 seconds using the HiGHS solver.
solver = Solver("highs")
s.solve(solver, time_limit_sec=60)

print(f"Status: {s.termination_status}")
print(f"Minimum cost: ${s.objective_value:.2f}")

# Select the foods with non-trivial amounts in the optimal solution.
diet_plan = select(Food.name, Food.x_amount).where(Food.x_amount > 0.001).to_df()

print("\nOptimal diet:")
print(diet_plan.to_string(index=False))
