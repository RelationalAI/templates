---
title: "Planogram Optimization"
description: "Decide integer facing counts per SKU to maximize predicted weekly demand under shelf capacity and category cardinality limits, where per-(SKU, facing_count) demand comes from a regression model."
featured: false
private: true
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
> The bundled runner ships with a vendored `predicted_demand_table.csv` -- a stand-in for the output of any per-(SKU, k) demand regressor -- so the predict->CSP hand-off pattern can be inspected and run without a training arm. Wiring in a real regressor is documented under "Customize this template"; the CSP shape is unchanged.

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
- Post-solve verification via `problem.verify()` for the capacity, cardinality, and active-coupling ICs, plus a Python dict lookup confirming `(sku_id, facings) -> demand_units` matches the input table

## What's included

- `planogram_optimization.py` -- main script with ontology, decisions, constraints, and solver call
- `data/skus.csv` -- 18 SKUs across 4 categories (snacks, beverages, candy, household_paper) with width, max-facings, and pre-assigned shelf; `sku_id` must be unique, `category` must match a `categories.csv` name, and `assigned_shelf_id` must reference a `shelves.csv` id. The `brand` column is loaded but not used by the bundled CSP -- it is reserved for the brand-block contiguity customization described under "Customize this template"
- `data/shelves.csv` -- 4 shelves (Top Eye-Level 100cm, Upper-Middle 80cm, Lower-Middle 80cm, Bottom 90cm); `id` must be unique and is the foreign-key target of `skus.assigned_shelf_id`
- `data/categories.csv` -- per-category min/max active SKU bounds; `name` must be unique and is the foreign-key target of `skus.category`
- `data/predicted_demand_table.csv` -- vendored regression output: one row per `(sku_id, facings_count)` for `k in {0, 1, ..., sku.max_facings}` with concave per-SKU demand curves; the `k=0` row is `demand_units=0` so the lookup is total over the decision domain
- `pyproject.toml` -- Python package configuration

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools
- Python >= 3.10
- RelationalAI Python SDK (`relationalai == 1.1.0`)

## Quickstart

1. Download ZIP:
   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/planogram_optimization.zip
   unzip planogram_optimization.zip
   cd planogram_optimization
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
   python planogram_optimization.py
   ```

6. Expected output (the solver maximizes total predicted weekly demand; the exact selection may vary across solver versions if multiple allocations achieve the same optimal objective). The script first prints the formulation (~30 lines, omitted here for brevity), then the solve-result block, then the per-SKU allocation, shelf utilization, and category active counts:
   ```text
   Solve result:
   • status: OPTIMAL
   • objective: 1656
   • solve time: 1.4s
   • num_points: 1
   • solver: MiniZinc_unknown

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

   `MiniZinc_unknown` is the version string MiniZinc reports for itself today; the underlying solver binary is selected by the RAI Native App. Total weekly demand of `1656` units, 16 of 18 SKUs active. Two SKUs go inactive because the candy and household_paper categories each have 4 SKUs but `max_skus_active=3`: Mint Roll loses the candy cap (lowest predicted demand at every k), Paper Towels 6pk loses the household_paper cap (lowest predicted demand-per-cm). The bottom shelf is fully binding (90/90cm); the other three are within 1-3cm of capacity.

## Template structure
```text
.
├── README.md
├── pyproject.toml
├── planogram_optimization.py
└── data/
    ├── skus.csv
    ├── shelves.csv
    ├── categories.csv
    └── predicted_demand_table.csv
```

**Start here**: run `python planogram_optimization.py` for the full predict-then-optimize run — it validates the data, binds each SKU's demand from the prediction table, solves the facing-count CSP, and prints the allocation.

## Sample data

The bundled CSVs are illustrative, fully synthetic demo data sized so the model runs in seconds. The `predicted_demand_table.csv` is a vendored stand-in for the output of any per-(SKU, facings-count) demand regressor, so the predict-to-CSP hand-off can be inspected and run without a training arm. A pre-solve pass validates unique keys, category and shelf foreign keys, and that the demand table is complete over every SKU's `[0, max_facings]` range with `demand_units = 0` at `facings_count = 0`.

