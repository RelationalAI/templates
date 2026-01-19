"""Order Fulfillment - Assign orders to fulfillment centers minimizing total cost."""

from pathlib import Path
from time import time_ns

from pandas import read_csv
from relationalai.semantics import Model, data, define, require, sum
from relationalai.semantics.reasoners.optimization import Solver, SolverModel


def define_model(config=None):
    """Define base model with FulfillmentCenter, Order, and ShippingCost concepts."""
    model = Model(f"order_fulfillment_{time_ns()}", config=config, use_lqp=False)
    Concept, Property, Relationship = model.Concept, model.Property, model.Relationship

    data_dir = Path(__file__).parent / "data"

    # FulfillmentCenter: warehouses that can fulfill orders
    FC = Concept("FulfillmentCenter")
    FC.name = Property("{FulfillmentCenter} has name {name:String}")
    FC.capacity = Property("{FulfillmentCenter} has capacity {capacity:int}")
    FC.fixed_cost = Property("{FulfillmentCenter} has fixed_cost {fixed_cost:float}")
    fc_df = read_csv(data_dir / "fulfillment_centers.csv")
    data(fc_df).into(FC, id="id", properties=["name", "capacity", "fixed_cost"])

    # Order: customer orders to fulfill
    Order = Concept("Order")
    Order.customer = Property("{Order} for customer {customer:String}")
    Order.quantity = Property("{Order} has quantity {quantity:int}")
    Order.priority = Property("{Order} has priority {priority:int}")
    orders_df = read_csv(data_dir / "orders.csv")
    data(orders_df).into(Order, id="id", properties=["customer", "quantity", "priority"])

    # ShippingCost: cost to ship from FC to order destination
    ShippingCost = Concept("ShippingCost")
    ShippingCost.cost_per_unit = Property("{ShippingCost} has cost_per_unit {cost_per_unit:float}")
    ShippingCost.fc = Relationship("{ShippingCost} from {fc:FulfillmentCenter}")
    ShippingCost.order = Relationship("{ShippingCost} for {order:Order}")
    costs_df = read_csv(data_dir / "shipping_costs.csv")
    data(costs_df).into(
        ShippingCost,
        keys=["fc_id", "order_id"],
        properties=["cost_per_unit"],
        relationships={"fc": ("fc_id", FC), "order": ("order_id", Order)},
    )

    # Assignment: decision variable for fulfilling orders from FCs
    Assignment = Concept("Assignment")
    Assignment.shipping = Relationship("{Assignment} uses {shipping:ShippingCost}")
    Assignment.quantity = Property("{Assignment} has quantity {quantity:float}")
    Assignment.selected = Property("{Assignment} is selected {selected:float}")
    define(Assignment.new(shipping=ShippingCost))

    model.FC, model.Order, model.ShippingCost, model.Assignment = FC, Order, ShippingCost, Assignment
    return model


def define_problem(model):
    """Define decision variables, constraints, and objective."""
    s = SolverModel(model, "cont")
    FC, Order, ShippingCost, Assignment = model.FC, model.Order, model.ShippingCost, model.Assignment

    # Decision variable: quantity fulfilled via each assignment
    s.solve_for(Assignment.quantity, name=[Assignment.shipping.fc, Assignment.shipping.order], lower=0)

    # Binary variable: whether FC is used for this order
    s.solve_for(Assignment.selected, type="bin", name=["sel", Assignment.shipping.fc, Assignment.shipping.order])

    # Constraint: quantity bounded when selected
    s.satisfy(require(Assignment.quantity <= Assignment.shipping.order.quantity * Assignment.selected))

    # Constraint: FC capacity - total fulfilled from FC cannot exceed capacity
    Asn = Assignment.ref()
    fc_usage = sum(Asn.quantity).where(Asn.shipping.fc == FC).per(FC)
    s.satisfy(require(fc_usage <= FC.capacity))

    # Constraint: order fulfillment - each order must be fully fulfilled
    order_fulfilled = sum(Asn.quantity).where(Asn.shipping.order == Order).per(Order)
    s.satisfy(require(order_fulfilled == Order.quantity))

    # Objective: minimize total shipping cost
    total_cost = sum(Assignment.quantity * Assignment.shipping.cost_per_unit)
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
    print(f"Total shipping cost: ${sol['objective']:.2f}")
    print("\nAssignments:")
    df = sol["variables"]
    active = df[df["float"] > 0] if "float" in df.columns else df
    print(active.to_string(index=False))
