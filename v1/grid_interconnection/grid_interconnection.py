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
Project.x_approved = Property(f"{Project} is {Float:approved}")

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
Upgrade.x_selected = Property(f"{Upgrade} is {Float:selected}")

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

# Parameters
budget = 2000000000

ProjectRef = Project.ref()
UpgradeRef = Upgrade.ref()

def build_formulation(s):
    """Register variables, constraints, and objective on the problem."""
    # Variables
    s.solve_for(Project.x_approved, type="bin", name=Project.name)
    s.solve_for(Upgrade.x_selected, type="bin", name=["upg", Upgrade.substation.name, Upgrade.capacity_added])

    # Constraint: capacity at substation must accommodate approved projects
    project_demand = sum(ProjectRef.x_approved * ProjectRef.capacity_needed).where(ProjectRef.substation == Substation).per(Substation)
    upgrade_capacity = sum(UpgradeRef.x_selected * UpgradeRef.capacity_added).where(UpgradeRef.substation == Substation).per(Substation)
    capacity_ok = model.require(Substation.current_capacity + upgrade_capacity >= project_demand)
    s.satisfy(capacity_ok)

    # Constraint: at most one upgrade per substation
    upgrades_per_sub = sum(UpgradeRef.x_selected).where(UpgradeRef.substation == Substation).per(Substation)
    one_upgrade = model.require(upgrades_per_sub <= 1)
    s.satisfy(one_upgrade)

    # Constraint: budget
    total_investment = sum(Project.x_approved * Project.connection_cost) + sum(Upgrade.x_selected * Upgrade.upgrade_cost)
    budget_ok = model.require(total_investment <= budget)
    s.satisfy(budget_ok)

    # Objective: maximize net revenue
    net_revenue = sum(Project.x_approved * (Project.revenue - Project.connection_cost))
    s.maximize(net_revenue)

# Scenarios (what-if analysis)
SCENARIO_PARAM = "budget"
SCENARIO_VALUES = [1000000000, 2000000000, 3000000000]

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

scenario_results = []

for scenario_value in SCENARIO_VALUES:
    print(f"\nRunning scenario: {SCENARIO_PARAM} = {scenario_value}")

    # Set scenario parameter value
    budget = scenario_value

    # Create fresh Problem for each scenario
    s = Problem(model, Float)
    build_formulation(s)

    s.display()
    s.solve("highs", time_limit_sec=60, _server_side_import=False)
    s.display_solve_info()

    scenario_results.append({
        "scenario": scenario_value,
        "status": str(s.termination_status),
        "objective": s.objective_value,
    })
    print(f"  Status: {s.termination_status}, Objective: {s.objective_value}")

    # Print approved projects from solver results
    var_df = s.variable_values().to_df()
    approved_df = var_df[~var_df["name"].str.startswith("upg") & (var_df["value"] > 0.5)]
    print(f"\n  Approved projects:")
    print(approved_df.to_string(index=False))

    upgrades_df = var_df[var_df["name"].str.startswith("upg") & (var_df["value"] > 0.5)]
    if not upgrades_df.empty:
        print(f"\n  Selected upgrades:")
        print(upgrades_df.to_string(index=False))

# Summary
print("\n" + "=" * 50)
print("Scenario Analysis Summary")
print("=" * 50)
for result in scenario_results:
    print(f"  {result['scenario']}: {result['status']}, obj={result['objective']}")
