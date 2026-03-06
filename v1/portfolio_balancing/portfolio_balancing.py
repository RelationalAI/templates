"""Portfolio Balancing (prescriptive optimization) template.

This script demonstrates a Markowitz mean-variance portfolio optimization model in RelationalAI:

- Load expected returns and a covariance matrix from CSV.
- Model stocks as *concepts* with typed properties and pairwise covariance.
- Choose non-negative allocations across available stocks.
- Enforce a budget constraint and a minimum expected return constraint.
- Minimize portfolio variance (risk).
- Solve multiple minimum-return scenarios to illustrate the efficient frontier.

Run:
    `python portfolio_balancing.py`

Output:
    Prints per-scenario termination status and risk (objective value), a non-trivial
    allocation table for each scenario, and a summary of scenario results.
"""

from pathlib import Path

from pandas import read_csv

from relationalai.semantics import Float, Integer, Model, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("portfolio")

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Concept: stocks with expected returns
Stock = model.Concept("Stock", identify_by={"index": Integer})
Stock.returns = model.Property(f"{Stock} has {Float:returns}")
returns_csv = read_csv(data_dir / "returns.csv")
model.define(Stock.new(model.data(returns_csv).to_schema()))

# Relationship: covariance matrix between stock pairs (binary property)
Stock.covar = model.Property(f"{Stock} and {Stock} have {Float:covar}")
PairedStock = Stock.ref()
covar_data = model.data(read_csv(data_dir / "covar.csv"))
model.where(Stock.index(covar_data.i), PairedStock.index(covar_data.j)).define(
    Stock.covar(Stock, PairedStock, covar_data.covar)
)

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

# Parameters
budget = 1000
min_return = 20

# Variable: quantity of each stock (continuous, non-negative)
Stock.x_quantity = model.Property(f"{Stock} quantity is {Float:x}")

# Objective: minimize portfolio variance (quadratic via covariance matrix)
covar_value = Float.ref()
risk = sum(covar_value * Stock.x_quantity * PairedStock.x_quantity).where(Stock.covar(PairedStock, covar_value))

# Constraints: non-negative quantities and budget limit
bounds = model.require(Stock.x_quantity >= 0)
budget_constraint = model.require(sum(Stock.x_quantity) <= budget)

def build_formulation(s, min_ret):
    """Register variables, constraints, and objective on the solver model."""
    # Variable: quantity of each stock
    s.solve_for(Stock.x_quantity, name=["qty", Stock.index], populate=False)

    # Constraint: no short selling
    s.satisfy(bounds)

    # Constraint: budget limit
    s.satisfy(budget_constraint)

    # Constraint: minimum return target (scenario parameter)
    return_constraint = model.require(sum(Stock.returns * Stock.x_quantity) >= min_ret)
    s.satisfy(return_constraint)

    # Objective: minimize portfolio risk
    s.minimize(risk)

# Scenarios (what-if analysis)
SCENARIO_PARAM = "min_return"
SCENARIO_VALUES = [10, 20, 30]

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

scenario_results = []

for scenario_value in SCENARIO_VALUES:
    print(f"\nRunning scenario: {SCENARIO_PARAM} = {scenario_value}")

    # Create fresh Problem for each scenario
    s = Problem(model, Float)
    build_formulation(s, min_ret=scenario_value)

    s.display()
    s.solve("highs", time_limit_sec=60, _server_side_import=False)
    s.display_solve_info()

    scenario_results.append({
        "scenario": scenario_value,
        "status": str(s.termination_status),
        "objective": s.objective_value,
    })
    print(f"  Status: {s.termination_status}, Risk: {s.objective_value:.6f}")

    # Extract solution via variable_values() — populate=False avoids overwriting between scenarios
    var_df = s.variable_values().to_df()
    alloc = var_df[var_df["value"] > 0.001]
    print(f"  Portfolio allocation:\n{alloc.to_string(index=False)}")

# Summary
print("\n" + "=" * 50)
print("Scenario Analysis Summary")
print("=" * 50)
for result in scenario_results:
    print(f"  min_return={result['scenario']}: {result['status']}, risk={result['objective']:.6f}")
