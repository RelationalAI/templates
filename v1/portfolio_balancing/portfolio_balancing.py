"""Portfolio Balancing (prescriptive optimization) template.

This script demonstrates a Markowitz mean-variance portfolio optimization model in RelationalAI:

- Load expected returns and a covariance matrix from CSV.
- Model stocks as *concepts* with typed properties and pairwise covariance.
- Choose non-negative allocations across available stocks.
- Enforce a budget constraint and a minimum expected return constraint.
- Minimize portfolio variance (risk) using Ipopt (interior-point NLP solver).
- Solve multiple minimum-return scenarios simultaneously using Scenario as a
  first-class Concept (single solve, all scenarios at once).

Modeling approach:
- Scenario is a Concept with a min_return parameter property.
- Decision variables are multi-argument Properties indexed by (Stock, Scenario).
- Constraints use ref() bindings + .per(Scenario) to scope per-scenario.
- One solve handles all min_return levels; results extracted via model.select().

Run:
    `python portfolio_balancing.py`

Output:
    Prints per-scenario termination status and risk (objective value), a non-trivial
    allocation table for each scenario, and a summary of scenario results.
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("portfolio")

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"

# Stock concept: equities with expected returns.
Stock = model.Concept("Stock", identify_by={"index": Integer})
Stock.returns = model.Property(f"{Stock} has {Float:returns}")
returns_csv = read_csv(DATA_DIR / "returns.csv")
model.define(Stock.new(model.data(returns_csv).to_schema()))

# Covariance concept: pairwise covariance matrix between stocks.
Stock.covar = model.Property(f"{Stock} and {Stock} have {Float:covar}")
PairedStock = Stock.ref()
covar_data = model.data(read_csv(DATA_DIR / "covar.csv"))
model.where(Stock.index(covar_data.i), PairedStock.index(covar_data.j)).define(
    Stock.covar(Stock, PairedStock, covar_data.covar)
)

# --------------------------------------------------
# Scenario Concept — min_return parameter variations
# --------------------------------------------------

Scenario = model.Concept("Scenario", identify_by={"name": String})
Scenario.min_return = model.Property(f"{Scenario} has {Float:min_return}")
scenario_data = model.data(
    [("return_10", 10), ("return_20", 20), ("return_30", 30)],
    columns=["name", "min_return"],
)
model.define(Scenario.new(scenario_data.to_schema()))

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

# Parameters
budget = 1000

# Decision variable — indexed by Scenario (multi-argument Property)
Stock.x_quantity = model.Property(f"{Stock} in {Scenario} has {Float:quantity}")

# Ref for binding multi-arg variable in constraints
x_qty = Float.ref()

p = Problem(model, Float)

# Variable: quantity of each stock per scenario
p.solve_for(Stock.x_quantity(Scenario, x_qty), name=["qty", Scenario.name, Stock.index])

# Constraint: no short selling (non-negative quantities)
p.satisfy(model.where(
    Stock.x_quantity(Scenario, x_qty),
).require(x_qty >= 0))

# Constraint: budget limit per scenario
p.satisfy(model.where(
    Stock.x_quantity(Scenario, x_qty),
).require(sum(x_qty).per(Scenario) <= budget))

# Constraint: minimum return target per scenario
p.satisfy(model.where(
    Stock.x_quantity(Scenario, x_qty),
).require(sum(Stock.returns * x_qty).per(Scenario) >= Scenario.min_return))

# Objective: minimize portfolio risk (quadratic via covariance matrix)
covar_value = Float.ref()
x_qty_paired = Float.ref()
p.minimize(
    sum(covar_value * x_qty * x_qty_paired)
    .where(Stock.covar(PairedStock, covar_value),
           Stock.x_quantity(Scenario, x_qty),
           PairedStock.x_quantity(Scenario, x_qty_paired))
)

# --------------------------------------------------
# Solve (single solve for all scenarios)
# --------------------------------------------------

# Solve with Ipopt (interior-point NLP solver).
# The quadratic covariance objective makes this a QP problem.
# Ipopt handles convex QP via interior-point methods and scales well
# on large covariance matrices.
p.display()
p.solve("ipopt", time_limit_sec=60)
si = p.solve_info()
si.display()
print(f"Status: {si.termination_status}, risk={si.objective_value:.4f}")

# --------------------------------------------------
# Extract results per scenario
# --------------------------------------------------

print("\nPortfolio allocation per scenario:")
model.select(
    Scenario.name.alias("scenario"),
    Stock.index.alias("stock"),
    Stock.returns,
    x_qty.alias("quantity"),
).where(
    Stock.x_quantity(Scenario, x_qty), x_qty > 0.001
).inspect()
