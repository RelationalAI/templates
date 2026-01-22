# Production Planning:
# Schedule production on machines to meet demand and maximize profit

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Model, data, define, require, select, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

model = Model("production_planning", config=globals().get("config", None), use_lqp=False)

# --------------------------------------------------
# Load Data and Define Ontology
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Products with demand and profit margin
Product = model.Concept("Product")
Product.id = model.Property("{Product} has {id:int}")
Product.name = model.Property("{Product} has {name:string}")
Product.demand = model.Property("{Product} has {demand:int}")
Product.profit = model.Property("{Product} has {profit:float}")
data(read_csv(data_dir / "products.csv")).into(Product, keys=["id"])

# Machines with available hours
Machine = model.Concept("Machine")
Machine.id = model.Property("{Machine} has {id:int}")
Machine.name = model.Property("{Machine} has {name:string}")
Machine.hours_available = model.Property("{Machine} has {hours_available:float}")
data(read_csv(data_dir / "machines.csv")).into(Machine, keys=["id"])

# Production rates: hours per unit for each machine/product combination
Rate = model.Concept("ProductionRate")
Rate.machine = model.Property("{ProductionRate} on {machine:Machine}")
Rate.product = model.Property("{ProductionRate} for {product:Product}")
Rate.hours_per_unit = model.Property("{ProductionRate} has {hours_per_unit:float}")

rates_data = data(read_csv(data_dir / "production_rates.csv"))
where(Machine.id(rates_data.machine_id), Product.id(rates_data.product_id)).define(
    Rate.new(machine=Machine, product=Product, hours_per_unit=rates_data.hours_per_unit)
)

# Production: decision variable for units produced
Production = model.Concept("Production")
Production.rate = model.Property("{Production} uses {rate:ProductionRate}")
Production.quantity = model.Property("{Production} has {quantity:float}")
define(Production.new(rate=Rate))

# --------------------------------------------------
# Define Optimization Problem
# --------------------------------------------------

Prod = Production.ref()

# Constraint: machine capacity
machine_hours = sum(Prod.quantity * Prod.rate.hours_per_unit).where(Prod.rate.machine == Machine).per(Machine)
capacity_limit = require(machine_hours <= Machine.hours_available)

# Constraint: meet demand
product_qty = sum(Prod.quantity).where(Prod.rate.product == Product).per(Product)
meet_demand = require(product_qty >= Product.demand)

# Objective: maximize total profit
total_profit = sum(Production.quantity * Production.rate.product.profit)

# --------------------------------------------------
# Set Up Solver Model
# --------------------------------------------------

s = SolverModel(model, "cont")
s.solve_for(Production.quantity, name=["qty", Production.rate.machine.name, Production.rate.product.name], lower=0, type="int")
s.maximize(total_profit)
s.satisfy(capacity_limit)
s.satisfy(meet_demand)

# --------------------------------------------------
# Solve and Display Results
# --------------------------------------------------

solver = Solver("highs")
s.solve(solver, time_limit_sec=60)

print(f"Status: {s.termination_status}")
print(f"Total profit: ${s.objective_value:.2f}")

# Access solution via populated relations
schedule = select(
    Production.rate.machine.name.alias("machine"),
    Production.rate.product.name.alias("product"),
    Production.quantity
).where(Production.quantity > 0).to_df()

print("\nProduction schedule:")
print(schedule.to_string(index=False))
