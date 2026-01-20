"""Supply Chain Transport - Route shipments from warehouses to customers via transport modes."""

from pathlib import Path
from time import time_ns

from pandas import read_csv
from relationalai.semantics import Model, data, define, require, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel


def define_model(config=None):
    """Define base model with Warehouse, Customer, TransportMode, and Route concepts."""
    model = Model(f"supply_chain_transport_{time_ns()}", config=config, use_lqp=False)

    # Concepts
    Warehouse = model.Concept("Warehouse")
    Warehouse.id = model.Property("{Warehouse} has {id:int}")
    Warehouse.name = model.Property("{Warehouse} has {name:string}")
    Warehouse.inventory = model.Property("{Warehouse} has {inventory:int}")

    Customer = model.Concept("Customer")
    Customer.id = model.Property("{Customer} has {id:int}")
    Customer.name = model.Property("{Customer} has {name:string}")
    Customer.demand = model.Property("{Customer} has {demand:int}")
    Customer.due_day = model.Property("{Customer} has {due_day:int}")

    TransportMode = model.Concept("TransportMode")
    TransportMode.id = model.Property("{TransportMode} has {id:int}")
    TransportMode.name = model.Property("{TransportMode} has {name:string}")
    TransportMode.cost_per_unit = model.Property("{TransportMode} has {cost_per_unit:float}")
    TransportMode.transit_days = model.Property("{TransportMode} has {transit_days:int}")
    TransportMode.capacity = model.Property("{TransportMode} has {capacity:int}")

    Route = model.Concept("Route")
    Route.id = model.Property("{Route} has {id:int}")
    Route.warehouse = model.Property("{Route} from {warehouse:Warehouse}")
    Route.customer = model.Property("{Route} to {customer:Customer}")
    Route.distance = model.Property("{Route} has {distance:int}")

    # Load data
    data_dir = Path(__file__).parent / "data"

    warehouses_df = read_csv(data_dir / "warehouses.csv")
    data(warehouses_df).into(Warehouse, keys=["id"])

    customers_df = read_csv(data_dir / "customers.csv")
    data(customers_df).into(Customer, keys=["id"])

    modes_df = read_csv(data_dir / "transport_modes.csv")
    data(modes_df).into(TransportMode, keys=["id"])

    routes_df = read_csv(data_dir / "routes.csv")
    routes_data = data(routes_df)
    where(Warehouse.id(routes_data.warehouse_id), Customer.id(routes_data.customer_id)).define(
        Route.new(id=routes_data.id, warehouse=Warehouse, customer=Customer, distance=routes_data.distance)
    )

    # Shipment: decision variable for quantity shipped via route and mode
    Shipment = model.Concept("Shipment")
    Shipment.route = model.Property("{Shipment} on {route:Route}")
    Shipment.mode = model.Property("{Shipment} via {mode:TransportMode}")
    Shipment.quantity = model.Property("{Shipment} has {quantity:float}")
    Shipment.selected = model.Property("{Shipment} is {selected:float}")
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
    s.solve_for(Shipment.quantity, name=["qty", Shipment.route.warehouse.name, Shipment.route.customer.name, Shipment.mode.name], lower=0)

    # Binary variable: whether shipment is used
    s.solve_for(Shipment.selected, type="bin", name=["sel", Shipment.route.warehouse.name, Shipment.route.customer.name, Shipment.mode.name])

    # Constraint: shipment quantity bounded by mode capacity when selected
    s.satisfy(require(Shipment.quantity <= Shipment.mode.capacity * Shipment.selected))
    s.satisfy(require(Shipment.quantity >= Shipment.selected))

    # Constraint: total outbound from warehouse cannot exceed inventory
    Sh = Shipment.ref()
    outbound = sum(Sh.quantity).where(Sh.route.warehouse == Warehouse).per(Warehouse)
    s.satisfy(require(outbound <= Warehouse.inventory))

    # Constraint: demand satisfaction for each customer
    inbound = sum(Sh.quantity).where(Sh.route.customer == Customer).per(Customer)
    s.satisfy(require(inbound >= Customer.demand))

    # Constraint: on-time delivery
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
