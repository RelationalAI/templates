---
title: "Diet Optimization"
description: "Select foods to satisfy nutritional requirements at minimum cost."
featured: false
experience_level: beginner
industry: "Healthcare & Nutrition"
reasoning_types:
  - Prescriptive
tags:
  - Linear Programming
  - Cost Minimization
  - Scenario Analysis
---

# Diet Optimization

## What this template is for

Choosing a balanced diet that meets nutritional requirements while staying within a budget is a classic optimization problem. Given a set of foods with known costs and nutrient contents, and a set of nutrients with minimum and maximum daily intake bounds, the goal is to find the cheapest combination of foods that satisfies all nutritional constraints.

This template uses prescriptive reasoning to formulate and solve the diet problem as a linear program. Each food has a continuous decision variable representing how much of it to include. Constraints enforce that the total nutrient intake from the selected foods falls within the required bounds for every nutrient.

The template also demonstrates scenario analysis by scaling nutritional requirements up and down (0.8x, 1.0x, 1.2x) and solving independently for each scenario. This lets you compare how dietary cost changes as requirements become more or less restrictive.

## Who this is for

- Data scientists and analysts learning prescriptive optimization with RelationalAI
- Operations researchers looking for a clean LP formulation example
- Anyone interested in nutritional planning or cost minimization problems
- Beginners who want to understand scenario analysis in optimization

## What you'll build

- A linear programming model that selects foods to minimize total cost
- Nutritional constraints ensuring minimum and maximum daily intake for calories, protein, fat, and sodium
- Scenario analysis that scales nutritional requirements and compares results across scenarios

## What's included

- `diet.py` -- Main script defining the optimization model, constraints, and scenario analysis
- `data/foods.csv` -- Food items with cost and nutrient content per serving
- `data/nutrients.csv` -- Nutrient names with minimum and maximum daily intake bounds
- `pyproject.toml` -- Python package configuration with dependencies

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools
- Python >= 3.10

## Quickstart

1. Download ZIP:
   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/diet.zip
   unzip diet.zip
   cd diet
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
   python diet.py
   ```

6. Expected output:
   ```text
   Running scenario: nutrient_scaling = 0.8
     Status: OPTIMAL, Objective: $6.53
     Diet plan:
        name  value
     chicken   0.52
        milk  10.41
    icecream   1.37

   Running scenario: nutrient_scaling = 1.0
     Status: OPTIMAL, Objective: $8.20
     Diet plan:
        name  value
     chicken   0.65
        milk  13.01
    icecream   1.71

   Running scenario: nutrient_scaling = 1.2
     Status: OPTIMAL, Objective: $9.87
     Diet plan:
        name  value
     chicken   0.78
        milk  15.62
    icecream   2.06

   ==================================================
   Scenario Analysis Summary
   ==================================================
     scaling=0.8: OPTIMAL, cost=$6.53
     scaling=1.0: OPTIMAL, cost=$8.20
     scaling=1.2: OPTIMAL, cost=$9.87
   ```

## Template structure

```text
.
├── README.md
├── pyproject.toml
├── diet.py
└── data/
    ├── foods.csv
    └── nutrients.csv
```

## How it works

### 1. Define concepts and load data

The model defines two concepts: `Nutrient` (with min/max bounds) and `Food` (with cost and nutrient content). A ternary property links each food to its nutrient quantities:

```python
Nutrient = model.Concept("Nutrient", identify_by={"name": String})
Nutrient.min = model.Property(f"{Nutrient} has {Float:min}")
Nutrient.max = model.Property(f"{Nutrient} has {Float:max}")

Food = model.Concept("Food", identify_by={"name": String})
Food.cost = model.Property(f"{Food} has {Float:cost}")
Food.contains = model.Property(f"{Food} contains {Nutrient} in {Float:qty}")
```

### 2. Decision variables

Each food gets a continuous decision variable representing the amount to include in the diet:

```python
Food.x_amount = model.Property(f"{Food} has {Float:amount}")
s.solve_for(Food.x_amount, name=Food.name, lower=0, populate=False)
```

### 3. Constraints and objective

Nutritional constraints ensure total intake from all foods falls within bounds for each nutrient. The objective minimizes total food cost:

```python
qty = Float.ref()
nutrient_total = sum(qty * Food.x_amount).where(Food.contains(Nutrient, qty)).per(Nutrient)
s.satisfy(model.require(
    nutrient_total >= Nutrient.min * scenario_value,
    nutrient_total <= Nutrient.max * scenario_value
))
s.minimize(sum(Food.cost * Food.x_amount))
```

### 4. Scenario analysis

The template solves three scenarios by scaling nutritional requirements to 80%, 100%, and 120% of their base values, demonstrating how tighter or looser requirements affect total cost.

## Customize this template

- **Add more foods or nutrients**: Extend the CSV files with additional rows and columns. The model automatically picks up new data.
- **Change scenario parameters**: Modify `SCENARIO_VALUES` to test different scaling factors or introduce entirely different scenario dimensions (e.g., budget caps).
- **Add dietary preferences**: Introduce upper bounds on specific foods (e.g., limit red meat) or add binary variables to model food inclusion/exclusion.
- **Weight objectives**: Add a secondary objective term to penalize undesirable foods alongside cost minimization.

## Troubleshooting

<details>
<summary>Problem is infeasible</summary>

The nutritional bounds may be too tight for the available foods. Check that at least one combination of foods can satisfy all min/max constraints simultaneously. Try relaxing the scaling factor to a lower value (e.g., 0.5).
</details>

<details>
<summary>rai init fails or connection errors</summary>

Ensure your Snowflake credentials are configured correctly and that the RAI Native App is installed on your account. Run `rai init` again and verify the connection settings.
</details>

<details>
<summary>ModuleNotFoundError for relationalai</summary>

Make sure you activated the virtual environment and ran `python -m pip install .` from the template directory. The `pyproject.toml` declares the required dependencies.
</details>

<details>
<summary>Unexpected zero values in solution</summary>

Foods with zero in the solution are not cost-effective given the constraints. This is expected behavior. If you want to force inclusion of specific foods, add a minimum bound on their decision variables.
</details>
