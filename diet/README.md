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

- **Model**: two concepts (`Food`, `Nutrient`), a `Scenario` concept, per-food decision variables, nutrient-bound constraints, and a cost-minimizing objective — all in `model/__init__.py`, which `rai models deploy --path model` deploys to your Snowflake account, where each refresh runs the solve.
- **Query**: `queries/diet_plan.py`, which prints the report from the deployed model.
- **Runbook**: `runbook.md` — a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the script itself.
- **Sample data**: `data/foods.csv` (foods with cost and per-nutrient content) and `data/nutrients.csv` (nutrient min/max bounds).
- **Outputs**: per-scenario termination status, objective cost, and a table of the foods (and amounts) in each least-cost basket, printed to stdout.

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- The one-time model deployment setup on that account, done by an account administrator: follow [Set up model deployment](https://private.relational.ai/early-access/model-deploy-setup) through **Governed setup**, **PAT authentication**, and steps 1-2 of **Additional setup for the prescriptive reasoner** (the Quickstart covers this template's own schema). It gives you a model role, a programmatic access token (PAT) stored as a secret, an external access integration, a PAT user, and a warehouse.
- A Snowflake user that holds the model role.

### Tools
- Python >= 3.10

## Quickstart

Before you start, install Python 3.10 or later and complete the access prerequisites above: a Snowflake account with the RAI Native App, the one-time model deployment setup, and a Snowflake user that holds the model role.

Before the first deploy, create this template's internal schema as the model role, and have an administrator grant the RAI Native App caller access to it. The internal schema holds only this model's objects, so the grants cover all of it, including the solver's result tables that the deploy creates:

```sql
-- as the model role
CREATE SCHEMA IF NOT EXISTS <DB>.DIET_META;

-- as an administrator
GRANT CALLER USAGE ON DATABASE <DB> TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON SCHEMA <DB>.DIET_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON WAREHOUSE <PAT_WAREHOUSE> TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL TABLES IN SCHEMA <DB>.DIET_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL DYNAMIC TABLES IN SCHEMA <DB>.DIET_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL VIEWS IN SCHEMA <DB>.DIET_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER INSERT, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA <DB>.DIET_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER CREATE TABLE, CREATE STAGE ON SCHEMA <DB>.DIET_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER READ, WRITE ON ALL STAGES IN SCHEMA <DB>.DIET_META TO APPLICATION <RAI_APP_NAME>;
```

Use this sequence to deploy the model and query it:

1. **Download the template**

   [Download the ZIP](https://docs.relational.ai/templates/zips/v1/diet.zip), unzip it, and enter the template directory:

   ```bash
   unzip diet.zip
   cd diet
   ```

2. **Create a Python environment**

   Create and activate a virtual environment, then update pip:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   ```

3. **Install the template**

   Install the dependencies pinned in `pyproject.toml`:

   ```bash
   python -m pip install .
   ```

4. **Configure your project**

   Use the configuration builder in [Install and run PyRel](https://docs.relational.ai/get-started/install-and-run-pyrel/#configure-your-project) to create `raiconfig.yaml` in the template directory and verify your connection.

   Set the connection `role` to the model role, then add the prescriptive reasoner and a `deployment` section. Give each template its own schema pair so two deployed templates never share one:

   ```yaml
   reasoners:
     prescriptive:
       name: diet_solver            # created on first deploy if it doesn't exist
   deployment:
     role: <MODEL_ROLE>
     public_schema: <DB>.DIET               # published views and tables
     identity:
       internal_schema: <DB>.DIET_META      # solver inputs, results, refresh procedures
     schedules:
       standard:
         interval_s: 0              # refresh only on deploy or on demand
     schedule: standard
     pat_secret: <PAT_SECRET>       # these four come from the setup page
     pat_eai: <PAT_EAI>
     pat_user: <PAT_USER>
     pat_warehouse: <PAT_WAREHOUSE>
   ```

5. **Deploy the model**

   Deploy the model in `model/` to the schemas in `raiconfig.yaml`:

   ```bash
   rai models deploy --path model
   ```

   The deploy creates the public schema `<DB>.DIET` if it doesn't exist and waits for the model's first refresh, which runs the solve. Each refresh of the deployed model runs the solve again.

   Deploying again without changing the model applies no updates and does not solve again. A change to the model or to `problem.configure(...)` redeploys, and the redeploy's refresh solves.

6. **Query the results**

   Print the report from the deployed model:

   ```bash
   python -m queries.diet_plan
   ```

   ```text
   Solve result:
   • status: OPTIMAL
   • objective: 35.486583333

   Diet plan per scenario:
            scenario       food  cost    amount
   0        baseline  hamburger  2.49  0.604514
   1        baseline   icecream  1.59  2.591319
   2        baseline       milk  0.89  6.970139
   3  scaling_120pct  hamburger  2.49  0.725417
   4  scaling_120pct   icecream  1.59  3.109583
   5  scaling_120pct       milk  0.89  8.364167
   6   scaling_80pct  hamburger  2.49  0.483611
   7   scaling_80pct   icecream  1.59  2.073056
   8   scaling_80pct       milk  0.89  5.576111
   ```

   The formulation printed above the solve result is trimmed here. The report checks the solve's termination status and stops unless it is `OPTIMAL`. The least-cost basket is the same three foods in every scenario, scaled with the requirements, for a per-scenario cost of $9.46 / $11.83 / $14.19 at 0.8 / 1.0 / 1.2 times the bounds. See `runbook.md` for the step-by-step walkthrough.

   To solve again without changing the model, refresh the deployed model, then run the query again:

   ```sql
   CALL <DB>.DIET_META._INTERNAL_REFRESH_MODEL('standard', NULL);
   ```

7. **Tear down the deployment**

   Preview what the teardown removes, then remove it:

   ```bash
   rai models teardown
   rai models teardown --force
   ```

   The first command lists the model's objects without dropping anything; the second drops them and keeps the two schemas.

## Template structure

```text
.
├── README.md          # this file
├── runbook.md         # step-by-step analyst walkthrough
├── pyproject.toml     # dependencies
├── model/
│   └── __init__.py    # the deployed model (concepts, constraints, scenarios, solve)
├── queries/
│   └── diet_plan.py   # report from the deployed model
└── data/
    ├── foods.csv      # foods with cost and per-nutrient content
    └── nutrients.csv  # nutrient min/max bounds
```

**Start here**: deploy with `rai models deploy --path model` and run `python -m queries.diet_plan` for the full model and scenario solve end to end, or follow `runbook.md` to rebuild it step by step.

## Sample data

The bundled data is small and illustrative — a handful of foods and four nutrients, sized to teach the linear-program formulation, not to represent a clinically complete diet.

- **`data/foods.csv`** — one row per food, with a `cost` per serving and one column per nutrient (`calories`, `protein`, `fat`, `sodium`) giving that food's content per serving. Each food's nutrient columns must match the nutrient `name`s in `nutrients.csv`.
- **`data/nutrients.csv`** — one row per nutrient, with `min` and `max` daily-intake bounds. The scenario scaling factor multiplies these bounds up and down.

## Model overview

The model is small and self-contained: two source concepts plus a `Scenario` concept that parameterizes the solve.

- **Key entities**: `Food` — a food with a per-serving cost and a per-nutrient content, carrying a continuous decision variable for the amount to include; `Nutrient` — a nutrient with minimum and maximum daily-intake bounds (the constraint bounds, scaled per scenario); and `Scenario` — a requirement-scaling case that scales every nutrient bound by its factor, with all scenarios solving together in one solve.
- **Primary identifiers**: `Food.name` and `Nutrient.name` (both strings); `Scenario.scenario_name` (string).
- **Important invariants**: nutrient `min` and `max` bounds are non-negative and `min <= max`; each food's decision amount is non-negative (`lower=0`); each food's per-nutrient content is keyed by a nutrient that exists in `nutrients.csv`.

For the full concept and property definitions, see `model/__init__.py`; `runbook.md` builds them step by step with the RAI skills.

## How it works

The model reads two source tables, adds a scenario axis, and hands a single parameterized linear program to the prescriptive solver:

```text
foods.csv + nutrients.csv → concepts → decision variables → constraints + objective → multi-scenario solve → per-scenario baskets
```

1. **Define concepts and map data.** `Nutrient` carries min/max daily-intake bounds; `Food` carries a per-serving cost and a per-nutrient content (a ternary `contains` property linking each food to a nutrient quantity).

2. **Decision variables.** Each food gets a continuous, non-negative decision variable — the amount to include in the diet — created per scenario so all cases share one formulation.

3. **Constraints and objective.** For each nutrient, total intake across foods (quantity times amount, summed) must fall between the scenario-scaled min and max bounds. The objective minimizes total cost (cost times amount, summed over foods).

4. **Scenario analysis.** A first-class `Scenario` concept scales every nutrient bound by a factor (0.8 / 1.0 / 1.2 here), so tighter and looser requirements solve together in a single solve and their costs are directly comparable.

The prescriptive decision variable appears in the model schema alongside the source-data properties — a unified view of everything the model knows, including variables added by `solve_for()`. See `model/__init__.py` for the implementation and `runbook.md` for the skill-driven reproduction.

## Customize this template

Focus on the first changes most users will make.

### Use your own data

- Replace `data/foods.csv` and `data/nutrients.csv` with your own; keep the column names described in *Sample data* above. Each food's nutrient columns must match the nutrient `name`s in `nutrients.csv` — the model reads one food column per nutrient row.
- For Snowflake-backed runs, swap the `read_csv(...)` calls for `model.data(snowflake_table)` calls.

### Tune parameters

- Edit the scenario rows in `model/__init__.py` (the `("scaling_80pct", 0.8)`, `("baseline", 1.0)`, `("scaling_120pct", 1.2)` tuples) to test different scaling factors, or add rows for finer resolution.
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
<summary>Connection errors</summary>

Ensure your Snowflake credentials are configured correctly and that the RAI Native App is installed on your account. Re-create `raiconfig.yaml` with the configuration builder (Quickstart step 4) and verify the connection settings.
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
