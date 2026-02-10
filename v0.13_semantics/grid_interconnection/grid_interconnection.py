# data center grid interconnection problem:
# approve data center interconnection requests and substation upgrades
# to maximize net revenue within capital budget

from pathlib import Path

import pandas; pandas.options.future.infer_string = False
from pandas import read_csv

from relationalai.semantics import Model, data, require, select, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

model = Model("grid", config=globals().get("config", None), use_lqp=False)

# --------------------------------------------------
# Define ontology & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Concept: substations with current and max capacity
Substation = model.Concept("Substation")
Substation.id = model.Property("{Substation} has {id:int}")
Substation.name = model.Property("{Substation} has {name:string}")
Substation.current_capacity = model.Property("{Substation} has {current_capacity:int}")
Substation.max_capacity = model.Property("{Substation} has {max_capacity:int}")
data(read_csv(data_dir / "substations.csv")).into(Substation, keys=["id"])

# Concept: projects with capacity needs, revenue, and connection costs
Project = model.Concept("Project")
Project.id = model.Property("{Project} has {id:int}")
Project.name = model.Property("{Project} has {name:string}")
Project.substation = model.Property("{Project} connects to {substation:Substation}")
Project.capacity_needed = model.Property("{Project} needs {capacity_needed:int}")
Project.revenue = model.Property("{Project} has {revenue:float}")
Project.connection_cost = model.Property("{Project} has {connection_cost:float}")
Project.approved = model.Property("{Project} is {approved:float}")

projects_data = data(read_csv(data_dir / "projects.csv"))
where(Substation.id(projects_data.substation_id)).define(
    Project.new(id=projects_data.id, name=projects_data.name, substation=Substation,
                capacity_needed=projects_data.capacity_needed,
                revenue=projects_data.revenue,
                connection_cost=projects_data.connection_cost)
)

# Concept: upgrades with capacity additions and costs
Upgrade = model.Concept("Upgrade")
Upgrade.id = model.Property("{Upgrade} has {id:int}")
Upgrade.substation = model.Property("{Upgrade} for {substation:Substation}")
Upgrade.capacity_added = model.Property("{Upgrade} adds {capacity_added:int}")
Upgrade.upgrade_cost = model.Property("{Upgrade} has {upgrade_cost:float}")
Upgrade.selected = model.Property("{Upgrade} is {selected:float}")

upgrades_data = data(read_csv(data_dir / "upgrades.csv"))
where(Substation.id(upgrades_data.substation_id)).define(
    Upgrade.new(id=upgrades_data.id, substation=Substation,
                capacity_added=upgrades_data.capacity_added,
                upgrade_cost=upgrades_data.upgrade_cost)
)

# --------------------------------------------------
# Model the problem
# --------------------------------------------------

# Parameters
budget = 1000000000

Proj = Project.ref()
Upg = Upgrade.ref()

# Scenarios (what-if analysis)
SCENARIO_PARAM = "budget"
SCENARIO_VALUES = [500000000, 1000000000, 2000000000]

# --------------------------------------------------
# Solve with Scenario Analysis (Numeric Parameter)
# --------------------------------------------------

scenario_results = []

for scenario_value in SCENARIO_VALUES:
    print(f"\nRunning scenario: {SCENARIO_PARAM} = {scenario_value}")

    # Set scenario parameter value
    budget = scenario_value

    # Create fresh SolverModel for each scenario
    s = SolverModel(model, "cont")

    # Variable: binary approval and selection
    s.solve_for(Project.approved, type="bin", name=Project.name)
    s.solve_for(Upgrade.selected, type="bin", name=["upg", Upgrade.substation.name, Upgrade.capacity_added])

    # Constraint: capacity at substation must accommodate approved projects
    project_demand = sum(Proj.approved * Proj.capacity_needed).where(Proj.substation == Substation).per(Substation)
    upgrade_capacity = sum(Upg.selected * Upg.capacity_added).where(Upg.substation == Substation).per(Substation)
    capacity_ok = require(Substation.current_capacity + upgrade_capacity >= project_demand)
    s.satisfy(capacity_ok)

    # Constraint: at most one upgrade per substation
    upgrades_per_sub = sum(Upg.selected).where(Upg.substation == Substation).per(Substation)
    one_upgrade = require(upgrades_per_sub <= 1)
    s.satisfy(one_upgrade)

    # Constraint: budget
    total_investment = sum(Project.approved * Project.connection_cost) + sum(Upgrade.selected * Upgrade.upgrade_cost)
    budget_ok = require(total_investment <= budget)
    s.satisfy(budget_ok)

    # Objective: maximize net revenue
    net_revenue = sum(Project.approved * (Project.revenue - Project.connection_cost))
    s.maximize(net_revenue)

    solver = Solver("highs")
    s.solve(solver, time_limit_sec=60)

    scenario_results.append({
        "scenario": scenario_value,
        "status": str(s.termination_status),
        "objective": s.objective_value,
    })
    print(f"  Status: {s.termination_status}, Objective: {s.objective_value}")

    # Print approved projects from solver results
    var_df = s.variable_values().to_df()
    approved_df = var_df[~var_df["name"].str.startswith("upg") & (var_df["float"] > 0.5)].rename(columns={"float": "value"})
    print(f"\n  Approved projects:")
    print(approved_df.to_string(index=False))

    upgrades_df = var_df[var_df["name"].str.startswith("upg") & (var_df["float"] > 0.5)].rename(columns={"float": "value"})
    if not upgrades_df.empty:
        print(f"\n  Selected upgrades:")
        print(upgrades_df.to_string(index=False))

# Summary
print("\n" + "=" * 50)
print("Scenario Analysis Summary")
print("=" * 50)
for result in scenario_results:
    print(f"  {result['scenario']}: {result['status']}, obj={result['objective']}")
