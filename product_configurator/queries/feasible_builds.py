"""Feasible builds report: reads the deployed product_configurator model.

Run `python -m queries.feasible_builds` after `rai models deploy --path model`. Prints the
status and number of solutions of the latest refresh's solve and every feasible build as a
pivot table (one row per build, one column per slot, sorted ascending by total price).
"""

from model import (
    NumPoints,
    Option,
    SelectedOption,
    SolveSettings,
    SolveStatus,
    model,
)
from relationalai.semantics import Integer

if __name__ == "__main__":
    status = model.select(SolveStatus).to_df().iloc[:, 0].tolist()
    points = model.select(NumPoints).to_df().iloc[:, 0].tolist()
    num_points = points[0] if points else 0
    region, price_ceiling_cents, max_configurations = model.select(SolveSettings).to_df().iloc[0]
    print(f"\nSolve result:\n• status: {', '.join(status)}\n• num_points: {num_points}\n")

    if num_points == 0:
        print(
            f"\nThe solver found no build for region {region!r}. See the solve "
            "status above and the README troubleshooting section for likely causes."
        )
    else:
        # ------------------------------------------
        # Inspect every feasible configuration
        # ------------------------------------------

        # `SelectedOption` holds, per solution, the options the solver picked. Pivot to
        # one row per build, one column per slot, sorted ascending by the exact total in cents.
        sol_idx = Integer.ref()
        selections_df = (
            model.select(
                sol_idx.alias("solution"),
                Option.slot.name.alias("slot"),
                Option.name.alias("option"),
                Option.price_cents.alias("price_cents"),
            )
            .where(SelectedOption(sol_idx, Option))
            .to_df()
        )
        build_view = selections_df.pivot(index="solution", columns="slot", values="option")
        total_cents = selections_df.groupby("solution")["price_cents"].sum()
        build_view["total_$"] = total_cents / 100
        build_view = build_view.loc[total_cents.sort_values().index].reset_index()
        build_view.columns.name = None
        print(
            f"\nFeasible builds for region {region!r} "
            f"(ceiling ${price_ceiling_cents / 100:,.2f}, up to {max_configurations} per run):"
        )
        print(build_view.to_string(index=False))
