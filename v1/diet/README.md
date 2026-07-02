---
title: "Diet Optimization"
description: "Select foods to satisfy nutritional requirements at minimum cost."
featured: false
experience_level: beginner
industry: "Healthcare & Life Sciences"
reasoning_types:
  - Prescriptive
tags:
  - Linear Programming
  - Cost Minimization
  - Scenario Analysis
---

## What this template is for

Choosing a balanced diet that meets nutritional requirements while staying within a budget is a classic optimization problem. Given a set of foods with known costs and nutrient contents, and a set of nutrients with minimum and maximum daily intake bounds, the goal is to find the cheapest combination of foods that satisfies all nutritional constraints. It also shows how the same model answers a "what if" question — how cost moves as requirements tighten or loosen — without re-modeling anything.

**The template uses prescriptive reasoning to formulate the diet problem as a linear program and solve several requirement scenarios in a single solve.**

## Who this is for

- Data scientists and analysts learning prescriptive optimization with RelationalAI
- Operations researchers looking for a clean LP formulation example
- Anyone interested in nutritional planning or cost minimization problems
- Beginners who want to understand scenario analysis in optimization

## What you'll build

- A least-cost diet plan — the amount of each food that meets every nutrient bound at minimum total cost — produced by **prescriptive reasoning** (a linear program).
- Nutritional constraints holding total intake within minimum and maximum daily bounds for calories, protein, fat, and sodium.
- A scenario comparison showing how least-cost changes as requirements scale, built with a first-class `Scenario` concept so all cases solve at once.

Built using **prescriptive reasoning** (linear programming with continuous decision variables and a `Scenario` concept for multi-case solves).

## What's included

- **Model**: two concepts (`Food`, `Nutrient`), a `Scenario` concept, per-food decision variables, nutrient-bound constraints, and a cost-minimizing objective — all in `diet.py`.
- **Runner**: `diet.py`, a single Python script that runs end-to-end against a Snowflake-connected RAI account.
- **Sample data**: `data/foods.csv` (foods with cost and per-nutrient content) and `data/nutrients.csv` (nutrient min/max bounds).
- **Outputs**: per-scenario termination status, objective cost, and a table of the foods (and amounts) in each least-cost basket, printed to stdout.

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

6. Expected output — a few lines confirm a successful run:

   ```text
   Solve result:
   • status: OPTIMAL
   • objective: 35.49

   Diet plan per scenario (0.8 / 1.0 / 1.2 demand): the same baseline
   basket — hamburger + icecream + milk — scaled per scenario, for a
   per-scenario cost of $9.46 / $11.83 / $14.19.
   ```

   The full per-scenario diet plan prints above; see `runbook.md` for the complete log.

## Template structure

```text
.
├── README.md          # this file
├── runbook.md         # step-by-step analyst walkthrough
├── pyproject.toml     # dependencies
├── diet.py            # main script (model, constraints, scenarios, solve)
└── data/
    ├── foods.csv      # foods with cost and per-nutrient content
    └── nutrients.csv  # nutrient min/max bounds
```

**Start here**: run `python diet.py` for the full model and scenario solve end to end, or follow `runbook.md` to rebuild it step by step.

## Sample data

The bundled data is small and illustrative — a handful of foods and four nutrients, sized to teach the linear-program formulation, not to represent a clinically complete diet.

- **`data/foods.csv`** — one row per food, with a `cost` per serving and one column per nutrient (`calories`, `protein`, `fat`, `sodium`) giving that food's content per serving. Each food's nutrient columns must match the nutrient `name`s in `nutrients.csv`.
- **`data/nutrients.csv`** — one row per nutrient, with `min` and `max` daily-intake bounds. The scenario scaling factor multiplies these bounds up and down.

## Model overview

The model is small and self-contained: two source concepts plus a `Scenario` concept that parameterizes the solve.

- **Key entities**: `Food`, `Nutrient`, and `Scenario`.
- **Primary identifiers**: `Food.name` and `Nutrient.name` (both strings); `Scenario.scenario_name` (string).
- **Important invariants**: nutrient `min` and `max` bounds are non-negative and `min <= max`; each food's decision amount is non-negative (`lower=0`); each food's per-nutrient content is keyed by a nutrient that exists in `nutrients.csv`.

### Concepts

**`Nutrient`** — a nutrient with a minimum and maximum daily-intake bound. The constraint bounds are read from these, scaled per scenario.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `name` | String | Yes | Nutrient name from `data/nutrients.csv` |
| `min` | Float | No | Minimum daily intake |
| `max` | Float | No | Maximum daily intake |

**`Food`** — a food with a per-serving cost and a per-nutrient content. Each food carries a continuous decision variable for the amount to include.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `name` | String | Yes | Food name from `data/foods.csv` |
| `cost` | Float | No | Cost per serving |
| `contains` | Relationship | — | `Food contains Nutrient in qty` — per-nutrient content (ternary) |
| `x_amount` | Float | No | Decision variable: amount of this food per `Scenario` |

