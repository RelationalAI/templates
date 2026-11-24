"""Budget reallocation report: reads the deployed campaign_roi model.

Run `python -m queries.budget_reallocation` after `rai models deploy --path model`. Prints the
status and objective of the latest refresh's solve, the total expected conversions against
the current budgets, the optimized budget per campaign, and the regional spend against the
paused-region cap.
"""

from model import (
    PAUSED_CAP_FRACTION,
    PAUSED_REGION,
    TOTAL_BUDGET,
    Campaign,
    SolveStatus,
    TotalConversions,
    model,
)

if __name__ == "__main__":
    status = model.select(SolveStatus).to_df().iloc[:, 0].tolist()
    conversions = model.select(TotalConversions).to_df().iloc[:, 0].tolist()
    print(f"\nSolve result:\n• status: {', '.join(status)}")
    if status != ["OPTIMAL"]:
        raise SystemExit(f"termination status {status}")
    if not conversions:
        raise SystemExit("The solve returned no budget plan, so there is nothing to report.")
    print(f"• objective: {round(conversions[0], 9)}\n")

    print(f"\nStatus: {status[0]}")
    objective_value = conversions[0]
    print(f"Total expected conversions (optimized): {objective_value:,.1f}")

    results_df = model.select(
        Campaign.name.alias("campaign"),
        Campaign.region.alias("region"),
        Campaign.current_budget.alias("current"),
        Campaign.x_budget.alias("optimized"),
        Campaign.conversion_rate.alias("rate"),
    ).to_df()

    current_total = (results_df["current"] * results_df["rate"]).sum()
    print(f"Total expected conversions (current):   {current_total:,.1f}")
    print(f"Lift: {(objective_value - current_total) / current_total * 100:+.1f}%")

    print("\nBudget reallocation per campaign (sorted by largest absolute change):")
    results_df["delta"] = results_df["optimized"] - results_df["current"]
    results_df["multiple"] = results_df["optimized"] / results_df["current"]
    results_df = results_df.sort_values("delta", key=abs, ascending=False).reset_index(drop=True)
    print(results_df.to_string(index=False))

    print("\nRegional spend (optimized):")
    regional = (
        results_df.groupby("region")[["current", "optimized"]]
        .sum()
        .reset_index()
        .sort_values("optimized", ascending=False)
    )
    regional["share_of_total"] = regional["optimized"] / TOTAL_BUDGET
    print(regional.to_string(index=False))
    print(
        f"\nPaused region '{PAUSED_REGION}' cap: "
        f"{PAUSED_CAP_FRACTION * TOTAL_BUDGET:.1f} ({PAUSED_CAP_FRACTION:.0%} of ${TOTAL_BUDGET:,.0f}K total)"
    )
