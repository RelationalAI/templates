"""Production Planning (prescriptive optimization) template.

This script demonstrates a mixed-integer linear optimization (MILP) workflow
in RelationalAI:

- Load sample CSVs describing products, machines, and machine-product production rates.
- Model those entities as *concepts* with typed properties.
- Create a Production decision concept with an integer decision variable for each
  machine-product pair.
- Add constraints for machine hour capacity and product demand satisfaction.
- Maximize total profit, with scenario analysis over demand multipliers using
  Scenario as a first-class Concept (single solve, all scenarios simultaneously).

Modeling approach:
- Scenario is a Concept with a demand_multiplier parameter property.
- Decision variables are multi-argument Properties indexed by (Production, Scenario).
- Constraints use ref() bindings + .per(Scenario) to scope per-scenario.
- One solve handles all demand levels; results extracted via model.select().

Run:
    `python production_planning.py`

Output:
    Prints the solver termination status, objective value, and a table of
    non-trivial production quantities for each scenario, followed by a scenario
    summary table.
"""

from pathlib import Path

from pandas import read_csv

from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("production_planning")
Concept, Property = model.Concept, model.Property

# --------------------------------------------------
# Define semantic model & load data
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
# Scenario Concept — demand_multiplier parameter variations
# --------------------------------------------------

Scenario = Concept("Scenario", identify_by={"name": String})
Scenario.demand_multiplier = Property(f"{Scenario} has {Float:demand_multiplier}")
scenario_data = model.data(
    [("low_demand", 0.8), ("baseline", 1.0), ("high_demand", 1.1)],
    columns=["name", "demand_multiplier"],
)
model.define(Scenario.new(scenario_data.to_schema()))

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

# Decision concept: production quantities for each machine/product
Production = Concept("Production")
Production.rate = Property(f"{Production} uses {Rate}", short_name="rate")
model.define(Production.new(rate=Rate))

# Decision variable — indexed by Scenario (multi-argument Property)
Production.x_quantity = Property(f"{Production} in {Scenario} has {Float:quantity}")

# Ref for binding multi-arg variable in constraints
x_qty = Float.ref()

ProductionRef = Production.ref()

p = Problem(model, Float)

# Variable: production quantity (integer, non-negative)
p.solve_for(
    Production.x_quantity(Scenario, x_qty),
    name=["qty", Scenario.name, Production.rate.machine.name, Production.rate.product.name],
    lower=0, type="int",
)

# Constraint: machine capacity (per machine, per scenario)
p.satisfy(model.where(
    Production.x_quantity(Scenario, x_qty),
    Production.rate.machine(Machine),
).require(
    sum(x_qty * Production.rate.hours_per_unit)
    .where(Production.rate.machine == Machine)
    .per(Machine, Scenario)
    <= Machine.hours_available
))

# Constraint: meet demand scaled by multiplier (per product, per scenario)
p.satisfy(model.where(
    Production.x_quantity(Scenario, x_qty),
    Production.rate.product(Product),
).require(
    sum(x_qty)
    .where(Production.rate.product == Product)
    .per(Product, Scenario)
    >= Product.demand * Scenario.demand_multiplier
))

# Objective: maximize total profit
p.maximize(
    sum(x_qty * Production.rate.product.profit)
    .where(Production.x_quantity(Scenario, x_qty))
)

# --------------------------------------------------
# Solve (single solve for all scenarios)
# --------------------------------------------------

p.display()
p.solve("highs", time_limit_sec=60)
model.require(p.termination_status() == "OPTIMAL")
p.solve_info().display()

# --------------------------------------------------
# Extract results per scenario
# --------------------------------------------------

print("\nProduction plan per scenario:")
model.select(
    Scenario.name.alias("scenario"),
    Production.rate.machine.name.alias("machine"),
    Production.rate.product.name.alias("product"),
    x_qty.alias("quantity"),
).where(
    Production.x_quantity(Scenario, x_qty), x_qty > 0.001
).inspect()
