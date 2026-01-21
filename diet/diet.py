"""Diet Optimization - Select foods to satisfy nutritional requirements at minimum cost.

This template demonstrates:
- Linear programming (LP) with continuous variables
- Accessing solutions via populated relations (not variable_values())
"""

from pathlib import Path
from time import time_ns

from pandas import read_csv
from relationalai.semantics import Model, data, define, require, select, sum
from relationalai.semantics.reasoners.optimization import Solver, SolverModel


def solve(config=None, solver_name="highs"):
    """
    Build and solve the diet optimization problem.

    Returns the model (with populated solution relations) and solver model.
    """
    # =========================================================================
    # 1. Create model and load data
    # =========================================================================
    model = Model(f"diet_{time_ns()}", config=config, use_lqp=False)

    # Define concepts
    Nutrient = model.Concept("Nutrient")
    Food = model.Concept("Food")
    Food.contains = model.Property("{Food} contains {Nutrient} in {qty:float}")

    # Load nutrients (with min/max bounds)
    data_dir = Path(__file__).parent / "data"
    nutrient_csv = read_csv(data_dir / "nutrients.csv")
    data(nutrient_csv).into(Nutrient, keys=["name"])

    # Load foods (with cost and nutrient content)
    food_csv = read_csv(data_dir / "foods.csv")
    food_data = data(food_csv)
    food = Food.new(name=food_data.name)
    define(food, food.cost(food_data.cost))

    # Link foods to nutrients with quantities
    for nutrient_name in nutrient_csv.name:
        define(
            Food.contains(food, Nutrient, getattr(food_data, nutrient_name))
        ).where(Nutrient.name == nutrient_name)

    # =========================================================================
    # 2. Define decision variable
    # =========================================================================
    # Food.amount is the decision variable - it will be populated by solve()
    Food.amount = model.Property("{Food} has {amount:float}")

    # =========================================================================
    # 3. Build optimization problem
    # =========================================================================
    s = SolverModel(model, "cont")

    # Decision variable: amount of each food to purchase (continuous, non-negative)
    s.solve_for(Food.amount, name=Food.name, lower=0)

    # Objective: minimize total cost
    total_cost = sum(Food.cost * Food.amount)
    s.minimize(total_cost)

    # Constraint: nutrient totals must be within bounds
    nutrient_total = sum(Food.contains.qty * Food.amount).where(
        Food.contains.nutrient == Nutrient
    ).per(Nutrient)
    s.satisfy(require(
        nutrient_total >= Nutrient.min,
        nutrient_total <= Nutrient.max
    ))

    # =========================================================================
    # 4. Solve
    # =========================================================================
    solver = Solver(solver_name)
    s.solve(solver, time_limit_sec=60)

    # Store references for solution access
    s.model = model
    s.Food = Food
    s.Nutrient = Nutrient

    return s


def extract_solution(solver_model):
    """Extract solution as meaningful dataframe (not internal solver hashes)."""
    Food = solver_model.Food
    df = select(Food.name, Food.amount).to_df()
    # Filter to foods actually in the diet
    df = df[df["amount"] > 0.001]
    return {
        "status": solver_model.termination_status,
        "objective": solver_model.objective_value,
        "diet": df,
    }


if __name__ == "__main__":
    # Run the optimization
    solver_model = solve()

    print(f"Status: {solver_model.termination_status}")
    print(f"Minimum cost: ${solver_model.objective_value:.2f}")

    # =========================================================================
    # Access solution via populated relations (PREFERRED)
    # =========================================================================
    # After solve(), the Food.amount relation is populated with optimal values.
    # Query it directly using select() - this gives meaningful domain data,
    # not internal solver hashes.

    Food = solver_model.Food
    diet_plan = select(Food.name, Food.amount).to_df()

    # Filter to foods actually in the diet (amount > small threshold)
    diet_plan = diet_plan[diet_plan["amount"] > 0.001]

    print("\nOptimal diet:")
    print(diet_plan.to_string(index=False))
