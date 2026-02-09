# grid interconnection problem:
# approve renewable projects and upgrades to maximize net revenue within budget

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
Project.annual_revenue = model.Property("{Project} has {annual_revenue:float}")
Project.connection_cost = model.Property("{Project} has {connection_cost:float}")
Project.approved = model.Property("{Project} is {approved:float}")

projects_data = data(read_csv(data_dir / "projects.csv"))
where(Substation.id(projects_data.substation_id)).define(
    Project.new(id=projects_data.id, name=projects_data.name, substation=Substation,
                capacity_needed=projects_data.capacity_needed,
                annual_revenue=projects_data.annual_revenue,
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
budget = 500000

Proj = Project.ref()
Upg = Upgrade.ref()

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
net_revenue = sum(Project.approved * (Project.annual_revenue - Project.connection_cost))
s.maximize(net_revenue)

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

solver = Solver("highs")
s.solve(solver, time_limit_sec=60)

print(f"Status: {s.termination_status}")
print(f"Net annual revenue: ${s.objective_value:.2f}")

approved = select(Project.name).where(Project.approved > 0.5).to_df()
print("\nApproved projects:")
print(approved.to_string(index=False))

selected = select(
    Upgrade.substation.name.alias("substation"),
    Upgrade.capacity_added.alias("capacity_added")
).where(Upgrade.selected > 0.5).to_df()
if not selected.empty:
    print("\nSelected upgrades:")
    print(selected.to_string(index=False))
