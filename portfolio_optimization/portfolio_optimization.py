"""Portfolio Optimization - Minimize portfolio risk for a given return target (Markowitz)."""

from pathlib import Path
from time import time_ns

from pandas import read_csv
from relationalai.semantics import Float, Model, data, require, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel


def define_model(config=None):
    """Define base model with Stock concept and covariance data."""
    model = Model(f"portfolio_{time_ns()}", config=config, use_lqp=False)

    # Concept: stock with expected returns
    Stock = model.Concept("Stock")
    Stock.returns = model.Property("{Stock} has {returns:float}")

    # Covariance relationship between stock pairs
    Stock.covar = model.Property("{Stock} and {stock2:Stock} have {covar:float}")
    Stock2 = Stock.ref()

    # Load stock returns
    data_dir = Path(__file__).parent / "data"
    returns_csv = read_csv(data_dir / "returns.csv")
    data(returns_csv).into(Stock, keys=["index"])

    # Load covariance matrix
    covar_csv = read_csv(data_dir / "covariance.csv")
    pairs = data(covar_csv)
    where(Stock.index(pairs.i), Stock2.index(pairs.j)).define(
        Stock.covar(Stock, Stock2, pairs.covar)
    )

    model.Stock = Stock
    model.Stock2 = Stock2
    return model


def define_problem(model, min_return=20, budget=1000):
    """Define decision variables, constraints, and objective."""
    Stock = model.Stock
    Stock2 = model.Stock2

    # Decision variable: quantity of each stock
    Stock.quantity = model.Property("{Stock} quantity is {x:float}")

    # Objective: minimize portfolio risk (variance)
    c = Float.ref()
    risk = sum(c * Stock.quantity * Stock2.quantity).where(Stock.covar(Stock2, c))

    # Constraints
    bounds = require(Stock.quantity >= 0)  # No short selling
    budget_constraint = require(sum(Stock.quantity) <= budget)
    return_constraint = require(sum(Stock.returns * Stock.quantity) >= min_return)

    # Build solver model
    s = SolverModel(model, "cont")
    s.solve_for(Stock.quantity, name=["qty", Stock.index], populate=False)
    s.minimize(risk)
    s.satisfy(bounds)
    s.satisfy(budget_constraint)
    s.satisfy(return_constraint)

    return s


def solve(config=None, solver_name="highs", min_return=20, budget=1000):
    """Orchestrate model, problem, and solver execution."""
    model = define_model(config)
    solver_model = define_problem(model, min_return=min_return, budget=budget)

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
    min_return = 20
    sm = solve(min_return=min_return)
    sol = extract_solution(sm)

    print(f"Status: {sol['status']}")
    print(f"Portfolio risk (variance): {sol['objective']:.4f}")
    print(f"Minimum return target: {min_return}")
    print("\nStock allocations:")
    df = sol["variables"]
    active = df[df["float"] > 0] if "float" in df.columns else df
    print(active.to_string(index=False))
