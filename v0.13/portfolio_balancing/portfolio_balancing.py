# portfolio balancing:
# minimize portfolio risk for a given return target (Markowitz mean-variance)

from pathlib import Path

import pandas; pandas.options.future.infer_string = False
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
budget = 1000

Stock.quantity = model.Property("{Stock} quantity is {x:float}")

c = Float.ref()

# Scenarios (what-if analysis)
SCENARIO_PARAM = "min_return"
SCENARIO_VALUES = [10, 20, 30]

# --------------------------------------------------
# Solve with Scenario Analysis (Numeric Parameter)
# --------------------------------------------------

scenario_results = []

for scenario_value in SCENARIO_VALUES:
    print(f"\nRunning scenario: {SCENARIO_PARAM} = {scenario_value}")

    # Set scenario parameter value
    min_return = scenario_value

    # Create fresh SolverModel for each scenario
    s = SolverModel(model, "cont")

    # Variable: quantity of each stock
    s.solve_for(Stock.quantity, name=["qty", Stock.index])

    # Constraint: no short selling
    bounds = require(Stock.quantity >= 0)
    s.satisfy(bounds)

    # Constraint: budget limit
    budget_constraint = require(sum(Stock.quantity) <= budget)
    s.satisfy(budget_constraint)

    # Constraint: minimum return target (scenario parameter)
    return_constraint = require(sum(Stock.returns * Stock.quantity) >= min_return)
    s.satisfy(return_constraint)

    # Objective: minimize portfolio risk (variance)
    risk = sum(c * Stock.quantity * Stock2.quantity).where(Stock.covar(Stock2, c))
    s.minimize(risk)

    solver = Solver("highs")
    s.solve(solver, time_limit_sec=60)

    scenario_results.append({
        "scenario": scenario_value,
        "status": str(s.termination_status),
        "objective": s.objective_value,
    })
    print(f"  Status: {s.termination_status}, Objective: {s.objective_value}")

    # Print portfolio allocation from solver results
    var_df = s.variable_values().to_df()
    qty_df = var_df[var_df["name"].str.startswith("qty") & (var_df["float"] > 0.001)].rename(columns={"float": "value"})
    print(f"\n  Portfolio allocation:")
    print(qty_df.to_string(index=False))

# Summary
print("\n" + "=" * 50)
print("Scenario Analysis Summary")
print("=" * 50)
for result in scenario_results:
    print(f"  {result['scenario']}: {result['status']}, obj={result['objective']}")
