"""Spend allocation report: reads the deployed ad_spend_allocation model.

Run `python -m queries.spend_allocation` after `rai models deploy --path model`. Prints the
status and objective of the latest refresh's solve and a table of the non-trivial spend
allocations for each budget scenario.
"""

from model import Allocation, Scenario, SolveStatus, TotalConversions, model, x_spend

if __name__ == "__main__":
    status = model.select(SolveStatus).to_df().iloc[:, 0].tolist()
    conversions = model.select(TotalConversions).to_df().iloc[:, 0].tolist()
    print(f"\nSolve result:\n• status: {', '.join(status)}")
    if status != ["OPTIMAL"]:
        raise SystemExit(f"termination status {status}")
    if conversions:
        print(f"• objective: {round(conversions[0], 9)}\n")

    # --------------------------------------------------
    # Extract results per scenario
    # --------------------------------------------------

    print("\nSpend allocation per scenario:")
    model.select(
        Scenario.name.alias("scenario"),
        Allocation.effectiveness.channel.name.alias("channel"),
        Allocation.effectiveness.campaign.name.alias("campaign"),
        x_spend.alias("spend"),
    ).where(Allocation.x_spend(Scenario, x_spend), x_spend > 0.001).inspect()
