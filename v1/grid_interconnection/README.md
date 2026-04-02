---
title: "Grid Interconnection"
description: "Explore the tradeoff between project revenue and infrastructure investment using bi-objective optimization with epsilon constraint."
featured: false
experience_level: intermediate
industry: "Energy & Utilities"
reasoning_types:
  - Prescriptive
tags:
  - capital-planning
  - mixed-integer-programming
  - energy
  - what-if-analysis
  - infrastructure
  - Multi-Objective
---

# Grid Interconnection

## What this template is for

This template uses **prescriptive reasoning (optimization)** to frame grid interconnection planning as a bi-objective problem with two competing objectives: maximize project revenue versus minimize infrastructure cost (substation upgrades and connection fees). Rather than collapsing both objectives into a single weighted sum, it uses the epsilon constraint method to sweep a range of infrastructure cost caps. At each cap the solver maximizes revenue subject to that spending limit, producing a Pareto frontier that reveals exactly how much additional revenue each dollar of infrastructure investment buys.

Inside the epsilon loop the template also demonstrates the Scenario concept, solving across multiple budget levels simultaneously. This combination -- epsilon constraint for the bi-objective tradeoff and scenarios for what-if analysis -- shows how to layer multi-objective and scenario techniques in a single model.

## Who this is for

- Utility planners evaluating data center interconnection queues
- Infrastructure investment analysts modeling capital allocation decisions
- Energy sector developers building grid planning optimization tools
- Operations researchers learning binary optimization with RelationalAI

## What you'll build

- A binary optimization model for project approval and infrastructure upgrade selection
- Substation capacity constraints linking approved projects to available/upgraded capacity
- Capital budget constraints across projects and upgrades
- Epsilon constraint method sweeping infrastructure cost caps to trace the revenue-cost frontier
- Anchor solves to establish the feasible cost range
- Scenario analysis across three budget levels with Pareto analysis and knee detection

## What's included

- `grid_interconnection.py` -- main script with ontology, formulation, epsilon constraint sweep, and Pareto analysis
- `data/substations.csv` -- 6 substations with current and maximum capacity
- `data/projects.csv` -- 14 data center projects with capacity needs, revenue, and connection costs
- `data/upgrades.csv` -- 12 upgrade options (2 per substation) with capacity additions and costs
- `pyproject.toml` -- Python package configuration

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools
- Python >= 3.10

## Quickstart

1. Download ZIP:
   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/grid_interconnection.zip
   unzip grid_interconnection.zip
   cd grid_interconnection
   ```
   > [!TIP]
   > You can also download the template ZIP using the "Download ZIP" button at the top of this page.

2. Create venv:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   ```

3. Install:
   ```bash
   python -m pip install .
   ```

4. Configure:
   ```bash
   rai init
   ```

5. Run:
   ```bash
   python grid_interconnection.py
   ```

6. Expected output:
   ```text
   ======================================================================
   ANCHOR SOLVE 1: Maximize revenue (no cost constraint)
   ======================================================================
   Status: OPTIMAL, total revenue: ...
     budget_1B: revenue=..., infra_cost=...
     budget_2B: revenue=..., infra_cost=...
     budget_3B: revenue=..., infra_cost=...

   ======================================================================
   EPSILON SWEEP: 5 interior points
   ======================================================================
     Point 1 (cost<=...): revenue=...  [OPTIMAL]
     Point 2 (cost<=...): revenue=...  [OPTIMAL]
     ...

   ======================================================================
   EFFICIENT FRONTIER: Revenue vs Infrastructure Cost (per budget scenario)
   ======================================================================

     budget_1B:
       #        Label        Revenue     Infra Cost
       -----------------------------------------------
       1     min_cost          ...            ...
       2        eps_1          ...            ...
       ...

     Marginal analysis (revenue per $ of infrastructure):
       ...
       Knee: Point N (...) -- diminishing returns beyond this investment level
   ```

## Template structure
```text
.
├── README.md
├── pyproject.toml
├── grid_interconnection.py
└── data/
    ├── substations.csv
    ├── projects.csv
    └── upgrades.csv
```

## How it works

This section walks through the highlights in `grid_interconnection.py`.

### Define concepts and load CSV data

Substations, projects, and upgrades are modeled as concepts with properties and relationships.

```python
Substation = Concept("Substation", identify_by={"id": Integer})
Substation.current_capacity = Property(f"{Substation} has {Integer:current_capacity}")
Substation.max_capacity = Property(f"{Substation} has {Integer:max_capacity}")

Project = Concept("Project", identify_by={"id": Integer})
Project.capacity_needed = Property(f"{Project} needs {Integer:capacity_needed}")
Project.revenue = Property(f"{Project} has {Float:revenue}")
Project.connection_cost = Property(f"{Project} has {Float:connection_cost}")

Upgrade = Concept("Upgrade", identify_by={"id": Integer})
Upgrade.capacity_added = Property(f"{Upgrade} adds {Integer:capacity_added}")
Upgrade.upgrade_cost = Property(f"{Upgrade} has {Float:upgrade_cost}")
```

