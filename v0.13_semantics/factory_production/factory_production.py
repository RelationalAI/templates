# factory production problem:
# maximize profit from production across machines

from pathlib import Path

import pandas; pandas.options.future.infer_string = False
from pandas import read_csv

from relationalai.semantics import Model, data, define, require, select, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

model = Model("factory", config=globals().get("config", None), use_lqp=False)

# --------------------------------------------------
# Define ontology & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Concept: machines with availability and costs
Machine = model.Concept("Machine")
Machine.id = model.Property("{Machine} has {id:int}")
Machine.name = model.Property("{Machine} has {name:string}")
Machine.hours_available = model.Property("{Machine} has {hours_available:float}")
Machine.hourly_cost = model.Property("{Machine} has {hourly_cost:float}")
data(read_csv(data_dir / "machines.csv")).into(Machine, keys=["id"])

# Concept: products with price and minimum production requirements
Product = model.Concept("Product")
Product.id = model.Property("{Product} has {id:int}")
Product.name = model.Property("{Product} has {name:string}")
Product.price = model.Property("{Product} has {price:float}")
Product.min_production = model.Property("{Product} has {min_production:int}")
data(read_csv(data_dir / "products.csv")).into(Product, keys=["id"])

# Relationship: production times for each machine/product combination
ProdTime = model.Concept("ProductionTime")
ProdTime.machine = model.Property("{ProductionTime} on {machine:Machine}")
ProdTime.product = model.Property("{ProductionTime} of {product:Product}")
ProdTime.hours_per_unit = model.Property("{ProductionTime} takes {hours_per_unit:float}")

times_data = data(read_csv(data_dir / "production_times.csv"))
where(Machine.id(times_data.machine_id), Product.id(times_data.product_id)).define(
    ProdTime.new(machine=Machine, product=Product, hours_per_unit=times_data.hours_per_unit)
)

# --------------------------------------------------
# Model the problem
# --------------------------------------------------

# Decision concept: production quantities for each machine/product
Production = model.Concept("Production")
Production.prod_time = model.Property("{Production} uses {prod_time:ProductionTime}")
Production.quantity = model.Property("{Production} has {quantity:float}")
define(Production.new(prod_time=ProdTime))

Prod = Production.ref()

s = SolverModel(model, "cont")

# Variable: production quantity
s.solve_for(
    Production.quantity,
    name=["qty", Production.prod_time.machine.name, Production.prod_time.product.name],
    lower=0
)

# Constraint: total production hours per machine <= hours_available
total_hours = sum(Prod.quantity * Prod.prod_time.hours_per_unit).where(
    Prod.prod_time.machine == Machine
).per(Machine)
machine_limit = require(total_hours <= Machine.hours_available)
s.satisfy(machine_limit)

# Constraint: total production per product >= min_production
total_produced = sum(Prod.quantity).where(Prod.prod_time.product == Product).per(Product)
meet_minimum = require(total_produced >= Product.min_production)
s.satisfy(meet_minimum)

# Objective: maximize profit (revenue - machine costs)
revenue = sum(Production.quantity * Production.prod_time.product.price)
machine_cost = sum(
    Production.quantity * Production.prod_time.hours_per_unit * Production.prod_time.machine.hourly_cost
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
    Production.quantity
).where(Production.quantity > 0).to_df()

print("\nProduction plan:")
print(plan.to_string(index=False))
