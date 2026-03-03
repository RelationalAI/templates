# factory production problem:
# maximize profit from production with limited resource availability per factory

from pathlib import Path

from pandas import read_csv

from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("factory_production")
Concept, Property = model.Concept, model.Property

# --------------------------------------------------
# Define ontology & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Concept: factories with total resource availability
Factory = Concept("Factory", identify_by={"name": String})
Factory.avail = Property(f"{Factory} has {Float:avail}")
factory_csv = read_csv(data_dir / "factories.csv")
model.define(Factory.new(model.data(factory_csv).to_schema()))

# Concept: products with production rate, profit, and demand cap
Product = Concept("Product", identify_by={"name": String, "factory_name": String})
Product.factory = Property(f"{Product} is produced by {Factory}")
Product.rate = Property(f"{Product} has {Float:rate}")
Product.profit = Property(f"{Product} has {Float:profit}")
Product.demand = Property(f"{Product} has {Integer:demand}")
product_csv = read_csv(data_dir / "products.csv")
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
# Model the problem
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

    s = Problem(model, Float)

    # Variable: production quantity per product, bounded by demand
    s.solve_for(
        Product.x_quantity,
        lower=0,
        upper=Product.demand,
        name=Product.name,
        where=[this_product],
        populate=False,
    )

    # Objective: maximize profit = sum(quantity * profit_per_unit)
    profit = sum(Product.profit * Product.x_quantity).where(this_product)
    s.maximize(profit)

    # Constraint: total resource usage <= factory availability
    s.satisfy(model.require(
        sum(Product.x_quantity / Product.rate) <= Factory.avail
    ).where(this_product, Factory.name(factory_name)))

    s.display()
    s.solve("highs", time_limit_sec=60, _server_side_import=False)
    s.display_solve_info()

    scenario_results.append({
        "factory": factory_name,
        "status": str(s.termination_status),
        "profit": s.objective_value,
    })
    print(f"  Status: {s.termination_status}, Profit: ${s.objective_value:.2f}")

    # Extract solution via variable_values() — populate=False avoids overwriting between scenarios
    var_df = s.variable_values().to_df()
    produced = var_df[var_df["value"] > 0.001]
    print(f"  Production plan:\n{produced.to_string(index=False)}")

# Summary
print("\n" + "=" * 50)
print("Factory Production Summary")
print("=" * 50)
for result in scenario_results:
    print(f"  {result['factory']}: {result['status']}, profit=${result['profit']:.2f}")