**`Scenario`** — a requirement-scaling case. Each scenario scales every nutrient bound by its factor; all scenarios solve together in one solve.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `scenario_name` | String | Yes | Scenario label (`scaling_80pct` / `baseline` / `scaling_120pct`) |
| `nutrient_scaling` | Float | No | Factor applied to every nutrient bound |

### Relationships

- `Food.contains(Nutrient, qty)` — the amount of each nutrient in one serving of a food; the nutrient-bound constraint sums `qty * amount` across foods per nutrient.

## How it works

### 1. Define concepts and map data

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
problem.solve_for(Food.x_amount, name=Food.name, lower=0, populate=False)
```

### 3. Constraints and objective

Nutritional constraints ensure total intake from all foods falls within bounds for each nutrient. The objective minimizes total food cost:

```python
nutrient_qty = Float.ref()
nutrient_total = sum(nutrient_qty * Food.x_amount).where(Food.contains(Nutrient, nutrient_qty)).per(Nutrient)
problem.satisfy(model.require(
    nutrient_total >= Nutrient.min * scenario_value,
    nutrient_total <= Nutrient.max * scenario_value
))
problem.minimize(sum(Food.cost * Food.x_amount))
```

### 4. Scenario analysis

The template solves three scenarios by scaling nutritional requirements to 80%, 100%, and 120% of their base values, demonstrating how tighter or looser requirements affect total cost.

### 5. Inspect the model schema

`relationalai.semantics.inspect` (available in `relationalai>=1.0.14`) surfaces a typed view of the registered concepts, properties, relationships, and data sources. It's handy for sanity-checking a model before handing it to the solver:

```python
from relationalai.semantics import inspect

print(inspect.schema(model))
```

Excerpt of the user-declared part of the output:

```text
Model: diet
===========

  Nutrient
    Identity:
      name: String
    Properties:
      min: Float
      max: Float

  Food
    Identity:
      name: String
    Properties:
      cost: Float
      contains(Nutrient) -> Float
      x_amount(Scenario) -> Float

  Scenario
    Identity:
      scenario_name: String
    Properties:
      nutrient_scaling: Float
```

Notice that the prescriptive decision variable (`Food.x_amount(Scenario) -> Float`) appears alongside the source-data properties -- the schema is a unified view of everything the model knows, including variables added by `solve_for()`.

After calling `Problem(...)` and `problem.solve_for / satisfy / minimize`, the prescriptive reasoner also registers root concepts named `Variable`, `Expression`, `Constraint`, and `Objective` (plus per-solve `Variable_<id>` subconcepts). They appear below the user-declared concepts in the full output; filter them out with a list-based check if you want a user-facing view (see the `machine_maintenance` template for the recipe).

## Customize this template

Focus on the first changes most users will make.

### Use your own data

- Replace `data/foods.csv` and `data/nutrients.csv` with your own; keep the column names described in *Sample data* above. Each food's nutrient columns must match the nutrient `name`s in `nutrients.csv` — the model reads one food column per nutrient row.
- For Snowflake-backed runs, swap the `read_csv(...)` calls for `model.data(snowflake_table)` calls.

### Tune parameters

- Edit the scenario rows in `diet.py` (the `("scaling_80pct", 0.8)`, `("baseline", 1.0)`, `("scaling_120pct", 1.2)` tuples) to test different scaling factors, or add rows for finer resolution.
- Adjust the solver time limit (`time_limit_sec`) if you scale up to many foods and nutrients.

### Extend the model

- Add dietary preferences: introduce upper bounds on specific foods (for example, limiting red meat), or add binary variables to model food inclusion/exclusion.
- Weight the objective: add a secondary term to penalize undesirable foods alongside cost minimization.
- Add a second scenario axis (for example, budget caps) as another `Scenario`-style concept.

### Scale up / productionize

- Pin `relationalai` and schedule the run as a pipeline step for reproducible, deterministic re-runs.
- Size the prescriptive engine up if the food and nutrient counts grow the linear program substantially.

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

## Learn more

### Core concepts

- [PyRel v1 query language](https://docs.relational.ai/) — `model.where(...)` / `model.select(...)` / `.per(...)` and result extraction.
- [Concepts and properties](https://docs.relational.ai/) — modeling entities like `Food` and `Nutrient` with typed properties.

### Reasoner reference

- [Prescriptive reasoner](https://docs.relational.ai/) — `Problem` API, decision variables, constraints, and objectives.
- [Scenario modeling](https://docs.relational.ai/) — parameterizing one solve across cases with a `Scenario` concept.

### CLI / SDK guides

- [RelationalAI setup](https://docs.relational.ai/) — `rai init`, profiles, and `raiconfig.yaml`.

## Support

- File issues at the RelationalAI templates repository.
