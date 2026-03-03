# portfolio balancing:
# minimize portfolio risk for a given return target (Markowitz mean-variance)

from pathlib import Path

from pandas import read_csv

from relationalai.semantics import Float, Integer, Model, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("portfolio")

# --------------------------------------------------
# Define ontology & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Concept: stocks with expected returns
Stock = model.Concept("Stock", identify_by={"index": Integer})
Stock.returns = model.Property(f"{Stock} has {Float:returns}")
returns_csv = read_csv(data_dir / "returns.csv")
model.define(Stock.new(model.data(returns_csv).to_schema()))

# Relationship: covariance matrix between stock pairs (binary property)
Stock.covar = model.Property(f"{Stock} and {Stock} have {Float:covar}")
Stock2 = Stock.ref()
covar_data = model.data(read_csv(data_dir / "covar.csv"))
model.where(Stock.index(covar_data.i), Stock2.index(covar_data.j)).define(
    Stock.covar(Stock, Stock2, covar_data.covar)
)

# --------------------------------------------------
# Model the problem
# --------------------------------------------------

# Parameters
budget = 1000
min_return = 20

# Variable: quantity of each stock (continuous, non-negative)
Stock.x_quantity = model.Property(f"{Stock} quantity is {Float:x}")

# Objective: minimize portfolio variance (quadratic via covariance matrix)
c = Float.ref()
risk = sum(c * Stock.x_quantity * Stock2.x_quantity).where(Stock.covar(Stock2, c))

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
