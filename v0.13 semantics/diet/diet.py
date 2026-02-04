# diet optimization problem:
# select foods to satisfy nutritional requirements at minimum cost

from pathlib import Path

from pandas import read_csv

from relationalai.semantics import Model, data, define, require, select, sum
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

model = Model("diet", config=globals().get("config", None), use_lqp=False)

# --------------------------------------------------
# Define ontology & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Concept: nutrients with min/max bounds
Nutrient = model.Concept("Nutrient")
nutrient_csv = read_csv(data_dir / "nutrients.csv")
data(nutrient_csv).into(Nutrient, keys=["name"])

# Concept: foods with cost and nutrient content
Food = model.Concept("Food")
Food.contains = model.Property("{Food} contains {Nutrient} in {qty:float}")

food_csv = read_csv(data_dir / "foods.csv")
food_data = data(food_csv)
food = Food.new(name=food_data.name)
define(food, food.cost(food_data.cost))

for nutrient_name in nutrient_csv.name:
    define(
        Food.contains(food, Nutrient, getattr(food_data, nutrient_name))
    ).where(Nutrient.name == nutrient_name)

# --------------------------------------------------
# Model the problem
# --------------------------------------------------

s = SolverModel(model, "cont")

# Variable: amount of each food (continuous, non-negative)
Food.amount = model.Property("{Food} has {amount:float}")
s.solve_for(Food.amount, name=Food.name, lower=0)

# Constraint: nutrient totals must be within bounds
nutrient_total = sum(Food.contains.qty * Food.amount).where(
    Food.contains.nutrient == Nutrient
).per(Nutrient)
nutrient_bounds = require(
    nutrient_total >= Nutrient.min,
    nutrient_total <= Nutrient.max
)
s.satisfy(nutrient_bounds)

# Objective: minimize total cost
total_cost = sum(Food.cost * Food.amount)
s.minimize(total_cost)

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

solver = Solver("highs")
s.solve(solver, time_limit_sec=60)

print(f"Status: {s.termination_status}")
print(f"Minimum cost: ${s.objective_value:.2f}")

diet_plan = select(Food.name, Food.amount).to_df()
diet_plan = diet_plan[diet_plan["amount"] > 0.001]

print("\nOptimal diet:")
print(diet_plan.to_string(index=False))
