"""Order Fulfillment - Assign orders to fulfillment centers minimizing total cost."""

from pathlib import Path
from time import time_ns

from pandas import read_csv
from relationalai.semantics import Model, data, define, require, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel


def define_model(config=None):
    """Define base model with FulfillmentCenter, Order, and ShippingCost concepts."""
    model = Model(f"order_fulfillment_{time_ns()}", config=config, use_lqp=False)

    # Concepts
    FC = model.Concept("FulfillmentCenter")
    FC.id = model.Property("{FulfillmentCenter} has {id:int}")
    FC.name = model.Property("{FulfillmentCenter} has {name:string}")
    FC.capacity = model.Property("{FulfillmentCenter} has {capacity:int}")
    FC.fixed_cost = model.Property("{FulfillmentCenter} has {fixed_cost:float}")

    Order = model.Concept("Order")
    Order.id = model.Property("{Order} has {id:int}")
    Order.customer = model.Property("{Order} for {customer:string}")
    Order.quantity = model.Property("{Order} has {quantity:int}")
    Order.priority = model.Property("{Order} has {priority:int}")

    ShippingCost = model.Concept("ShippingCost")
    ShippingCost.fc = model.Property("{ShippingCost} from {fc:FulfillmentCenter}")
    ShippingCost.order = model.Property("{ShippingCost} for {order:Order}")
    ShippingCost.cost_per_unit = model.Property("{ShippingCost} has {cost_per_unit:float}")

    # Load data
    data_dir = Path(__file__).parent / "data"

    fc_df = read_csv(data_dir / "fulfillment_centers.csv")
    data(fc_df).into(FC, keys=["id"])

    orders_df = read_csv(data_dir / "orders.csv")
    data(orders_df).into(Order, keys=["id"])

    costs_df = read_csv(data_dir / "shipping_costs.csv")
    costs_data = data(costs_df)
    where(FC.id(costs_data.fc_id), Order.id(costs_data.order_id)).define(
        ShippingCost.new(fc=FC, order=Order, cost_per_unit=costs_data.cost_per_unit)
    )

    # Assignment: decision variable for fulfilling orders from FCs
    Assignment = model.Concept("Assignment")
    Assignment.shipping = model.Property("{Assignment} uses {shipping:ShippingCost}")
    Assignment.qty = model.Property("{Assignment} has {qty:float}")
    Assignment.selected = model.Property("{Assignment} is {selected:float}")
    define(Assignment.new(shipping=ShippingCost))

    model.FC, model.Order, model.ShippingCost, model.Assignment = FC, Order, ShippingCost, Assignment
    return model


def define_problem(model):
    """Define decision variables, constraints, and objective."""
    s = SolverModel(model, "cont")
    FC, Order, ShippingCost, Assignment = model.FC, model.Order, model.ShippingCost, model.Assignment

    # Decision variable: quantity fulfilled via each assignment
    s.solve_for(Assignment.qty, name=["qty", Assignment.shipping.fc.id, Assignment.shipping.order.id], lower=0)

    # Binary variable: whether FC is used for this order
    s.solve_for(Assignment.selected, type="bin", name=["sel", Assignment.shipping.fc.id, Assignment.shipping.order.id])

    # Constraint: quantity bounded when selected
    s.satisfy(require(Assignment.qty <= Assignment.shipping.order.quantity * Assignment.selected))

    # Constraint: FC capacity - total fulfilled from FC cannot exceed capacity
    Asn = Assignment.ref()
    fc_usage = sum(Asn.qty).where(Asn.shipping.fc == FC).per(FC)
    s.satisfy(require(fc_usage <= FC.capacity))

    # Constraint: order fulfillment - each order must be fully fulfilled
    order_fulfilled = sum(Asn.qty).where(Asn.shipping.order == Order).per(Order)
    s.satisfy(require(order_fulfilled == Order.quantity))

    # Objective: minimize total shipping cost
    total_cost = sum(Assignment.qty * Assignment.shipping.cost_per_unit)
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
