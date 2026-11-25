"""Semantic schema for the planogram optimization template: SKUs, shelves, categories, and predicted demand."""

from relationalai.semantics import Integer, Model, String

model = Model("planogram_optimization")

# Sku concept: a stock-keeping unit pre-assigned to a shelf, with width and
# the maximum facings the planogram is allowed to allocate to it.
Sku = model.Concept("Sku", identify_by={"id": Integer})
Sku.name = model.Property(f"{Sku} has {String:name}")
Sku.category = model.Property(f"{Sku} has {String:category}")
Sku.width_cm = model.Property(f"{Sku} has {Integer:width_cm}")
Sku.max_facings = model.Property(f"{Sku} has {Integer:max_facings}")

# Shelf concept: a fixed-length shelf the planogram allocates SKU facings
# onto.
Shelf = model.Concept("Shelf", identify_by={"id": Integer})
Shelf.name = model.Property(f"{Shelf} has {String:name}")
Shelf.length_cm = model.Property(f"{Shelf} has {Integer:length_cm}")

# Pre-determined shelf assignment per SKU (kept static so the CSP focuses on
# the integer-facings decision).
Sku.shelf = model.Property(f"{Sku} is on {Shelf}")

# Category concept: per-category min/max active-SKU bounds.
Category = model.Concept("Category", identify_by={"name": String})
Category.min_skus_active = model.Property(f"{Category} has {Integer:min_skus_active}")
Category.max_skus_active = model.Property(f"{Category} has {Integer:max_skus_active}")

# PredictedDemand concept: predictive output, indexed by (sku_id,
# facings_count). The `k=0` row is hard-coded `demand_units=0` so the lookup
# is total over the decision domain `Sku.facings in {0..max_facings}`.
PredictedDemand = model.Concept(
    "PredictedDemand",
    identify_by={"sku_id": Integer, "facings_count": Integer},
)
PredictedDemand.demand_units = model.Property(f"{PredictedDemand} has {Integer:demand_units}")
