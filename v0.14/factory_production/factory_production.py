"""Factory production (prescriptive optimization) template.

This script demonstrates a linear optimization problem in RelationalAI:

- Load sample CSVs describing machines, products, and per-machine production times.
- Model machines, products, and machine-product production times as *concepts*.
- Choose non-negative production quantities for each machine-product pair.
- Constrain machine hours and enforce minimum product production.
- Maximize total profit (revenue minus machine operating cost).

Run:
    `python factory_production.py`

Output:
    Prints the solver termination status, objective value, and a table of
    machine-product quantities with non-trivial production.
"""

from pathlib import Path

import pandas
from pandas import read_csv

from relationalai.semantics import Model, Relationship, data, define, require, select, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel


DATA_DIR = Path(__file__).parent / "data"

# Disable pandas inference of string types. This ensures that string columns
# in the CSVs are loaded as object dtype. This is only required when using
# relationalai versions prior to v1.0.
pandas.options.future.infer_string = False

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

# Create a Semantics model container.
model = Model("factory")

# Machine concept: represents a production machine with available hours and hourly cost
Machine = model.Concept("Machine")
Machine.id = model.Property("{Machine} has {id:int}")
Machine.name = model.Property("{Machine} has {name:string}")
Machine.hours_available = model.Property("{Machine} has {hours_available:float}")
Machine.hourly_cost = model.Property("{Machine} has {hourly_cost:float}")

# Load machine data from CSV and create Machine entities.
data(read_csv(DATA_DIR / "machines.csv")).into(Machine, keys=["id"])

# Product concept: represents a product with price and minimum production requirements
Product = model.Concept("Product")
Product.id = model.Property("{Product} has {id:int}")
Product.name = model.Property("{Product} has {name:string}")
Product.price = model.Property("{Product} has {price:float}")
Product.min_production = model.Property("{Product} has {min_production:int}")

# Load product data from CSV and create Product entities.
data(read_csv(DATA_DIR / "products.csv")).into(Product, keys=["id"])

# ProdTime concept: represents the time required to produce one unit of a product on a machine
ProdTime = model.Concept("ProductionTime")
ProdTime.machine = model.Relationship("{ProductionTime} on {machine:Machine}")
ProdTime.product = model.Relationship("{ProductionTime} of {product:Product}")
ProdTime.hours_per_unit = model.Property("{ProductionTime} takes {hours_per_unit:float}")

# Load production time data from CSV.
times_data = data(read_csv(DATA_DIR / "production_times.csv"))

# Define ProductionTime entities by joining machine/product IDs from the CSV with
# the Machine and Product concepts.
where(
    Machine.id == times_data.machine_id,
    Product.id == times_data.product_id,
).define(
    ProdTime.new(machine=Machine, product=Product, hours_per_unit=times_data.hours_per_unit)
)

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

# Decision concept: production quantities for each machine/product
Production = model.Concept("Production")
Production.prod_time = model.Relationship("{Production} uses {prod_time:ProductionTime}")
Production.x_quantity = model.Property("{Production} has {quantity:float}")

# Define one Production entity per machine-product ProductionTime record.
define(Production.new(prod_time=ProdTime))

Prod = Production.ref()

s = SolverModel(model, "cont")

# Variable: production quantity
s.solve_for(
    Production.x_quantity,
    name=["qty", Production.prod_time.machine.name, Production.prod_time.product.name],
    lower=0,
)

# Constraint: total production hours per machine <= hours_available
total_hours = sum(
    Prod.x_quantity * Prod.prod_time.hours_per_unit
).where(
    Prod.prod_time.machine == Machine
).per(Machine)
machine_limit = require(total_hours <= Machine.hours_available)
s.satisfy(machine_limit)

# Constraint: total production per product >= min_production
total_produced = sum(Prod.x_quantity).where(Prod.prod_time.product == Product).per(Product)
meet_minimum = require(total_produced >= Product.min_production)
s.satisfy(meet_minimum)

# Objective: maximize profit (revenue - machine costs)
revenue = sum(Production.x_quantity * Production.prod_time.product.price)
machine_cost = sum(
    Production.x_quantity * Production.prod_time.hours_per_unit * Production.prod_time.machine.hourly_cost
)
profit = revenue - machine_cost
s.maximize(profit)

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

solver = Solver("highs")
s.solve(solver, time_limit_sec=60)

print(f"Status: {s.termination_status}")
print(f"Total profit: ${s.objective_value:.2f}")

plan = select(
    Production.prod_time.machine.name.alias("machine"),
    Production.prod_time.product.name.alias("product"),
    Production.x_quantity
).where(Production.x_quantity > 0).to_df()

print("\nProduction plan:")
print(plan.to_string(index=False))
