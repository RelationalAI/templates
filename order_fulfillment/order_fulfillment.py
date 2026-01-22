# Order Fulfillment:
# Assign orders to fulfillment centers minimizing total cost

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Model, data, define, require, select, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

model = Model("order_fulfillment", config=globals().get("config", None), use_lqp=False)

# --------------------------------------------------
# Load Data and Define Ontology
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Fulfillment centers with capacity and fixed costs
FC = model.Concept("FulfillmentCenter")
FC.id = model.Property("{FulfillmentCenter} has {id:int}")
FC.name = model.Property("{FulfillmentCenter} has {name:string}")
FC.capacity = model.Property("{FulfillmentCenter} has {capacity:int}")
FC.fixed_cost = model.Property("{FulfillmentCenter} has {fixed_cost:float}")
data(read_csv(data_dir / "fulfillment_centers.csv")).into(FC, keys=["id"])

# Orders with customer, quantity, and priority
Order = model.Concept("Order")
Order.id = model.Property("{Order} has {id:int}")
Order.customer = model.Property("{Order} for {customer:string}")
Order.quantity = model.Property("{Order} has {quantity:int}")
Order.priority = model.Property("{Order} has {priority:int}")
data(read_csv(data_dir / "orders.csv")).into(Order, keys=["id"])

# Shipping costs between FCs and orders
ShippingCost = model.Concept("ShippingCost")
ShippingCost.fc = model.Property("{ShippingCost} from {fc:FulfillmentCenter}")
ShippingCost.order = model.Property("{ShippingCost} for {order:Order}")
ShippingCost.cost_per_unit = model.Property("{ShippingCost} has {cost_per_unit:float}")

costs_data = data(read_csv(data_dir / "shipping_costs.csv"))
where(FC.id(costs_data.fc_id), Order.id(costs_data.order_id)).define(
    ShippingCost.new(fc=FC, order=Order, cost_per_unit=costs_data.cost_per_unit)
)

# Assignment: decision variable for fulfilling orders from FCs
Assignment = model.Concept("Assignment")
Assignment.shipping = model.Property("{Assignment} uses {shipping:ShippingCost}")
Assignment.qty = model.Property("{Assignment} has {qty:float}")
define(Assignment.new(shipping=ShippingCost))

# FCUsage: track whether each FC is used (for fixed costs)
FCUsage = model.Concept("FCUsage")
FCUsage.fc = model.Property("{FCUsage} for {fc:FulfillmentCenter}")
FCUsage.used = model.Property("{FCUsage} is {used:float}")
define(FCUsage.new(fc=FC))

# --------------------------------------------------
# Define Optimization Problem
# --------------------------------------------------

Asn = Assignment.ref()

# Constraint: FC capacity
fc_total_qty = sum(Asn.qty).where(Asn.shipping.fc == FC).per(FC)
capacity_limit = require(fc_total_qty <= FC.capacity)

# Constraint: link FC usage to assignments
fc_total_qty_for_usage = sum(Asn.qty).where(Asn.shipping.fc == FCUsage.fc).per(FCUsage)
usage_link = require(fc_total_qty_for_usage <= FCUsage.fc.capacity * FCUsage.used)

# Constraint: each order must be fully fulfilled
order_fulfilled = sum(Asn.qty).where(Asn.shipping.order == Order).per(Order)
fulfill_all = require(order_fulfilled == Order.quantity)

# Objective: minimize total cost (shipping + fixed FC costs)
shipping_cost = sum(Assignment.qty * Assignment.shipping.cost_per_unit)
fixed_cost = sum(FCUsage.used * FCUsage.fc.fixed_cost)
total_cost = shipping_cost + fixed_cost

# --------------------------------------------------
# Set Up Solver Model
# --------------------------------------------------

s = SolverModel(model, "cont")
s.solve_for(Assignment.qty, name=["qty", Assignment.shipping.fc.name, Assignment.shipping.order.customer], lower=0)
s.solve_for(FCUsage.used, type="bin", name=["fc_used", FCUsage.fc.name])
s.minimize(total_cost)
s.satisfy(capacity_limit)
s.satisfy(usage_link)
s.satisfy(fulfill_all)

# --------------------------------------------------
# Solve and Display Results
# --------------------------------------------------

solver = Solver("highs")
s.solve(solver, time_limit_sec=60)

print(f"Status: {s.termination_status}")
print(f"Total cost (shipping + fixed): ${s.objective_value:.2f}")

# Access solution via populated relations
assignments = select(
    Assignment.shipping.fc.name.alias("fulfillment_center"),
    Assignment.shipping.order.customer.alias("customer"),
    Assignment.qty.alias("quantity")
).where(Assignment.qty > 0.001).to_df()

print("\nAssignments:")
print(assignments.to_string(index=False))

# Show which FCs are used
fc_used = select(FCUsage.fc.name.alias("fc")).where(FCUsage.used > 0.5).to_df()
print(f"\nActive fulfillment centers: {', '.join(fc_used['fc'].tolist())}")
