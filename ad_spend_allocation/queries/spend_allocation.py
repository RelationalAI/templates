"""Spend allocation report: reads the deployed ad_spend_allocation model.

Run `python -m queries.spend_allocation` after `rai models deploy --path model`. Prints the
result of the latest refresh's solve and a table of the non-trivial spend allocations for
each budget scenario.
"""

from model import Allocation, Scenario, model, problem, x_spend

if __name__ == "__main__":
    si = problem.solve_info()
    si.display()

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
