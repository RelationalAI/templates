"""Production planning (prescriptive optimization) template.

This script demonstrates an end-to-end mixed-integer linear optimization (MILP)
workflow in RelationalAI:

- Load sample CSVs describing products, machines, and machine-product production rates.
- Model those entities as *concepts* with typed properties.
- Create a `Production` decision concept with an integer decision variable
  `Production.x_quantity` for each machine-product pair.
- Add constraints for machine hour capacity and product demand satisfaction.
- Maximize total profit.

Run:
    `python production_planning.py`

Output:
    Prints the solver termination status, objective value, and a table of
    non-trivial production quantities for each scenario, followed by a scenario
    summary table.
"""

from pathlib import Path

import pandas
from pandas import read_csv

from relationalai.semantics import Model, Relationship, data, define, require, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"

# Disable pandas inference of string types. This ensures that string columns
# in the CSVs are loaded as object dtype. This is only required when using
# relationalai versions prior to v1.0.
pandas.options.future.infer_string = False

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

# Create a Semantics model container.
model = Model("production_planning", config=globals().get("config", None))

# Product concept: products with demand and profit per unit.
Product = model.Concept("Product")
Product.id = model.Property("{Product} has {id:int}")
Product.name = model.Property("{Product} has {name:string}")
Product.demand = model.Property("{Product} has {demand:int}")
Product.profit = model.Property("{Product} has {profit:float}")

# Load product data from CSV.
data(read_csv(DATA_DIR / "products.csv")).into(Product, keys=["id"])

# Machine concept: machines with a limited number of available production hours.
Machine = model.Concept("Machine")
Machine.id = model.Property("{Machine} has {id:int}")
Machine.name = model.Property("{Machine} has {name:string}")
Machine.hours_available = model.Property("{Machine} has {hours_available:float}")

# Load machine data from CSV.
data(read_csv(DATA_DIR / "machines.csv")).into(Machine, keys=["id"])

# ProductionRate concept: hours required per unit for each machine-product pair.
Rate = model.Concept("ProductionRate")
Rate.machine = model.Relationship("{ProductionRate} on {machine:Machine}")
Rate.product = model.Relationship("{ProductionRate} for {product:Product}")
Rate.hours_per_unit = model.Property("{ProductionRate} has {hours_per_unit:float}")

# Load production rate data from CSV.
rates_data = data(read_csv(DATA_DIR / "production_rates.csv"))

# Define ProductionRate entities by joining the rate CSV with Machine and Product.
where(
    Machine.id == rates_data.machine_id,
    Product.id == rates_data.product_id
).define(
    Rate.new(machine=Machine, product=Product, hours_per_unit=rates_data.hours_per_unit)
)

# --------------------------------------------------
# Model the problem
# --------------------------------------------------

# Production decision concept: production quantity for each machine-product pair.
Production = model.Concept("Production")
Production.rate = model.Relationship("{Production} uses {rate:ProductionRate}")
Production.x_quantity = model.Property("{Production} has {quantity:float}")
define(Production.new(rate=Rate))

Prod = Production.ref()

# Scenario parameter (overridden within the scenario loop).
demand_multiplier = 1.0


def build_formulation(s):
    """Register variables, constraints, and objective on the solver model."""
    # Variable: production quantity (integer)
    s.solve_for(
        Production.x_quantity,
        name=[
            "qty",
            Production.rate.machine.name,
            Production.rate.product.name,
        ],
        lower=0,
        type="int",
    )

    # Constraint: machine capacity
    machine_hours = (
        sum(Prod.x_quantity * Prod.rate.hours_per_unit)
        .where(Prod.rate.machine == Machine)
        .per(Machine)
    )
    capacity_limit = require(machine_hours <= Machine.hours_available)
    s.satisfy(capacity_limit)

    # Constraint: meet demand (scaled by demand_multiplier)
    product_qty = sum(Prod.x_quantity).where(Prod.rate.product == Product).per(Product)
    meet_demand = require(product_qty >= Product.demand * demand_multiplier)
    s.satisfy(meet_demand)

    # Objective: maximize total profit
    total_profit = sum(Production.x_quantity * Production.rate.product.profit)
    s.maximize(total_profit)


# --------------------------------------------------
# Solve with Scenario Analysis (Numeric Parameter)
# --------------------------------------------------

SCENARIO_PARAM = "demand_multiplier"
SCENARIO_VALUES = [0.8, 1.0, 1.1]

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

scenario_results = []

for scenario_value in SCENARIO_VALUES:
    print(f"\nRunning scenario: {SCENARIO_PARAM} = {scenario_value}")

    # Set scenario parameter value
    demand_multiplier = scenario_value

    # Create fresh SolverModel for each scenario.
    s = SolverModel(model, "cont")
    build_formulation(s)

    solver = Solver("highs")
    s.solve(solver, time_limit_sec=60)

    scenario_results.append(
        {
            "scenario": scenario_value,
            "status": str(s.termination_status),
            "objective": s.objective_value,
        }
    )
    print(f"  Status: {s.termination_status}, Objective: {s.objective_value}")

    # Print production plan from solver results
    var_df = s.variable_values().to_df()
    qty_df = var_df[
        var_df["name"].str.startswith("qty") & (var_df["value"] > 0.001)
    ]
    print(f"\n  Production plan:")
    print(qty_df.to_string(index=False))

# Summary
print("\n" + "=" * 50)
print("Scenario Analysis Summary")
print("=" * 50)
for result in scenario_results:
    print(f"  {result['scenario']}: {result['status']}, obj={result['objective']}")
