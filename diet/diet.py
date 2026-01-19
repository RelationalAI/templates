"""Diet Optimization - Select foods to satisfy nutritional requirements at minimum cost."""

from pathlib import Path
from time import time_ns

from pandas import read_csv
from relationalai.semantics import Model, data, define, require, sum
from relationalai.semantics.reasoners.optimization import Solver, SolverModel


def define_model(config=None):
    """Define base model with Food and Nutrient concepts."""
    model = Model(f"diet_{time_ns()}", config=config, use_lqp=False)

    # Concepts
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

    # Store references
    model.Nutrient = Nutrient
    model.Food = Food

    return model


def define_problem(model):
    """Define decision variables, constraints, and objective."""
    Food = model.Food
    Nutrient = model.Nutrient

    # Decision variable: amount of each food to purchase
    Food.amount = model.Property("{Food} has {amount:float}")

    # Objective: minimize total cost
    total_cost = sum(Food.cost * Food.amount)

    # Constraint: nutrient totals must be within bounds
    nutrient_total = sum(Food.contains.qty * Food.amount).where(
        Food.contains.nutrient == Nutrient
    ).per(Nutrient)
    nutrient_bounds = require(
        nutrient_total >= Nutrient.min,
        nutrient_total <= Nutrient.max
    )

    # Build solver model
    s = SolverModel(model, "cont")
    s.solve_for(Food.amount, name=Food.name, lower=0)
    s.minimize(total_cost)
    s.satisfy(nutrient_bounds)

    return s


def solve(config=None, solver_name="highs"):
    """Orchestrate model, problem, and solver execution."""
    model = define_model(config)
    solver_model = define_problem(model)

    solver = Solver(solver_name)
    solver_model.solve(solver, time_limit_sec=60)

    return solver_model


def extract_solution(solver_model):
    """Extract solution as dict with metadata."""
    return {
        "status": solver_model.termination_status,
        "objective": solver_model.objective_value,
        "variables": solver_model.variable_values().to_df(),
    }


if __name__ == "__main__":
    sm = solve()
    sol = extract_solution(sm)

    print(f"Status: {sol['status']}")
    print(f"Minimum cost: ${sol['objective']:.2f}")
    print("\nFood amounts:")
    print(sol["variables"].to_string(index=False))
