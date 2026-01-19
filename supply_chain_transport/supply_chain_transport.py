"""Supply Chain Transport - Route shipments from warehouses to customers via transport modes."""

from pathlib import Path
from time import time_ns

from pandas import read_csv
from relationalai.semantics import Model, data, define, require, sum
from relationalai.semantics.reasoners.optimization import Solver, SolverModel


def define_model(config=None):
    """Define base model with Warehouse, Customer, TransportMode, and Route concepts."""
    model = Model(f"supply_chain_transport_{time_ns()}", config=config, use_lqp=False)
    Concept, Property, Relationship = model.Concept, model.Property, model.Relationship

    data_dir = Path(__file__).parent / "data"

    # Warehouse: sources with inventory
    Warehouse = Concept("Warehouse")
    Warehouse.name = Property("{Warehouse} has name {name:String}")
    Warehouse.inventory = Property("{Warehouse} has inventory {inventory:int}")
    warehouses_df = read_csv(data_dir / "warehouses.csv")
    data(warehouses_df).into(Warehouse, id="id", properties=["name", "inventory"])

    # Customer: destinations with demand and due dates
    Customer = Concept("Customer")
    Customer.name = Property("{Customer} has name {name:String}")
    Customer.demand = Property("{Customer} has demand {demand:int}")
    Customer.due_day = Property("{Customer} has due_day {due_day:int}")
    customers_df = read_csv(data_dir / "customers.csv")
    data(customers_df).into(Customer, id="id", properties=["name", "demand", "due_day"])

    # TransportMode: available transport options
    TransportMode = Concept("TransportMode")
    TransportMode.name = Property("{TransportMode} has name {name:String}")
    TransportMode.cost_per_unit = Property("{TransportMode} has cost_per_unit {cost_per_unit:float}")
    TransportMode.transit_days = Property("{TransportMode} has transit_days {transit_days:int}")
    TransportMode.capacity = Property("{TransportMode} has capacity {capacity:int}")
    modes_df = read_csv(data_dir / "transport_modes.csv")
    data(modes_df).into(TransportMode, id="id", properties=["name", "cost_per_unit", "transit_days", "capacity"])

    # Route: warehouse to customer connections
    Route = Concept("Route")
    Route.distance = Property("{Route} has distance {distance:int}")
    Route.warehouse = Relationship("{Route} from {warehouse:Warehouse}")
    Route.customer = Relationship("{Route} to {customer:Customer}")
    routes_df = read_csv(data_dir / "routes.csv")
    data(routes_df).into(
        Route,
        id="id",
        properties=["distance"],
        relationships={"warehouse": ("warehouse_id", Warehouse), "customer": ("customer_id", Customer)},
    )

    # Shipment: decision variable for quantity shipped via route and mode
    Shipment = Concept("Shipment")
    Shipment.route = Relationship("{Shipment} on {route:Route}")
    Shipment.mode = Relationship("{Shipment} via {mode:TransportMode}")
    Shipment.quantity = Property("{Shipment} has quantity {quantity:float}")
    Shipment.selected = Property("{Shipment} is selected {selected:float}")
    define(Shipment.new(route=Route, mode=TransportMode))

    model.Warehouse = Warehouse
    model.Customer = Customer
    model.TransportMode = TransportMode
    model.Route = Route
    model.Shipment = Shipment
    return model


def define_problem(model):
    """Define decision variables, constraints, and objective."""
    s = SolverModel(model, "cont")
    Warehouse, Customer, TransportMode, Route, Shipment = (
        model.Warehouse, model.Customer, model.TransportMode, model.Route, model.Shipment
    )

    # Decision variable: quantity to ship via each route/mode combination
    s.solve_for(Shipment.quantity, name=[Shipment.route, Shipment.mode], lower=0)

    # Binary variable: whether shipment is used (for fixed costs if needed)
    s.solve_for(Shipment.selected, type="bin", name=["sel", Shipment.route, Shipment.mode])

    # Constraint: shipment quantity bounded by mode capacity when selected
    M = 10000  # Big-M
    s.satisfy(require(Shipment.quantity <= Shipment.mode.capacity * Shipment.selected))
    s.satisfy(require(Shipment.quantity >= Shipment.selected))  # At least 1 if selected

    # Constraint: total outbound from warehouse cannot exceed inventory
    Sh = Shipment.ref()
    outbound = sum(Sh.quantity).where(Sh.route.warehouse == Warehouse).per(Warehouse)
    s.satisfy(require(outbound <= Warehouse.inventory))

    # Constraint: demand satisfaction for each customer
    inbound = sum(Sh.quantity).where(Sh.route.customer == Customer).per(Customer)
    s.satisfy(require(inbound >= Customer.demand))

    # Constraint: on-time delivery (transit_days <= due_day)
    # Only allow shipments where mode transit time meets customer due date
    s.satisfy(
        require(Shipment.quantity == 0).where(
            Shipment.mode.transit_days > Shipment.route.customer.due_day
        )
    )

    # Objective: minimize total transport cost
    total_cost = sum(Shipment.quantity * Shipment.mode.cost_per_unit)
    s.minimize(total_cost)

    return s


def solve(config=None, solver_name="highs"):
    """Orchestrate model, problem, and solver execution."""
    model = define_model(config)
    solver_model = define_problem(model)
    solver = Solver(solver_name)
    solver_model.solve(solver, time_limit_sec=60)
    return solver_model


def extract_solution(solver_model):
    """Extract solution as dict with metadata."""
    return {
        "status": solver_model.termination_status,
        "objective": solver_model.objective_value,
        "variables": solver_model.variable_values().to_df(),
    }


if __name__ == "__main__":
    sm = solve()
    sol = extract_solution(sm)

    print(f"Status: {sol['status']}")
    print(f"Total transport cost: ${sol['objective']:.2f}")
    print("\nShipments:")
    df = sol["variables"]
    active = df[df["float"] > 0] if "float" in df.columns else df
    print(active.to_string(index=False))
