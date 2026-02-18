"""Supplier Reliability (prescriptive optimization) template.

This script demonstrates a small sourcing model that balances cost and supplier
reliability:

- Load sample CSVs describing suppliers, products, and supplier–product supply options.
- Choose non-negative order quantities for each supply option.
- Enforce supplier capacity limits and product demand satisfaction.
- Optionally exclude a supplier as a disruption scenario.

Run:
    `python supplier_reliability.py`

Output:
    Prints the solver termination status and an order plan per scenario, then a
    scenario summary table with termination status and objective value.
"""

from pathlib import Path

import pandas
from pandas import read_csv

from relationalai.semantics import Model, data, define, require, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"

# Disable pandas inference of string types. This ensures that string columns
# in the CSVs are loaded as object dtype. This is only required when using
# relationalai versions prior to v1.0.
pandas.options.future.infer_string = False

# Parameters.
RELIABILITY_WEIGHT = 0.0  # Penalty weight for unreliable suppliers (0 = cost only).
EXCLUDED_SUPPLIER = None

# Scenarios (what-if analysis).
SCENARIO_PARAM = "excluded_supplier"
SCENARIO_VALUES = [None, "SupplierC", "SupplierB"]
SCENARIO_CONCEPT = "Supplier"  # Entity type for exclusion scenarios.

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

# Create a Semantics model container.
model = Model("supplier_reliability", config=globals().get("config", None), use_lqp=False)

# Supplier concept: suppliers with reliability scores and capacity.
Supplier = model.Concept("Supplier")
Supplier.id = model.Property("{Supplier} has {id:int}")
Supplier.name = model.Property("{Supplier} has {name:string}")
Supplier.reliability = model.Property("{Supplier} has {reliability:float}")
Supplier.capacity = model.Property("{Supplier} has {capacity:int}")

# Load supplier data from CSV.
data(read_csv(DATA_DIR / "suppliers.csv")).into(Supplier, keys=["id"])

# Product concept: products with demand requirements.
Product = model.Concept("Product")
Product.id = model.Property("{Product} has {id:int}")
Product.name = model.Property("{Product} has {name:string}")
Product.demand = model.Property("{Product} has {demand:int}")

# Load product data from CSV.
data(read_csv(DATA_DIR / "products.csv")).into(Product, keys=["id"])

# SupplyOption concept: supplier–product supply options with a per-unit cost.
SupplyOption = model.Concept("SupplyOption")
SupplyOption.id = model.Property("{SupplyOption} has {id:int}")
SupplyOption.supplier = model.Property("{SupplyOption} from {supplier:Supplier}")
SupplyOption.product = model.Property("{SupplyOption} for {product:Product}")
SupplyOption.cost_per_unit = model.Property("{SupplyOption} has {cost_per_unit:float}")

# Load supply option data from CSV.
options_data = data(read_csv(DATA_DIR / "supply_options.csv"))

# Create one SupplyOption entity per row by joining supplier_id and product_id.
where(
    Supplier.id == options_data.supplier_id,
    Product.id == options_data.product_id
).define(
    SupplyOption.new(
        id=options_data.id,
        supplier=Supplier,
        product=Product,
        cost_per_unit=options_data.cost_per_unit,
    )
)

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

# Order decision concept: quantity ordered via each supply option.
Order = model.Concept("Order")
Order.option = model.Property("{Order} uses {option:SupplyOption}")
Order.x_quantity = model.Property("{Order} has {quantity:float}")
define(Order.new(option=SupplyOption))

# Derived properties for direct access in constraints and objective.
Order.supplier = model.Property("{Order} has {supplier:Supplier}")
define(Order.supplier(Supplier)).where(
    Order.option == SupplyOption,
    SupplyOption.supplier == Supplier,
)

Order.product = model.Property("{Order} has {product:Product}")
define(Order.product(Product)).where(
    Order.option == SupplyOption,
    SupplyOption.product == Product,
)

Order.cost_per_unit = model.Property("{Order} has {cost_per_unit:float}")
define(Order.cost_per_unit(SupplyOption.cost_per_unit)).where(Order.option == SupplyOption)


def build_formulation(s):
    """Register variables, constraints, and objective on the solver model."""
    # Variable: order quantity
    s.solve_for(Order.x_quantity, name=["qty", Order.supplier.name, Order.product.name], lower=0)

    # Constraint: total orders from supplier cannot exceed supplier capacity
    capacity_limit = require(
        sum(Order.x_quantity).where(Order.supplier == Supplier).per(Supplier) <= Supplier.capacity
    )
    s.satisfy(capacity_limit)

    # Constraint: demand satisfaction for each product
    meet_demand = require(
        sum(Order.x_quantity).where(Order.product == Product).per(Product) >= Product.demand
    )
    s.satisfy(meet_demand)

    # Constraint: exclude supplier if specified
    if EXCLUDED_SUPPLIER is not None:
        exclude = require(Order.x_quantity == 0).where(Order.supplier.name == EXCLUDED_SUPPLIER)
        s.satisfy(exclude)

    # Objective: minimize cost with optional reliability penalty
    direct_cost = sum(Order.x_quantity * Order.cost_per_unit)
    if RELIABILITY_WEIGHT > 0:
        reliability_penalty = RELIABILITY_WEIGHT * sum(
            Order.x_quantity * (1.0 - Order.supplier.reliability)
        )
        total_cost = direct_cost + reliability_penalty
    else:
        total_cost = direct_cost
    s.minimize(total_cost)


# --------------------------------------------------
# Solve with Scenario Analysis (Supplier Exclusion)
# --------------------------------------------------

scenario_results = []

for scenario_value in SCENARIO_VALUES:
    print(f"\nRunning scenario: {SCENARIO_PARAM} = {scenario_value}")

    # Set scenario parameter (entity to exclude).
    EXCLUDED_SUPPLIER = scenario_value

    # Create a fresh SolverModel for each scenario.
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

    # Print order plan from solver results.
    var_df = s.variable_values().to_df()
    qty_df = var_df[
        var_df["name"].str.startswith("qty") & (var_df["float"] > 0.001)
    ].rename(columns={"float": "value"})
    print("\n  Orders:")
    print(qty_df.to_string(index=False))

# Summary.
print("\n" + "=" * 50)
print("Scenario Analysis Summary")
print("=" * 50)
for result in scenario_results:
    print(f"  {result['scenario']}: {result['status']}, obj={result['objective']}")
