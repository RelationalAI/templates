"""Grid interconnection (prescriptive optimization) template.

This script demonstrates a mixed-integer linear optimization (MILP) workflow in
RelationalAI for planning data center interconnections:

- Load sample CSVs describing substations, interconnection projects, and
  candidate upgrades.
- Decide which projects to approve (binary) and which upgrades to select (binary).
- Enforce capacity feasibility at each substation and a total capital budget.
- Maximize total net revenue.
- Run scenario analysis over different capital budget levels.

Run:
    `python grid_interconnection.py`

Output:
    Prints the solver termination status, objective value, and tables of approved
    projects and selected upgrades for each budget scenario.
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("grid")
Concept, Property = model.Concept, model.Property

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Concept: substations with current and max capacity
Substation = Concept("Substation", identify_by={"id": Integer})
Substation.name = Property(f"{Substation} has {String:name}")
Substation.current_capacity = Property(f"{Substation} has {Integer:current_capacity}")
Substation.max_capacity = Property(f"{Substation} has {Integer:max_capacity}")
substation_csv = read_csv(data_dir / "substations.csv")
model.define(Substation.new(model.data(substation_csv).to_schema()))

# Concept: projects with capacity needs, revenue, and connection costs
Project = Concept("Project", identify_by={"id": Integer})
Project.name = Property(f"{Project} has {String:name}")
Project.substation_id = Property(f"{Project} has {Integer:substation_id}")
Project.substation = Property(f"{Project} connects to {Substation}")
Project.capacity_needed = Property(f"{Project} needs {Integer:capacity_needed}")
Project.revenue = Property(f"{Project} has {Float:revenue}")
Project.connection_cost = Property(f"{Project} has {Float:connection_cost}")
project_csv = read_csv(data_dir / "projects.csv")
project_data = model.data(project_csv)
model.define(
    p := Project.new(id=project_data.id, substation_id=project_data.substation_id),
    p.name(project_data.name),
    p.capacity_needed(project_data.capacity_needed),
    p.revenue(project_data.revenue),
    p.connection_cost(project_data.connection_cost),
)
model.define(Project.substation(Substation)).where(Project.substation_id == Substation.id)

# Concept: upgrades with capacity additions and costs
Upgrade = Concept("Upgrade", identify_by={"id": Integer})
Upgrade.substation_id = Property(f"{Upgrade} has {Integer:substation_id}")
Upgrade.substation = Property(f"{Upgrade} for {Substation}")
Upgrade.capacity_added = Property(f"{Upgrade} adds {Integer:capacity_added}")
Upgrade.upgrade_cost = Property(f"{Upgrade} has {Float:upgrade_cost}")
upgrade_csv = read_csv(data_dir / "upgrades.csv")
upgrade_data = model.data(upgrade_csv)
model.define(
    u := Upgrade.new(id=upgrade_data.id, substation_id=upgrade_data.substation_id),
    u.capacity_added(upgrade_data.capacity_added),
    u.upgrade_cost(upgrade_data.upgrade_cost),
)
model.define(Upgrade.substation(Substation)).where(Upgrade.substation_id == Substation.id)

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

# Scenario concept — budget parameter variations
Scenario = Concept("Scenario", identify_by={"name": String})
Scenario.budget = Property(f"{Scenario} has {Float:budget}")
scenario_data = model.data(
    [("budget_1B", 1000000000), ("budget_2B", 2000000000), ("budget_3B", 3000000000)],
    columns=["name", "budget"],
)
model.define(Scenario.new(scenario_data.to_schema()))

# Decision variables — indexed by Scenario (multi-argument Properties)
Project.x_approved = Property(f"{Project} in {Scenario} is {Float:approved}")
Upgrade.x_selected = Property(f"{Upgrade} in {Scenario} is {Float:selected}")

# Refs for binding multi-arg variables in constraints
x_approved = Float.ref()
x_selected = Float.ref()

ProjectRef = Project.ref()
UpgradeRef = Upgrade.ref()

p = Problem(model, Float)

# Variables
p.solve_for(
    Project.x_approved(Scenario, x_approved),
    type="bin",
    name=["proj", Scenario.name, Project.name],
)
p.solve_for(
    Upgrade.x_selected(Scenario, x_selected),
    type="bin",
    name=["upg", Scenario.name, Upgrade.substation.name, Upgrade.capacity_added],
)

# Constraint: capacity at substation must accommodate approved projects (per scenario)
x_approved_ref = Float.ref()
x_selected_ref = Float.ref()
p.satisfy(model.where(
    Project.x_approved(Scenario, x_approved_ref),
    Upgrade.x_selected(Scenario, x_selected_ref),
    Project.substation(Substation),
    Upgrade.substation(Substation),
).require(
    Substation.current_capacity
    + sum(x_selected_ref * UpgradeRef.capacity_added).where(UpgradeRef.substation == Substation).per(Substation, Scenario)
    >= sum(x_approved_ref * ProjectRef.capacity_needed).where(ProjectRef.substation == Substation).per(Substation, Scenario)
))

# Constraint: at most one upgrade per substation (per scenario)
p.satisfy(model.where(
    Upgrade.x_selected(Scenario, x_selected),
).require(
    sum(x_selected).where(Upgrade.substation == Substation).per(Substation, Scenario) <= 1
))

# Constraint: budget limit (per scenario)
p.satisfy(model.where(
    Project.x_approved(Scenario, x_approved),
    Upgrade.x_selected(Scenario, x_selected),
).require(
    sum(x_approved * Project.connection_cost).per(Scenario)
    + sum(x_selected * Upgrade.upgrade_cost).per(Scenario)
    <= Scenario.budget
))

# Objective: maximize net revenue
p.maximize(
    sum(x_approved * (Project.revenue - Project.connection_cost))
    .where(Project.x_approved(Scenario, x_approved))
)

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

p.display()
p.solve("highs", time_limit_sec=60)
p.display_solve_info()

print("\nApproved projects per scenario:")
model.select(
    Scenario.name.alias("scenario"),
    Project.name.alias("project"),
    Project.revenue,
    Project.connection_cost,
).where(
    Project.x_approved(Scenario, x_approved), x_approved > 0.5
).inspect()

print("\nSelected upgrades per scenario:")
model.select(
    Scenario.name.alias("scenario"),
    Upgrade.substation.name.alias("substation"),
    Upgrade.capacity_added,
    Upgrade.upgrade_cost,
).where(
    Upgrade.x_selected(Scenario, x_selected), x_selected > 0.5
).inspect()
