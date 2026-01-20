"""Factory Production - Maximize profit from production across machines."""

from pathlib import Path
from time import time_ns

from pandas import read_csv
from relationalai.semantics import Model, data, define, require, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel


def define_model(config=None):
    """Define base model with Machine, Product, and ProductionTime concepts."""
    model = Model(f"factory_{time_ns()}", config=config, use_lqp=False)

    # Concepts
    Machine = model.Concept("Machine")
    Machine.id = model.Property("{Machine} has {id:int}")
    Machine.name = model.Property("{Machine} has {name:string}")
    Machine.hours_available = model.Property("{Machine} has {hours_available:float}")
    Machine.hourly_cost = model.Property("{Machine} has {hourly_cost:float}")

    Product = model.Concept("Product")
    Product.id = model.Property("{Product} has {id:int}")
    Product.name = model.Property("{Product} has {name:string}")
    Product.price = model.Property("{Product} has {price:float}")
    Product.min_production = model.Property("{Product} has {min_production:int}")

    ProdTime = model.Concept("ProductionTime")
    ProdTime.machine = model.Property("{ProductionTime} on {machine:Machine}")
    ProdTime.product = model.Property("{ProductionTime} of {product:Product}")
    ProdTime.hours_per_unit = model.Property("{ProductionTime} takes {hours_per_unit:float}")

    # Load data
    data_dir = Path(__file__).parent / "data"

    machines_df = read_csv(data_dir / "machines.csv")
    data(machines_df).into(Machine, keys=["id"])

    products_df = read_csv(data_dir / "products.csv")
    data(products_df).into(Product, keys=["id"])

    times_df = read_csv(data_dir / "production_times.csv")
    times_data = data(times_df)
    where(Machine.id(times_data.machine_id), Product.id(times_data.product_id)).define(
        ProdTime.new(machine=Machine, product=Product, hours_per_unit=times_data.hours_per_unit)
    )

    # Production: decision variable for units produced per machine/product
    Production = model.Concept("Production")
    Production.prod_time = model.Property("{Production} uses {prod_time:ProductionTime}")
    Production.quantity = model.Property("{Production} has {quantity:float}")
    define(Production.new(prod_time=ProdTime))

    model.Machine = Machine
    model.Product = Product
    model.ProdTime = ProdTime
    model.Production = Production

    return model


def define_problem(model):
    """Define decision variables, constraints, and objective."""
    Machine = model.Machine
    Product = model.Product
    Production = model.Production

    s = SolverModel(model, "cont")

    # Variable: quantity >= 0
    s.solve_for(
        Production.quantity,
        name=["qty", Production.prod_time.machine.name, Production.prod_time.product.name],
        lower=0
    )

    # Constraint: total production hours per machine <= hours_available
    Prod = Production.ref()
    total_hours = sum(Prod.quantity * Prod.prod_time.hours_per_unit).where(
        Prod.prod_time.machine == Machine
    ).per(Machine)
    s.satisfy(require(total_hours <= Machine.hours_available))

    # Constraint: total production per product >= min_production
    total_produced = sum(Prod.quantity).where(Prod.prod_time.product == Product).per(Product)
    s.satisfy(require(total_produced >= Product.min_production))

    # Objective: maximize profit (revenue - machine costs)
    revenue = sum(Production.quantity * Production.prod_time.product.price)
    machine_cost = sum(
        Production.quantity * Production.prod_time.hours_per_unit * Production.prod_time.machine.hourly_cost
    )
    profit = revenue - machine_cost
    s.maximize(profit)

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
    print("\nProduction plan:")
    df = sol["variables"]
    active = df[df["float"] > 0] if "float" in df.columns else df
    print(active.to_string(index=False))
