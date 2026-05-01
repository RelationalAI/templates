"""Factory production (prescriptive optimization) template.

This script demonstrates a linear optimization problem in RelationalAI:

- Load sample CSVs describing factories and products with production rates and profit.
- Model factories and products as *concepts* with typed properties.
- Choose non-negative production quantities for each product, bounded by demand.
- Constrain total resource usage per factory by available capacity.
- Maximize total profit per factory via scenario analysis.

Run:
    `python factory_production.py`

Output:
    Prints per-factory termination status, profit, and a production plan table,
    followed by a factory production summary.
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

model = Model("factory_production")
Concept, Property = model.Concept, model.Property

# Factory concept: factories with total resource availability.
Factory = Concept("Factory", identify_by={"name": String})
Factory.avail = Property(f"{Factory} has {Float:avail}")

# Load factories from CSV.
factory_csv = read_csv(DATA_DIR / "factories.csv")
model.define(Factory.new(model.data(factory_csv).to_schema()))

# Product concept: products with production rate, profit, demand cap, and parent factory.
Product = Concept("Product", identify_by={"name": String, "factory_name": String})
Product.factory = Property(f"{Product} is produced by {Factory}")
Product.rate = Property(f"{Product} has {Float:rate}")
Product.profit = Property(f"{Product} has {Float:profit}")
Product.demand = Property(f"{Product} has {Integer:demand}")

# Load products from CSV and link each product to its factory.
product_csv = read_csv(DATA_DIR / "products.csv")
product_data = model.data(product_csv)
model.define(
    p := Product.new(name=product_data.name, factory_name=product_data.factory_name),
    p.rate(product_data.rate),
    p.profit(product_data.profit),
    p.demand(product_data.demand),
)
model.define(Product.factory(Factory)).where(
    Product.factory_name(product_data.factory_name),
    Factory.name(product_data.factory_name),
)

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

# Variable: quantity[product] = amount produced (bounded by demand)
Product.x_quantity = Property(f"{Product} has {Float:quantity}")

# Scenarios: solve independently per factory
SCENARIO_PARAM = "factory_name"
SCENARIO_VALUES = list(factory_csv["name"])

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

scenario_results = []

for factory_name in SCENARIO_VALUES:
    print(f"\nFor factory: {factory_name}")

    # Restrict to products of this factory
    this_product = Product.factory.name(factory_name)

    problem = Problem(model, Float)

    # Variable: production quantity per product, bounded by demand
    quantity_var = problem.solve_for(
        Product.x_quantity,
        lower=0,
        upper=Product.demand,
        name=Product.name,
        where=[this_product],
        populate=False,
    )

    # Objective: maximize profit = sum(quantity * profit_per_unit)
    profit = sum(Product.profit * Product.x_quantity).where(this_product)
    problem.maximize(profit)

    # Constraint: total resource usage <= factory availability
    problem.satisfy(model.require(
        sum(Product.x_quantity / Product.rate) <= Factory.avail
    ).where(this_product, Factory.name(factory_name)))

    problem.display()
    problem.solve("highs", time_limit_sec=60)
    si = problem.solve_info()
    si.display()

    scenario_results.append(
        {
            "factory": factory_name,
            "status": str(si.termination_status),
            "profit": si.objective_value,
        }
    )
    if si.termination_status != "OPTIMAL":
        print(f"  Status: {si.termination_status} — skipping results")
        continue
    print(f"  Status: {si.termination_status}, Profit: ${si.objective_value:.2f}")

    # Extract solution via Variable.values() — populate=False avoids overwriting between scenarios.
    value_ref = Float.ref()
    produced = model.select(
        quantity_var.product.name.alias("product"),
        value_ref.alias("quantity"),
    ).where(quantity_var.values(0, value_ref), value_ref > 0.001).to_df()
    print(f"  Production plan:\n{produced.to_string(index=False)}")

# Summary
print("\n" + "=" * 50)
print("Factory Production Summary")
print("=" * 50)
for result in scenario_results:
    profit = result["profit"]
    profit_str = f"${profit:.2f}" if profit is not None else "N/A"
    print(f"  {result['factory']}: {result['status']}, profit={profit_str}")
