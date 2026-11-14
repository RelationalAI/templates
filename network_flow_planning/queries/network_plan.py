"""Network plan report: reads the deployed network_flow_planning model.

Run `python -m queries.network_plan` after `rai models deploy --path model`. Prints the
result of the latest refresh's solve, the opened fulfillment centers, and the active flow
on each lane.
"""

from model import Lane, Site, model, problem

if __name__ == "__main__":
    si = problem.solve_info()
    si.display()

    print(f"\nStatus: {si.termination_status}")
    print(f"Total cost: ${si.objective_value:,.2f}")

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
