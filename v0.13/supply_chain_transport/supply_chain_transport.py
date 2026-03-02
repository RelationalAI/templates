"""Supply Chain Transport (prescriptive optimization) template.

This script demonstrates a multi-mode transportation optimization model in RelationalAI:

- Load sample CSVs describing warehouses, customers, transport modes, and routes.
- Create a shipment decision for each route–mode combination.
- Enforce warehouse inventory limits, customer demand satisfaction, and delivery deadlines.
- Minimize total transport cost.

Run:
    `python supply_chain_transport.py`

Output:
    Prints an optimal shipment plan per scenario, then a scenario summary with
    termination status and objective value.
"""

from pathlib import Path

import pandas
from pandas import read_csv

from relationalai.semantics import Model, data, define, require, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"

# Disable pandas inference of string types. This ensures that string columns
# in the CSVs are loaded as object dtype. This is only required when using
# relationalai versions prior to v1.0.
pandas.options.future.infer_string = False

# Parameters.
EXCLUDED_WAREHOUSE = None

# Scenarios (what-if analysis).
SCENARIO_PARAM = "excluded_warehouse"
SCENARIO_VALUES = [None, "Warehouse_East", "Warehouse_Central"]
SCENARIO_CONCEPT = "Warehouse"  # Entity type for exclusion scenarios.

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

# Create a Semantics model container.
model = Model("supply_chain_transport", config=globals().get("config", None), use_lqp=False)

# Warehouse concept: warehouses with inventory.
Warehouse = model.Concept("Warehouse")
Warehouse.id = model.Property("{Warehouse} has {id:int}")
Warehouse.name = model.Property("{Warehouse} has {name:string}")
Warehouse.inventory = model.Property("{Warehouse} has {inventory:int}")

# Load warehouse data from CSV.
data(read_csv(DATA_DIR / "warehouses.csv")).into(Warehouse, keys=["id"])

# Customer concept: customers with demand and due dates.
Customer = model.Concept("Customer")
Customer.id = model.Property("{Customer} has {id:int}")
Customer.name = model.Property("{Customer} has {name:string}")
Customer.demand = model.Property("{Customer} has {demand:int}")
Customer.due_day = model.Property("{Customer} has {due_day:int}")

# Load customer data from CSV.
data(read_csv(DATA_DIR / "customers.csv")).into(Customer, keys=["id"])

# TransportMode concept: modes with cost, transit time, and capacity.
TransportMode = model.Concept("TransportMode")
TransportMode.id = model.Property("{TransportMode} has {id:int}")
TransportMode.name = model.Property("{TransportMode} has {name:string}")
TransportMode.cost_per_unit = model.Property("{TransportMode} has {cost_per_unit:float}")
TransportMode.transit_days = model.Property("{TransportMode} has {transit_days:int}")
TransportMode.capacity = model.Property("{TransportMode} has {capacity:int}")

# Load transport mode data from CSV.
data(read_csv(DATA_DIR / "transport_modes.csv")).into(TransportMode, keys=["id"])

# Route concept: routes between warehouses and customers.
Route = model.Concept("Route")
Route.id = model.Property("{Route} has {id:int}")
Route.warehouse = model.Property("{Route} from {warehouse:Warehouse}")
Route.customer = model.Property("{Route} to {customer:Customer}")
Route.distance = model.Property("{Route} has {distance:int}")

# Load route data from CSV.
routes_data = data(read_csv(DATA_DIR / "routes.csv"))

# Create one Route entity per row by joining warehouse_id and customer_id.
where(
    Warehouse.id == routes_data.warehouse_id,
    Customer.id == routes_data.customer_id
).define(
    Route.new(
        id=routes_data.id,
        warehouse=Warehouse,
        customer=Customer,
        distance=routes_data.distance,
    )
)

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

