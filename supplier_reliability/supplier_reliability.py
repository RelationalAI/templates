# supplier reliability problem:
# select suppliers to meet demand balancing cost and reliability

from pathlib import Path

from pandas import read_csv

from relationalai.semantics import Model, data, define, require, select, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

model = Model("supplier_reliability", config=globals().get("config", None), use_lqp=False)

# --------------------------------------------------
# Define ontology & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Concept: suppliers with reliability scores and capacity
Supplier = model.Concept("Supplier")
Supplier.id = model.Property("{Supplier} has {id:int}")
Supplier.name = model.Property("{Supplier} has {name:string}")
Supplier.reliability = model.Property("{Supplier} has {reliability:float}")
Supplier.capacity = model.Property("{Supplier} has {capacity:int}")
data(read_csv(data_dir / "suppliers.csv")).into(Supplier, keys=["id"])

# Concept: products with demand requirements
Product = model.Concept("Product")
Product.id = model.Property("{Product} has {id:int}")
Product.name = model.Property("{Product} has {name:string}")
Product.demand = model.Property("{Product} has {demand:int}")
data(read_csv(data_dir / "products.csv")).into(Product, keys=["id"])

# Relationship: supply options linking suppliers to products
SupplyOption = model.Concept("SupplyOption")
SupplyOption.id = model.Property("{SupplyOption} has {id:int}")
SupplyOption.supplier = model.Property("{SupplyOption} from {supplier:Supplier}")
SupplyOption.product = model.Property("{SupplyOption} for {product:Product}")
SupplyOption.cost_per_unit = model.Property("{SupplyOption} has {cost_per_unit:float}")

options_data = data(read_csv(data_dir / "supply_options.csv"))
where(Supplier.id(options_data.supplier_id), Product.id(options_data.product_id)).define(
    SupplyOption.new(id=options_data.id, supplier=Supplier, product=Product,
                     cost_per_unit=options_data.cost_per_unit)
)

# --------------------------------------------------
# Model the problem
# --------------------------------------------------

# Decision concept: orders placed via each supply option
Order = model.Concept("Order")
Order.option = model.Property("{Order} uses {option:SupplyOption}")
Order.quantity = model.Property("{Order} has {quantity:float}")
define(Order.new(option=SupplyOption))

# Parameters
reliability_weight = 0.0  # penalty weight for unreliable suppliers (0 = cost only)

Ord = Order.ref()
Pr = Product.ref()

s = SolverModel(model, "cont")

# Variable: order quantity
s.solve_for(Order.quantity, name=["qty", Order.option.supplier.name, Order.option.product.name], lower=0)

# Constraint: total orders from supplier cannot exceed supplier capacity
orders_from_supplier = sum(Ord.quantity).where(Ord.option.supplier == Supplier).per(Supplier)
capacity_limit = require(orders_from_supplier <= Supplier.capacity)
s.satisfy(capacity_limit)

# Constraint: demand satisfaction for each product
orders_for_product = sum(Ord.quantity).where(Ord.option.product == Pr).per(Pr)
meet_demand = require(orders_for_product >= Pr.demand)
s.satisfy(meet_demand)

# Objective: minimize cost with optional reliability penalty
direct_cost = sum(Order.quantity * Order.option.cost_per_unit)
if reliability_weight > 0:
    reliability_penalty = reliability_weight * sum(
        Order.quantity * (1.0 - Order.option.supplier.reliability)
    )
    total_cost = direct_cost + reliability_penalty
else:
    total_cost = direct_cost
s.minimize(total_cost)

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

solver = Solver("highs")
s.solve(solver, time_limit_sec=60)

print(f"Status: {s.termination_status}")
print(f"Total cost: ${s.objective_value:.2f}")

orders = select(
    Order.option.supplier.name.alias("supplier"),
    Order.option.product.name.alias("product"),
    Order.quantity
).where(Order.quantity > 0.001).to_df()

print("\nOrder quantities:")
print(orders.to_string(index=False))
