"""Load the sample SKUs, shelves, categories, and demand table, and check them before the solve."""

from pathlib import Path

from pandas import read_csv

from .schema import Category, PredictedDemand, Shelf, Sku, model

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

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

shelf_data = model.data(shelves_csv)
model.define(
    Shelf.new(
        id=shelf_data.shelf_id,
        name=shelf_data.name,
        length_cm=shelf_data.length_cm,
    )
)

model.define(Sku.shelf(Shelf)).where(
    Sku.id(sku_data.sku_id),
    Shelf.id(sku_data.assigned_shelf_id),
)

category_data = model.data(categories_csv)
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
model.define(PredictedDemand.new(model.data(demand_csv).to_schema()))
