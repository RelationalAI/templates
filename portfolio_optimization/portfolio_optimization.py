# Portfolio Optimization:
# Minimize portfolio risk for a given return target (Markowitz mean-variance)

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Float, Model, data, require, select, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

model = Model("portfolio", config=globals().get("config", None), use_lqp=False)

# --------------------------------------------------
# Load Data and Define Ontology
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Stocks with expected returns
Stock = model.Concept("Stock")
Stock.returns = model.Property("{Stock} has {returns:float}")
data(read_csv(data_dir / "returns.csv")).into(Stock, keys=["index"])

# Covariance matrix between stock pairs
Stock.covar = model.Property("{Stock} and {stock2:Stock} have {covar:float}")
Stock2 = Stock.ref()

covar_csv = read_csv(data_dir / "covariance.csv")
pairs = data(covar_csv)
where(Stock.index(pairs.i), Stock2.index(pairs.j)).define(
    Stock.covar(Stock, Stock2, pairs.covar)
)

# --------------------------------------------------
# Define Optimization Problem
# --------------------------------------------------

min_return = 20  # minimum required portfolio return
budget = 1000  # maximum investment amount

# Decision variable: quantity of each stock
Stock.quantity = model.Property("{Stock} quantity is {x:float}")

# Objective: minimize portfolio risk (variance)
c = Float.ref()
risk = sum(c * Stock.quantity * Stock2.quantity).where(Stock.covar(Stock2, c))

# Constraints
bounds = require(Stock.quantity >= 0)  # No short selling
budget_constraint = require(sum(Stock.quantity) <= budget)
return_constraint = require(sum(Stock.returns * Stock.quantity) >= min_return)

# --------------------------------------------------
# Set Up Solver Model
# --------------------------------------------------

s = SolverModel(model, "cont")
s.solve_for(Stock.quantity, name=["qty", Stock.index])
s.minimize(risk)
s.satisfy(bounds)
s.satisfy(budget_constraint)
s.satisfy(return_constraint)

# --------------------------------------------------
# Solve and Display Results
# --------------------------------------------------

solver = Solver("highs")
s.solve(solver, time_limit_sec=60)

print(f"Status: {s.termination_status}")
print(f"Portfolio risk (variance): {s.objective_value:.4f}")
print(f"Minimum return target: {min_return}")

# Access solution via populated relations
allocations = select(Stock.index, Stock.quantity).where(Stock.quantity > 0.001).to_df()

print("\nStock allocations:")
print(allocations.to_string(index=False))
