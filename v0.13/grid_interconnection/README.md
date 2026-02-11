---
title: "Grid Interconnection"
description: "Approve data center interconnection requests and substation upgrades to maximize net revenue within capital budget."
featured: false
experience_level: intermediate
industry: "Energy & Utilities"
reasoning_types:
  - Prescriptive
tags:
  - Design
  - MILP
---

# Grid Interconnection

> [!WARNING]
> This template uses the early access `relational.semantics` API in version `0.13` of the `relationalai` Python package.

## What this template is for

Utilities are seeing a surge of data center interconnection requests. Each project requires substation capacity (MW) and capital investment to connect to the grid, and utilities can also invest in substation upgrades to expand capacity.

This template helps you choose which interconnection projects to approve and which substation upgrades to build, subject to capacity and budget constraints, to maximize net revenue.

## Who this is for

- Data scientists, analysts, and engineers building portfolio selection or infrastructure planning optimizers.
- Readers who are comfortable with basic linear optimization ideas (binary decisions, budgets, capacity constraints).

## What you’ll build

- A semantic model representing substations, interconnection projects, and upgrade options.
- A mixed-integer optimization model with:
  - binary project approvals
  - binary upgrade selections
  - capacity and budget constraints
- A simple scenario analysis that solves multiple budget levels and compares objective values.

## What’s included

- `grid_interconnection.py` — defines the semantic model, optimization problem, and prints a solution
- `data/` — sample CSV inputs (`substations.csv`, `projects.csv`, `upgrades.csv`)

## Prerequisites

### Access

- RelationalAI account with access to an org/project.
- A configured profile for the RAI Native App.

### Tools

- Python 3.10+
- RelationalAI CLI (`rai`)

## Quickstart

Follow these steps to run the template with the included sample data.

1. **Create and activate a virtual environment**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install -U pip
   ```

2. **Install dependencies**

   From this folder:

   ```bash
   python -m pip install .
   ```

3. **Configure Snowflake connection and RAI profile**

   ```bash
   rai init
   ```

4. **Run the template**

   ```bash
   python grid_interconnection.py
   ```

5. **Expected output**

   Decision variables shown for the baseline scenario (budget = $2B). The summary below shows objectives for all scenarios.

   ```text
   Running scenario: budget = 2000000000
     Status: OPTIMAL, Objective: 4398000000.0

     Approved projects:
              name  value
       Azure_South    1.0
       MetaAI_West    1.0
         Oracle_SA    1.0
   Stargate_Phase2    1.0
       xAI_Permian    1.0

     Selected upgrades:
                    name  value
   upg_Permian_Basin_200    1.0

   ==================================================
   Scenario Analysis Summary
   ==================================================
     1000000000: OPTIMAL, obj=2710000000.0
     2000000000: OPTIMAL, obj=4398000000.0
     3000000000: OPTIMAL, obj=5879000000.0
   ```

## Template structure

```text
grid_interconnection/
  README.md
  pyproject.toml
  grid_interconnection.py     # main script with model and optimization
  data/                       # sample data
    substations.csv
    projects.csv
    upgrades.csv
```

## Sample data

Data files are located in the `data/` subdirectory.

### substations.csv

6 substations with varying current and maximum capacity (MW).

| Column | Description |
|--------|-------------|
| `id` | Unique substation identifier |
| `name` | Substation name |
| `current_capacity` | Existing capacity (MW) |
| `max_capacity` | Maximum possible capacity after upgrades (MW) |

### projects.csv

14 data center interconnection requests.

| Column | Description |
|--------|-------------|
| `id` | Unique project identifier |
| `name` | Project name |
| `substation_id` | Substation where project connects |
| `capacity_needed` | Capacity required (MW) |
| `revenue` | 10-year NPV ($) |
| `connection_cost` | One-time connection cost ($) |

### upgrades.csv

12 upgrade options (2 per substation) with capacity additions and upgrade costs.

| Column | Description |
|--------|-------------|
| `id` | Unique upgrade identifier |
| `substation_id` | Substation to upgrade |
| `capacity_added` | Additional capacity from upgrade (MW) |
| `upgrade_cost` | Cost of upgrade ($) |

## Model overview

The template uses three base concepts and two binary decision variables.

### `Substation`

Represents a grid connection point where projects interconnect and where upgrades can add capacity.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | int | Yes | Loaded from `data/substations.csv` |
| `name` | string | No | Human-readable identifier |
| `current_capacity` | int | No | MW available before upgrades |
| `max_capacity` | int | No | Upper bound after upgrades |

### `Project`

Represents an interconnection request with required capacity and economics.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | int | Yes | Loaded from `data/projects.csv` |
| `name` | string | No | Used to name decision variables |
| `substation` | `Substation` | No | Where the project connects |
| `capacity_needed` | int | No | MW required if approved |
| `revenue` | float | No | 10-year NPV ($) |
| `connection_cost` | float | No | Capital cost ($) |
| `approved` | float | No | Decision variable (binary 0/1) |

### `Upgrade`

Represents a candidate substation upgrade option.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | int | Yes | Loaded from `data/upgrades.csv` |
| `substation` | `Substation` | No | Substation being upgraded |
| `capacity_added` | int | No | MW added if selected |
| `upgrade_cost` | float | No | Capital cost ($) |
| `selected` | float | No | Decision variable (binary 0/1) |

## How it works

This section walks through the highlights in `grid_interconnection.py`.

### Import libraries and configure inputs

```python
from pathlib import Path

