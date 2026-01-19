"""Production Planning - Schedule production on machines to meet demand and maximize profit."""

from pathlib import Path
from time import time_ns

from pandas import read_csv
from relationalai.semantics import Model, data, define, require, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel


def define_model(config=None):
    """Define base model with Product, Machine, and ProductionRate concepts."""
    model = Model(f"production_planning_{time_ns()}", config=config, use_lqp=False)

    # Concepts
    Product = model.Concept("Product")
    Product.id = model.Property("{Product} has {id:int}")
    Product.name = model.Property("{Product} has {name:string}")
    Product.demand = model.Property("{Product} has {demand:int}")
    Product.profit = model.Property("{Product} has {profit:float}")

    Machine = model.Concept("Machine")
    Machine.id = model.Property("{Machine} has {id:int}")
    Machine.name = model.Property("{Machine} has {name:string}")
    Machine.hours_available = model.Property("{Machine} has {hours_available:float}")

    Rate = model.Concept("ProductionRate")
    Rate.machine = model.Property("{ProductionRate} on {machine:Machine}")
    Rate.product = model.Property("{ProductionRate} for {product:Product}")
    Rate.hours_per_unit = model.Property("{ProductionRate} has {hours_per_unit:float}")

    # Load data
    data_dir = Path(__file__).parent / "data"

    products_df = read_csv(data_dir / "products.csv")
    data(products_df).into(Product, keys=["id"])

    machines_df = read_csv(data_dir / "machines.csv")
    data(machines_df).into(Machine, keys=["id"])

    rates_df = read_csv(data_dir / "production_rates.csv")
    rates_data = data(rates_df)
    where(Machine.id(rates_data.machine_id), Product.id(rates_data.product_id)).define(
        Rate.new(machine=Machine, product=Product, hours_per_unit=rates_data.hours_per_unit)
    )

    # Production: decision variable for units produced per machine/product
    Production = model.Concept("Production")
    Production.rate = model.Property("{Production} uses {rate:ProductionRate}")
    Production.quantity = model.Property("{Production} has {quantity:float}")
    define(Production.new(rate=Rate))

    model.Product, model.Machine, model.Rate, model.Production = Product, Machine, Rate, Production
    return model


def define_problem(model):
    """Define decision variables, constraints, and objective."""
    s = SolverModel(model, "cont")
    Product, Machine, Rate, Production = model.Product, model.Machine, model.Rate, model.Production

    # Decision variable: quantity to produce via each machine/product combination
    s.solve_for(Production.quantity, name=["qty", Production.rate.machine.id, Production.rate.product.id], lower=0, type="int")

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
