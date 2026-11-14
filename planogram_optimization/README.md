---
title: "Planogram Optimization"
description: "Decide integer facing counts per SKU to maximize predicted weekly demand under shelf capacity and category cardinality limits, where per-(SKU, facing_count) demand comes from a regression model."
featured: false
private: false
experience_level: intermediate
industry: "Retail & Consumer"
reasoning_types:
  - Predictive
  - Prescriptive
tags:
  - constraint-programming
  - predict-then-optimize
  - element-table-lookup
  - retail
  - shelf-space-allocation
---

## What this template is for

Retailers running grocery, mass-merchandise, drug, and CPG categories decide how many *facings* (front-row product positions) to allocate per SKU on each shelf. More facings of a hot product lift its weekly sales; more facings of a slow mover wastes shelf length that could carry a faster competitor. The right answer differs by category, by SKU within a category, and by the diminishing-returns curve each SKU exhibits as you give it more space.

This template uses **Predictive** + **Prescriptive** reasoning: it solves the per-shelf facing-count allocation as a constraint satisfaction model where the per-(SKU, facing_count) expected weekly demand is a *predictive output*. The hand-off from the predictive arm into the CSP is the canonical **element-style decision-indexed table lookup**: the CSP picks an integer `Sku.facings`, and `Sku.realized_demand` is bound -- via an `implies` cascade -- to the `PredictedDemand.demand_units` row whose `facings_count` matches the chosen value. No bilinearity, no big-M, no SOS2.

The same pattern applies to any predict-then-optimize problem where the prediction is a per-decision-value lookup table: workforce demand by staffing level, conversion rate by ad-spend bucket, throughput by line speed.

> [!IMPORTANT]
> The bundled model ships with a vendored `predicted_demand_table.csv` -- a stand-in for the output of any per-(SKU, k) demand regressor -- so the predict->CSP hand-off pattern can be inspected and run without a training arm. Wiring in a real regressor is documented under "Customize this template"; the CSP shape is unchanged.

## Who this is for

- Retail and CPG analysts allocating shelf space across SKUs and categories
- Operations researchers exploring the predict-then-optimize pattern with decision-indexed table lookups
- Data scientists wiring regression-based demand prediction into integer optimization
- Software developers seeking a clean canonical example of predictive output as a decision-indexed lookup

## What you'll build

- A constraint model with one integer decision per SKU (`facings` in `[0, max_facings]`) plus two derived integer variables pinned by ICs (`realized_demand` via the lookup, `active` via a linear-inequality coupling)
- An element-style decision-indexed table lookup binding `realized_demand` to the matching `PredictedDemand` row via an `implies` cascade
- Shelf-length capacity (`sum(Sku.facings * Sku.width_cm).per(Shelf) <= Shelf.length_cm`) and per-category cardinality (`sum(Sku.active).per(Category)` in `[min_skus_active, max_skus_active]`)
- A linear `sum(realized_demand)` objective the CSP maximizes
- A post-solve check in the report: a Python dict lookup confirming `(sku_id, facings) -> demand_units` matches the deployed demand table, and the solver status is `OPTIMAL`

## What's included

