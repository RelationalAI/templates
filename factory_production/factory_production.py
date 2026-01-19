"""Factory Production - Maximize profit from production across machines."""

from pathlib import Path
from time import time_ns

from pandas import read_csv
from relationalai.semantics import Model, data, require, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel


def define_model(config=None):
    """Define base model with Machine, Product, and Production concepts."""
    model = Model(f"factory_{time_ns()}", config=config, use_lqp=False)

    Concept, Property = model.Concept, model.Property

    # Concepts
    Machine = Concept("Machine")
    Machine.id = Property("{Machine} has {id:int}")
    Machine.name = Property("{Machine} has {name:string}")
    Machine.hours_available = Property("{Machine} has {hours_available:float}")
    Machine.hourly_cost = Property("{Machine} has {hourly_cost:float}")

    Product = Concept("Product")
    Product.id = Property("{Product} has {id:int}")
    Product.name = Property("{Product} has {name:string}")
    Product.price = Property("{Product} has {price:float}")
    Product.min_production = Property("{Product} has {min_production:int}")

    Production = Concept("Production")
    Production.machine = Property("{Production} on {machine:Machine}")
    Production.product = Property("{Production} of {product:Product}")
    Production.hours_per_unit = Property("{Production} takes {hours_per_unit:float}")

    # Load data from CSVs
    data_dir = Path(__file__).parent / "data"

    machines_df = read_csv(data_dir / "machines.csv")
    data(machines_df).into(Machine, keys=["id"])

    products_df = read_csv(data_dir / "products.csv")
    data(products_df).into(Product, keys=["id"])

    # Load production times with references
    times_df = read_csv(data_dir / "production_times.csv")
    times_data = data(times_df)
    where(Machine.id(times_data.machine_id), Product.id(times_data.product_id)).define(
        Production.machine(Production, Machine),
        Production.product(Production, Product),
        Production.hours_per_unit(Production, times_data.hours_per_unit),
    )

    # Store references
    model.Machine = Machine
    model.Product = Product
    model.Production = Production

    return model


def define_problem(model):
    """Define decision variables, constraints, and objective."""
    Machine = model.Machine
    Product = model.Product
    Production = model.Production

    # Decision variable: quantity to produce
    Production.quantity = model.Property("{Production} has {quantity:float}")

    s = SolverModel(model, "cont")

    # Variable: quantity >= 0
    s.solve_for(
        Production.quantity,
        name=["qty", Production.machine.id, Production.product.id],
        lower=0
    )

    # Constraint: total production hours per machine <= hours_available
    total_hours = sum(Production.quantity * Production.hours_per_unit).where(
        Production.machine == Machine
    )
    s.satisfy(require(total_hours <= Machine.hours_available))

    # Constraint: total production per product >= min_production
    total_produced = sum(Production.quantity).where(Production.product == Product)
    s.satisfy(require(total_produced >= Product.min_production))

    # Objective: maximize profit (revenue - machine costs)
    # Revenue = sum(quantity * price)
    revenue = sum(Production.quantity * Production.product.price)
    # Machine cost = sum(hours_used * hourly_cost)
    machine_cost = sum(
        Production.quantity * Production.hours_per_unit * Production.machine.hourly_cost
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
