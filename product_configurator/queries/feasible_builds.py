"""Feasible builds report: reads the deployed product_configurator model.

Run `python -m queries.feasible_builds` after `rai models deploy --path model`. Prints the
status and number of solutions of the latest refresh's solve and every feasible build as a
pivot table (one row per build, one column per slot, sorted ascending by total price).
"""

from model import (
    MAX_CONFIGURATIONS,
    PRICE_CEILING_CENTS,
    TARGET_REGION,
    NumPoints,
    SolveStatus,
    model,
    selected_var,
)
from relationalai.semantics import Integer

if __name__ == "__main__":
    status = model.select(SolveStatus).to_df().iloc[:, 0].tolist()
    points = model.select(NumPoints).to_df().iloc[:, 0].tolist()
    num_points = points[0] if points else 0
    print(f"\nSolve result:\n• status: {', '.join(status)}\n• num_points: {num_points}\n")

    if num_points == 0:
        print(
            f"\nThe solver found no build for region {TARGET_REGION!r}. See the solve "
            "status above and the README troubleshooting section for likely causes."
        )
    else:
        # ------------------------------------------
        # Inspect every feasible configuration
        # ------------------------------------------

        # `selected_var.values(sol_idx, 1)` indexes the per-solution outputs and
        # filters to the options the solver picked. Pivot to one row per build,
        # one column per slot, sorted ascending by total dollars.
        sol_idx = Integer.ref()
        selections_df = (
            model.select(
                sol_idx.alias("solution"),
                selected_var.option.slot.name.alias("slot"),
                selected_var.option.name.alias("option"),
                selected_var.option.price_cents.alias("price_cents"),
            )
            .where(selected_var.values(sol_idx, 1))
            .to_df()
            .astype({"solution": "int64", "price_cents": "int64"})
        )
        build_view = selections_df.pivot(index="solution", columns="slot", values="option")
        build_view["total_$"] = selections_df.groupby("solution")["price_cents"].sum() // 100
        build_view = build_view.sort_values("total_$").reset_index()
        build_view.columns.name = None
        print(
            f"\nFeasible builds for region {TARGET_REGION!r} "
            f"(ceiling ${PRICE_CEILING_CENTS // 100:,}, up to {MAX_CONFIGURATIONS} per run):"
        )
        print(build_view.to_string(index=False))