import pandas
from pandas import read_csv

from relationalai.semantics import Model, data, require, select, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

# --------------------------------------------------
# Configure inputs and create the model
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"

# Disable pandas inference of string types. This ensures that string columns
# in the CSVs are loaded as object dtype. This is only required when using
# relationalai versions prior to v1.0.
pandas.options.future.infer_string = False
```

### Define concepts and load CSV data

```python
# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

# Create a Semantics model container.
model = Model("grid", config=globals().get("config", None), use_lqp=False)

# Concept: substations with current and max capacity
Substation = model.Concept("Substation")
Substation.id = model.Property("{Substation} has {id:int}")
Substation.name = model.Property("{Substation} has {name:string}")
Substation.current_capacity = model.Property("{Substation} has {current_capacity:int}")
Substation.max_capacity = model.Property("{Substation} has {max_capacity:int}")

# Load substations from CSV.
data(read_csv(DATA_DIR / "substations.csv")).into(Substation, keys=["id"])

# Concept: projects with capacity needs, revenue, and connection costs
Project = model.Concept("Project")
Project.id = model.Property("{Project} has {id:int}")
Project.name = model.Property("{Project} has {name:string}")
Project.substation = model.Property("{Project} connects to {substation:Substation}")
Project.capacity_needed = model.Property("{Project} needs {capacity_needed:int}")
Project.revenue = model.Property("{Project} has {revenue:float}")
Project.connection_cost = model.Property("{Project} has {connection_cost:float}")
Project.approved = model.Property("{Project} is {approved:float}")

# Load projects from CSV.
projects_data = data(read_csv(DATA_DIR / "projects.csv"))

# Define Project entities by joining each project row to its Substation.
where(Substation.id(projects_data.substation_id)).define(
    Project.new(
        id=projects_data.id,
        name=projects_data.name,
        substation=Substation,
        capacity_needed=projects_data.capacity_needed,
        revenue=projects_data.revenue,
        connection_cost=projects_data.connection_cost,
    )
)

# Concept: upgrades with capacity additions and costs
Upgrade = model.Concept("Upgrade")
Upgrade.id = model.Property("{Upgrade} has {id:int}")
Upgrade.substation = model.Property("{Upgrade} for {substation:Substation}")
Upgrade.capacity_added = model.Property("{Upgrade} adds {capacity_added:int}")
Upgrade.upgrade_cost = model.Property("{Upgrade} has {upgrade_cost:float}")
Upgrade.selected = model.Property("{Upgrade} is {selected:float}")

# Load upgrades from CSV.
upgrades_data = data(read_csv(DATA_DIR / "upgrades.csv"))

# Define Upgrade entities by joining each upgrade row to its Substation.
where(Substation.id(upgrades_data.substation_id)).define(
    Upgrade.new(
        id=upgrades_data.id,
        substation=Substation,
        capacity_added=upgrades_data.capacity_added,
        upgrade_cost=upgrades_data.upgrade_cost,
    )
)
```

### Define decision variables, constraints, and objective

The script solves multiple budget scenarios:

```python
SCENARIO_VALUES = [1000000000, 2000000000, 3000000000]

