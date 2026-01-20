"""Supplier Reliability - Select suppliers to meet demand balancing cost and reliability."""

from pathlib import Path
from time import time_ns

from pandas import read_csv
from relationalai.semantics import Model, data, define, require, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel


def define_model(config=None):
    """Define base model with Supplier, Product, and SupplyOption concepts."""
    model = Model(f"supplier_reliability_{time_ns()}", config=config, use_lqp=False)

    # Concepts
    Supplier = model.Concept("Supplier")
    Supplier.id = model.Property("{Supplier} has {id:int}")
    Supplier.name = model.Property("{Supplier} has {name:string}")
    Supplier.reliability = model.Property("{Supplier} has {reliability:float}")
    Supplier.capacity = model.Property("{Supplier} has {capacity:int}")

    Product = model.Concept("Product")
    Product.id = model.Property("{Product} has {id:int}")
    Product.name = model.Property("{Product} has {name:string}")
    Product.demand = model.Property("{Product} has {demand:int}")

    SupplyOption = model.Concept("SupplyOption")
    SupplyOption.id = model.Property("{SupplyOption} has {id:int}")
    SupplyOption.supplier = model.Property("{SupplyOption} from {supplier:Supplier}")
    SupplyOption.product = model.Property("{SupplyOption} for {product:Product}")
    SupplyOption.cost_per_unit = model.Property("{SupplyOption} has {cost_per_unit:float}")

    # Load data
    data_dir = Path(__file__).parent / "data"

    suppliers_df = read_csv(data_dir / "suppliers.csv")
    data(suppliers_df).into(Supplier, keys=["id"])

    products_df = read_csv(data_dir / "products.csv")
    data(products_df).into(Product, keys=["id"])

    options_df = read_csv(data_dir / "supply_options.csv")
    options_data = data(options_df)
    where(Supplier.id(options_data.supplier_id), Product.id(options_data.product_id)).define(
        SupplyOption.new(id=options_data.id, supplier=Supplier, product=Product,
                         cost_per_unit=options_data.cost_per_unit)
    )

    # Order: decision variable for quantity ordered via each supply option
    Order = model.Concept("Order")
    Order.option = model.Property("{Order} uses {option:SupplyOption}")
    Order.quantity = model.Property("{Order} has {quantity:float}")
    define(Order.new(option=SupplyOption))

    model.Supplier, model.Product, model.SupplyOption, model.Order = Supplier, Product, SupplyOption, Order
    return model


def define_problem(model, reliability_weight=0.0):
    """Define decision variables, constraints, and objective."""
    s = SolverModel(model, "cont")
    Supplier, Product, SupplyOption, Order = model.Supplier, model.Product, model.SupplyOption, model.Order

    # Decision variable: quantity to order via each supply option
    s.solve_for(Order.quantity, name=["qty", Order.option.supplier.name, Order.option.product.name], lower=0)

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
