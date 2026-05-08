"""Planogram Optimization (predict-then-optimize) template.

This script demonstrates a predictive + prescriptive shelf-allocation problem
in RelationalAI:

- Decide integer facing counts per SKU on each shelf.
- Per-(SKU, facing_count) expected weekly demand comes from a vendored
  prediction table (a stand-in for any per-(SKU, k) regression model).
- The predict->CSP hand-off is an *element-style decision-indexed table
  lookup*: for each SKU, `Sku.realized_demand` is bound to the
  `PredictedDemand.demand_units` row whose `facings_count` matches the chosen
  `Sku.facings`. Pure CSP -- no bilinearity, no big-M, no SOS2.
- Solve as a maximization problem (MiniZinc) and inspect the allocation.

Modeling approach:
- One free integer decision per SKU (`facings` in `[0, max_facings]`) plus
  two integer variables pinned by ICs: `realized_demand` (via the lookup)
  and `active` (a 0/1 indicator coupled to `facings` by a linear-inequality
  pair so the per-category active-SKU cardinality is expressible as
  `sum(Sku.active).per(Category)`).
- Capacity, cardinality, and the active-iff-facings coupling are pure
  relational arithmetic and are re-evaluated by `problem.verify()`. The
  implies-bodied table lookup is solver-only; a post-solve check
  re-validates `(sku_id, facings) -> demand_units` against the input
  table via a Python dict lookup.

Run:
    `python planogram_optimization.py`

Output:
    Prints the formulation, the solve-result block, the optimal facings per
    SKU, per-shelf utilization, and per-category active counts.
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem, implies

DATA_DIR = Path(__file__).parent / "data"

# --------------------------------------------------
# Pre-solve data invariants
# --------------------------------------------------


# Each entity-keyed CSV must have unique key rows; duplicates would silently
# merge into the same entity with conflicting property values.
def _assert_unique_keys(df, key, source):
    cols = key if isinstance(key, list) else [key]
    dupe_rows = df[df.duplicated(subset=cols, keep=False)]
    if not dupe_rows.empty:
        duplicates = sorted({tuple(row) for row in dupe_rows[cols].itertuples(index=False)})
        raise ValueError(
            f"{source} has duplicate {tuple(cols) if len(cols) > 1 else cols[0]}"
            f"={duplicates}. Each key must be unique; remove or merge the "
            "conflicting rows."
        )


# The element-style table lookup binds Sku.realized_demand to the
# PredictedDemand row whose facings_count matches the chosen Sku.facings.
# If a row is missing for some (sku_id, k) with k in {0..max_facings}, the
# implies cascade leaves realized_demand unconstrained for that pair and
# the solver may pick an arbitrary value. The k=0 row must carry
# demand_units=0 so an inactive SKU (facings=0) cannot collect demand
# without consuming shelf capacity. Fail loudly before solve.
def _assert_demand_table_complete(skus_csv, demand_csv):
    expected = {
        (int(row.sku_id), k)
        for row in skus_csv.itertuples(index=False)
        for k in range(int(row.max_facings) + 1)
    }
    actual = {
        (int(row.sku_id), int(row.facings_count)) for row in demand_csv.itertuples(index=False)
    }
    missing = sorted(expected - actual)
    if missing:
        raise ValueError(
            "predicted_demand_table.csv is missing rows for "
            f"(sku_id, facings_count) pairs {missing[:10]}"
            f"{' ...' if len(missing) > 10 else ''}. The table must contain a "
            "row for every (sku_id, k) with k in {0..max_facings} so the "
            "decision-indexed lookup is total over the decision domain."
        )
    nonzero_at_zero = sorted(
        int(row.sku_id)
        for row in demand_csv.itertuples(index=False)
        if int(row.facings_count) == 0 and int(row.demand_units) != 0
    )
    if nonzero_at_zero:
        raise ValueError(
            f"predicted_demand_table.csv has rows with facings_count=0 and "
            f"demand_units != 0 for sku_id {nonzero_at_zero}. The k=0 row "
            "must always carry demand_units=0 so the objective cannot pull "
            "demand from inactive SKUs that consume no shelf capacity."
        )


# Each Sku.category must appear in categories.csv; otherwise the
# `where(Sku.category == Category.name)` joins drop those SKUs from the
# cardinality ICs and the solver is free to leave them inactive. The reverse
# direction is also enforced: a Category row with no SKUs has an empty
# `.per(Category)` group, so the cardinality IC is vacuously satisfied for
# that Category and a `min_skus_active >= 1` is silently dropped.
def _assert_categories_match_skus(skus_csv, categories_csv):
    sku_categories = set(skus_csv["category"].unique())
    catalog_categories = set(categories_csv["category"].unique())
    missing = sorted(sku_categories - catalog_categories)
    if missing:
        raise ValueError(
            f"categories.csv is missing entries for SKU categories {missing}. "
            "Add a row of the form `<category>,<min_skus_active>,"
            "<max_skus_active>` to categories.csv for each missing category "
            "so every SKU is covered by the category-cardinality constraints."
        )
    extras = sorted(catalog_categories - sku_categories)
    if extras:
        raise ValueError(
            f"categories.csv has rows for categories {extras} that have no "
            "SKUs in skus.csv. Such rows produce empty `.per(Category)` "
            "groups and `min_skus_active` is silently unenforced. Either "
            "remove these rows or add SKUs in those categories."
        )


# Each Sku.assigned_shelf_id must appear in shelves.csv; otherwise the
# `Sku.shelf` binding is empty and the SKU is silently dropped from
# `shelf_capacity_ic`, letting the solver allocate facings without
# consuming any shelf length.
def _assert_shelves_cover_skus(skus_csv, shelves_csv):
    sku_shelves = set(int(v) for v in skus_csv["assigned_shelf_id"].unique())
    catalog_shelves = set(int(v) for v in shelves_csv["shelf_id"].unique())
    missing = sorted(sku_shelves - catalog_shelves)
    if missing:
        raise ValueError(
            f"skus.csv references assigned_shelf_id {missing} that has no "
            "matching row in shelves.csv. Each SKU's `assigned_shelf_id` must "
            "match a `shelf_id` in shelves.csv so the SKU is bound to a "
            "Shelf and consumes capacity."
        )


skus_csv = read_csv(DATA_DIR / "skus.csv")
shelves_csv = read_csv(DATA_DIR / "shelves.csv")
categories_csv = read_csv(DATA_DIR / "categories.csv")
demand_csv = read_csv(DATA_DIR / "predicted_demand_table.csv")
_assert_unique_keys(skus_csv, "sku_id", "skus.csv")
_assert_unique_keys(shelves_csv, "shelf_id", "shelves.csv")
_assert_unique_keys(categories_csv, "category", "categories.csv")
_assert_unique_keys(demand_csv, ["sku_id", "facings_count"], "predicted_demand_table.csv")
_assert_demand_table_complete(skus_csv, demand_csv)
_assert_categories_match_skus(skus_csv, categories_csv)
_assert_shelves_cover_skus(skus_csv, shelves_csv)

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

model = Model("planogram_optimization")

# Sku concept: a stock-keeping unit pre-assigned to a shelf, with width and
# the maximum facings the planogram is allowed to allocate to it.
Sku = model.Concept("Sku", identify_by={"id": Integer})
Sku.name = model.Property(f"{Sku} has {String:name}")
Sku.category = model.Property(f"{Sku} has {String:category}")
Sku.width_cm = model.Property(f"{Sku} has {Integer:width_cm}")
Sku.max_facings = model.Property(f"{Sku} has {Integer:max_facings}")
sku_data = model.data(skus_csv)
model.define(
    Sku.new(
        id=sku_data.sku_id,
        name=sku_data.name,
        category=sku_data.category,
        width_cm=sku_data.width_cm,
        max_facings=sku_data.max_facings,
    )
)

# Shelf concept: a fixed-length shelf the planogram allocates SKU facings
# onto.
Shelf = model.Concept("Shelf", identify_by={"id": Integer})
Shelf.name = model.Property(f"{Shelf} has {String:name}")
Shelf.length_cm = model.Property(f"{Shelf} has {Integer:length_cm}")
shelf_data = model.data(shelves_csv)
model.define(
    Shelf.new(
        id=shelf_data.shelf_id,
        name=shelf_data.name,
        length_cm=shelf_data.length_cm,
    )
)

# Pre-determined shelf assignment per SKU (kept static so the CSP focuses on
# the integer-facings decision).
Sku.shelf = model.Property(f"{Sku} is on {Shelf}")
model.define(Sku.shelf(Shelf)).where(
    Sku.id(sku_data.sku_id),
    Shelf.id(sku_data.assigned_shelf_id),
)

# Category concept: per-category min/max active-SKU bounds.
Category = model.Concept("Category", identify_by={"name": String})
Category.min_skus_active = model.Property(f"{Category} has {Integer:min_skus_active}")
Category.max_skus_active = model.Property(f"{Category} has {Integer:max_skus_active}")
category_data = model.data(categories_csv)
model.define(
    Category.new(
        name=category_data.category,
        min_skus_active=category_data.min_skus_active,
        max_skus_active=category_data.max_skus_active,
    )
)

# PredictedDemand concept: predictive output, indexed by (sku_id,
# facings_count). The `k=0` row is hard-coded `demand_units=0` so the lookup
# is total over the decision domain `Sku.facings in {0..max_facings}`.
PredictedDemand = model.Concept(
    "PredictedDemand",
    identify_by={"sku_id": Integer, "facings_count": Integer},
)
PredictedDemand.demand_units = model.Property(f"{PredictedDemand} has {Integer:demand_units}")
# Schema form works here because predicted_demand_table.csv columns
# (sku_id, facings_count, demand_units) match PredictedDemand's identify_by +
# property names exactly. The Sku/Shelf/Category concepts use the per-field
# form because their CSVs use different column names (e.g. sku_id vs id).
model.define(PredictedDemand.new(model.data(demand_csv).to_schema()))

# --------------------------------------------------
# Decision-valued properties on Sku
# --------------------------------------------------

Sku.facings = model.Property(f"{Sku} has {Integer:facings}")
Sku.realized_demand = model.Property(f"{Sku} has {Integer:realized_demand}")
# 0/1 indicator that EXISTS so the per-category cardinality can be written as
# `sum(Sku.active).per(Category)`. Without it, the natural form
# `sum(Sku.facings >= 1).per(Category)` is not a valid relational sum.
# Boolean is not a valid `solve_for` type, so the indicator is encoded as an
# Integer 0/1, coupled to facings via the linear inequality pair below.
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

# Active iff facings >= 1, encoded as two linear inequalities:
# - `Sku.facings >= Sku.active` forces `facings >= 1` when `active == 1`.
# - `Sku.facings <= Sku.max_facings * Sku.active` forces `facings == 0` when
#   `active == 0`.
# Together they pin `active = 1` whenever `facings >= 1`, and `active = 0`
# otherwise. Pure relational arithmetic, so both ICs are re-evaluated by
# `problem.verify()` below.
active_lower_ic = model.require(Sku.facings >= Sku.active)
active_upper_ic = model.require(Sku.facings <= Sku.max_facings * Sku.active)
problem.satisfy(active_lower_ic)
problem.satisfy(active_upper_ic)

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

# Re-check the relational arithmetic ICs in the returned solution. Never
# pass the implies-bodied table lookup (demand_lookup_ic) to verify() --
# implies-bodied ICs are solver-only and verify() returns silently-OK
# without actually evaluating them. The lookup is verified post-solve via
# a Python dict lookup below.
problem.verify(
    shelf_capacity_ic,
    category_min_ic,
    category_max_ic,
    active_lower_ic,
    active_upper_ic,
)
model.require(problem.termination_status() == "OPTIMAL")

# Post-solve table-lookup check. Pull the chosen `(Sku.id, Sku.facings,
# Sku.realized_demand)` triples and confirm `realized_demand` matches the
# input table at the chosen `facings`. Catches the silent-failure mode
# where the implies cascade leaves `realized_demand` unconstrained for a
# missing (sku_id, k) row -- the pre-solve `_assert_demand_table_complete`
# guard already covers the bundled data, but this is defense in depth.
solution_df = model.select(
    Sku.id.alias("sku_id"),
    Sku.facings.alias("facings_count"),
    Sku.realized_demand.alias("realized_demand"),
).to_df()
expected_lookup = {
    (int(row.sku_id), int(row.facings_count)): int(row.demand_units)
    for row in demand_csv.itertuples(index=False)
}
mismatches = []
for row in solution_df.itertuples(index=False):
    key = (int(row.sku_id), int(row.facings_count))
    expected = expected_lookup.get(key)
    if expected is None or int(row.realized_demand) != expected:
        mismatches.append((*key, int(row.realized_demand), expected))
if mismatches:
    raise AssertionError(
        "Demand-lookup verification failed: Sku.realized_demand does not "
        "match PredictedDemand.demand_units at the chosen facings count for "
        f"{len(mismatches)} SKU(s). Pre-solve guards rule out the common "
        "case (missing rows in predicted_demand_table.csv); reaching this "
        "check means the implies cascade did not bind realized_demand for "
        "the chosen `facings`. Inspect the formulation printed by "
        "`problem.display()` to confirm the demand-lookup constraint expanded "
        "as expected. Mismatches "
        "(sku_id, facings, realized_demand, expected_demand):\n"
        f"{mismatches}"
    )

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

print("\nShelf utilization:")
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
