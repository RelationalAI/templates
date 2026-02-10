---
title: "Diet Optimization"
description: "Select foods to satisfy daily nutritional requirements at minimum cost."
featured: false
experience_level: beginner
industry: "Healthcare"
reasoning_types:
  - Prescriptive
tags:
  - Allocation
  - LP
  - Nutrition
---

# Diet Optimization

> [!WARNING]
> This template uses the early access `relational.semantics` API in version `0.13` of the `relationalai` Python package.

## What this template is for

Meal planning services, hospitals, and institutional food services need to design menus that meet nutritional requirements without overspending.
This template models selecting from a small set of foods to satisfy daily bounds on calories, protein, fat, and sodium at minimum cost.

This is the classic “diet problem”, one of the earliest practical applications of linear programming originally formulated by economist George Stigler in 1945.
This template uses RelationalAI's **prescriptive reasoning (optimization)** capabilities to find the optimal food combination that meets all nutritional constraints at the lowest cost.

Prescriptive reasoning helps you:

- **Reduce cost** while still meeting nutrition guidelines.
- **Guarantee compliance** with min/max nutrient bounds.
- **Scale decision-making** from a handful of foods to large catalogs.

## Who this is for

- You want a small, end-to-end example of **prescriptive reasoning (optimization)** with RelationalAI.
- You’re comfortable with basic Python and linear optimization concepts.

## What you’ll build

- A semantic model of foods and nutrients using concepts and properties.
- A linear program that chooses non-negative servings per food.
- Nutrient bound constraints and a cost-minimization objective.
- A solver that uses the **HiGHS** backend to print a readable diet plan.

## What’s included

- **Model + solve script**: `diet.py`
- **Sample data**: `data/foods.csv`, `data/nutrients.csv`

## Prerequisites

### Access

- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools

- Python >= 3.10

## Quickstart

Follow these steps to run the template with the included sample data.

1. **Create and activate a virtual environment**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   ```

2. **Install dependencies**

   ```bash
   python -m pip install .
   ```

3. **Configure Snowflake connection and RAI profile**

   ```bash
   rai init
   ```

4. **Run the template**

   ```bash
   python diet.py
   ```

5. **Expected output**

   ```text
   Status: OPTIMAL
   Minimum cost: $11.83

   Optimal diet:
        name    amount
   hamburger  0.604514
    icecream  2.591319
        milk  6.970139
   ```

## Repository structure

```text
.
├─ README.md
├─ pyproject.toml
├─ diet.py
└─ data/
   ├─ foods.csv
   └─ nutrients.csv
```

**Start here**: `diet.py`

## Sample data

Data files are in `data/`.

### `nutrients.csv`

Defines nutrient bounds (min/max) for a single day.

| Column | Meaning |
| --- | --- |
| `name` | Nutrient name (e.g., `calories`, `protein`) |
| `min` | Minimum daily requirement |
| `max` | Maximum daily allowance |

### `foods.csv`

Lists foods, their cost, and nutrient quantities per serving.
Each nutrient in `nutrients.csv.name` is also a column in this file.

| Column | Meaning |
| --- | --- |
| `name` | Food name |
| `cost` | Cost per serving |
| `<nutrient columns>` | Quantity per serving (e.g., `calories`, `protein`, `fat`, `sodium`) |

## Model overview

The semantic model for this template is built around two concepts and one relationship.

### `Nutrient`

A nutrient with minimum and maximum daily bounds.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `name` | string | Yes | Loaded as the key from `data/nutrients.csv` |
| `min` | float | No | Minimum daily requirement |
| `max` | float | No | Maximum daily allowance |

### `Food`

A food item with a cost, plus a decision variable (`amount`) chosen by the solver.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `name` | string | Yes | Loaded from `data/foods.csv.name` and used for output labeling |
| `cost` | float | No | Cost per serving |
| `amount` | float | No | Continuous decision variable (servings, $\ge 0$) |

### Relationships

This template uses a relationship (not just properties) to represent per-food nutrient quantities.

| Relationship | Schema (reading string fields) | Notes |
| --- | --- | --- |
| `Food.nutrients` | `{Food} contains {qty:float} of {Nutrient}` | Quantity per serving loaded from the nutrient columns in `data/foods.csv` |

## How it works

This section walks through the highlights in `diet.py`.

### Configure inputs and create the model

```python
from pathlib import Path

import pandas
from pandas import read_csv

from relationalai.semantics import Model, data, define, require, select, sum
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

# --------------------------------------------------
# Configure inputs and create the model
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"

# Disable pandas inference of string types. This ensures that string columns
# in the CSVs are loaded as object dtype. This is only required when using
# relationalai versions prior to v1.0.
pandas.options.future.infer_string = False

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

