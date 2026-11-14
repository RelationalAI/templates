"""Facings plan report: reads the deployed planogram_optimization model.

Run `python -m queries.facings_plan` after `rai models deploy --path model`. Prints the
formulation, the termination status and objective of the latest refresh's solve, the optimal
facings per SKU, per-shelf utilization, and per-category active counts. It first checks that
each SKU's realized demand matches the predicted-demand table at its chosen facings.
"""

from model import (
    Category,
    PredictedDemand,
    Shelf,
    Sku,
    SolveStatus,
    TotalDemand,
    model,
    problem,
)
from relationalai.semantics import sum

if __name__ == "__main__":
    problem.display()

    # Status and objective of the latest refresh's solve. A refresh records any
    # termination status, so the report checks it.
    status = model.select(SolveStatus).to_df().iloc[:, 0].tolist()
    demand = model.select(TotalDemand).to_df().iloc[:, 0].tolist()
    print(f"\nSolve result:\n• status: {', '.join(status)}")
    if status != ["OPTIMAL"]:
        raise SystemExit(f"termination status {status}")
    if len(demand) != 1:
        raise SystemExit(f"expected one objective value, got {demand}")
    print(f"• objective: {demand[0]}\n")

    # Post-solve table-lookup check. Pull the chosen `(Sku.id, Sku.facings,
    # Sku.realized_demand)` triples and confirm `realized_demand` matches the
    # deployed demand table at the chosen `facings`. Catches the silent-failure mode
    # where the implies cascade leaves `realized_demand` unconstrained for a
    # missing (sku_id, k) row -- the pre-solve `_assert_demand_table_complete`
    # guard already covers the bundled data, but this is defense in depth.
    solution_df = model.select(
        Sku.id.alias("sku_id"),
        Sku.facings.alias("facings_count"),
        Sku.realized_demand.alias("realized_demand"),
    ).to_df()
    demand_table_df = model.select(
        PredictedDemand.sku_id.alias("sku_id"),
        PredictedDemand.facings_count.alias("facings_count"),
        PredictedDemand.demand_units.alias("demand_units"),
    ).to_df()
    expected_lookup = {
        (int(row.sku_id), int(row.facings_count)): int(row.demand_units)
        for row in demand_table_df.itertuples(index=False)
    }
    mismatches = []
    for row in solution_df.itertuples(index=False):
        key = (int(row.sku_id), int(row.facings_count))
        expected = expected_lookup.get(key)
        if expected is None or int(row.realized_demand) != expected:
            mismatches.append((*key, int(row.realized_demand), expected))
    if mismatches:
        raise SystemExit(
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

    # ----------------------------------------------
    # Inspect solution
    # ----------------------------------------------

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
