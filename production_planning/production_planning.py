"""Production Planning - Schedule production on machines to meet demand and maximize profit."""

from pathlib import Path
from time import time_ns

from pandas import read_csv
from relationalai.semantics import Model, data, define, require, sum
from relationalai.semantics.reasoners.optimization import Solver, SolverModel


def define_model(config=None):
    """Define base model with Product, Machine, and ProductionRate concepts."""
    model = Model(f"production_planning_{time_ns()}", config=config, use_lqp=False)
    Concept, Property, Relationship = model.Concept, model.Property, model.Relationship

    data_dir = Path(__file__).parent / "data"

    # Product: items to produce with demand and profit
    Product = Concept("Product")
    Product.name = Property("{Product} has name {name:String}")
    Product.demand = Property("{Product} has demand {demand:int}")
    Product.profit = Property("{Product} has profit {profit:float}")
    products_df = read_csv(data_dir / "products.csv")
    data(products_df).into(Product, id="id", properties=["name", "demand", "profit"])

    # Machine: production resources with time availability
    Machine = Concept("Machine")
    Machine.name = Property("{Machine} has name {name:String}")
    Machine.hours_available = Property("{Machine} has hours_available {hours_available:float}")
    machines_df = read_csv(data_dir / "machines.csv")
    data(machines_df).into(Machine, id="id", properties=["name", "hours_available"])

    # ProductionRate: how long each machine takes to produce each product
    Rate = Concept("ProductionRate")
    Rate.hours_per_unit = Property("{ProductionRate} has hours_per_unit {hours_per_unit:float}")
    Rate.machine = Relationship("{ProductionRate} on {machine:Machine}")
    Rate.product = Relationship("{ProductionRate} for {product:Product}")
    rates_df = read_csv(data_dir / "production_rates.csv")
    data(rates_df).into(
        Rate,
        keys=["machine_id", "product_id"],
        properties=["hours_per_unit"],
        relationships={"machine": ("machine_id", Machine), "product": ("product_id", Product)},
    )

    # Production: decision variable for units produced per machine/product
    Production = Concept("Production")
    Production.rate = Relationship("{Production} uses {rate:ProductionRate}")
    Production.quantity = Property("{Production} has quantity {quantity:float}")
    define(Production.new(rate=Rate))

    model.Product, model.Machine, model.Rate, model.Production = Product, Machine, Rate, Production
    return model


def define_problem(model):
    """Define decision variables, constraints, and objective."""
    s = SolverModel(model, "cont")
    Product, Machine, Rate, Production = model.Product, model.Machine, model.Rate, model.Production

    # Decision variable: quantity to produce via each machine/product combination
    s.solve_for(Production.quantity, name=[Production.rate.machine, Production.rate.product], lower=0, type="int")

    # Constraint: machine capacity - total hours used on machine cannot exceed availability
    Prod = Production.ref()
    machine_hours = sum(Prod.quantity * Prod.rate.hours_per_unit).where(Prod.rate.machine == Machine).per(Machine)
    s.satisfy(require(machine_hours <= Machine.hours_available))

    # Constraint: demand satisfaction - production across machines must meet demand
    product_qty = sum(Prod.quantity).where(Prod.rate.product == Product).per(Product)
    s.satisfy(require(product_qty >= Product.demand))

    # Objective: maximize total profit
    total_profit = sum(Production.quantity * Production.rate.product.profit)
    s.maximize(total_profit)

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
    print(f"Total profit: ${sol['objective']:.2f}")
    print("\nProduction schedule:")
    df = sol["variables"]
    active = df[df["float"] > 0] if "float" in df.columns else df
    print(active.to_string(index=False))
