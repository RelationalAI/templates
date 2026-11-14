"""Diet plan report: reads the deployed diet model.

Run `python -m queries.diet_plan` after `rai models deploy --path model`. Prints the
status and objective of the latest refresh's solve and the foods (and amounts) in each scenario's
least-cost basket.
"""

from model import Food, Scenario, SolveStatus, TotalCost, model, x_amt

if __name__ == "__main__":
    status = model.select(SolveStatus).to_df().iloc[:, 0].tolist()
    cost = model.select(TotalCost).to_df().iloc[:, 0].tolist()
    print(f"\nSolve result:\n• status: {', '.join(status)}")
    if cost:
        print(f"• objective: {round(cost[0], 9)}\n")

    print("\nDiet plan per scenario:")
    model.select(
        Scenario.scenario_name.alias("scenario"),
        Food.name.alias("food"),
        Food.cost,
        x_amt.alias("amount"),
    ).where(Food.x_amount(Scenario, x_amt), x_amt > 0.001).inspect()
