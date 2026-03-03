# production planning problem:
# schedule production on machines to meet demand and maximize profit

from pathlib import Path

from pandas import read_csv

from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("production_planning")
Concept, Property = model.Concept, model.Property

# --------------------------------------------------
# Define ontology & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Concept: products with demand and profit margin
Product = Concept("Product", identify_by={"id": Integer})
Product.name = Property(f"{Product} has {String:name}")
Product.demand = Property(f"{Product} has {Integer:demand}")
Product.profit = Property(f"{Product} has {Float:profit}")
product_csv = read_csv(data_dir / "products.csv")
model.define(Product.new(model.data(product_csv).to_schema()))

# Concept: machines with available hours
Machine = Concept("Machine", identify_by={"id": Integer})
Machine.name = Property(f"{Machine} has {String:name}")
Machine.hours_available = Property(f"{Machine} has {Float:hours_available}")
machine_csv = read_csv(data_dir / "machines.csv")
model.define(Machine.new(model.data(machine_csv).to_schema()))

# Relationship: production rates for each machine/product combination
Rate = Concept("ProductionRate")
Rate.machine = Property(f"{Rate} on {Machine}", short_name="machine")
Rate.product = Property(f"{Rate} for {Product}", short_name="product")
Rate.hours_per_unit = Property(f"{Rate} has {Float:hours_per_unit}")

rates_csv = read_csv(data_dir / "production_rates.csv")
rates_data = model.data(rates_csv)
model.define(
    r := Rate.new(machine=Machine, product=Product, hours_per_unit=rates_data.hours_per_unit)
).where(Machine.id == rates_data.machine_id, Product.id == rates_data.product_id)

# --------------------------------------------------
# Model the problem
# --------------------------------------------------

# Decision concept: production quantities for each machine/product
Production = Concept("Production")
Production.rate = Property(f"{Production} uses {Rate}", short_name="rate")
Production.x_quantity = Property(f"{Production} has {Float:quantity}")
model.define(Production.new(rate=Rate))

ProductionRef = Production.ref()

# Scenarios (what-if analysis)
SCENARIO_PARAM = "demand_multiplier"
SCENARIO_VALUES = [0.8, 1.0, 1.1]

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

scenario_results = []

for demand_multiplier in SCENARIO_VALUES:
    print(f"\nRunning scenario: {SCENARIO_PARAM} = {demand_multiplier}")

    # Create fresh Problem for each scenario
    s = Problem(model, Float)

    # Variable: production quantity (integer)
    s.solve_for(Production.x_quantity, name=["qty", Production.rate.machine.name, Production.rate.product.name], lower=0, type="int", populate=False)

    # Constraint: machine capacity
    machine_hours = sum(ProductionRef.x_quantity * ProductionRef.rate.hours_per_unit).where(ProductionRef.rate.machine == Machine).per(Machine)
    capacity_limit = model.require(machine_hours <= Machine.hours_available)
    s.satisfy(capacity_limit)

    # Constraint: meet demand (scaled by demand_multiplier)
    product_qty = sum(ProductionRef.x_quantity).where(ProductionRef.rate.product == Product).per(Product)
    meet_demand = model.require(product_qty >= Product.demand * demand_multiplier)
    s.satisfy(meet_demand)

    # Objective: maximize total profit
    total_profit = sum(Production.x_quantity * Production.rate.product.profit)
    s.maximize(total_profit)

    s.display()
    s.solve("highs", time_limit_sec=60, _server_side_import=False)
    s.display_solve_info()

    scenario_results.append({
        "scenario": demand_multiplier,
        "status": str(s.termination_status),
        "objective": s.objective_value,
    })
    print(f"  Status: {s.termination_status}, Objective: {s.objective_value}")

    # Print production plan from solver results
    var_df = s.variable_values().to_df()
    qty_df = var_df[var_df["name"].str.startswith("qty") & (var_df["value"] > 0.001)]
    print(f"\n  Production plan:")
    print(qty_df.to_string(index=False))

# Summary
print("\n" + "=" * 50)
print("Scenario Analysis Summary")
print("=" * 50)
for result in scenario_results:
    print(f"  {result['scenario']}: {result['status']}, obj={result['objective']}")
