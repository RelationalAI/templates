"""Allocation usage: the shelf length each shelf uses and the active SKUs each category has under the
chosen facings."""

from relationalai.semantics import Integer, String
from relationalai.semantics.std import aggregates as aggs

# Declares Sku.facings and Sku.active, the decisions the usage totals read.
from . import facing_allocation  # noqa: F401
from .schema import Category, Shelf, Sku, model

# Values computed from the solution live on concepts of their own, not on Shelf or Category:
# such a property on a concept the solve reads fails the deploy.

# Each shelf's used length: facings times SKU width, summed over the SKUs on it. A shelf with no
# SKU has no usage.
ShelfUsage = model.Concept("ShelfUsage", identify_by={"shelf_id": Integer})
ShelfUsage.used_cm = model.Property(f"{ShelfUsage} has {Integer:used_cm}")
model.where(Sku.shelf == Shelf).define(ShelfUsage.new(shelf_id=Shelf.id))
model.define(
    ShelfUsage.used_cm(
        aggs.sum(Sku, Sku.facings * Sku.width_cm).per(ShelfUsage).where(Sku.shelf.id == ShelfUsage.shelf_id)
    )
)

# Each category's number of active SKUs. A category with no SKU has no count.
CategoryUsage = model.Concept("CategoryUsage", identify_by={"name": String})
CategoryUsage.active_skus = model.Property(f"{CategoryUsage} has {Integer:active_skus}")
model.where(Sku.category == Category.name).define(CategoryUsage.new(name=Category.name))
model.define(
    CategoryUsage.active_skus(
        aggs.sum(Sku, Sku.active).per(CategoryUsage).where(Sku.category == CategoryUsage.name)
    )
)
