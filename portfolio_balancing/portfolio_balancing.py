# portfolio optimization problem:
# minimize portfolio risk for a given return target (Markowitz mean-variance)

from pathlib import Path

from pandas import read_csv

from relationalai.semantics import Float, Model, data, require, select, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

model = Model("portfolio", config=globals().get("config", None), use_lqp=False)

# --------------------------------------------------
# Define ontology & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Concept: stocks with expected returns
Stock = model.Concept("Stock")
Stock.returns = model.Property("{Stock} has {returns:float}")
data(read_csv(data_dir / "returns.csv")).into(Stock, keys=["index"])

# Relationship: covariance matrix between stock pairs
Stock.covar = model.Property("{Stock} and {stock2:Stock} have {covar:float}")
Stock2 = Stock.ref()

covar_csv = read_csv(data_dir / "covariance.csv")
pairs = data(covar_csv)
where(Stock.index(pairs.i), Stock2.index(pairs.j)).define(
    Stock.covar(Stock, Stock2, pairs.covar)
)

# --------------------------------------------------
# Model the problem
# --------------------------------------------------

# Parameters
min_return = 20
budget = 1000

c = Float.ref()

s = SolverModel(model, "cont")

# Variable: quantity of each stock
Stock.quantity = model.Property("{Stock} quantity is {x:float}")
s.solve_for(Stock.quantity, name=["qty", Stock.index])

# Constraint: no short selling
bounds = require(Stock.quantity >= 0)
s.satisfy(bounds)

# Constraint: budget limit
budget_constraint = require(sum(Stock.quantity) <= budget)
s.satisfy(budget_constraint)

# Constraint: minimum return target
return_constraint = require(sum(Stock.returns * Stock.quantity) >= min_return)
s.satisfy(return_constraint)

# Objective: minimize portfolio risk (variance)
risk = sum(c * Stock.quantity * Stock2.quantity).where(Stock.covar(Stock2, c))
s.minimize(risk)

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

solver = Solver("highs")
s.solve(solver, time_limit_sec=60)

print(f"Status: {s.termination_status}")
print(f"Portfolio risk (variance): {s.objective_value:.4f}")
print(f"Minimum return target: {min_return}")

allocations = select(Stock.index, Stock.quantity).where(Stock.quantity > 0.001).to_df()

print("\nStock allocations:")
print(allocations.to_string(index=False))
