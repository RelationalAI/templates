"""Diet plan report: reads the deployed diet model.

Run `python -m queries.diet_plan` after `rai models deploy --path model`. Prints the
formulation, the termination status and objective of the latest refresh's solve, and
the foods (and amounts) in each scenario's least-cost basket.
"""

from model import Food, Scenario, SolveStatus, TotalCost, model, problem, x_amt

if __name__ == "__main__":
    problem.display()

    # Status and objective of the latest refresh's solve. A refresh records any
    # termination status, so the report checks it.
    status = model.select(SolveStatus).to_df().iloc[:, 0].tolist()
    cost = model.select(TotalCost).to_df().iloc[:, 0].tolist()
    print(f"\nSolve result:\n• status: {', '.join(status)}")
    if status != ["OPTIMAL"]:
        raise SystemExit(f"No optimal diet plan: termination status {status}")
    print(f"• objective: {round(cost[0], 9)}\n")

    print("\nDiet plan per scenario:")
    model.select(
        Scenario.scenario_name.alias("scenario"),
        Food.name.alias("food"),
        Food.cost,
        x_amt.alias("amount"),
    ).where(Food.x_amount(Scenario, x_amt), x_amt > 0.001).inspect()
