"""Planogram Optimization (predict-then-optimize) template.

This script demonstrates a predictive + prescriptive shelf-allocation problem
in RelationalAI:

- Decide integer facing counts per SKU on each shelf.
- Per-(SKU, facing_count) expected weekly demand comes from a regression model
  (here, a vendored stand-in for live GNN output).
- The predict->CSP hand-off is an *element-style decision-indexed table
  lookup*: for each SKU, `Sku.realized_demand` is bound to the
  `PredictedDemand.demand_units` row whose `facings_count` matches the chosen
  `Sku.facings`. Pure CSP -- no bilinearity, no big-M, no SOS2.
- Solve as a maximisation problem (MiniZinc) and inspect the allocation.

Modeling approach:
- Three integer decisions per SKU: `facings` in `[0, max_facings]`,
  `realized_demand` (pinned by the lookup), and `active` (0/1 indicator
  coupled to `facings` via a half-reified `implies` pair so the per-category
  active-SKU cardinality is expressible as `sum(Sku.active).per(Category)`).
- Capacity and cardinality constraints are pure relational arithmetic and are
  re-evaluated by `problem.verify()`. The implies-bodied lookup and active
  coupling are solver-only.

Run:
    `python planogram_optimization.py`

Output:
    Prints the formulation, the optimal facings per SKU, per-shelf utilisation,
    per-category active counts, and post-solve constraint verification.
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem, implies

DATA_DIR = Path(__file__).parent / "data"

model = Model("planogram_optimization")

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

# Concept: SKU
Sku = model.Concept("Sku", identify_by={"id": Integer})
Sku.name = model.Property(f"{Sku} has {String:name}")
Sku.category = model.Property(f"{Sku} has {String:category}")
Sku.brand = model.Property(f"{Sku} has {String:brand}")
Sku.width_cm = model.Property(f"{Sku} has {Integer:width_cm}")
Sku.max_facings = model.Property(f"{Sku} has {Integer:max_facings}")

# Concept: Shelf
Shelf = model.Concept("Shelf", identify_by={"id": Integer})
Shelf.name = model.Property(f"{Shelf} has {String:name}")
Shelf.length_cm = model.Property(f"{Shelf} has {Integer:length_cm}")

# Pre-determined shelf assignment per SKU (kept static so the CSP focuses on
# the integer-facings decision).
Sku.shelf = model.Property(f"{Sku} is on {Shelf}")

# Concept: category cardinality bounds
Category = model.Concept("Category", identify_by={"name": String})
Category.min_skus_active = model.Property(f"{Category} has {Integer:min_skus_active}")
Category.max_skus_active = model.Property(f"{Category} has {Integer:max_skus_active}")

# Concept: predictive output, indexed by (sku_id, facings_count). The `k=0`
# row is hard-coded `demand_units=0` so the lookup is total over the decision
# domain `Sku.facings in {0..max_facings}`.
PredictedDemand = model.Concept(
    "PredictedDemand",
    identify_by={"sku_id": Integer, "facings_count": Integer},
)
PredictedDemand.demand_units = model.Property(
    f"{PredictedDemand} has {Integer:demand_units}"
)

sku_data = model.data(read_csv(DATA_DIR / "skus.csv"))
shelf_data = model.data(read_csv(DATA_DIR / "shelves.csv"))
category_data = model.data(read_csv(DATA_DIR / "categories.csv"))
demand_data = model.data(read_csv(DATA_DIR / "predicted_demand_table.csv"))

model.define(
    Sku.new(
        id=sku_data.sku_id,
        name=sku_data.name,
        category=sku_data.category,
        brand=sku_data.brand,
        width_cm=sku_data.width_cm,
        max_facings=sku_data.max_facings,
    )
)
model.define(
    Shelf.new(
        id=shelf_data.shelf_id,
        name=shelf_data.name,
        length_cm=shelf_data.length_cm,
    )
)
model.define(
    Category.new(
        name=category_data.category,
        min_skus_active=category_data.min_skus_active,
        max_skus_active=category_data.max_skus_active,
    )
)
# Schema form works here because predicted_demand_table.csv columns
# (sku_id, facings_count, demand_units) match PredictedDemand's identify_by +
# property names exactly. The Sku/Shelf/Category concepts use the per-field
# form because their CSVs use different column names (e.g. sku_id vs id).
model.define(PredictedDemand.new(demand_data.to_schema()))

model.define(Sku.shelf(Shelf)).where(
    Sku.id(sku_data.sku_id),
    Shelf.id(sku_data.assigned_shelf_id),
)

# --------------------------------------------------
# Decision-valued properties on Sku
# --------------------------------------------------

Sku.facings = model.Property(f"{Sku} has {Integer:facings}")
Sku.realized_demand = model.Property(f"{Sku} has {Integer:realized_demand}")
# 0/1 indicator that EXISTS so the per-category cardinality can be written as
# `sum(Sku.active).per(Category)`. Without it, the natural form
# `sum(Sku.facings >= 1).per(Category)` is not a valid relational sum.
# Boolean is not a valid `solve_for` type, so the indicator is encoded as an
# Integer 0/1, coupled to facings via the half-reified `implies` pair below.
Sku.active = model.Property(f"{Sku} has {Integer:active}")

problem = Problem(model, Integer)
problem.solve_for(Sku.facings, type="int", lower=0, upper=Sku.max_facings, name=["facings", Sku.id])
problem.solve_for(Sku.realized_demand, type="int", lower=0, name=["demand", Sku.id])
problem.solve_for(Sku.active, type="bin", name=["active", Sku.id])

# --------------------------------------------------
# Constraints
# --------------------------------------------------

# Element-style decision-indexed table lookup. The implies expands per row of
# PredictedDemand into `implies(k == Sku.facings, Sku.realized_demand ==
# table[sku, k])`; only the row with k == Sku.facings activates.
demand_lookup_ic = model.where(PredictedDemand.sku_id == Sku.id).require(
    implies(
        PredictedDemand.facings_count == Sku.facings,
        Sku.realized_demand == PredictedDemand.demand_units,
    )
)
problem.satisfy(demand_lookup_ic)

# Shelf capacity: total facings * width on each shelf cannot exceed length.
shelf_capacity_ic = model.where(Sku.shelf == Shelf).require(
    sum(Sku.facings * Sku.width_cm).per(Shelf) <= Shelf.length_cm
)
problem.satisfy(shelf_capacity_ic)

# Active iff facings >= 1: half-reified `implies` pair couples the indicator
# to the facings decision so per-category cardinality can be expressed as
# `sum(Sku.active).per(Category)`.
active_implies_facings_ic = model.require(implies(Sku.active == 1, Sku.facings >= 1))
facings_implies_active_ic = model.require(implies(Sku.facings >= 1, Sku.active == 1))
problem.satisfy(active_implies_facings_ic)
problem.satisfy(facings_implies_active_ic)

# Category cardinality bounds.
category_min_ic = model.where(Sku.category == Category.name).require(
    sum(Sku.active).per(Category) >= Category.min_skus_active
)
category_max_ic = model.where(Sku.category == Category.name).require(
    sum(Sku.active).per(Category) <= Category.max_skus_active
)
problem.satisfy(category_min_ic)
problem.satisfy(category_max_ic)

problem.maximize(sum(Sku.realized_demand))

# --------------------------------------------------
# Solve and verify
# --------------------------------------------------

problem.display()
problem.solve("minizinc", time_limit_sec=60)
problem.solve_info().display()

# Re-check the relational arithmetic ICs in the returned solution. Never pass
# implies-bodied ICs (demand_lookup_ic, active_implies_facings_ic,
# facings_implies_active_ic) to verify() -- the relational engine cannot
# re-evaluate wire-format constraint relations and would return silently-OK
# regardless of whether the constraint actually holds.
problem.verify(shelf_capacity_ic, category_min_ic, category_max_ic)
model.require(problem.termination_status() == "OPTIMAL")

# --------------------------------------------------
# Inspect solution
# --------------------------------------------------

print("\nOptimal facings per SKU:")
model.select(
    Sku.id,
    Sku.name,
    Sku.category,
    Sku.shelf.name.alias("shelf"),
    Sku.facings,
    Sku.realized_demand,
).inspect()

print("\nShelf utilisation:")
model.select(
    Shelf.id,
    Shelf.name,
    sum(Sku.facings * Sku.width_cm).per(Shelf).alias("used_cm"),
    Shelf.length_cm,
).where(Sku.shelf == Shelf).inspect()

print("\nCategory active counts:")
model.select(
    Category.name,
    sum(Sku.active).per(Category).alias("active_skus"),
    Category.min_skus_active,
    Category.max_skus_active,
).where(Sku.category == Category.name).inspect()
