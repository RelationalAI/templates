"""Order Fulfillment (prescriptive optimization) template.

This script demonstrates a mixed-integer linear optimization problem in RelationalAI:

- Load fulfillment centers, orders, and shipping costs from CSV.
- Choose shipment quantities for each fulfillment-center/order pair.
- Enforce fulfillment and capacity constraints.
- Pay a fixed cost for each fulfillment center that is used.
- Minimize total cost (shipping + fixed costs).

Run:
    `python order_fulfillment.py`

Output:
    Prints the solver termination status, objective value, a table of non-trivial
    assignments, and the active fulfillment centers.
"""

from pathlib import Path

import pandas
from pandas import read_csv

from relationalai.semantics import Model, data, define, require, select, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"

# Disable pandas inference of string types. This ensures that string columns
# in the CSVs are loaded as object dtype. This is only required when using
# relationalai versions prior to v1.0.
pandas.options.future.infer_string = False

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

# Create a Semantics model container.
model = Model("order_fulfillment", config=globals().get("config", None), use_lqp=False)

# FulfillmentCenter concept: fulfillment centers with capacity and fixed operating costs.
FC = model.Concept("FulfillmentCenter")
FC.id = model.Property("{FulfillmentCenter} has {id:int}")
FC.name = model.Property("{FulfillmentCenter} has {name:string}")
FC.capacity = model.Property("{FulfillmentCenter} has {capacity:int}")
FC.fixed_cost = model.Property("{FulfillmentCenter} has {fixed_cost:float}")

# Load fulfillment center data from CSV.
data(read_csv(DATA_DIR / "fulfillment_centers.csv")).into(FC, keys=["id"])

# Order concept: customer orders with required quantity and priority.
Order = model.Concept("Order")
Order.id = model.Property("{Order} has {id:int}")
Order.customer = model.Property("{Order} for {customer:string}")
Order.quantity = model.Property("{Order} has {quantity:int}")
Order.priority = model.Property("{Order} has {priority:int}")

# Load order data from CSV.
data(read_csv(DATA_DIR / "orders.csv")).into(Order, keys=["id"])

# ShippingCost concept: per-unit shipping cost for an FC/order pair.
ShippingCost = model.Concept("ShippingCost")
ShippingCost.fc = model.Property("{ShippingCost} from {fc:FulfillmentCenter}")
ShippingCost.order = model.Property("{ShippingCost} for {order:Order}")
ShippingCost.cost_per_unit = model.Property("{ShippingCost} has {cost_per_unit:float}")

# Load shipping cost data from CSV.
costs_data = data(read_csv(DATA_DIR / "shipping_costs.csv"))

# Define ShippingCost entities by joining FC and Order IDs from the CSV.
where(
    FC.id == costs_data.fc_id,
    Order.id == costs_data.order_id,
).define(
    ShippingCost.new(fc=FC, order=Order, cost_per_unit=costs_data.cost_per_unit)
)

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

# Assignment decision concept: shipment quantity for each shipping-cost option.
Assignment = model.Concept("Assignment")
Assignment.shipping = model.Property("{Assignment} uses {shipping:ShippingCost}")
Assignment.x_qty = model.Property("{Assignment} has {qty:float}")
define(Assignment.new(shipping=ShippingCost))

# FCUsage decision concept: whether each fulfillment center is active (for fixed costs).
FCUsage = model.Concept("FCUsage")
FCUsage.fc = model.Property("{FCUsage} for {fc:FulfillmentCenter}")
FCUsage.x_used = model.Property("{FCUsage} is {used:float}")
define(FCUsage.new(fc=FC))

Asn = Assignment.ref()

s = SolverModel(model, "cont")

# Decision variables: assignment quantity and fulfillment-center usage.
s.solve_for(
    Assignment.x_qty,
    name=["qty", Assignment.shipping.fc.name, Assignment.shipping.order.customer],
    lower=0,
)
s.solve_for(FCUsage.x_used, type="bin", name=["fc_used", FCUsage.fc.name])

# Constraint: FC capacity
fc_total_qty = sum(Asn.qty).where(Asn.shipping.fc == FC).per(FC)
capacity_limit = require(fc_total_qty <= FC.capacity)
s.satisfy(capacity_limit)

# Constraint: link FC usage to assignments
fc_total_qty_for_usage = sum(Asn.qty).where(Asn.shipping.fc == FCUsage.fc).per(FCUsage)
usage_link = require(fc_total_qty_for_usage <= FCUsage.fc.capacity * FCUsage.x_used)
s.satisfy(usage_link)

# Constraint: each order must be fully fulfilled
order_fulfilled = sum(Asn.qty).where(Asn.shipping.order == Order).per(Order)
fulfill_all = require(order_fulfilled == Order.quantity)
s.satisfy(fulfill_all)

# Objective: minimize total cost (shipping + fixed FC costs)
shipping_cost = sum(Assignment.x_qty * Assignment.shipping.cost_per_unit)
fixed_cost = sum(FCUsage.x_used * FCUsage.fc.fixed_cost)
total_cost = shipping_cost + fixed_cost
s.minimize(total_cost)

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

solver = Solver("highs")
s.solve(solver, time_limit_sec=60)

print(f"Status: {s.termination_status}")
print(f"Total cost (shipping + fixed): ${s.objective_value:.2f}")

assignments = select(
    Assignment.shipping.fc.name.alias("fulfillment_center"),
    Assignment.shipping.order.customer.alias("customer"),
    Assignment.x_qty.alias("quantity")
).where(Assignment.x_qty > 0.001).to_df()

print("\nAssignments:")
print(assignments.to_string(index=False))

fc_used = select(FCUsage.fc.name.alias("fc")).where(FCUsage.x_used > 0.5).to_df()
print(f"\nActive fulfillment centers: {', '.join(fc_used['fc'].tolist())}")
