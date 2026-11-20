"""Production plan report: reads the deployed production_planning model.

Run `python -m queries.production_plan` after `rai models deploy --path model`. Prints the
status and objective of the latest refresh's solve and the non-trivial production
quantities for each scenario.
"""

from model import Production, Scenario, SolveStatus, TotalProfit, model, x_qty

if __name__ == "__main__":
    status = model.select(SolveStatus).to_df().iloc[:, 0].tolist()
    profit = model.select(TotalProfit).to_df().iloc[:, 0].tolist()
    print(f"\nSolve result:\n• status: {', '.join(status)}")
    if profit:
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
