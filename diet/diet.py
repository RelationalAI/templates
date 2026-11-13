"""Diet optimization (prescriptive optimization) template.

This script demonstrates a classic diet linear optimization problem in RelationalAI:

- Map sample data from CSVs describing foods, nutrients, and per-food nutrient quantities.
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
    `python diet.py` deploys the model to the schema in raiconfig.yaml, waits for
    its first refresh (which runs the solve), and prints the report from the
    deployed model.

Output:
    Prints per-scenario termination status, objective value, and a table of foods
    with non-trivial amounts, followed by a scenario analysis summary.
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Float, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"

# --------------------------------------------------
# Define semantic model & map data
# --------------------------------------------------

model = Model("diet")

# Nutrient concept: nutritional requirements with min/max bounds.
Nutrient = model.Concept("Nutrient", identify_by={"name": String})
Nutrient.min = model.Property(f"{Nutrient} has {Float:min}")
Nutrient.max = model.Property(f"{Nutrient} has {Float:max}")

# Map nutrients data from CSV.
nutrient_csv = read_csv(DATA_DIR / "nutrients.csv")
model.define(Nutrient.new(model.data(nutrient_csv).to_schema()))

# Food concept: foods with cost and per-nutrient content (ternary property).
Food = model.Concept("Food", identify_by={"name": String})
Food.cost = model.Property(f"{Food} has {Float:cost}")
Food.contains = model.Property(f"{Food} contains {Nutrient} in {Float:qty}")

# Map foods data from CSV (one column per nutrient name).
food_csv = read_csv(DATA_DIR / "foods.csv")
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

problem = Problem(model, Float)

# Variable: amount of each food per scenario (non-negative)
problem.solve_for(Food.x_amount(Scenario, x_amt), name=["amt", Scenario.scenario_name, Food.name], lower=0)

# Constraint: nutrient bounds scaled by scenario parameter (per nutrient, per scenario)
nutrient_qty = Float.ref()
problem.satisfy(model.where(
    Food.x_amount(Scenario, x_amt),
    Food.contains(Nutrient, nutrient_qty),
).require(
    sum(Food, nutrient_qty * x_amt).per(Nutrient, Scenario) >= Nutrient.min * Scenario.nutrient_scaling,
    sum(Food, nutrient_qty * x_amt).per(Nutrient, Scenario) <= Nutrient.max * Scenario.nutrient_scaling,
))

# Objective: minimize total cost
problem.minimize(sum(Food, Scenario, Food.cost * x_amt).where(Food.x_amount(Scenario, x_amt)))

# --------------------------------------------------
# Solve (single solve for all scenarios)
# --------------------------------------------------

# Each refresh of the deployed model runs this solve.
problem.configure("highs", time_limit_sec=60)

# Deploy the rules behind problem.display() with the model.
problem.install_display_strings()

# The solve's status and objective, published through the model's own relationships.
SolveStatus = model.Relationship(f"diet solve status is {String:status}")
TotalCost = model.Relationship(f"diet total cost is {Float:cost}")
model.define(SolveStatus(problem.termination_status()), TotalCost(problem.objective_value()))

# --------------------------------------------------
# Deploy, then report (`rai models deploy` skips this block)
# --------------------------------------------------

if __name__ == "__main__":
    # Deploy and wait for the first refresh, which runs the solve.
    model.deploy()

    problem.display()

    # Status and objective of the latest refresh's solve. A refresh records any
    # termination status, so the report checks it.
    status = model.select(SolveStatus).to_df().iloc[:, 0].tolist()
    cost = model.select(TotalCost).to_df().iloc[:, 0].tolist()
    print(f"\nSolve result:\n• status: {', '.join(status)}")
    if status != ["OPTIMAL"]:
        raise SystemExit(f"No optimal diet plan: termination status {status}")
    print(f"• objective: {round(cost[0], 9)}\n")

    print("\nDiet plan per scenario:")
    model.select(
        Scenario.scenario_name.alias("scenario"),
        Food.name.alias("food"),
        Food.cost,
        x_amt.alias("amount"),
    ).where(Food.x_amount(Scenario, x_amt), x_amt > 0.001).inspect()
