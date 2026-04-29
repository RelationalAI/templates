"""Planogram Optimization -- predict-then-optimize for retail shelf allocation.

Decide integer facing counts per SKU on each shelf to maximise total predicted
weekly demand subject to shelf-length capacity and per-category cardinality
limits.

Two-pillar showcase:
  * Predictive (GNN regression) -- predicts per-(SKU, facing_count) weekly
    demand. Output: a `PredictedDemand(sku_id, facings_count, demand_units)`
    relation indexed by SKU and integer facings. The `k=0` row is hard-coded
    `demand_units=0` (a SKU not on shelf has zero demand) so the lookup below
    is total over the decision domain `Sku.facings in {0..max_facings}`.
  * Prescriptive (CSP) -- picks integer facings per SKU. The predict->CSP
    hand-off is an *element-style decision-indexed table lookup* expressed
    as an `implies` cascade: for each SKU, `forall k in {0..max_facings}:
    Sku.facings == k => Sku.realized_demand == predicted_demand_table[sku,
    k]`. No bilinearity, no big-M, no SOS2 -- pure CSP.

The bundled `predicted_demand_table.csv` is a stand-in for live GNN output,
hand-rolled to a concave per-SKU demand curve. To wire in a GNN regressor
end-to-end, follow the pattern in v1/retail_planning/retail_planning_local.py:
train a sales-regression GNN whose features include facing-count, then for
each SKU x each k in {0..max_facings} call `gnn.predictions(...)` and
aggregate into PredictedDemand. The CSP shape below is unchanged.
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem, implies

DATA_DIR = Path(__file__).parent / "data"

model = Model("planogram_optimization")

# --------------------------------------------------
# Schema
# --------------------------------------------------
Sku = model.Concept("Sku", identify_by={"id": Integer})
Sku.name = model.Property(f"{Sku} has {String:name}")
Sku.category = model.Property(f"{Sku} has {String:category}")
Sku.brand = model.Property(f"{Sku} has {String:brand}")
Sku.width_cm = model.Property(f"{Sku} has {Integer:width_cm}")
Sku.max_facings = model.Property(f"{Sku} has {Integer:max_facings}")

Shelf = model.Concept("Shelf", identify_by={"id": Integer})
Shelf.name = model.Property(f"{Shelf} has {String:name}")
Shelf.length_cm = model.Property(f"{Shelf} has {Integer:length_cm}")

# Pre-determined shelf assignment per SKU (a real planogram step that
# precedes facing-count optimisation; kept static here to keep the CSP focused
# on the integer-facings decision).
Sku.shelf = model.Property(f"{Sku} is on {Shelf}")

Category = model.Concept("Category", identify_by={"name": String})
Category.min_skus_active = model.Property(f"{Category} has {Integer:min_skus_active}")
Category.max_skus_active = model.Property(f"{Category} has {Integer:max_skus_active}")

# Predictive output: a relation indexed by (sku_id, facings_count) yielding
# expected weekly demand. Modeled as a concept so it loads via to_schema()
# directly and can be referenced as a join target.
PredictedDemand = model.Concept(
    "PredictedDemand",
    identify_by={"sku_id": Integer, "facings_count": Integer},
)
PredictedDemand.demand_units = model.Property(
    f"{PredictedDemand} has {Integer:demand_units}"
)

# --------------------------------------------------
# Load data
# --------------------------------------------------
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

model.define(PredictedDemand.new(demand_data.to_schema()))

# Wire SKUs onto their pre-assigned shelves.
model.define(Sku.shelf(Shelf)).where(
    Sku.id(sku_data.sku_id),
    Shelf.id(sku_data.assigned_shelf_id),
)

# --------------------------------------------------
# CSP: pick integer facings per SKU; maximise total realized demand
# --------------------------------------------------
problem = Problem(model, Integer)

Sku.facings = model.Property(f"{Sku} has {Integer:facings}")
problem.solve_for(
    Sku.facings,
    type="int",
    lower=0,
    upper=Sku.max_facings,
    name=["facings", Sku.id],
)

# Element-style decision-indexed table lookup. The predict->CSP hand-off
# binds realized_demand on each SKU to the demand_units row of
# PredictedDemand whose facings_count matches the chosen Sku.facings. The
# implies expands per row of PredictedDemand into `implies(k = facings_sku,
# demand_sku = table[sku, k])` — one half-reified linear equality per
# (sku, k); only the row with k == Sku.facings activates.
Sku.realized_demand = model.Property(f"{Sku} has {Integer:realized_demand}")
problem.solve_for(
    Sku.realized_demand,
    type="int",
    lower=0,
    name=["demand", Sku.id],
)
problem.satisfy(
    model.where(
        PredictedDemand.sku_id == Sku.id,
    ).require(
        implies(
            PredictedDemand.facings_count == Sku.facings,
            Sku.realized_demand == PredictedDemand.demand_units,
        )
    )
)

# Shelf capacity: total facings * width on each shelf cannot exceed length.
problem.satisfy(
    model.where(
        Sku.shelf == Shelf,
    ).require(sum(Sku.facings * Sku.width_cm).per(Shelf) <= Shelf.length_cm)
)

# Category cardinality: number of active SKUs per category in
# [min_skus_active, max_skus_active]. `Sku.active` is an integer 0/1
# indicator decision (Boolean is not a valid `solve_for` type) coupled to
# `Sku.facings` via a half-reified `implies`: active iff facings >= 1.
Sku.active = model.Property(f"{Sku} has {Integer:active}")
problem.solve_for(
    Sku.active,
    type="bin",
    name=["active", Sku.id],
)
problem.satisfy(model.require(implies(Sku.active == 1, Sku.facings >= 1)))
problem.satisfy(model.require(implies(Sku.facings >= 1, Sku.active == 1)))

problem.satisfy(
    model.where(
        Sku.category == Category.name,
    ).require(sum(Sku.active).per(Category) >= Category.min_skus_active)
)
problem.satisfy(
    model.where(
        Sku.category == Category.name,
    ).require(sum(Sku.active).per(Category) <= Category.max_skus_active)
)

problem.maximize(sum(Sku.realized_demand))

problem.display()
problem.solve("minizinc", time_limit_sec=60)
problem.solve_info().display()

model.require(problem.termination_status() == "OPTIMAL")

# --------------------------------------------------
# Inspect solution
# --------------------------------------------------
print("\n=== Optimal facings per SKU ===")
model.select(
    Sku.id,
    Sku.name,
    Sku.category,
    Sku.shelf.name.alias("shelf"),
    Sku.facings,
    Sku.realized_demand,
).inspect()

print("\n=== Shelf utilisation ===")
model.select(
    Shelf.id,
    Shelf.name,
    sum(Sku.facings * Sku.width_cm).per(Shelf).alias("used_cm"),
    Shelf.length_cm,
).where(Sku.shelf == Shelf).inspect()

print("\n=== Category active counts ===")
model.select(
    Category.name,
    sum(Sku.active).per(Category).alias("active_skus"),
    Category.min_skus_active,
    Category.max_skus_active,
).where(Sku.category == Category.name).inspect()