- **`skus.csv`** (18 rows) — SKUs across 4 categories (snacks, beverages, candy, household_paper) with `width_cm`, `max_facings`, `category`, and a pre-assigned `assigned_shelf_id`. The `brand` column is loaded but unused by the bundled CSP (reserved for the brand-block-contiguity customization).
- **`shelves.csv`** (4 rows) — shelves with fixed lengths (Top Eye-Level 100cm, Upper-Middle 80cm, Lower-Middle 80cm, Bottom 90cm); `shelf_id` is the foreign-key target of `skus.assigned_shelf_id`.
- **`categories.csv`** (4 rows) — per-category minimum and maximum active-SKU bounds; `category` is the foreign-key target of `skus.category`.
- **`predicted_demand_table.csv`** — one row per `(sku_id, facings_count)` for every `facings_count` in `{0, 1, ..., sku.max_facings}`, with concave per-SKU demand curves; the `facings_count = 0` row is `demand_units = 0`.

## Model overview

The model has four concepts. The predictive output (`PredictedDemand`) is a data table that the CSP reads through a decision-indexed lookup; the decision lives on `Sku`.

- **Key entities**: `Sku`, `Shelf`, `Category`, `PredictedDemand`.
- **Primary identifiers**: integer `id` on `Sku` and `Shelf`; string `name` on `Category`; composite `(sku_id, facings_count)` on `PredictedDemand`.
- **Important invariants**: `width_cm`, `max_facings`, and `length_cm` are non-negative integers; every `Sku.category` matches a `Category`, and every `Sku.assigned_shelf_id` matches a `Shelf`; `PredictedDemand` covers every `(sku_id, facings_count)` over `[0, max_facings]` with `demand_units = 0` at `facings_count = 0`; the CSP decisions `facings`, `realized_demand`, and `active` are integers (`active` is 0/1).

### Sku

A stock-keeping unit pre-assigned to a shelf, carrying the integer facing-count decision and its two derived decision variables.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | Integer | Yes | `sku_id` from `data/skus.csv` |
| `name` | String | No | Human-readable product name |
| `category` | String | No | Matches a `Category.name` |
| `width_cm` | Integer | No | Facing width; drives shelf-capacity use |
| `max_facings` | Integer | No | Upper bound on the `facings` decision |
| `shelf` | Shelf | No | Relationship from the static `assigned_shelf_id` |
| `facings` | Integer | No | Decision: facings allocated, in `[0, max_facings]` |
| `realized_demand` | Integer | No | Decision pinned by the lookup to `PredictedDemand.demand_units` at the chosen `facings` |
| `active` | Integer | No | Decision (0/1) coupled to `facings` for the per-category cardinality |

### Shelf

A fixed-length shelf the planogram allocates facings onto.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | Integer | Yes | `shelf_id` from `data/shelves.csv` |
| `name` | String | No | Human-readable shelf name |
| `length_cm` | Integer | No | Capacity bound: `sum(facings * width_cm)` per shelf cannot exceed it |

### Category

A merchandising category with active-SKU count bounds.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `name` | String | Yes | `category` from `data/categories.csv` |
| `min_skus_active` | Integer | No | Lower bound on active SKUs in the category |
| `max_skus_active` | Integer | No | Upper bound on active SKUs in the category |

### PredictedDemand

The vendored regression output: predicted weekly demand at each candidate facing count, one row per `(sku_id, facings_count)`.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `sku_id`, `facings_count` | Integer | Yes | Composite key, from `data/predicted_demand_table.csv` |
| `demand_units` | Integer | No | Predicted weekly demand at that facing count |

## How it works

The CSP picks integer facings per SKU; the predictive output binds the realized-demand decision via a decision-indexed table lookup. The script consists of these patterns:

**Element-style decision-indexed table lookup is the predict->CSP hand-off.** For each SKU, `Sku.realized_demand` is pinned to the `demand_units` row of `PredictedDemand` whose `facings_count` matches the chosen `Sku.facings`. The `implies` cascade lowers per row of `PredictedDemand` into one half-reified linear equality `implies(k == Sku.facings, Sku.realized_demand == table[sku, k])`; only the row with `k == Sku.facings` activates:

