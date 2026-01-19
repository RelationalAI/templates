"""Supplier Reliability - Select suppliers to meet demand balancing cost and reliability."""

from pathlib import Path
from time import time_ns

from pandas import read_csv
from relationalai.semantics import Model, data, define, require, sum
from relationalai.semantics.reasoners.optimization import Solver, SolverModel


def define_model(config=None):
    """Define base model with Supplier, Product, and SupplyOption concepts."""
    model = Model(f"supplier_reliability_{time_ns()}", config=config, use_lqp=False)
    Concept, Property, Relationship = model.Concept, model.Property, model.Relationship

    data_dir = Path(__file__).parent / "data"

    # Supplier: sources with reliability scores and capacity limits
    Supplier = Concept("Supplier")
    Supplier.name = Property("{Supplier} has name {name:String}")
    Supplier.reliability = Property("{Supplier} has reliability {reliability:float}")
    Supplier.capacity = Property("{Supplier} has capacity {capacity:int}")
    suppliers_df = read_csv(data_dir / "suppliers.csv")
    data(suppliers_df).into(Supplier, id="id", properties=["name", "reliability", "capacity"])

    # Product: items with demand requirements
    Product = Concept("Product")
    Product.name = Property("{Product} has name {name:String}")
    Product.demand = Property("{Product} has demand {demand:int}")
    products_df = read_csv(data_dir / "products.csv")
    data(products_df).into(Product, id="id", properties=["name", "demand"])

    # SupplyOption: which suppliers can supply which products at what cost
    SupplyOption = Concept("SupplyOption")
    SupplyOption.cost_per_unit = Property("{SupplyOption} has cost_per_unit {cost_per_unit:float}")
    SupplyOption.supplier = Relationship("{SupplyOption} from {supplier:Supplier}")
    SupplyOption.product = Relationship("{SupplyOption} for {product:Product}")
    options_df = read_csv(data_dir / "supply_options.csv")
    data(options_df).into(
        SupplyOption,
        id="id",
        properties=["cost_per_unit"],
        relationships={"supplier": ("supplier_id", Supplier), "product": ("product_id", Product)},
    )

    # Order: decision variable for quantity ordered via each supply option
    Order = Concept("Order")
    Order.option = Relationship("{Order} uses {option:SupplyOption}")
    Order.quantity = Property("{Order} has quantity {quantity:float}")
    define(Order.new(option=SupplyOption))

    model.Supplier, model.Product, model.SupplyOption, model.Order = Supplier, Product, SupplyOption, Order
    return model


def define_problem(model, reliability_weight=0.0):
    """Define decision variables, constraints, and objective."""
    s = SolverModel(model, "cont")
    Supplier, Product, SupplyOption, Order = model.Supplier, model.Product, model.SupplyOption, model.Order

    # Decision variable: quantity to order via each supply option
    s.solve_for(Order.quantity, name=Order.option, lower=0)

    # Constraint: total orders from supplier cannot exceed supplier capacity
    Ord = Order.ref()
    orders_from_supplier = sum(Ord.quantity).where(Ord.option.supplier == Supplier).per(Supplier)
    s.satisfy(require(orders_from_supplier <= Supplier.capacity))

    # Constraint: demand satisfaction for each product
    Pr = Product.ref()
    orders_for_product = sum(Ord.quantity).where(Ord.option.product == Pr).per(Pr)
    s.satisfy(require(orders_for_product >= Pr.demand))

    # Objective: minimize cost with optional reliability penalty
    direct_cost = sum(Order.quantity * Order.option.cost_per_unit)

    if reliability_weight > 0:
        # Penalize unreliable suppliers: cost + weight * quantity * (1 - reliability)
        reliability_penalty = reliability_weight * sum(
            Order.quantity * (1.0 - Order.option.supplier.reliability)
        )
        total_cost = direct_cost + reliability_penalty
    else:
        total_cost = direct_cost

    s.minimize(total_cost)
    return s


def solve(config=None, solver_name="highs", reliability_weight=0.0):
    """Orchestrate model, problem, and solver execution."""
    model = define_model(config)
    solver_model = define_problem(model, reliability_weight)
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
    sm = solve(reliability_weight=0.0)
    sol = extract_solution(sm)

    print(f"Status: {sol['status']}")
    print(f"Total cost: ${sol['objective']:.2f}")
    print("\nOrder quantities:")
    df = sol["variables"]
    active = df[df["float"] > 0] if "float" in df.columns else df
    print(active.to_string(index=False))
