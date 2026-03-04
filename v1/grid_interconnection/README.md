---
title: "Grid Interconnection"
description: "Approve data center interconnection requests and substation upgrades to maximize net revenue within a capital budget."
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
---

# Grid Interconnection

## What this template is for

As data center demand surges, utilities must decide which interconnection requests to approve and whether to invest in substation capacity upgrades. Each data center project requires a certain amount of electrical capacity at a specific substation, generates ongoing revenue, and has a one-time connection cost. Substations have limited current capacity but can be upgraded (at a cost) to accommodate more load. The utility wants to maximize net revenue -- the total revenue from approved projects minus connection and upgrade costs -- subject to a capital budget constraint.

This template formulates the grid interconnection problem as a mixed-integer program. Binary variables determine which projects are approved and which substation upgrades are selected. Constraints ensure that the total capacity demand at each substation does not exceed current capacity plus any selected upgrade, that at most one upgrade is chosen per substation, and that total investment stays within budget. The objective maximizes net revenue across all approved projects.

The template includes scenario analysis across three capital budget levels ($1B, $2B, $3B), showing how additional investment capacity unlocks more projects and higher net revenue.

## Who this is for

- Utility planners evaluating data center interconnection queues
- Infrastructure investment analysts modeling capital allocation decisions
- Energy sector developers building grid planning optimization tools
- Operations researchers learning binary optimization with RelationalAI

## What you'll build

- A binary optimization model for project approval and infrastructure upgrade selection
- Substation capacity constraints linking approved projects to available/upgraded capacity
- Capital budget constraints across projects and upgrades
- Scenario analysis across three budget levels

## What's included

- `grid_interconnection.py` -- main script with ontology, formulation, and scenario loop
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
   Running scenario: budget = 1000000000
     Status: OPTIMAL, Objective: 1876000000.0

     Approved projects:
                  name  value
       Stargate_Phase2    1.0
        HyperCloud_DFW    1.0
        DataBank_Colo     1.0

     Selected upgrades:
                        name  value
    upg_Abilene_350           1.0

   Running scenario: budget = 2000000000
     Status: OPTIMAL, Objective: 4560000000.0
     ...

   Running scenario: budget = 3000000000
     Status: OPTIMAL, Objective: 6230000000.0
     ...

   ==================================================
   Scenario Analysis Summary
   ==================================================
     1000000000: OPTIMAL, obj=1876000000.0
     2000000000: OPTIMAL, obj=4560000000.0
     3000000000: OPTIMAL, obj=6230000000.0
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

**1. Define the ontology.** Substations, projects, and upgrades are modeled as concepts with properties and relationships:

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

**2. Define decision variables.** Binary variables for project approval and upgrade selection:

```python
s.solve_for(Project.x_approved, type="bin", name=Project.name)
s.solve_for(Upgrade.x_selected, type="bin", name=["upg", Upgrade.substation.name, Upgrade.capacity_added])
```

**3. Add capacity constraints.** At each substation, the total capacity demand from approved projects must not exceed current capacity plus any selected upgrade:

```python
project_demand = sum(ProjectRef.x_approved * ProjectRef.capacity_needed).where(
    ProjectRef.substation == Substation).per(Substation)
upgrade_capacity = sum(UpgradeRef.x_selected * UpgradeRef.capacity_added).where(
    UpgradeRef.substation == Substation).per(Substation)
s.satisfy(model.require(Substation.current_capacity + upgrade_capacity >= project_demand))
```

**4. Enforce budget and upgrade limits.** At most one upgrade per substation, and total investment within budget:

```python
s.satisfy(model.require(sum(UpgradeRef.x_selected).where(
    UpgradeRef.substation == Substation).per(Substation) <= 1))

total_investment = sum(Project.x_approved * Project.connection_cost) + sum(Upgrade.x_selected * Upgrade.upgrade_cost)
s.satisfy(model.require(total_investment <= budget))
```

**5. Maximize net revenue:**

```python
net_revenue = sum(Project.x_approved * (Project.revenue - Project.connection_cost))
s.maximize(net_revenue)
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

- The optimizer maximizes net revenue (revenue minus connection cost), not gross revenue. A high-revenue project with a high connection cost may be less attractive than a moderate-revenue project with a low connection cost.
- Check that upgrade costs and capacity additions are consistent -- a cheaper upgrade that unlocks high-value projects will be preferred.

</details>
