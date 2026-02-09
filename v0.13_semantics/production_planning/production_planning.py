# production planning problem:
# schedule production on machines to meet demand and maximize profit

from pathlib import Path

import pandas; pandas.options.future.infer_string = False
from pandas import read_csv

from relationalai.semantics import Model, data, define, require, select, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

model = Model("production_planning", config=globals().get("config", None), use_lqp=False)

# --------------------------------------------------
# Define ontology & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Concept: products with demand and profit margin
Product = model.Concept("Product")
Product.id = model.Property("{Product} has {id:int}")
Product.name = model.Property("{Product} has {name:string}")
Product.demand = model.Property("{Product} has {demand:int}")
Product.profit = model.Property("{Product} has {profit:float}")
data(read_csv(data_dir / "products.csv")).into(Product, keys=["id"])

# Concept: machines with available hours
Machine = model.Concept("Machine")
Machine.id = model.Property("{Machine} has {id:int}")
Machine.name = model.Property("{Machine} has {name:string}")
Machine.hours_available = model.Property("{Machine} has {hours_available:float}")
data(read_csv(data_dir / "machines.csv")).into(Machine, keys=["id"])

# Relationship: production rates for each machine/product combination
Rate = model.Concept("ProductionRate")
Rate.machine = model.Property("{ProductionRate} on {machine:Machine}")
Rate.product = model.Property("{ProductionRate} for {product:Product}")
Rate.hours_per_unit = model.Property("{ProductionRate} has {hours_per_unit:float}")

rates_data = data(read_csv(data_dir / "production_rates.csv"))
where(Machine.id(rates_data.machine_id), Product.id(rates_data.product_id)).define(
    Rate.new(machine=Machine, product=Product, hours_per_unit=rates_data.hours_per_unit)
)

# --------------------------------------------------
# Model the problem
# --------------------------------------------------

# Decision concept: production quantities for each machine/product
Production = model.Concept("Production")
Production.rate = model.Property("{Production} uses {rate:ProductionRate}")
Production.quantity = model.Property("{Production} has {quantity:float}")
define(Production.new(rate=Rate))

Prod = Production.ref()

s = SolverModel(model, "cont")

# Variable: production quantity (integer)
s.solve_for(Production.quantity, name=["qty", Production.rate.machine.name, Production.rate.product.name], lower=0, type="int")

# Constraint: machine capacity
machine_hours = sum(Prod.quantity * Prod.rate.hours_per_unit).where(Prod.rate.machine == Machine).per(Machine)
capacity_limit = require(machine_hours <= Machine.hours_available)
s.satisfy(capacity_limit)

# Constraint: meet demand
product_qty = sum(Prod.quantity).where(Prod.rate.product == Product).per(Product)
meet_demand = require(product_qty >= Product.demand)
s.satisfy(meet_demand)

# Objective: maximize total profit
total_profit = sum(Production.quantity * Production.rate.product.profit)
s.maximize(total_profit)

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

solver = Solver("highs")
s.solve(solver, time_limit_sec=60)

print(f"Status: {s.termination_status}")
print(f"Total profit: ${s.objective_value:.2f}")

schedule = select(
    Production.rate.machine.name.alias("machine"),
    Production.rate.product.name.alias("product"),
    Production.quantity
).where(Production.quantity > 0).to_df()

print("\nProduction schedule:")
print(schedule.to_string(index=False))
