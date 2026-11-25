"""Budget reallocation report: reads the deployed campaign_roi model.

Run `python -m queries.budget_reallocation` after `rai models deploy --path model`. Prints the
status and objective of the latest refresh's solve, the total expected conversions against
the current budgets, the optimized budget per campaign, and the regional spend against the
paused-region cap.
"""

from model import (
    PAUSED_CAP,
    PAUSED_CAP_FRACTION,
    PAUSED_REGION,
    TOTAL_BUDGET,
    Campaign,
    CampaignPlan,
    ConversionLift,
    CurrentConversions,
    RegionSpend,
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

    current_total = model.select(CurrentConversions).to_df().iloc[0, 0]
    lift = model.select(ConversionLift).to_df().iloc[0, 0]
    print(f"Total expected conversions (current):   {current_total:,.1f}")
    print(f"Lift: {lift * 100:+.1f}%")

    # The id keeps campaigns that share every displayed value as separate rows.
    plan = CampaignPlan.ref()
    results_df = model.select(
        Campaign.id.alias("id"),
        Campaign.name.alias("campaign"),
        Campaign.region.alias("region"),
        Campaign.current_budget.alias("current"),
        Campaign.x_budget.alias("optimized"),
        Campaign.conversion_rate.alias("rate"),
        plan.delta.alias("delta"),
        plan.multiple.alias("multiple"),
    ).where(plan.campaign == Campaign).to_df()

    print("\nBudget reallocation per campaign (sorted by largest absolute change):")
    results_df = results_df.sort_values("delta", key=abs, ascending=False).reset_index(drop=True)
    print(results_df.drop(columns="id").to_string(index=False))

    print("\nRegional spend (optimized):")
    regional = (
        model.select(
            RegionSpend.region.alias("region"),
            RegionSpend.current_spend.alias("current"),
            RegionSpend.optimized_spend.alias("optimized"),
            RegionSpend.share_of_total.alias("share_of_total"),
        )
        .to_df()
        .sort_values("optimized", ascending=False)
    )
    print(regional.to_string(index=False))
    print(
        f"\nPaused region '{PAUSED_REGION}' cap: "
        f"{PAUSED_CAP:.1f} ({PAUSED_CAP_FRACTION:.0%} of ${TOTAL_BUDGET:,.0f}K total)"
    )
