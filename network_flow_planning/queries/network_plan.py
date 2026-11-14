"""Network plan report: reads the deployed network_flow_planning model.

Run `python -m queries.network_plan` after `rai models deploy --path model`. Prints the
formulation, the termination status and total cost of the latest refresh's solve, the
opened fulfillment centers, and the active flow on each lane.
"""

from model import Lane, Site, SolveStatus, TotalCost, model, problem

if __name__ == "__main__":
    problem.display()

    # Status and objective of the latest refresh's solve. A refresh records any
    # termination status, so the report checks it.
    status = model.select(SolveStatus).to_df().iloc[:, 0].tolist()
    cost = model.select(TotalCost).to_df().iloc[:, 0].tolist()
    print(f"\nSolve result:\n• status: {', '.join(status)}")
    if status != ["OPTIMAL"]:
        raise SystemExit(f"No optimal network plan: termination status {status}")
    total_cost = cost[0]
    print(f"• objective: {round(total_cost, 9)}\n")

    print(f"\nStatus: {status[0]}")
    print(f"Total cost: ${total_cost:,.2f}")

    print("\nOpened fulfillment centers:")
    model.select(
        Site.name.alias("fulfillment_center"),
        Site.capacity.alias("capacity"),
        Site.fixed_cost.alias("fixed_cost"),
    ).where(Site.x_open > 0.5).inspect()

    print("\nActive flows:")
    model.select(
        Lane.source.name.alias("from_site"),
        Lane.dest.name.alias("to_site"),
        Lane.x_flow.alias("flow"),
        Lane.cost_per_unit.alias("unit_cost"),
    ).where(Lane.x_flow > 0.001).inspect()
