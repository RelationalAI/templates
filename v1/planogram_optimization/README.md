---
title: "Planogram Optimization"
description: "Decide integer facing counts per SKU to maximise predicted weekly demand under shelf capacity and category cardinality limits, where per-(SKU, facing_count) demand comes from a GNN regressor and the CSP hand-off is an element-style decision-indexed table lookup."
featured: false
experience_level: intermediate
industry: "Retail"
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

# Planogram Optimization

## What this template is for

Retailers running grocery, mass-merchandise, drug, and CPG categories decide
how many *facings* (front-row product positions) to allocate per SKU on each
shelf. More facings of a hot product lift its weekly sales; more facings of a
slow mover wastes shelf length that could carry a faster competitor. The
right answer differs by category, by SKU within a category, and by the
diminishing-returns curve each SKU exhibits as you give it more space.

This template solves the per-shelf facing-count allocation as a pure CSP,
where the per-(SKU, facing_count) expected weekly demand is a *predictive
output*. The hand-off from the predictive arm into the CSP is the canonical
**element-style decision-indexed table lookup**: the CSP picks an integer
`Sku.facings`, and `Sku.realized_demand` is bound -- via an `implies`
cascade -- to the `PredictedDemand.demand_units` row whose
`facings_count` matches the chosen value. No bilinearity, no big-M, no
SOS2; the lowering is `forall k in {0..max_facings}: Sku.facings == k =>
Sku.realized_demand == predicted_demand_table[sku, k]`.

> [!IMPORTANT]
> The RelationalAI **predictive reasoner (GNN)** referenced in the
> "Predictive arm" section is in early access. The bundled runner ships the
> CSP arm runnable on a vendored `predicted_demand_table.csv` (a stand-in
> for live GNN output) so the predict->CSP hand-off pattern can be inspected
> and run without the GNN dependency. The GNN training arm is documented as
> a follow-up; the CSP shape is unchanged.

## Who this is for

- Retail and CPG analysts allocating shelf space across SKUs and categories
- Operations researchers exploring the predict-then-optimize pattern with
  decision-indexed table lookups
- Data scientists wiring GNN-based demand prediction into integer
  optimisation
- ML engineers seeking a clean canonical example of predictive output as a
  decision-indexed lookup

Assumes familiarity with Python and basic constraint-programming concepts.

## What you'll build

- A SKU / Shelf / Category data model
- A `PredictedDemand(sku_id, facings_count)` relation representing GNN output
- A CSP that picks integer facing counts per SKU, with:
  - Element-style decision-indexed lookup binding realized demand
  - Shelf-length capacity (sum of `facings * width` per shelf <= length)
  - Category cardinality (active-SKU count per category in
    `[min_skus_active, max_skus_active]`)
- A linear `sum(realized_demand)` objective the CSP maximises

## What's included

- **Runner**: `planogram_optimization.py` -- single linear file. Loads CSVs,
  defines the model, declares decision variables, asserts the predict->CSP
  coupling and shelf/category constraints, solves, prints results.
- **Sample data** (under `data/`):
  - `skus.csv` -- 18 SKUs across 4 categories (snacks, beverages, candy,
    household_paper) with width, max-facings, and pre-assigned shelf
  - `shelves.csv` -- 4 shelves (Top Eye-Level 100cm, Upper-Middle 80cm,
    Lower-Middle 80cm, Bottom 90cm); all four shelves are capacity-binding
    in the optimal solution
  - `categories.csv` -- per-category min/max active SKU bounds
  - `predicted_demand_table.csv` -- vendored GNN output: 73 rows of
    `(sku_id, facings_count, demand_units)` with concave per-SKU demand
    curves (one row per `(sku, k)` for `k in {0, 1, ..., sku.max_facings}`)
- **Output**: `OPTIMAL` total weekly demand of `1656` units, 16 of 18 SKUs
  active (the two inactives are the lowest-base-demand candy and the
  bulkiest household-paper SKU, squeezed out by the binding bottom-shelf
  capacity), all shelves near-full

> [!NOTE]
> **Data invariant**: `predicted_demand_table.csv` MUST contain a row for
> every `(sku_id, k)` for `k in {0, 1, ..., sku.max_facings}`. If a row is
> missing, the implies cascade leaves `Sku.realized_demand` unconstrained
> for that combination and the solver may pick an arbitrary value. The
> `k=0` row is always `demand_units=0` (a SKU not on shelf has zero
> demand).

## Prerequisites

### Access

A Snowflake account with the RelationalAI Native App installed. The CSP arm
runs entirely on bundled CSV data via `model.data(...)` -- no Snowflake-side
data loading required. The GNN training arm (see "Predictive arm" below)
additionally requires a database with `USAGE` granted to the GNN Native App
plus `CREATE EXPERIMENT` and `CREATE MODEL` on a schema in that database.

### Tools

- Python >= 3.10
- RelationalAI Python SDK (`relationalai`) >= 1.0.14

## Quickstart