- `model/__init__.py` -- ontology, decisions, constraints, and solver configuration; `rai models deploy --path model` deploys it
- `queries/facings_plan.py` -- prints the report from the deployed model
- **Runbook**: `runbook.md` -- a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the script itself.
- `data/skus.csv` -- 18 SKUs across 4 categories (snacks, beverages, candy, household_paper) with width, max-facings, and pre-assigned shelf; `sku_id` must be unique, `category` must match a `categories.csv` name, and `assigned_shelf_id` must reference a `shelves.csv` id. The `brand` column is loaded but not used by the bundled CSP -- it is reserved for the brand-block contiguity customization described under "Customize this template"
- `data/shelves.csv` -- 4 shelves (Top Eye-Level 100cm, Upper-Middle 80cm, Lower-Middle 80cm, Bottom 90cm); `id` must be unique and is the foreign-key target of `skus.assigned_shelf_id`
- `data/categories.csv` -- per-category min/max active SKU bounds; `name` must be unique and is the foreign-key target of `skus.category`
- `data/predicted_demand_table.csv` -- vendored regression output: one row per `(sku_id, facings_count)` for `k in {0, 1, ..., sku.max_facings}` with concave per-SKU demand curves; the `k=0` row is `demand_units=0` so the lookup is total over the decision domain
- `pyproject.toml` -- Python package configuration

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- The one-time model deployment setup on that account, done by an account administrator: follow [Set up model deployment](https://private.relational.ai/early-access/model-deploy-setup) through **Governed setup**, **PAT authentication**, and steps 1-2 of **Additional setup for the prescriptive reasoner** (the Quickstart covers this template's own schema). It gives you a model role, a programmatic access token (PAT) stored as a secret, an external access integration, a PAT user, and a warehouse.
- A Snowflake user that holds the model role.

### Tools
- Python >= 3.10
- RelationalAI Python SDK (`relationalai == 2.1.1`)

## Quickstart

Before you start, install Python 3.10 or later and complete the access prerequisites above: a Snowflake account with the RAI Native App, the one-time model deployment setup, and a Snowflake user that holds the model role.

Before the first deploy, create this template's internal schema as the model role, and have an administrator grant the RAI Native App caller access to it. The internal schema holds only this model's objects, so the grants cover all of it, including the solver's result tables that the deploy creates:

```sql
-- as the model role
CREATE SCHEMA IF NOT EXISTS <DB>.PLANOGRAM_OPTIMIZATION_META;

-- as an administrator
GRANT CALLER USAGE ON DATABASE <DB> TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON SCHEMA <DB>.PLANOGRAM_OPTIMIZATION_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON WAREHOUSE <PAT_WAREHOUSE> TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL TABLES IN SCHEMA <DB>.PLANOGRAM_OPTIMIZATION_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL DYNAMIC TABLES IN SCHEMA <DB>.PLANOGRAM_OPTIMIZATION_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL VIEWS IN SCHEMA <DB>.PLANOGRAM_OPTIMIZATION_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER INSERT, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA <DB>.PLANOGRAM_OPTIMIZATION_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER CREATE TABLE, CREATE STAGE ON SCHEMA <DB>.PLANOGRAM_OPTIMIZATION_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER READ, WRITE ON ALL STAGES IN SCHEMA <DB>.PLANOGRAM_OPTIMIZATION_META TO APPLICATION <RAI_APP_NAME>;
```

Use this sequence to deploy the model and query it:

1. **Download the template**

   [Download the ZIP](https://docs.relational.ai/templates/zips/v1/planogram_optimization.zip), unzip it, and enter the template directory:

   ```bash
   unzip planogram_optimization.zip
   cd planogram_optimization
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
       name: planogram_optimization_solver            # created on first deploy if it doesn't exist
   deployment:
     role: <MODEL_ROLE>
     public_schema: <DB>.PLANOGRAM_OPTIMIZATION               # published views and tables
     identity:
       internal_schema: <DB>.PLANOGRAM_OPTIMIZATION_META      # solver inputs, results, refresh procedures
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

   The deploy creates the public schema named in `raiconfig.yaml` if it doesn't exist and waits for the model's first refresh, which runs the solve. Each refresh of the deployed model runs the solve again.

   Deploying again without changing the model applies no updates and does not solve again. A change to the model or to `problem.configure(...)` redeploys, and the redeploy's refresh solves.

6. **Query the results**

   Print the report from the deployed model:

   ```bash
   python -m queries.facings_plan
   ```

   ```text
   Solve result:
   • status: OPTIMAL
   • objective: 1656

   Optimal facings per SKU:
       id               name         category                shelf  facings  realized_demand
   0    1         Cookie Box           snacks  Top Eye-Level Shelf        2               82
   1    2        Granola Bar           snacks  Top Eye-Level Shelf        3              147
   2    3          Trail Mix           snacks  Top Eye-Level Shelf        2               66
   3    4     Tortilla Chips           snacks   Upper-Middle Shelf        2              140
   4    5        Popcorn Bag           snacks   Upper-Middle Shelf        3               94
   5    6          Cola 12oz        beverages   Lower-Middle Shelf        4              212
   6    7    Lemon Soda 12oz        beverages   Lower-Middle Shelf        3              136
   7    8    Sparkling Water        beverages   Lower-Middle Shelf        2               58
   8    9      Bottled Water        beverages   Lower-Middle Shelf        3              116
   9   10       Energy Drink        beverages   Upper-Middle Shelf        3              158
   10  11         Gummy Pack            candy  Top Eye-Level Shelf        3               74
   11  12      Chocolate Bar            candy  Top Eye-Level Shelf        3              116
   12  13          Mint Roll            candy         Bottom Shelf        0                0
   13  14    Caramel Squares            candy         Bottom Shelf        2               50
   14  15   Paper Towels 6pk  household_paper         Bottom Shelf        0                0
   15  16  Toilet Tissue 4pk  household_paper         Bottom Shelf        2               99
   16  17  Facial Tissue Box  household_paper         Bottom Shelf        2               58
   17  18      Napkins 200ct  household_paper         Bottom Shelf        2               50

   Shelf utilization:
      id                 name  used_cm  length_cm
   0   1  Top Eye-Level Shelf       98        100
   1   2   Upper-Middle Shelf       79         80
   2   3   Lower-Middle Shelf       77         80
   3   4         Bottom Shelf       90         90

   Category active counts:
                 name  active_skus  min_skus_active  max_skus_active
   0        beverages            5                3                5
   1            candy            3                2                3
   2  household_paper            3                2                3
   3           snacks            5                3                5
   ```

   The formulation printed first (about 30 lines) is omitted here. The solver maximizes total predicted weekly demand, and the exact selection may vary across solver versions if several allocations reach the same optimal objective. The report stops unless the solve is OPTIMAL and each SKU's realized demand matches the demand table at its chosen facings.

   Total weekly demand of `1656` units, 16 of 18 SKUs active. Two SKUs go inactive because the candy and household_paper categories each have 4 SKUs but `max_skus_active=3`: Mint Roll loses the candy cap (lowest predicted demand at every k), Paper Towels 6pk loses the household_paper cap (lowest predicted demand-per-cm). The bottom shelf is fully binding (90/90cm); the other three are within 1-3cm of capacity.

   To solve again without changing the model, refresh the deployed model, then run the query again:

   ```sql
   CALL <DB>.PLANOGRAM_OPTIMIZATION_META._INTERNAL_REFRESH_MODEL('standard', NULL);
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
├── README.md
├── pyproject.toml
├── model/
│   └── __init__.py
├── queries/
│   └── facings_plan.py
└── data/
    ├── skus.csv
    ├── shelves.csv
    ├── categories.csv
    └── predicted_demand_table.csv
```

**Start here**: deploy with `rai models deploy --path model` and run `python -m queries.facings_plan` for the full predict-then-optimize run end to end — the deploy validates the data, binds each SKU's demand from the prediction table, and solves the facing-count CSP, and the query prints the allocation — or follow `runbook.md` to reproduce it step by step with the RAI skills.

## Sample data

The bundled CSVs are illustrative, fully synthetic demo data sized so the model runs in seconds. The `predicted_demand_table.csv` is a vendored stand-in for the output of any per-(SKU, facings-count) demand regressor, so the predict-to-CSP hand-off can be inspected and run without a training arm. A pre-solve pass validates unique keys, category and shelf foreign keys, and that the demand table is complete over every SKU's `[0, max_facings]` range with `demand_units = 0` at `facings_count = 0`.

- **`skus.csv`** (18 rows) — SKUs across 4 categories (snacks, beverages, candy, household_paper) with `width_cm`, `max_facings`, `category`, and a pre-assigned `assigned_shelf_id`. The `brand` column is loaded but unused by the bundled CSP (reserved for the brand-block-contiguity customization).
- **`shelves.csv`** (4 rows) — shelves with fixed lengths (Top Eye-Level 100cm, Upper-Middle 80cm, Lower-Middle 80cm, Bottom 90cm); `shelf_id` is the foreign-key target of `skus.assigned_shelf_id`.
- **`categories.csv`** (4 rows) — per-category minimum and maximum active-SKU bounds; `category` is the foreign-key target of `skus.category`.
- **`predicted_demand_table.csv`** — one row per `(sku_id, facings_count)` for every `facings_count` in `{0, 1, ..., sku.max_facings}`, with concave per-SKU demand curves; the `facings_count = 0` row is `demand_units = 0`.

## Model overview

The model has four concepts. The predictive output (`PredictedDemand`) is a data table that the CSP reads through a decision-indexed lookup; the decision lives on `Sku`.

- **Key entities**: `Sku` — a product with a width, max-facings cap, category, and assigned shelf (its facing count is the CSP decision); `Shelf` — a shelf with a fixed length that facings must fit within; `Category` — a product category with minimum and maximum active-SKU bounds; `PredictedDemand` — the predicted demand for each `(sku, facings_count)`, read by the CSP through a decision-indexed lookup.
- **Primary identifiers**: integer `id` on `Sku` and `Shelf`; string `name` on `Category`; composite `(sku_id, facings_count)` on `PredictedDemand`.
- **Important invariants**: `width_cm`, `max_facings`, and `length_cm` are non-negative integers; every `Sku.category` matches a `Category`, and every `Sku.assigned_shelf_id` matches a `Shelf`; `PredictedDemand` covers every `(sku_id, facings_count)` over `[0, max_facings]` with `demand_units = 0` at `facings_count = 0`; the CSP decisions `facings`, `realized_demand`, and `active` are integers (`active` is 0/1).

For the full concept and property definitions, see `model/__init__.py`; `runbook.md` builds them step by step with the RAI skills.

## How it works

The CSP picks integer facings per SKU; the predictive output binds each SKU's realized demand via a decision-indexed table lookup, and the solver maximizes total predicted demand under shelf and category limits.

```text
skus + shelves + categories + predicted-demand table → facings / realized_demand / active decisions → lookup + capacity + cardinality constraints → maximize demand → configure solve → deploy → check and report
```

**The decision-indexed table lookup is the predict-to-CSP hand-off.** For each SKU, `realized_demand` must equal the `PredictedDemand` row whose `facings_count` matches the chosen `facings`. Because equating a data property with a decision variable inside a `where` binding isn't a form the prescriptive rewriter lowers today, the lookup is written with an `implies` cascade — one half-reified equality per candidate facing count, of which only the row matching the chosen `facings` activates. This is the element-style lookup: no bilinearity, no big-M, no SOS2.

**An `active` indicator couples to `facings` via two linear inequalities.** The per-category cardinality is a relational sum over a 0/1 `active` variable (a sum over a Boolean expression like `facings >= 1` is not a valid form). Two linear constraints pin `active = 1` whenever `facings >= 1` and `active = 0` otherwise, after which the per-category count reads as a plain `sum(active).per(Category)` with min/max bounds. Shelf capacity is likewise a plain relational inequality: facings times width, summed per shelf, cannot exceed the shelf length.

**Checks run in the report.** The `implies`-bodied lookup is solver-only; after the deploy, a Python dict re-checks each `(sku_id, facings) -> demand_units` against the deployed demand table, and the report stops unless the solver reached `OPTIMAL`. The constraints (lookup, capacity, cardinality, active coupling) all go to the solver; the report does not re-evaluate them, and a refresh started outside the report (`rai models deploy`, the refresh procedure, a schedule) runs no checks, so read `SolveStatus` before relying on a refreshed solution.

For the exact PyRel formulation, see `model/__init__.py`; `runbook.md` reproduces the pipeline step by step with the RAI skills.

## Customize this template

### Use your own data

- Replace the four CSV files with your SKUs, shelves, categories, and predicted demand table. The constraint structure does not change. The data invariant: `predicted_demand_table.csv` must contain a row for every `(sku_id, k)` for `k in {0, 1, ..., sku.max_facings}` — if a row is missing, the implies cascade leaves `Sku.realized_demand` unconstrained for that combination and the solver may pick an arbitrary value.
- **Wire in a real demand model.** In production, `PredictedDemand` is the output of any model that predicts weekly demand at each candidate facing count — linear or GBM (gradient-boosted machine) regression over engineered features, a per-tier head, or a graph-aware regressor over `(sku, week, facings_count, units_sold)` history. The structural requirement is that `facings_count` is a feature (or there is a head per tier) so the model can be queried at every `k`. Produce `data/predicted_demand_table.csv` in the format `sku_id,facings_count,demand_units` (integer demand) from your inference pipeline and drop it in — the script picks it up unchanged. To call inference inline, replace the `read_csv(DATA_DIR / "predicted_demand_table.csv")` line with code that returns a DataFrame with those three columns.

### Tune parameters

- **Per-SKU minimum facings** — tighten the lower-coupling IC to `model.where(Sku).require(Sku.facings >= Sku.min_facings * Sku.active)` after adding a `Sku.min_facings` data property. (Removing disallowed `(sku, k)` rows from `predicted_demand_table.csv` would trip `_assert_demand_table_complete`; the lookup formulation requires the table to cover the full `[0, max_facings]` range.)
- **Category cardinality** — adjust `min_skus_active` / `max_skus_active` in `categories.csv` to change how many SKUs each category may keep active.

### Extend the model

- **Eye-level priority** is a constraint over the *static* shelf assignment in the bundled model — it validates that every premium SKU's `assigned_shelf_id` already points to the eye-level shelf and fails otherwise. Reassigning premium SKUs at solve time requires the multi-shelf reformulation below.
  ```python
  Sku.is_premium = model.Property(f"{Sku} has {Integer:is_premium}")
  # ... populate from a column on skus.csv ...
  EYE_LEVEL_SHELF_ID = 1  # Top Eye-Level Shelf
  eye_level_ic = model.where(Sku).require(
      implies(Sku.is_premium == 1, Sku.shelf.id == EYE_LEVEL_SHELF_ID)
  )
  problem.satisfy(eye_level_ic)
  ```
- **Multi-shelf reassignment** changes the shape of the model meaningfully. `solve_for` accepts only `int` / `cont` / `bin`, not relationship-valued domains, so shelf assignment cannot be a `Sku.shelf` decision directly. The same decision-vs-data-equality limitation that drives the `implies`-cascade table lookup also blocks `model.define(Sku.shelf(Shelf)).where(Shelf.id == Sku.shelf_id)` when `Sku.shelf_id` is a decision variable. The principled rewrite introduces a per-`(SKU, Shelf)` integer facing decision (e.g. `SkuShelf.facings`), uses `sum(SkuShelf.facings).per(Sku)` as the SKU's total facings, and writes capacity as `sum(SkuShelf.facings * Sku.width_cm).per(Shelf) <= Shelf.length_cm`. This is more involved than the bundled CSP and is left as an exercise.
- **Brand-block contiguity** — same-brand SKUs must occupy adjacent facings on the shelf — requires a per-shelf SKU position decision variable with adjacency constraints (more involved; the basic facing-count CSP above is unchanged but augmented).

### Scale up / productionize

- For a live catalog, replace the `read_csv(...)` loads with `model.data(snowflake_table)` calls so the SKUs, shelves, categories, and predicted-demand table read directly from your warehouse; the CSP is unchanged.
- The vendored `predicted_demand_table.csv` becomes a materialized inference output on a schedule — refresh it from your demand model. The completeness guard (`_assert_demand_table_complete`) runs when `model` is imported, so it checks the table each deploy uses, not a scheduled refresh's; validate the table in the workflow that refreshes it.
- The bundled data is 18 SKUs across 4 shelves; the CSP scales to whatever the constraint solver's budget allows. Raise `time_limit_sec` in the `problem.configure(...)` call for larger catalogs.
- Pin `relationalai` (see Prerequisites) so runs stay reproducible across environments.

## Troubleshooting

<details>
  <summary>Solver returns INFEASIBLE</summary>

- The category cardinality bounds may be inconsistent with the SKU pool. If `sum(min_skus_active)` exceeds the number of SKUs whose categories appear in the data, no allocation can satisfy every category's minimum. Check that each category's `min_skus_active` is `<=` the number of SKUs in that category.
- Shelf-capacity binding can starve a category. If the SKUs in a category all share a small shelf and their widths exceed the shelf's `length_cm` even at `facings = 1`, the category's `min_skus_active` is unreachable. Inspect `data/skus.csv` against `data/shelves.csv`.
- Missing rows in `predicted_demand_table.csv` for some `(sku, k)` combination cause the lookup to leave `realized_demand` unconstrained for that pair. The solver is free to pick a feasible value, but the resulting solution does not reflect real demand. Confirm that every SKU has rows for `k in {0, 1, ..., sku.max_facings}`.

</details>

<details>
  <summary>Import error or AttributeError on <code>relationalai</code></summary>

- Confirm your virtual environment is active: `which python` should point to `.venv`.
- Reinstall dependencies: `python -m pip install .`. The pinned version (`relationalai==2.1.1`) ships the `configure()`, `install_display_strings()`, and `where().require()` APIs this template uses; older versions lack them and produce attribute errors.
- If you share a venv across templates, run `python -m pip install --upgrade --force-reinstall relationalai==2.1.1`.

</details>

<details>
  <summary>FileNotFoundError on a CSV</summary>

- Run `rai models deploy --path model` and `python -m queries.facings_plan` from the unzipped template root, not from a parent directory.
- Confirm `data/` contains `skus.csv`, `shelves.csv`, `categories.csv`, and `predicted_demand_table.csv`.

</details>

<details>
  <summary>Authentication or configuration errors</summary>

- Re-create `raiconfig.yaml` with the configuration builder (Quickstart step 4) and verify the connection settings.
- If you have multiple profiles, set `export RAI_PROFILE=<your_profile>`.

</details>

<details>
  <summary>MiniZinc solver not available</summary>

- This template uses the MiniZinc constraint solver. Ensure the RAI Native App version supports MiniZinc.
- MiniZinc is the right backend for the current PyRel formulation: the `implies`-bodied table lookup lowers to half-reified linear equalities the constraint backend handles natively. A reformulation that one-hot encodes `(sku_id, k)` and writes the lookup as a linear sum could run on HiGHS, but it adds O(N * max_facings) auxiliary binaries and loses the pure-CSP "no big-M, no SOS2" framing this template is meant to demonstrate.

</details>

<details>
  <summary>The optimal allocation differs slightly between runs</summary>

- The solver is free to return any allocation that achieves the optimal objective. If multiple allocations tie, different solver versions may pick different ones.
- To pin a single answer, add a tie-breaker to the objective -- e.g. `problem.maximize(sum(Sku.realized_demand) * 1000 - sum(Sku.facings))` prefers fewer facings among equal-demand allocations.

</details>

## Learn more

### Core concepts

- [Predict-then-optimize patterns](https://docs.relational.ai/) — feeding a predictive model's output into a prescriptive solve on one ontology.
- [Prescriptive reasoner](https://docs.relational.ai/) — the `Problem` API: integer decisions (`solve_for`), constraints (`satisfy`), objective (`maximize`), and `configure`.

### Language / modeling reference

- [Concepts and properties](https://docs.relational.ai/) — modeling `Sku`, `Shelf`, `Category`, and the composite-keyed `PredictedDemand`.
- [Integrity constraints and `implies`](https://docs.relational.ai/) — half-reified linear equalities behind the decision-indexed table lookup.

### Deeper dives

- [Constraint-solver selection (MiniZinc)](https://docs.relational.ai/) — why a pure CSP formulation avoids big-M and SOS2, and when to reformulate for a linear backend.

## Support

- File issues at the RelationalAI templates repository.
