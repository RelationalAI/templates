"""Grid Interconnection - Approve renewable projects and upgrades to maximize net revenue."""

from pathlib import Path
from time import time_ns

from pandas import read_csv
from relationalai.semantics import Model, data, define, require, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel


def define_model(config=None):
    """Define base model with Substation, Project, and Upgrade concepts."""
    model = Model(f"grid_{time_ns()}", config=config, use_lqp=False)

    # Concepts
    Substation = model.Concept("Substation")
    Substation.id = model.Property("{Substation} has {id:int}")
    Substation.name = model.Property("{Substation} has {name:string}")
    Substation.current_capacity = model.Property("{Substation} has {current_capacity:int}")
    Substation.max_capacity = model.Property("{Substation} has {max_capacity:int}")

    Project = model.Concept("Project")
    Project.id = model.Property("{Project} has {id:int}")
    Project.name = model.Property("{Project} has {name:string}")
    Project.substation = model.Property("{Project} connects to {substation:Substation}")
    Project.capacity_needed = model.Property("{Project} needs {capacity_needed:int}")
    Project.annual_revenue = model.Property("{Project} has {annual_revenue:float}")
    Project.connection_cost = model.Property("{Project} has {connection_cost:float}")
    Project.approved = model.Property("{Project} is {approved:float}")

    Upgrade = model.Concept("Upgrade")
    Upgrade.id = model.Property("{Upgrade} has {id:int}")
    Upgrade.substation = model.Property("{Upgrade} for {substation:Substation}")
    Upgrade.capacity_added = model.Property("{Upgrade} adds {capacity_added:int}")
    Upgrade.upgrade_cost = model.Property("{Upgrade} has {upgrade_cost:float}")
    Upgrade.selected = model.Property("{Upgrade} is {selected:float}")

    # Load data
    data_dir = Path(__file__).parent / "data"

    subs_df = read_csv(data_dir / "substations.csv")
    data(subs_df).into(Substation, keys=["id"])

    projects_df = read_csv(data_dir / "projects.csv")
    projects_data = data(projects_df)
    where(Substation.id(projects_data.substation_id)).define(
        Project.new(id=projects_data.id, name=projects_data.name, substation=Substation,
                    capacity_needed=projects_data.capacity_needed,
                    annual_revenue=projects_data.annual_revenue,
                    connection_cost=projects_data.connection_cost)
    )

    upgrades_df = read_csv(data_dir / "upgrades.csv")
    upgrades_data = data(upgrades_df)
    where(Substation.id(upgrades_data.substation_id)).define(
        Upgrade.new(id=upgrades_data.id, substation=Substation,
                    capacity_added=upgrades_data.capacity_added,
                    upgrade_cost=upgrades_data.upgrade_cost)
    )

    model.Substation, model.Project, model.Upgrade = Substation, Project, Upgrade
    return model


def define_problem(model, budget=500000):
    """Define decision variables, constraints, and objective."""
    s = SolverModel(model, "cont")
    Substation, Project, Upgrade = model.Substation, model.Project, model.Upgrade

    # Decision variable: approve project
    s.solve_for(Project.approved, type="bin", name=Project.name)

    # Decision variable: select upgrade
    s.solve_for(Upgrade.selected, type="bin", name=["upg", Upgrade.substation.name, Upgrade.capacity_added])

    # Constraint: capacity at substation
    Proj = Project.ref()
    Upg = Upgrade.ref()
    project_demand = sum(Proj.approved * Proj.capacity_needed).where(Proj.substation == Substation).per(Substation)
    upgrade_capacity = sum(Upg.selected * Upg.capacity_added).where(Upg.substation == Substation).per(Substation)
    s.satisfy(require(Substation.current_capacity + upgrade_capacity >= project_demand))

    # Constraint: at most one upgrade per substation
    upgrades_per_sub = sum(Upg.selected).where(Upg.substation == Substation).per(Substation)
    s.satisfy(require(upgrades_per_sub <= 1))

    # Constraint: budget
    total_investment = sum(Project.approved * Project.connection_cost) + sum(Upgrade.selected * Upgrade.upgrade_cost)
    s.satisfy(require(total_investment <= budget))

    # Objective: maximize net revenue
    net_revenue = sum(Project.approved * (Project.annual_revenue - Project.connection_cost))
    s.maximize(net_revenue)

    return s


def solve(config=None, solver_name="highs", budget=500000):
    """Orchestrate model, problem, and solver execution."""
    model = define_model(config)
    solver_model = define_problem(model, budget)
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
    sm = solve(budget=500000)
    sol = extract_solution(sm)

    print(f"Status: {sol['status']}")
    print(f"Net annual revenue: ${sol['objective']:.2f}")
    print("\nApproved projects and upgrades:")
    df = sol["variables"]
    active = df[df["float"] > 0.5] if "float" in df.columns else df
    print(active.to_string(index=False))