```python
demand_lookup_ic = model.where(PredictedDemand.sku_id == Sku.id).require(
    implies(
        PredictedDemand.facings_count == Sku.facings,
        Sku.realized_demand == PredictedDemand.demand_units,
    )
)
```

The natural relational form -- `where(PredictedDemand.facings_count == Sku.facings).require(Sku.realized_demand == PredictedDemand.demand_units)` -- equates a data property with a decision variable inside a `where` binding, which the prescriptive rewriter doesn't lower today. Pushing the decision-vs-data equality into the predicate of an `implies` lets the rewriter expand into the canonical per-`k` form.

**Active iff facings is a pair of linear inequalities.** `Sku.active` is a 0/1 integer (declared as `solve_for(..., type="bin")`) because the per-category cardinality is written as `sum(Sku.active).per(Category)`, and a relational sum over a Boolean expression like `Sku.facings >= 1` is not a valid form. Two linear constraints couple the indicator to `Sku.facings`:

```python
active_lower_ic = model.require(Sku.facings >= Sku.active)
active_upper_ic = model.require(Sku.facings <= Sku.max_facings * Sku.active)
```

`Sku.facings >= Sku.active` forces `facings >= 1` when `active == 1`; `Sku.facings <= Sku.max_facings * Sku.active` forces `facings == 0` when `active == 0`. Together they pin `active = 1` whenever `facings >= 1` and `active = 0` otherwise. Both ICs are pure relational arithmetic, so they get re-evaluated by `problem.verify()` below.

Once `active` is bound, the per-category cardinality reads as a plain relational sum:

```python
category_min_ic = model.where(Sku.category == Category.name).require(
    sum(Sku.active).per(Category) >= Category.min_skus_active
)
```

**The `implies`-bodied table lookup is solver-only.** It goes to `satisfy()` but must NOT be passed to `verify()` -- implies-bodied ICs are solver-only and `verify()` returns silently-OK without actually evaluating them. The relational-arithmetic ICs (capacity, cardinality, active coupling) ARE re-evaluated by `verify()`, and a post-solve Python dict lookup re-checks the table lookup against the input CSV:

```python
problem.solve("minizinc", time_limit_sec=60)
problem.verify(
    shelf_capacity_ic,
    category_min_ic,
    category_max_ic,
    active_lower_ic,
    active_upper_ic,
)
model.require(problem.termination_status() == "OPTIMAL")
# ... post-solve Python dict lookup verifies (sku_id, facings) -> demand_units ...
```

## Customize this template

### Use your own data

- Replace the four CSV files with your SKUs, shelves, categories, and predicted demand table. The constraint structure does not change. The data invariant: `predicted_demand_table.csv` must contain a row for every `(sku_id, k)` for `k in {0, 1, ..., sku.max_facings}` — if a row is missing, the implies cascade leaves `Sku.realized_demand` unconstrained for that combination and the solver may pick an arbitrary value.
- **Wire in a real demand model.** In production, `PredictedDemand` is the output of any model that predicts weekly demand at each candidate facing count — linear or GBM (gradient-boosted machine) regression over engineered features, a per-tier head, or a graph-aware regressor over `(sku, week, facings_count, units_sold)` history. The structural requirement is that `facings_count` is a feature (or there is a head per tier) so the model can be queried at every `k`. Produce `data/predicted_demand_table.csv` in the format `sku_id,facings_count,demand_units` (integer demand) from your inference pipeline and drop it in — the script picks it up unchanged. To call inference inline, replace the `read_csv(DATA_DIR / "predicted_demand_table.csv")` line with code that returns a DataFrame with those three columns.

### Tune parameters

- **Per-SKU minimum facings** — tighten the lower-coupling IC to `model.require(Sku.facings >= Sku.min_facings * Sku.active)` after adding a `Sku.min_facings` data property. (Removing disallowed `(sku, k)` rows from `predicted_demand_table.csv` would trip `_assert_demand_table_complete`; the lookup formulation requires the table to cover the full `[0, max_facings]` range.)
- **Category cardinality** — adjust `min_skus_active` / `max_skus_active` in `categories.csv` to change how many SKUs each category may keep active.

