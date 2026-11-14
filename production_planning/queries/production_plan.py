"""Production plan report: reads the deployed production_planning model.

Run `python -m queries.production_plan` after `rai models deploy --path model`. Prints the
formulation, the termination status and objective of the latest refresh's solve, and the
non-trivial production quantities for each scenario.
"""

from model import Production, Scenario, SolveStatus, TotalProfit, model, problem, x_qty

if __name__ == "__main__":
    problem.display()

    # Status and objective of the latest refresh's solve. A refresh records any
    # termination status, so the report checks it.
    status = model.select(SolveStatus).to_df().iloc[:, 0].tolist()
    profit = model.select(TotalProfit).to_df().iloc[:, 0].tolist()
    print(f"\nSolve result:\n• status: {', '.join(status)}")
    if status != ["OPTIMAL"]:
        raise SystemExit(f"No optimal production plan: termination status {status}")
    print(f"• objective: {round(profit[0], 9)}\n")

    # --------------------------------------------------
    # Extract results per scenario
    # --------------------------------------------------

    print("\nProduction plan per scenario:")
    model.select(
        Scenario.name.alias("scenario"),
        Production.rate.machine.name.alias("machine"),
        Production.rate.product.name.alias("product"),
        x_qty.alias("quantity"),
    ).where(Production.x_quantity(Scenario, x_qty), x_qty > 0.001).inspect()
