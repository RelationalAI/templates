"""Diet optimization (prescriptive optimization) template.

This script demonstrates a classic diet linear optimization problem in RelationalAI:

- Load sample CSVs describing foods, nutrients, and per-food nutrient quantities.
- Model foods and nutrients as *concepts* with typed properties.
- Choose a non-negative amount of each food to satisfy nutrient bounds.
- Minimize total cost.
- Solve multiple scenarios scaling nutrient requirements to illustrate what-if analysis.

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
# Model the decision problem
# --------------------------------------------------

# Decision variable property (defined on model, solved per scenario)
Food.x_amount = model.Property(f"{Food} has {Float:amount}")

# Scenarios (what-if analysis)
SCENARIO_PARAM = "nutrient_scaling"
SCENARIO_VALUES = [0.8, 1.0, 1.2]

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

scenario_results = []

for scenario_value in SCENARIO_VALUES:
    print(f"\nRunning scenario: {SCENARIO_PARAM} = {scenario_value}")

    # Create fresh Problem for each scenario
    s = Problem(model, Float)
    s.solve_for(Food.x_amount, name=Food.name, lower=0, populate=False)
    nutrient_qty = Float.ref()
    nutrient_total = sum(nutrient_qty * Food.x_amount).where(Food.contains(Nutrient, nutrient_qty)).per(Nutrient)
    s.satisfy(model.require(
        nutrient_total >= Nutrient.min * scenario_value,
        nutrient_total <= Nutrient.max * scenario_value
    ))
    s.minimize(sum(Food.cost * Food.x_amount))

    s.display()
    s.solve("highs", time_limit_sec=60, _server_side_import=False)
    s.display_solve_info()

    scenario_results.append({
        "scenario": scenario_value,
        "status": str(s.termination_status),
        "objective": s.objective_value,
    })
    print(f"  Status: {s.termination_status}, Objective: ${s.objective_value:.2f}")

    # Extract solution via variable_values() — populate=False avoids overwriting between scenarios
    var_df = s.variable_values().to_df()
    chosen = var_df[var_df["value"] > 0.001]
    print(f"  Diet plan:\n{chosen.to_string(index=False)}")

# Summary
print("\n" + "=" * 50)
print("Scenario Analysis Summary")
print("=" * 50)
for result in scenario_results:
    print(f"  scaling={result['scenario']}: {result['status']}, cost=${result['objective']:.2f}")