# Shipment decision concept: quantity shipped for each route–mode combination.
Shipment = model.Concept("Shipment")
Shipment.route = model.Property("{Shipment} on {route:Route}")
Shipment.mode = model.Property("{Shipment} via {mode:TransportMode}")
Shipment.x_quantity = model.Property("{Shipment} has {quantity:float}")
Shipment.x_selected = model.Property("{Shipment} is {selected:float}")
define(Shipment.new(route=Route, mode=TransportMode))

Sh = Shipment.ref()


def build_formulation(s):
    """Register variables, constraints, and objective on the solver model."""
    # Variable: shipment quantity and selection.
    s.solve_for(
        Shipment.x_quantity,
        name=[
            "qty",
            Shipment.route.warehouse.name,
            Shipment.route.customer.name,
            Shipment.mode.name,
        ],
        lower=0,
    )
    s.solve_for(
        Shipment.x_selected,
        type="bin",
        name=[
            "sel",
            Shipment.route.warehouse.name,
            Shipment.route.customer.name,
            Shipment.mode.name,
        ],
    )

    # Constraint: shipment quantity bounded by mode capacity when selected.
    capacity_bound = require(Shipment.x_quantity <= Shipment.mode.capacity * Shipment.x_selected)
    s.satisfy(capacity_bound)

    min_bound = require(Shipment.x_quantity >= Shipment.x_selected)
    s.satisfy(min_bound)

    # Constraint: total outbound from warehouse cannot exceed inventory.
    outbound = sum(Sh.quantity).where(Sh.route.warehouse == Warehouse).per(Warehouse)
    inventory_limit = require(outbound <= Warehouse.inventory)
    s.satisfy(inventory_limit)

    # Constraint: demand satisfaction for each customer.
    inbound = sum(Sh.quantity).where(Sh.route.customer == Customer).per(Customer)
    demand_met = require(inbound >= Customer.demand)
    s.satisfy(demand_met)

    # Constraint: on-time delivery (no shipments via modes that would be late)
    on_time = require(Shipment.x_quantity == 0).where(
        Shipment.mode.transit_days > Shipment.route.customer.due_day
    )
    s.satisfy(on_time)

    # Constraint: exclude warehouse if specified.
    if EXCLUDED_WAREHOUSE is not None:
        exclude = require(Shipment.x_quantity == 0).where(
            Shipment.route.warehouse.name == EXCLUDED_WAREHOUSE
        )
        s.satisfy(exclude)

    # Objective: minimize total transport cost (distance-weighted)
    total_cost = sum(Shipment.x_quantity * Shipment.mode.cost_per_unit * Shipment.route.distance / 100)
    s.minimize(total_cost)


# --------------------------------------------------
# Solve with Scenario Analysis (Warehouse Exclusion)
# --------------------------------------------------

scenario_results = []

for scenario_value in SCENARIO_VALUES:
    print(f"\nRunning scenario: {SCENARIO_PARAM} = {scenario_value}")

    # Set scenario parameter (entity to exclude).
    EXCLUDED_WAREHOUSE = scenario_value

    # Create a fresh SolverModel for each scenario.
    s = SolverModel(model, "cont")
    build_formulation(s)

    solver = Solver("highs")
    s.solve(solver, time_limit_sec=60)

    scenario_results.append(
        {
            "scenario": scenario_value,
            "status": str(s.termination_status),
            "objective": s.objective_value,
        }
    )
    print(f"  Status: {s.termination_status}, Objective: {s.objective_value}")

    # Print shipment plan from solver results.
    var_df = s.variable_values().to_df()
    qty_df = var_df[
        var_df["name"].str.startswith("qty") & (var_df["float"] > 0.001)
    ].rename(columns={"float": "value"})
    print("\n  Shipments:")
    print(qty_df.to_string(index=False))

# Summary.
print("\n" + "=" * 50)
print("Scenario Analysis Summary")
print("=" * 50)
for result in scenario_results:
    print(f"  {result['scenario']}: {result['status']}, obj={result['objective']}")