# Create a Semantics model container.
model = Model("diet", config=globals().get("config", None), use_lqp=False)
```

### Define concepts and load CSV data

```python
# Nutrient concept: represents a nutrient with minimum and maximum daily requirements.
Nutrient = model.Concept("Nutrient")
Nutrient.name = model.Property("{Nutrient} is named {name:string}")
Nutrient.min = model.Property("{Nutrient} has minimum daily requirement {min:float}")
Nutrient.max = model.Property("{Nutrient} has maximum daily requirement {max:float}")

nutrient_csv = read_csv(DATA_DIR / "nutrients.csv")
data(nutrient_csv).into(Nutrient, keys=["name"])

# Food concept: foods have a cost and contain nutrients in some quantity.
Food = model.Concept("Food")
Food.nutrients = model.Relationship("{Food} contains {qty:float} of {Nutrient}")
Food.cost = model.Property("{Food} costs {cost:float}")

food_csv = read_csv(DATA_DIR / "foods.csv")
food_data = data(food_csv)

# Create one Food entity per row in the food data and define its cost.
food = Food.new(name=food_data.name)
define(food, food.cost(food_data.cost))

# Define nutrient quantities for each food by iterating the nutrient columns.
for nutrient_name in nutrient_csv.name:
    define(Food.nutrients(food, food_data[nutrient_name], Nutrient)).where(
        Nutrient.name == nutrient_name
    )
```

### Define decision variables, constraints, and objective

```python
# Create a continuous optimization model.
s = SolverModel(model, "cont")

# Decision Variable: amount of each food (continuous, non-negative)
Food.amount = model.Property("{Food} has {amount:float}")
s.solve_for(Food.amount, name=Food.name, lower=0)

# Calculate total quantity of each nutrient across all foods: sum(qty * amount) per nutrient.
nutrient_total = sum(
    Food.nutrients["qty"] * Food.amount
).where(
    Food.nutrients == Nutrient
).per(Nutrient)

# Constraint: nutrient totals must be within specified bounds.
nutrient_bounds = require(
    nutrient_total >= Nutrient.min,
    nutrient_total <= Nutrient.max
)
s.satisfy(nutrient_bounds)

# Objective: minimize total cost
total_cost = sum(Food.cost * Food.amount)
s.minimize(total_cost)
```

### Solve and print results

```python
# Solve the model with a time limit of 60 seconds using the HiGHS solver.
solver = Solver("highs")
s.solve(solver, time_limit_sec=60)

print(f"Status: {s.termination_status}")
print(f"Minimum cost: ${s.objective_value:.2f}")

# Select the foods with non-trivial amounts in the optimal solution.
diet_plan = select(Food.name, Food.amount).where(Food.amount > 0.001).to_df()

print("\nOptimal diet:")
print(diet_plan.to_string(index=False))
```

## Customize this template

Here are some ideas for how to customize and extend this template to fit your specific use case.

### Use your own data

- Replace the CSVs in `data/` with your own, keeping the same column names (or update the loading logic in `diet.py`).
- Ensure `foods.csv` includes a column for every nutrient listed in `nutrients.csv.name`.

### Tune parameters

- Tighten or relax nutritional bounds by editing `data/nutrients.csv`.
- Add new nutrients by adding rows to `data/nutrients.csv` and adding matching columns to `data/foods.csv`.

### Extend the model

- Add constraints like maximum servings per food or food category requirements.
- Add an “integer servings” variant by making `Food.amount` an integer variable (and adjusting the model type if needed).

### Scale up and productionize

- Replace CSV ingestion with Snowflake sources.
- Write the resulting diet plan back to Snowflake after solving.

## Troubleshooting

<details>
  <summary>Why does authentication/configuration fail?</summary>


- Run `rai init` to create/update `raiconfig.toml`.
- If you have multiple profiles, set `RAI_PROFILE` or switch profiles in your config.

</details>

<details>
  <summary>Why does the script fail to connect to the RAI Native App?</summary>


- Verify the Snowflake account/role/warehouse and `rai_app_name` are correct in `raiconfig.toml`.
- Ensure the RAI Native App is installed and you have access.

</details>

<details>
  <summary>Why do I get <code>Status: INFEASIBLE</code>?</summary>


- Check for impossible bounds (e.g., `min > max` for a nutrient).
- Confirm that the foods collectively can meet each nutrient’s minimum without violating other maximums.

</details>

<details>
  <summary>Why is the output diet empty?</summary>


- The script filters foods with `Food.amount > 0.001`. If all values are tiny, inspect nutrient bounds and costs.
- Confirm the CSVs were read correctly and contain rows.

</details>

## Next steps

- Add more nutrients, foods, and additional business constraints (e.g., variety).
- Compare solutions under different nutritional policies by changing `data/nutrients.csv`.
