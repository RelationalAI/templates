"""Grid Interconnection - Approve renewable projects and upgrades to maximize net revenue."""

from pathlib import Path
from time import time_ns

from pandas import read_csv
from relationalai.semantics import Model, data, define, require, sum
from relationalai.semantics.reasoners.optimization import Solver, SolverModel


def define_model(config=None):
    """Define base model with Substation, Project, and Upgrade concepts."""
    model = Model(f"grid_{time_ns()}", config=config, use_lqp=False)
    Concept, Property, Relationship = model.Concept, model.Property, model.Relationship

    data_dir = Path(__file__).parent / "data"

    # Substation: grid connection points with capacity limits
    Substation = Concept("Substation")
    Substation.name = Property("{Substation} has name {name:String}")
    Substation.current_capacity = Property("{Substation} has current_capacity {current_capacity:int}")
    Substation.max_capacity = Property("{Substation} has max_capacity {max_capacity:int}")
    subs_df = read_csv(data_dir / "substations.csv")
    data(subs_df).into(Substation, id="id", properties=["name", "current_capacity", "max_capacity"])

    # Project: renewable energy projects seeking interconnection
    Project = Concept("Project")
    Project.name = Property("{Project} has name {name:String}")
    Project.substation = Relationship("{Project} connects to {substation:Substation}")
    Project.capacity_needed = Property("{Project} needs capacity {capacity_needed:int}")
    Project.annual_revenue = Property("{Project} has annual_revenue {annual_revenue:float}")
    Project.connection_cost = Property("{Project} has connection_cost {connection_cost:float}")
    Project.approved = Property("{Project} is approved {approved:float}")
    projects_df = read_csv(data_dir / "projects.csv")
    data(projects_df).into(
        Project,
        id="id",
        properties=["name", "capacity_needed", "annual_revenue", "connection_cost"],
        relationships={"substation": ("substation_id", Substation)},
    )

    # Upgrade: capacity expansion options for substations
    Upgrade = Concept("Upgrade")
    Upgrade.substation = Relationship("{Upgrade} for {substation:Substation}")
    Upgrade.capacity_added = Property("{Upgrade} adds capacity {capacity_added:int}")
    Upgrade.upgrade_cost = Property("{Upgrade} has upgrade_cost {upgrade_cost:float}")
    Upgrade.selected = Property("{Upgrade} is selected {selected:float}")
    upgrades_df = read_csv(data_dir / "upgrades.csv")
    data(upgrades_df).into(
        Upgrade,
        id="id",
        properties=["capacity_added", "upgrade_cost"],
        relationships={"substation": ("substation_id", Substation)},
    )

    model.Substation, model.Project, model.Upgrade = Substation, Project, Upgrade
    return model


def define_problem(model, budget=500000):
    """Define decision variables, constraints, and objective."""
    s = SolverModel(model, "cont")
    Substation, Project, Upgrade = model.Substation, model.Project, model.Upgrade

    # Decision variable: approve project (binary)
    s.solve_for(Project.approved, type="bin", name=Project.name)

    # Decision variable: select upgrade (binary)
    s.solve_for(Upgrade.selected, type="bin", name=[Upgrade.substation, Upgrade.capacity_added])

    # Constraint: total capacity at substation (current + upgrades) >= approved project needs
    Proj = Project.ref()
    Upg = Upgrade.ref()
    project_demand = sum(Proj.approved * Proj.capacity_needed).where(Proj.substation == Substation).per(Substation)
    upgrade_capacity = sum(Upg.selected * Upg.capacity_added).where(Upg.substation == Substation).per(Substation)
    s.satisfy(require(Substation.current_capacity + upgrade_capacity >= project_demand))

    # Constraint: at most one upgrade per substation
    upgrades_per_sub = sum(Upg.selected).where(Upg.substation == Substation).per(Substation)
    s.satisfy(require(upgrades_per_sub <= 1))

    # Constraint: total investment (connection + upgrades) within budget
    total_investment = sum(Project.approved * Project.connection_cost) + sum(Upgrade.selected * Upgrade.upgrade_cost)
    s.satisfy(require(total_investment <= budget))

    # Objective: maximize net revenue (annual revenue - connection cost)
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
