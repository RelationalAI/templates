"""Staffing frontier report: reads the deployed hospital staffing model.

Run `python -m queries.staffing_frontier` after `rai models deploy --path model`. Prints the
status and result of each solve in the latest refresh (the two anchors and the epsilon sweep),
the efficient frontier of overtime cost against unmet demand, the marginal analysis with knee
detection, and the nurse assignments at the knee.
"""

from model import (
    N_INTERIOR,
    FreeKnee,
    FrontierPoint,
    FrontierStep,
    JumpKnee,
    Nurse,
    Shift,
    SweepPoint,
    model,
)
from relationalai.semantics import Float, Integer

if __name__ == "__main__":
    status = model.select(
        FrontierPoint.position.alias("position"), FrontierPoint.status.alias("status")
    ).to_df()
    overtime = model.select(
        FrontierPoint.position.alias("position"), FrontierPoint.overtime_cost.alias("overtime_cost")
    ).to_df()
    unmet = model.select(
        FrontierPoint.position.alias("position"), FrontierPoint.unmet_demand.alias("unmet_demand")
    ).to_df()
    points = (
        status.merge(overtime, on="position", how="left")
        .merge(unmet, on="position", how="left")
        .set_index("position")
    )
    eps_df = model.select(SweepPoint.index.alias("index"), SweepPoint.eps_unmet.alias("eps")).to_df()
    eps_by_index = dict(zip(eps_df["index"], eps_df["eps"]))

    def solved(position):
        return position in points.index and points.loc[position, "status"] == "OPTIMAL"

    cheapest, best = 0, N_INTERIOR + 1

    print("=" * 70)
    print("ANCHOR SOLVE 1: Minimize overtime cost (no unmet demand constraint)")
    print("=" * 70)
    anchor_status = points.loc[cheapest, "status"] if cheapest in points.index else "none"
    print(f"Status: {anchor_status}")
    if not solved(cheapest):
        raise SystemExit(f"termination status {anchor_status}")
    print(f"Overtime cost: ${points.loc[cheapest, 'overtime_cost']:.2f}")
    print(f"Unmet demand: {points.loc[cheapest, 'unmet_demand']:.1f} patients")

    print(f"\n{'=' * 70}")
    print("ANCHOR SOLVE 2: Minimize unmet demand (no overtime cost objective)")
    print("=" * 70)
    anchor_status = points.loc[best, "status"] if best in points.index else "none"
    print(f"Status: {anchor_status}")
    if not solved(best):
        raise SystemExit(f"termination status {anchor_status}")
    print(f"Min unmet demand: {points.loc[best, 'unmet_demand']:.1f} patients")
    print(f"Overtime cost at best service: ${points.loc[best, 'overtime_cost']:.2f}")

    print(
        f"\nFeasible unmet demand range: [{points.loc[best, 'unmet_demand']:.1f}, "
        f"{points.loc[cheapest, 'unmet_demand']:.1f}]"
    )

    # --------------------------------------------------
    # Epsilon sweep: minimize overtime s.t. unmet <= eps
    # --------------------------------------------------

    print(f"\n{'=' * 70}")
    print(f"EPSILON SWEEP: {N_INTERIOR} interior points")
    print(f"Unmet demand targets: {[f'{eps_by_index[i]:.1f}' for i in sorted(eps_by_index)]}")
    print(f"{'=' * 70}")

    # The model publishes the frontier: the cheapest anchor and the sweep points up to the first
    # that failed, then the best-service anchor only when the whole sweep solved, so no marginal
    # rate spans a failed interval. The report stops reading the sweep at the first failed point.
    pareto = (
        model.select(
            FrontierPoint.position.alias("position"),
            FrontierPoint.number.alias("number"),
            FrontierPoint.label.alias("label"),
            FrontierPoint.overtime_cost.alias("overtime_cost"),
            FrontierPoint.unmet_demand.alias("unmet_demand"),
        )
        .where(FrontierPoint.on_frontier())
        .to_df()
        .sort_values("number")
        .to_dict("records")
    )
    on_frontier = {pt["position"] for pt in pareto}
    sweep_complete = True
    for i in range(1, N_INTERIOR + 1):
        eps = eps_by_index.get(i)
        eps_text = f"{eps:.1f}" if eps is not None else "?"
        if i not in on_frontier:
            point_status = points.loc[i, "status"] if i in points.index else "none"
            print(f"  Point {i} (unmet<={eps_text}): {point_status} -- stopping")
            sweep_complete = False
            break
        pt = points.loc[i]
        print(
            f"  Point {i} (unmet<={eps_text}): overtime=${pt['overtime_cost']:.2f}, "
            f"actual_unmet={pt['unmet_demand']:.1f}  [{pt['status']}]"
        )
    if not sweep_complete:
        print("  The frontier below ends at the last solved sweep point.")

    # --------------------------------------------------
    # Pareto analysis
    # --------------------------------------------------

    print(f"\n{'=' * 70}")
    print("EFFICIENT FRONTIER: Overtime Cost vs Patient Service")
    print(f"{'=' * 70}")
    print(f"{'#':>3} {'Label':>14} {'Unmet Demand':>14} {'Overtime Cost':>14}")
    print("-" * 48)
    for pt in pareto:
        print(f"{pt['number']:>3} {pt['label']:>14} {pt['unmet_demand']:>14.1f} ${pt['overtime_cost']:>13.2f}")

    # ASCII Pareto plot: Overtime Cost (y) vs Unmet Demand (x)
    if len(pareto) >= 2:
        plot_h, plot_w = 12, 50
        unmets = [pt['unmet_demand'] for pt in pareto]
        costs = [pt['overtime_cost'] for pt in pareto]
        u_min, u_max = min(unmets), max(unmets)
        c_min, c_max = min(costs), max(costs)
        u_range = u_max - u_min if u_max > u_min else 1
        c_range = c_max - c_min if c_max > c_min else 1
        grid = [[" "] * plot_w for _ in range(plot_h)]
        for k, pt in enumerate(pareto):
            col = int((pt['unmet_demand'] - u_min) / u_range * (plot_w - 1))
            row = int((pt['overtime_cost'] - c_min) / c_range * (plot_h - 1))
            row = plot_h - 1 - row
            col = max(0, min(plot_w - 1, col))
            row = max(0, min(plot_h - 1, row))
            grid[row][col] = str(k + 1)
        print("\nOvertime Cost")
        for i, row in enumerate(grid):
            if i == 0:
                label = f"${c_max:>9,.2f}"
            elif i == plot_h - 1:
                label = f"${c_min:>9,.2f}"
            else:
                label = " " * 10
            print(f"{label} |{''.join(row)}|")
        print(f"{' ' * 10} +{'-' * plot_w}+")
        print(f"{' ' * 10}  {u_min:<.0f}{u_max:>{plot_w - len(f'{u_min:.0f}')},.0f} patients")
        print(f"{' ' * 10}  {'Unmet Demand':^{plot_w}}")

    # Marginal analysis
    if len(pareto) >= 3:
        print("\nMarginal analysis (cost of reducing unmet demand by 1 patient):")
        # The model publishes each step between consecutive frontier points; a flat step has
        # no rate, so it has no line.
        steps = (
            model.select(
                FrontierStep.number.alias("number"),
                FrontierStep.cost_added.alias("cost_added"),
                FrontierStep.unmet_removed.alias("unmet_removed"),
                FrontierStep.rate.alias("rate"),
            )
            .to_df()
            .sort_values("number")
        )
        for step in steps.itertuples():
            j = step.number - 1
            print(f"  {pareto[j]['label']:>14} → {pareto[j+1]['label']:<14}: "
                  f"Δcost=${step.cost_added:>+10.2f}, Δunmet={-step.unmet_removed:>+6.1f}, "
                  f"marginal=${step.rate:>8.2f}/patient")

        # The model publishes the knee: when service improves for free before the first paid
        # step, the last free point; otherwise the point after the largest jump between
        # consecutive rates. With no paid step there is no knee.
        free_number, next_rate, jump_number, jump = (
            Integer.ref(), Float.ref(), Integer.ref(), Float.ref()
        )
        free_knee = (
            model.where(FreeKnee(free_number, next_rate))
            .select(free_number.alias("number"), next_rate.alias("next_rate"))
            .to_df()
        )
        jump_knee = (
            model.where(JumpKnee(jump_number, jump))
            .select(jump_number.alias("number"), jump.alias("jump"))
            .to_df()
        )
        if not free_knee.empty:
            knee_number = int(free_knee["number"].iloc[0])
            knee_text = (f"the last free improvement; the next costs "
                         f"${free_knee['next_rate'].iloc[0]:.2f}/patient")
        elif not jump_knee.empty:
            knee_number = int(jump_knee["number"].iloc[0])
            knee_text = f"marginal cost jumps {jump_knee['jump'].iloc[0]:.1f}x beyond this point"
        else:
            knee_number = None
        if knee_number is None:
            print("\n  No knee: no service improvement has a positive marginal cost.")
        else:
            knee = pareto[knee_number - 1]
            print(f"\n  Knee: Point {knee_number} ({knee['label']}) -- {knee_text}")
            print(f"  Recommendation: Target {knee['unmet_demand']:.0f} unmet patients "
                  f"at ${knee['overtime_cost']:.2f} overtime cost -- "
                  f"further service improvement costs significantly more per patient.")

            # Print nurse assignments at the knee point
            knee_assignments = model.select(
                Nurse.name.alias("nurse"), Shift.name.alias("shift")
            ).where(
                FrontierPoint.position == int(knee["position"]),
                FrontierPoint.assigns(Nurse, Shift),
            ).to_df()
            if not knee_assignments.empty:
                print("\n  Knee-point assignments:")
                by_shift = knee_assignments.groupby("shift")["nurse"]

                for shift, nurses in by_shift:
                    nurses = ", ".join(sorted(nurses))
                    print(f"    {shift}: {nurses}")
