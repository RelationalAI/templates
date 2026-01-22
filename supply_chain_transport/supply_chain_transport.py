# supply chain transport problem:
# route shipments from warehouses to customers minimizing cost while meeting demand

from pathlib import Path

from pandas import read_csv

from relationalai.semantics import Model, data, define, require, select, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

model = Model("supply_chain_transport", config=globals().get("config", None), use_lqp=False)

# --------------------------------------------------
# Define ontology & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Concept: warehouses with inventory
Warehouse = model.Concept("Warehouse")
Warehouse.id = model.Property("{Warehouse} has {id:int}")
Warehouse.name = model.Property("{Warehouse} has {name:string}")
Warehouse.inventory = model.Property("{Warehouse} has {inventory:int}")
data(read_csv(data_dir / "warehouses.csv")).into(Warehouse, keys=["id"])

# Concept: customers with demand and due dates
Customer = model.Concept("Customer")
Customer.id = model.Property("{Customer} has {id:int}")
Customer.name = model.Property("{Customer} has {name:string}")
Customer.demand = model.Property("{Customer} has {demand:int}")
Customer.due_day = model.Property("{Customer} has {due_day:int}")
data(read_csv(data_dir / "customers.csv")).into(Customer, keys=["id"])

# Concept: transport modes with cost, transit time, and capacity
TransportMode = model.Concept("TransportMode")
TransportMode.id = model.Property("{TransportMode} has {id:int}")
TransportMode.name = model.Property("{TransportMode} has {name:string}")
TransportMode.cost_per_unit = model.Property("{TransportMode} has {cost_per_unit:float}")
TransportMode.transit_days = model.Property("{TransportMode} has {transit_days:int}")
TransportMode.capacity = model.Property("{TransportMode} has {capacity:int}")
data(read_csv(data_dir / "transport_modes.csv")).into(TransportMode, keys=["id"])

# Relationship: routes between warehouses and customers
Route = model.Concept("Route")
Route.id = model.Property("{Route} has {id:int}")
Route.warehouse = model.Property("{Route} from {warehouse:Warehouse}")
Route.customer = model.Property("{Route} to {customer:Customer}")
Route.distance = model.Property("{Route} has {distance:int}")

routes_data = data(read_csv(data_dir / "routes.csv"))
where(Warehouse.id(routes_data.warehouse_id), Customer.id(routes_data.customer_id)).define(
    Route.new(id=routes_data.id, warehouse=Warehouse, customer=Customer, distance=routes_data.distance)
)

# --------------------------------------------------
# Model the problem
# --------------------------------------------------

# Decision concept: shipments as route × mode combinations
Shipment = model.Concept("Shipment")
Shipment.route = model.Property("{Shipment} on {route:Route}")
Shipment.mode = model.Property("{Shipment} via {mode:TransportMode}")
Shipment.quantity = model.Property("{Shipment} has {quantity:float}")
Shipment.selected = model.Property("{Shipment} is {selected:float}")
define(Shipment.new(route=Route, mode=TransportMode))

Sh = Shipment.ref()

s = SolverModel(model, "cont")

# Variable: shipment quantity and selection
s.solve_for(Shipment.quantity, name=["qty", Shipment.route.warehouse.name, Shipment.route.customer.name, Shipment.mode.name], lower=0)
s.solve_for(Shipment.selected, type="bin", name=["sel", Shipment.route.warehouse.name, Shipment.route.customer.name, Shipment.mode.name])

# Constraint: shipment quantity bounded by mode capacity when selected
capacity_bound = require(Shipment.quantity <= Shipment.mode.capacity * Shipment.selected)
s.satisfy(capacity_bound)

min_bound = require(Shipment.quantity >= Shipment.selected)
s.satisfy(min_bound)

# Constraint: total outbound from warehouse cannot exceed inventory
outbound = sum(Sh.quantity).where(Sh.route.warehouse == Warehouse).per(Warehouse)
inventory_limit = require(outbound <= Warehouse.inventory)
s.satisfy(inventory_limit)

# Constraint: demand satisfaction for each customer
inbound = sum(Sh.quantity).where(Sh.route.customer == Customer).per(Customer)
demand_met = require(inbound >= Customer.demand)
s.satisfy(demand_met)

# Constraint: on-time delivery (no shipments via modes that would be late)
on_time = require(Shipment.quantity == 0).where(
    Shipment.mode.transit_days > Shipment.route.customer.due_day
)
s.satisfy(on_time)

# Objective: minimize total transport cost
total_cost = sum(Shipment.quantity * Shipment.mode.cost_per_unit)
s.minimize(total_cost)

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

solver = Solver("highs")
s.solve(solver, time_limit_sec=60)

print(f"Status: {s.termination_status}")
print(f"Total transport cost: ${s.objective_value:.2f}")

shipments = select(
    Shipment.route.warehouse.name.alias("warehouse"),
    Shipment.route.customer.name.alias("customer"),
    Shipment.mode.name.alias("mode"),
    Shipment.quantity
).where(Shipment.quantity > 0.001).to_df()

print("\nShipments:")
print(shipments.to_string(index=False))
