# order fulfillment problem:
# assign orders to fulfillment centers minimizing total cost

from pathlib import Path

from pandas import read_csv

from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("order_fulfillment")
Concept, Property = model.Concept, model.Property

# --------------------------------------------------
# Define ontology & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Concept: fulfillment centers with capacity and fixed costs
FC = Concept("FulfillmentCenter", identify_by={"id": Integer})
FC.name = Property(f"{FC} has {String:name}")
FC.capacity = Property(f"{FC} has {Integer:capacity}")
FC.fixed_cost = Property(f"{FC} has {Float:fixed_cost}")
fc_csv = read_csv(data_dir / "fulfillment_centers.csv")
model.define(FC.new(model.data(fc_csv).to_schema()))

# Concept: orders with customer, quantity, and priority
Order = Concept("Order", identify_by={"id": Integer})
Order.customer = Property(f"{Order} for {String:customer}")
Order.quantity = Property(f"{Order} has {Integer:quantity}")
Order.priority = Property(f"{Order} has {Integer:priority}")
order_csv = read_csv(data_dir / "orders.csv")
model.define(Order.new(model.data(order_csv).to_schema()))

# Relationship: shipping costs between FCs and orders
ShippingCost = Concept("ShippingCost")
ShippingCost.fc = Property(f"{ShippingCost} from {FC}", short_name="fc")
ShippingCost.order = Property(f"{ShippingCost} for {Order}", short_name="order")
ShippingCost.cost_per_unit = Property(f"{ShippingCost} has {Float:cost_per_unit}")

costs_csv = read_csv(data_dir / "shipping_costs.csv")
costs_data = model.data(costs_csv)
model.define(
    sc := ShippingCost.new(fc=FC, order=Order, cost_per_unit=costs_data.cost_per_unit)
).where(FC.id == costs_data.fc_id, Order.id == costs_data.order_id)

# --------------------------------------------------
# Model the problem
# --------------------------------------------------

# Decision concept: assignments of orders to fulfillment centers
Assignment = Concept("Assignment")
Assignment.shipping = Property(f"{Assignment} uses {ShippingCost}", short_name="shipping")
Assignment.x_qty = Property(f"{Assignment} has {Float:qty}")
model.define(Assignment.new(shipping=ShippingCost))

# Decision concept: track whether each FC is used (for fixed costs)
FCUsage = Concept("FCUsage")
FCUsage.fc = Property(f"{FCUsage} for {FC}", short_name="fc")
FCUsage.x_used = Property(f"{FCUsage} is {Float:used}")
model.define(FCUsage.new(fc=FC))

AssignmentRef = Assignment.ref()

s = Problem(model, Float)

# Variable: assignment quantity and FC usage
s.solve_for(Assignment.x_qty, name=["qty", Assignment.shipping.fc.name, Assignment.shipping.order.customer], lower=0)
s.solve_for(FCUsage.x_used, type="bin", name=["fc_used", FCUsage.fc.name])

# Constraint: FC capacity
fc_total_qty = sum(AssignmentRef.x_qty).where(AssignmentRef.shipping.fc == FC).per(FC)
capacity_limit = model.require(fc_total_qty <= FC.capacity)
s.satisfy(capacity_limit)

# Constraint: link FC usage to assignments
fc_total_qty_for_usage = sum(AssignmentRef.x_qty).where(AssignmentRef.shipping.fc == FCUsage.fc).per(FCUsage)
usage_link = model.require(fc_total_qty_for_usage <= FCUsage.fc.capacity * FCUsage.x_used)
s.satisfy(usage_link)

# Constraint: each order must be fully fulfilled
order_fulfilled = sum(AssignmentRef.x_qty).where(AssignmentRef.shipping.order == Order).per(Order)
fulfill_all = model.require(order_fulfilled == Order.quantity)
s.satisfy(fulfill_all)

# Objective: minimize total cost (shipping + fixed FC costs)
shipping_cost = sum(Assignment.x_qty * Assignment.shipping.cost_per_unit)
fixed_cost = sum(FCUsage.x_used * FCUsage.fc.fixed_cost)
total_cost = shipping_cost + fixed_cost
s.minimize(total_cost)

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

s.display()
s.solve("highs", time_limit_sec=60, _server_side_import=False)
s.display_solve_info()

print(f"Status: {s.termination_status}")
print(f"Total cost (shipping + fixed): ${s.objective_value:.2f}")

assignments = model.select(
    Assignment.shipping.fc.name.alias("fulfillment_center"),
    Assignment.shipping.order.customer.alias("customer"),
    Assignment.x_qty.alias("quantity")
).where(Assignment.x_qty > 0.001).to_df()

print("\nAssignments:")
print(assignments.to_string(index=False))

fc_used = model.select(FCUsage.fc.name.alias("fc")).where(FCUsage.x_used > 0.5).to_df()
print(f"\nActive fulfillment centers: {', '.join(fc_used['fc'].tolist())}")
