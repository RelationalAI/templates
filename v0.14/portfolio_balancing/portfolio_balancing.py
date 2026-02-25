"""Portfolio Balancing (prescriptive optimization) template.

This script demonstrates a classic Markowitz mean-variance portfolio optimization model in RelationalAI:

- Load expected returns and a covariance matrix from CSV.
- Choose non-negative allocations across available stocks.
- Enforce a budget constraint and a minimum expected return constraint.
- Minimize portfolio variance (risk).
- Solve multiple minimum-return scenarios to illustrate the efficient frontier.

Run:
    `python portfolio_balancing.py`

Output:
    Prints per-scenario termination status and objective value, a non-trivial
    allocation table for each scenario, and a summary of scenario objectives.
"""

from pathlib import Path

import pandas
from pandas import read_csv

from relationalai.semantics import Float, Model, Relationship, data, require, select, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"

# Disable pandas inference of string types. This ensures that string columns
# in the CSVs are loaded as object dtype. This is only required when using
# relationalai versions prior to v1.0.
pandas.options.future.infer_string = False

# Budget and minimum return parameters.
BUDGET = 1000
MIN_RETURN = 20

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

# Create a Semantics model container.
model = Model("portfolio", config=globals().get("config", None))

# Stock concept: available investments with expected returns.
Stock = model.Concept("Stock")
Stock.returns = model.Property("{Stock} has {returns:float}")

# Load expected return data from CSV.
data(read_csv(DATA_DIR / "returns.csv")).into(Stock, keys=["index"])

# Stock.covar property: covariance matrix between stock pairs.
Stock.covar = model.Relationship("{Stock} and {stock2:Stock} have {covar:float}")
Stock2 = Stock.ref()

# Load covariance data from CSV.
covar_csv = read_csv(DATA_DIR / "covariance.csv")
pairs = data(covar_csv)
where(
    Stock.index == pairs.i,
    Stock2.index == pairs.j
).define(
    Stock.covar(Stock, Stock2, pairs.covar)
)

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

# Stock.x_quantity decision variable: amount allocated to each stock.
Stock.x_quantity = model.Property("{Stock} quantity is {x:float}")

c = Float.ref()

# Scenario parameter. This is updated inside the scenario loop.
min_return = MIN_RETURN

# Budget is fixed across scenarios.
budget = BUDGET


def build_formulation(s):
    """Register variables, constraints, and objective on the solver model."""
    # Decision variable: quantity of each stock.
    s.solve_for(Stock.x_quantity, name=["qty", Stock.index])

    # Constraint: no short selling.
    bounds = require(Stock.x_quantity >= 0)
    s.satisfy(bounds)

    # Constraint: budget limit.
    budget_constraint = require(sum(Stock.x_quantity) <= budget)
    s.satisfy(budget_constraint)

    # Constraint: minimum return target (scenario parameter).
    return_constraint = require(sum(Stock.returns * Stock.x_quantity) >= min_return)
    s.satisfy(return_constraint)

    # Objective: minimize portfolio risk (variance)
    risk = sum(c * Stock.x_quantity * Stock2.x_quantity).where(Stock.covar(Stock2, c))
    s.minimize(risk)

# --------------------------------------------------
# Solve with Scenario Analysis (Numeric Parameter)
# --------------------------------------------------

SCENARIO_PARAM = "min_return"
SCENARIO_VALUES = [10, 20, 30]

scenario_results = []

for scenario_value in SCENARIO_VALUES:
    print(f"\nRunning scenario: {SCENARIO_PARAM} = {scenario_value}")

    # Set scenario parameter value.
    min_return = scenario_value

    # Create a fresh SolverModel for each scenario.
    s = SolverModel(model, "cont")
    build_formulation(s)

    solver = Solver("highs")
    s.solve(solver, time_limit_sec=60)

    scenario_results.append({
        "scenario": scenario_value,
        "status": str(s.termination_status),
        "objective": s.objective_value,
    })
    print(f"  Status: {s.termination_status}, Objective: {s.objective_value}")

    # Print portfolio allocation from solver results.
    var_df = s.variable_values().to_df()
    qty_df = var_df[
        var_df["name"].str.startswith("qty") & (var_df["value"] > 0.001)
    ]
    print(f"\n  Portfolio allocation:")
    print(qty_df.to_string(index=False))

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

# Print a scenario summary table.
print("\n" + "=" * 50)
print("Scenario Analysis Summary")
print("=" * 50)
for result in scenario_results:
    print(f"  {result['scenario']}: {result['status']}, obj={result['objective']}")
