"""Grid Interconnection (prescriptive optimization) template.

This template demonstrates **multi-objective optimization** via epsilon constraint
for a grid interconnection planning problem with two competing objectives:

- **Primary**: Maximize total project revenue
- **Secondary**: Minimize total infrastructure cost (connection + upgrade costs)

Instead of combining revenue and cost into a single net-revenue objective, the
epsilon constraint method sweeps the maximum allowed infrastructure cost — producing
the **efficient frontier** between revenue generation and capital investment.

The template also demonstrates **Scenario Concept inside the epsilon loop**:
budget levels are modeled as a Scenario Concept, so each epsilon solve handles
all budget scenarios simultaneously (N epsilon solves, not N × M).

TRANSFORMATION FROM SINGLE-OBJECTIVE:
  The original template optimized net revenue in a single expression:
    p.maximize(sum(x_approved * (Project.revenue - Project.connection_cost)))
  The bi-objective version splits revenue and cost:
    Primary:    p.maximize(sum(x_approved * Project.revenue))
    Secondary → constraint: p.satisfy(require(total_infra_cost <= eps))
  This reveals how much additional revenue each dollar of infrastructure buys.

Run:
    `python grid_interconnection.py`

Output:
    Prints anchor solve results, Pareto frontier (revenue vs infrastructure cost)
    per budget scenario, marginal analysis with knee detection.
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

Substation = Concept("Substation", identify_by={"id": Integer})
Substation.name = Property(f"{Substation} has {String:name}")
Substation.current_capacity = Property(f"{Substation} has {Integer:current_capacity}")
Substation.max_capacity = Property(f"{Substation} has {Integer:max_capacity}")
substation_csv = read_csv(data_dir / "substations.csv")
model.define(Substation.new(model.data(substation_csv).to_schema()))

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
# Scenario Concept — budget parameter variations
# (Scenarios handle parameter variations; epsilon loop handles the tradeoff)
# --------------------------------------------------

Scenario = Concept("Scenario", identify_by={"name": String})
Scenario.budget = Property(f"{Scenario} has {Float:budget}")
scenario_data = model.data(
    [("budget_1B", 1_000_000_000), ("budget_2B", 2_000_000_000), ("budget_3B", 3_000_000_000)],
    columns=["name", "budget"],
)
model.define(Scenario.new(scenario_data.to_schema()))

# --------------------------------------------------
# Decision variables — indexed by Scenario
# --------------------------------------------------

Project.x_approved = Property(f"{Project} in {Scenario} is {Float:approved}")
Upgrade.x_selected = Property(f"{Upgrade} in {Scenario} is {Float:selected}")

x_approved = Float.ref()
x_selected = Float.ref()
ProjectRef = Project.ref()
UpgradeRef = Upgrade.ref()

scenario_names = ["budget_1B", "budget_2B", "budget_3B"]


def solve_grid(objective="max_revenue", eps_cost=None):
    """Solve grid interconnection with given objective and optional cost epsilon.

    objective: "max_revenue" (primary) or "min_cost" (anchor 2)
    eps_cost: if set, total infrastructure cost <= eps_cost per scenario
    Returns (solve_info, variable_values_df) or None if infeasible.
    """
    prob = Problem(model, Float)

    prob.solve_for(
        Project.x_approved(Scenario, x_approved),
        type="bin",
        name=["proj", Scenario.name, Project.name],
        populate=False,
    )
    prob.solve_for(
        Upgrade.x_selected(Scenario, x_selected),
        type="bin",
        name=["upg", Scenario.name, Upgrade.substation.name, Upgrade.capacity_added],
        populate=False,
    )

    # --- Constraints (same as original) ---

    # Capacity at substation must accommodate approved projects (per scenario)
    x_approved_ref = Float.ref()
    x_selected_ref = Float.ref()
    prob.satisfy(model.where(
        Project.x_approved(Scenario, x_approved_ref),
        Upgrade.x_selected(Scenario, x_selected_ref),
        Project.substation(Substation),
        Upgrade.substation(Substation),
    ).require(
        Substation.current_capacity
        + sum(x_selected_ref * UpgradeRef.capacity_added).where(
            UpgradeRef.substation == Substation).per(Substation, Scenario)
        >= sum(x_approved_ref * ProjectRef.capacity_needed).where(
            ProjectRef.substation == Substation).per(Substation, Scenario)
    ))

    # At most one upgrade per substation (per scenario)
    prob.satisfy(model.where(
        Upgrade.x_selected(Scenario, x_selected),
    ).require(
        sum(x_selected).where(Upgrade.substation == Substation).per(Substation, Scenario) <= 1
    ))

    # Budget limit (per scenario)
    prob.satisfy(model.where(
        Project.x_approved(Scenario, x_approved),
        Upgrade.x_selected(Scenario, x_selected),
    ).require(
        sum(x_approved * Project.connection_cost).per(Scenario)
        + sum(x_selected * Upgrade.upgrade_cost).per(Scenario)
        <= Scenario.budget
    ))

    # --- Epsilon constraint: infrastructure cost <= eps ---
    # SINGLE-OBJECTIVE: cost was subtracted from revenue in the objective
    # BI-OBJECTIVE: cost is bounded by epsilon, revenue is maximized separately
    if eps_cost is not None:
        prob.satisfy(model.where(
            Project.x_approved(Scenario, x_approved),
            Upgrade.x_selected(Scenario, x_selected),
        ).require(
            sum(x_approved * Project.connection_cost).per(Scenario)
            + sum(x_selected * Upgrade.upgrade_cost).per(Scenario)
            <= eps_cost
        ))

    # --- Objective ---
    if objective == "max_revenue":
        prob.maximize(
            sum(x_approved * Project.revenue).where(
                Project.x_approved(Scenario, x_approved))
        )
    elif objective == "min_cost":
        prob.minimize(
            sum(x_approved * Project.connection_cost).where(
                Project.x_approved(Scenario, x_approved))
            + sum(x_selected * Upgrade.upgrade_cost).where(
                Upgrade.x_selected(Scenario, x_selected))
        )

    prob.solve("highs", time_limit_sec=60)
    si = prob.solve_info()

    if si.termination_status != "OPTIMAL":
        return None

    df = prob.variable_values().to_df()
    return si, df


def extract_cost_from_df(df, scenario_name):
    """Extract total infrastructure cost for a scenario from variable_values df."""
    proj_costs = dict(zip(project_csv["name"], project_csv["connection_cost"]))
    # Key by (substation_name, capacity_added) to match variable naming
    # which uses Upgrade.substation.name (e.g. "Permian_Basin"), not substation_id
    sub_id_to_name = dict(zip(substation_csv["id"], substation_csv["name"]))
    upg_costs = {}
    for _, row in upgrade_csv.iterrows():
        sub_name = sub_id_to_name[row["substation_id"]]
        upg_costs[(sub_name, str(int(row["capacity_added"])))] = row["upgrade_cost"]

    total = 0.0
    for _, row in df.iterrows():
        name = str(row.iloc[0])
        val = float(row.iloc[1])
        if val < 0.5:
            continue
        if name.startswith(f"proj_{scenario_name}_"):
            proj_name = name.replace(f"proj_{scenario_name}_", "")
            total += proj_costs.get(proj_name, 0)
        elif name.startswith(f"upg_{scenario_name}_"):
            parts = name.replace(f"upg_{scenario_name}_", "").rsplit("_", 1)
            if len(parts) == 2:
                total += upg_costs.get((parts[0], parts[1]), 0)
    return total


def extract_revenue_from_df(df, scenario_name):
    """Extract total project revenue for a scenario from variable_values df."""
    proj_revenues = dict(zip(project_csv["name"], project_csv["revenue"]))
    total = 0.0
    for _, row in df.iterrows():
        name = str(row.iloc[0])
        val = float(row.iloc[1])
        if val > 0.5 and name.startswith(f"proj_{scenario_name}_"):
            proj_name = name.replace(f"proj_{scenario_name}_", "")
            total += proj_revenues.get(proj_name, 0)
    return total


# --------------------------------------------------
# Bi-objective: anchor solves + epsilon sweep
# --------------------------------------------------

if __name__ == "__main__":

    print("=" * 70)
    print("ANCHOR SOLVE 1: Maximize revenue (no cost constraint)")
    print("=" * 70)
    result1 = solve_grid("max_revenue", eps_cost=None)
    if result1 is None:
        raise SystemExit("Anchor solve 1 (max revenue) is infeasible — check data and constraints.")
    si1, df1 = result1
    print(f"Status: {si1.termination_status}, total revenue: {si1.objective_value:,.0f}")
    for sn in scenario_names:
        rev = extract_revenue_from_df(df1, sn)
        cost = extract_cost_from_df(df1, sn)
        print(f"  {sn}: revenue={rev:,.0f}, infra_cost={cost:,.0f}")

    # Get cost range from anchor 1
    anchor1_costs = {sn: extract_cost_from_df(df1, sn) for sn in scenario_names}
    cost_max = max(anchor1_costs.values())

    print(f"\n{'=' * 70}")
    print("ANCHOR SOLVE 2: Minimize infrastructure cost")
    print(f"{'=' * 70}")
    result2 = solve_grid("min_cost", eps_cost=None)
    if result2 is None:
        raise SystemExit("Anchor solve 2 (min cost) is infeasible — check data and constraints.")
    si2, df2 = result2
    print(f"Status: {si2.termination_status}, min cost: {si2.objective_value:,.0f}")
    anchor2_costs = {sn: extract_cost_from_df(df2, sn) for sn in scenario_names}
    # Use min per-scenario cost (not aggregate objective) since epsilon constraint is .per(Scenario)
    cost_min = min(anchor2_costs.values())
    for sn in scenario_names:
        rev = extract_revenue_from_df(df2, sn)
        cost = extract_cost_from_df(df2, sn)
        print(f"  {sn}: revenue={rev:,.0f}, infra_cost={cost:,.0f}")

    print(f"\nInfrastructure cost range: [{cost_min:,.0f}, {cost_max:,.0f}]")

    # --------------------------------------------------
    # Epsilon sweep: maximize revenue s.t. cost <= eps
    # --------------------------------------------------

    n_interior = 5
    epsilon_values = [
        cost_min + i * (cost_max - cost_min) / (n_interior + 1)
        for i in range(1, n_interior + 1)
    ]

    print(f"\n{'=' * 70}")
    print(f"EPSILON SWEEP: {n_interior} interior points")
    print(f"Cost caps: {[f'{e:,.0f}' for e in epsilon_values]}")
    print(f"{'=' * 70}")

    pareto = {sn: [] for sn in scenario_names}

    # Add anchor 2 (min cost) as first point
    for sn in scenario_names:
        pareto[sn].append({
            "label": "min_cost",
            "cost_cap": cost_min,
            "revenue": extract_revenue_from_df(df2, sn),
            "cost": extract_cost_from_df(df2, sn),
            "df": df2,
        })

    for i, eps in enumerate(epsilon_values):
        result = solve_grid("max_revenue", eps_cost=eps)
        if result is None:
            print(f"  Point {i+1} (cost<={eps:,.0f}): INFEASIBLE -- stopping")
            break

        si, df = result
        print(f"  Point {i+1} (cost<={eps:,.0f}): revenue={si.objective_value:,.0f}  [{si.termination_status}]")
        for sn in scenario_names:
            pareto[sn].append({
                "label": f"eps_{i+1}",
                "cost_cap": eps,
                "revenue": extract_revenue_from_df(df, sn),
                "cost": extract_cost_from_df(df, sn),
                "df": df,
            })

    # Add anchor 1 (max revenue) as last point
    for sn in scenario_names:
        pareto[sn].append({
            "label": "max_revenue",
            "cost_cap": cost_max,
            "revenue": extract_revenue_from_df(df1, sn),
            "cost": extract_cost_from_df(df1, sn),
            "df": df1,
        })

    # --------------------------------------------------
    # Pareto analysis
    # --------------------------------------------------

    print(f"\n{'=' * 70}")
    print("EFFICIENT FRONTIER: Revenue vs Infrastructure Cost (per budget scenario)")
    print(f"{'=' * 70}")

    for sn in scenario_names:
        pts = pareto[sn]
        if len(pts) < 2:
            continue
        print(f"\n  {sn}:")
        print(f"  {'#':>3} {'Label':>12} {'Revenue':>14} {'Infra Cost':>14}")
        print(f"  {'-' * 46}")
        for j, pt in enumerate(pts):
            print(f"  {j+1:>3} {pt['label']:>12} {pt['revenue']:>14,.0f} {pt['cost']:>14,.0f}")

        # Marginal analysis
        if len(pts) >= 3:
            print("\n  Marginal analysis (revenue per $ of infrastructure):")
            rates = []
            for j in range(len(pts) - 1):
                d_rev = pts[j+1]['revenue'] - pts[j]['revenue']
                d_cost = pts[j+1]['cost'] - pts[j]['cost']
                if abs(d_cost) > 1e-6:
                    rate = d_rev / d_cost
                    rates.append(rate)
                    print(f"    {pts[j]['label']:>12} → {pts[j+1]['label']:<12}: "
                          f"Δrev={d_rev:>+14,.0f}, Δcost={d_cost:>+14,.0f}, "
                          f"marginal={rate:>6.2f}x return")
                else:
                    rates.append(0)

            # Knee detection: rates[j]/rates[j+1] finds where marginal revenue
            # per dollar of infra drops most sharply (ratio > 1 = diminishing returns).
            # This is rates[j]/rates[j+1] because revenue-per-cost is DECREASING
            # along the frontier, so the biggest drop ratio marks the knee.
            if len(rates) >= 2:
                max_jump = 0
                knee_idx = 1
                for j in range(len(rates) - 1):
                    if rates[j] > 1e-6:
                        jump = abs(rates[j] / rates[j+1]) if rates[j+1] > 1e-6 else float('inf')
                    else:
                        jump = 0
                    if jump > max_jump:
                        max_jump = jump
                        knee_idx = j + 1
                print(f"\n    Knee: Point {knee_idx + 1} ({pts[knee_idx]['label']}) "
                      f"-- diminishing returns beyond this investment level")

                # Print approved projects at the knee point
                knee_df = pts[knee_idx]["df"]
                proj_names = dict(zip(project_csv["name"], project_csv["revenue"]))
                prefix = f"proj_{sn}_"
                approved = []
                for _, row in knee_df.iterrows():
                    vname = str(row.iloc[0])
                    val = float(row.iloc[1])
                    if val > 0.5 and vname.startswith(prefix):
                        pname = vname.replace(prefix, "")
                        approved.append((pname, proj_names.get(pname, 0)))
                if approved:
                    print(f"\n    Knee-point approved projects ({sn}):")
                    for pname, rev in sorted(approved, key=lambda x: -x[1]):
                        print(f"      {pname}: revenue={rev:,.0f}")