A `Scenario` concept holds three budget levels so all scenarios are solved simultaneously inside each epsilon solve.

```python
Scenario = Concept("Scenario", identify_by={"name": String})
Scenario.budget = Property(f"{Scenario} has {Float:budget}")
scenario_data = model.data(
    [("budget_1B", 1_000_000_000), ("budget_2B", 2_000_000_000), ("budget_3B", 3_000_000_000)],
    columns=["name", "budget"],
)
model.define(Scenario.new(scenario_data.to_schema()))
```

### Define decision variables, constraints, and objective

Binary variables for project approval and upgrade selection are indexed by `Scenario`. The `solve_grid` helper encapsulates the shared constraints and objective, accepting an `objective` parameter and an optional `eps_cost` epsilon bound.

The original single-objective template optimized net revenue in one expression (`p.maximize(sum(x_approved * (Project.revenue - Project.connection_cost)))`). The bi-objective version splits revenue and cost: the primary objective maximizes revenue, while infrastructure cost is bounded by an epsilon constraint.

```python
def solve_grid(objective="max_revenue", eps_cost=None):
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
```

Constraints enforce substation capacity, at most one upgrade per substation, and a budget limit -- all scoped per Scenario.

```python
    # Capacity at substation must accommodate approved projects (per scenario)
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
```

When `eps_cost` is provided, a constraint caps total infrastructure spending per scenario.

```python
    if eps_cost is not None:
        prob.satisfy(model.where(
            Project.x_approved(Scenario, x_approved),
            Upgrade.x_selected(Scenario, x_selected),
        ).require(
            sum(x_approved * Project.connection_cost).per(Scenario)
            + sum(x_selected * Upgrade.upgrade_cost).per(Scenario)
            <= eps_cost
        ))
```

The objective switches between maximizing revenue (primary) and minimizing cost (used for anchor solve 2).

```python
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
```

### Solve anchor points and run the epsilon sweep

Two anchor solves establish the infrastructure cost range. Anchor 1 maximizes revenue with no cost cap (finding the highest cost the solver would choose). Anchor 2 minimizes cost (finding the minimum feasible investment).

```python
result1 = solve_grid("max_revenue", eps_cost=None)
result2 = solve_grid("min_cost", eps_cost=None)
```

The epsilon sweep then traces interior points between the cost extremes. Each solve maximizes revenue subject to a progressively higher infrastructure cost cap.

```python
n_interior = 5
epsilon_values = [
    cost_min + i * (cost_max - cost_min) / (n_interior + 1)
    for i in range(1, n_interior + 1)
]

for i, eps in enumerate(epsilon_values):
    result = solve_grid("max_revenue", eps_cost=eps)
```

### Pareto analysis output

The script prints the efficient frontier for each budget scenario, showing how revenue grows as the infrastructure cost cap increases. Marginal analysis computes the incremental revenue per dollar of infrastructure, and a knee detector identifies the point where diminishing returns set in.

```python
for sn in scenario_names:
    pts = pareto[sn]
    # ...
    # Marginal analysis (revenue per $ of infrastructure)
    for j in range(len(pts) - 1):
        d_rev = pts[j+1]['revenue'] - pts[j]['revenue']
        d_cost = pts[j+1]['cost'] - pts[j]['cost']
        if abs(d_cost) > 1e-6:
            rate = d_rev / d_cost
            # ...
    # Knee detection
    print(f"\n    Knee: Point {knee_idx + 1} ({pts[knee_idx]['label']}) "
          f"— diminishing returns beyond this investment level")
```

## Customize this template

- **Add your own substations and projects** by editing the CSV files with real capacity and cost data.
- **Add multi-year phasing** by introducing time periods and annual budget constraints.
- **Add reliability constraints** such as N-1 contingency requirements per substation.
- **Model interdependencies** between projects (e.g., mutually exclusive projects, prerequisite projects).
- **Add environmental constraints** such as carbon limits or renewable energy requirements.
- **Weight the objective** to include social or strategic value beyond pure revenue.

## Troubleshooting

<details>
  <summary>Solver returns INFEASIBLE</summary>

- Check that the budget is large enough to cover connection costs for at least some projects.
- Verify that substation capacities (current + max upgrade) can accommodate at least one project each.
- Ensure project substation IDs in `projects.csv` match IDs in `substations.csv`.

</details>

<details>
  <summary>Import error for <code>relationalai</code></summary>

- Confirm your virtual environment is active: `which python` should point to `.venv`.
- Reinstall dependencies: `python -m pip install .`.

</details>

<details>
  <summary>Authentication or configuration errors</summary>

- Run `rai init` to create or update your RelationalAI/Snowflake configuration.
- If you have multiple profiles, set `export RAI_PROFILE=<your_profile>`.

</details>

<details>
  <summary>Unexpected project selections</summary>

- The optimizer maximizes gross revenue subject to an infrastructure cost cap. At tighter cost caps, high-connection-cost projects may be excluded even if they have high revenue.
- Check that upgrade costs and capacity additions are consistent -- a cheaper upgrade that unlocks high-value projects will be preferred.

</details>