### Extend the model

- **Eye-level priority** is a constraint over the *static* shelf assignment in the bundled model — it validates that every premium SKU's `assigned_shelf_id` already points to the eye-level shelf and fails otherwise. Reassigning premium SKUs at solve time requires the multi-shelf reformulation below.
  ```python
  Sku.is_premium = model.Property(f"{Sku} has {Integer:is_premium}")
  # ... populate from a column on skus.csv ...
  EYE_LEVEL_SHELF_ID = 1  # Top Eye-Level Shelf
  eye_level_ic = model.require(
      implies(Sku.is_premium == 1, Sku.shelf.id == EYE_LEVEL_SHELF_ID)
  )
  problem.satisfy(eye_level_ic)
  ```
- **Multi-shelf reassignment** changes the shape of the model meaningfully. `solve_for` accepts only `int` / `cont` / `bin`, not relationship-valued domains, so shelf assignment cannot be a `Sku.shelf` decision directly. The same decision-vs-data-equality limitation that drives the `implies`-cascade table lookup also blocks `model.define(Sku.shelf(Shelf)).where(Shelf.id == Sku.shelf_id)` when `Sku.shelf_id` is a decision variable. The principled rewrite introduces a per-`(SKU, Shelf)` integer facing decision (e.g. `SkuShelf.facings`), uses `sum(SkuShelf.facings).per(Sku)` as the SKU's total facings, and writes capacity as `sum(SkuShelf.facings * Sku.width_cm).per(Shelf) <= Shelf.length_cm`. This is more involved than the bundled CSP and is left as an exercise.
- **Brand-block contiguity** — same-brand SKUs must occupy adjacent facings on the shelf — requires a per-shelf SKU position decision variable with adjacency constraints (more involved; the basic facing-count CSP above is unchanged but augmented).

### Scale up / productionize

- For a live catalog, replace the `read_csv(...)` loads with `model.data(snowflake_table)` calls so the SKUs, shelves, categories, and predicted-demand table read directly from your warehouse; the CSP is unchanged.
- The vendored `predicted_demand_table.csv` becomes a materialized inference output on a schedule — refresh it from your demand model, and the pre-solve completeness guard (`_assert_demand_table_complete`) gates each run.
- The bundled data is 18 SKUs across 4 shelves; the CSP scales to whatever the constraint solver's budget allows. Raise `time_limit_sec` in the `problem.solve(...)` call for larger catalogs.
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
- Reinstall dependencies: `python -m pip install .`. The pinned version (`relationalai==1.1.0`) ships the `solve_info()`, `verify()`, and `where().require()` APIs this template uses; older versions lack them and produce attribute errors.
- If you share a venv across templates, run `python -m pip install --upgrade --force-reinstall relationalai==1.1.0`.

</details>

<details>
  <summary>FileNotFoundError on a CSV</summary>

- The script resolves data paths as `Path(__file__).parent / "data"`. Run `python planogram_optimization.py` from the unzipped template root, not from a parent directory.
- Confirm `data/` contains `skus.csv`, `shelves.csv`, `categories.csv`, and `predicted_demand_table.csv`.

</details>

<details>
  <summary>Authentication or configuration errors</summary>

- Run `rai init` to create or update your RelationalAI/Snowflake configuration.
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
- [Prescriptive reasoner](https://docs.relational.ai/) — the `Problem` API: integer decisions (`solve_for`), constraints (`satisfy`), objective (`maximize`), and `verify`.

### Language / modeling reference

- [Concepts and properties](https://docs.relational.ai/) — modeling `Sku`, `Shelf`, `Category`, and the composite-keyed `PredictedDemand`.
- [Integrity constraints and `implies`](https://docs.relational.ai/) — half-reified linear equalities behind the decision-indexed table lookup.

### Deeper dives

- [Constraint-solver selection (MiniZinc)](https://docs.relational.ai/) — why a pure CSP formulation avoids big-M and SOS2, and when to reformulate for a linear backend.

## Support

- File issues at the RelationalAI templates repository.