scenario_results = []

for scenario_value in SCENARIO_VALUES:
    print(f"\nRunning scenario: {SCENARIO_PARAM} = {scenario_value}")

    # Set scenario parameter value
    budget = scenario_value

    # Create fresh SolverModel for each scenario
    solver_model = SolverModel(model, "cont")

    # Variable: binary approval and selection
    solver_model.solve_for(Project.approved, type="bin", name=Project.name)
    solver_model.solve_for(
        Upgrade.selected,
        type="bin",
        name=["upg", Upgrade.substation.name, Upgrade.capacity_added],
    )

    # Constraint: capacity at substation must accommodate approved projects
    project_demand = (
        sum(Proj.approved * Proj.capacity_needed)
        .where(Proj.substation == Substation)
        .per(Substation)
    )
    upgrade_capacity = (
        sum(Upg.selected * Upg.capacity_added)
        .where(Upg.substation == Substation)
        .per(Substation)
    )
```

Then it adds constraints, defines the objective, and solves:

```python
    capacity_ok = require(Substation.current_capacity + upgrade_capacity >= project_demand)
    solver_model.satisfy(capacity_ok)

    # Constraint: at most one upgrade per substation
    upgrades_per_sub = sum(Upg.selected).where(Upg.substation == Substation).per(Substation)
    one_upgrade = require(upgrades_per_sub <= 1)
    solver_model.satisfy(one_upgrade)

    # Constraint: budget
    total_investment = sum(Project.approved * Project.connection_cost) + sum(Upgrade.selected * Upgrade.upgrade_cost)
    budget_ok = require(total_investment <= budget)
    solver_model.satisfy(budget_ok)

    # Objective: maximize net revenue
    net_revenue = sum(Project.approved * (Project.revenue - Project.connection_cost))
    solver_model.maximize(net_revenue)

    solver = Solver("highs")
    solver_model.solve(solver, time_limit_sec=60)
```

### Solve and print results

For each scenario, the script prints the objective and the selected decisions:

```python
    print(f"  Status: {solver_model.termination_status}, Objective: {solver_model.objective_value}")

    # Print approved projects from solver results
    var_df = solver_model.variable_values().to_df()
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
```

## Customize this template

### Use your own data

- Replace the CSVs under `data/` with your own.
- Keep the same column names (or update the corresponding data-loading code in `grid_interconnection.py`).

### Change the scenario parameters

This template includes budget sensitivity analysis by solving multiple values of `budget`.

| Parameter | Type | Values | Description |
| --- | --- | --- | --- |
| `budget` | numeric | `1000000000`, `2000000000`, `3000000000` | Total capital budget for connection costs and upgrades |

To customize the scenarios, edit `SCENARIO_VALUES` in `grid_interconnection.py`.

How to interpret results:

- If increasing `budget` doesn’t change the objective or selected projects, the budget is likely **non-binding** (capacity or single-upgrade constraints are limiting).
- If increasing `budget` increases the objective and unlocks more projects, the budget is **binding** over that range.

### Extend the model

- Add additional constraints such as project dependencies, minimum portfolio composition, or substation-specific policy rules.
- Add a penalty or risk term (e.g., prefer diversified substations) and trade it off against net revenue.

## Troubleshooting

<details>
  <summary>Connection/auth issues</summary>

- Re-run `rai init` and confirm the selected profile is correct.
- Ensure you have access to the RAI Native App in Snowflake.

</details>

<details>
  <summary><code>ModuleNotFoundError</code> when running the script</summary>

- Confirm your virtual environment is activated.
- Install the template dependencies from this folder: `python -m pip install .`

</details>

<details>
  <summary>CSV loading fails (missing file or column)</summary>

- Confirm the CSVs exist under `data/` and the filenames match.
- Confirm the headers match the expected schemas:
  - `substations.csv`: `id`, `name`, `current_capacity`, `max_capacity`
  - `projects.csv`: `id`, `name`, `substation_id`, `capacity_needed`, `revenue`, `connection_cost`
  - `upgrades.csv`: `id`, `substation_id`, `capacity_added`, `upgrade_cost`

</details>

<details>
  <summary>Why are no projects approved?</summary>

- Check whether the budget is too small to pay for any project connection costs.
- Check whether the capacity constraints are too tight (for example, low `current_capacity` and no upgrades selected).

</details>