1. Download ZIP:
   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/planogram_optimization.zip
   unzip planogram_optimization.zip
   cd planogram_optimization
   ```

2. Create venv:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. Install:
   ```bash
   pip install .
   ```

4. Configure with `rai init` if you do not already have a `raiconfig.yaml`.

5. Run:
   ```bash
   python planogram_optimization.py
   ```

## Expected output

```
Solve result:
  status: OPTIMAL
  objective: 1656
  solve time: 0.24s
  num_points: 1
  solver: MiniZinc

=== Optimal facings per SKU ===
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

=== Shelf utilisation ===
   id                 name  used_cm  length_cm
0   1  Top Eye-Level Shelf       98        100
1   2   Upper-Middle Shelf       79         80
2   3   Lower-Middle Shelf       77         80
3   4         Bottom Shelf       90         90

=== Category active counts ===
              name  active_skus  min_skus_active  max_skus_active
0        beverages            5                3                5
1            candy            3                2                3
2  household_paper            3                2                3
3           snacks            5                3                5
```

## How it works

### Schema

Three core concepts:
- `Sku` (PK `id`) with `name`, `category`, `brand`, `width_cm`,
  `max_facings`, and a pre-assigned `shelf` relationship
- `Shelf` (PK `id`) with `name`, `length_cm`
- `Category` (PK `name`) with `min_skus_active`, `max_skus_active`

Plus the predictive output, modelled as a concept with composite key:
- `PredictedDemand` (PK `(sku_id, facings_count)`) with `demand_units`

### Predictive arm (out of scope for the bundled runner)

In production, `PredictedDemand` is the output of a sales-regression GNN
trained on historical `(sku, week, facings_count, units_sold)` rows. The
GNN learns the per-SKU demand-vs-facings curve from observed shelf
configurations. At inference time, for each SKU and each k in
`{0..max_facings}`, the GNN predicts an expected units count; those
predictions are quantised and loaded into `PredictedDemand` for the CSP to
consume. The H&M-style sales-regression pipeline already proven in the
`retail_planning` template (see `v1/retail_planning/retail_planning_local.py`)
is the recommended starting point; the structural difference is that the
planogram regressor includes facing-count as a feature (or trains a
per-tier head) so the same model can be queried at every k.

### CSP

Three decision variables:
- `Sku.facings` -- integer, `[0, Sku.max_facings]`
- `Sku.realized_demand` -- integer, lower-bound 0; pinned by the implies
  cascade
- `Sku.active` -- 0/1 indicator; coupled to `facings` via half-reified
  `implies` so the SKU-count cardinality constraints can be expressed as
  `sum(Sku.active).per(Category)`

Constraints:
- **Element-style decision-indexed lookup** -- for each SKU, `Sku.facings`
  picks one of its `PredictedDemand` rows; the `implies` cascade pins
  `Sku.realized_demand` to the matching `demand_units`
- **Shelf capacity** -- `sum(Sku.facings * Sku.width_cm).per(Shelf) <=
  Shelf.length_cm`
- **Active iff facings >= 1** -- two half-reified `implies` couple
  `Sku.active` to `Sku.facings`
- **Category cardinality** -- `sum(Sku.active).per(Category)` between
  `min_skus_active` and `max_skus_active`

Objective: `maximize sum(Sku.realized_demand)`. Linear in the CSP because
`Sku.realized_demand` is a decision pinned by the table lookup.

### Why the implies cascade?

The natural relational form -- `where(PredictedDemand.facings_count ==
Sku.facings).require(Sku.realized_demand == PredictedDemand.demand_units)`
-- equates a data property with a decision variable inside a `where`
binding, which the prescriptive rewriter doesn't lower today. Pushing the
decision-vs-data equality into the predicate of an `implies` lets the
rewriter expand into the canonical per-`k` form: one `implies(k =
facings_X, demand_X = TABLE[X, k])` per row of `PredictedDemand`. The CSP
backend then handles each as a half-reified linear equality.

## Extending

- **Brand-block contiguity** -- same-brand SKUs must occupy adjacent
  facings on the shelf; encode as a relational adjacency rule on a
  per-shelf SKU position decision variable (out of scope here)
- **Eye-level priority** -- mark a "premium" SKU subset whose `Sku.shelf`
  must be eye-level only
- **Per-SKU minimum facings** -- e.g. `Sku.facings >= Sku.min_facings`
  whenever `Sku.facings >= 1`. Encode either via a Boolean
  is-active-coupled `implies(active == 1, facings >= min_facings)` (the
  pattern shown above for the cardinality coupling), or by removing
  disallowed `(sku, k)` pairs from `PredictedDemand`
- **Multi-shelf reassignment** -- promote `Sku.shelf` to a decision
  variable and add per-SKU eligibility constraints

## Files

```
planogram_optimization/
  README.md                       (this file)
  planogram_optimization.py       Linear runner: schema, data, CSP, solve, inspect
  pyproject.toml                  Dependency declaration
  data/
    skus.csv                      8 SKUs in 3 categories
    shelves.csv                   2 shelves
    categories.csv                Category cardinality bounds
    predicted_demand_table.csv    Vendored GNN regression output (concave curves)
```
