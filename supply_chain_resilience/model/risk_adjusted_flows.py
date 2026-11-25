"""Risk-adjusted network flow: the baseline routing problem, the disruption scenarios, and what each
solve publishes."""

from typing import Any, NamedTuple

from relationalai.semantics import Float, Integer, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.std import aggregates as aggs

# Declare Site.centrality and Site.is_most_critical, and the Business risk flags, that the
# objective and the constraints read.
from . import network_criticality, supplier_risk  # noqa: F401
from .schema import Business, Demand, Operation, Site, model

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

UNMET_PENALTY = 100.0  # penalty for unmet demand (kept moderate so routing costs are visible)
RISK_SURCHARGE = 5.0  # cost multiplier for "watch" supplier operations
CENTRALITY_WEIGHT = 2.0  # multiplier for bottleneck site penalty
FLOW_TOLERANCE = 0.001  # solved flows and unmet quantities at or below this are solver noise

# Derived relationship: Operation's source business (via shared site).
Operation.source_business = model.Relationship(
    f"{Operation} sourced from {Business}"
)
model.define(Operation.source_business(Operation, Business)).where(
    Operation.source_site == Business.site
)

# How many source links that relationship holds.
num_source_links = model.Relationship(f"there are {Integer:num_source_links} operation source links")
op_linked, biz_linked = Operation.ref(), Business.ref()
model.define(num_source_links(
    aggs.count(op_linked, biz_linked).where(Operation.source_business(op_linked, biz_linked)) | 0
))

# --------------------------------------------------
# Stage 3: Prescriptive -- risk-adjusted network flow
# --------------------------------------------------

# Define decision variable properties once, outside build_flow().
Operation.x_flow = model.Property(f"{Operation} has {Float:flow}")
Demand.x_unmet = model.Property(f"{Demand} has {Float:unmet}")


class Flow(NamedTuple):
    """One network flow problem, its decision variables, and its published result."""

    name: str
    problem: Any
    routes: Any
    unmet: Any
    status: Any
    cost: Any
    active_flows: Any
    unmet_orders: Any
    unmet_units: Any


def build_flow(name, exclude_critical_site=False, block_watch_level=False):
    """Define a network flow problem named `name`, optionally disabling the most critical site or blocking more suppliers.

    Args:
        name: Problem name, which also prefixes the problem's published status and cost.
        exclude_critical_site: If True, all operations from the most critical site
            (Site.is_most_critical) get zero flow.
        block_watch_level: If True, operations sourced from every watch-level
            business (unreliable or high delay risk) get zero flow, in place of the
            Business.is_avoid() block that the other problems use.
    """
    problem = Problem(model, Float, name=name)

    # Decision variable: flow on each operation.
    flow_var = problem.solve_for(
        Operation.x_flow,
        name=["x_flow", Operation.id],
        lower=0,
        upper=Operation.capacity_per_day,
        populate=False,
    )

    # Slack variable: unmet demand per demand order.
    unmet_var = problem.solve_for(
        Demand.x_unmet,
        name=["x_unmet", Demand.id],
        lower=0,
        populate=False,
    )

    # Constraint: demand satisfaction.
    # For each demand, inbound flow at the customer's site for the demanded
    # SKU, plus unmet slack, must cover the quantity.
    D = Demand.ref()
    Op = Operation.ref()
    B = Business.ref()
    problem.satisfy(
        model.require(
            sum(Op.x_flow).per(D) + D.x_unmet >= D.quantity
        ).where(
            D.business(B),
            B.site == Op.output_site,
            D.sku == Op.output_sku,
        ),
        name=["demand_sat", D.id],
    )

    if block_watch_level:
        # Constraint: block operations sourced from watch-level businesses (a strict
        # superset of the avoid businesses).
        biz_block = Business.ref()
        op_block = Operation.ref()
        problem.satisfy(
            model.require(op_block.x_flow == 0).where(
                op_block.source_business(biz_block),
                biz_block.is_watch_level(),
            ),
            name=["block_watch", op_block.id],
        )
    else:
        # Constraint: block operations sourced from "avoid" businesses, read
        # directly from the ontology Business.is_avoid() Relationship.
        biz_avoid = Business.ref()
        op_avoid = Operation.ref()
        problem.satisfy(
            model.require(op_avoid.x_flow == 0).where(
                op_avoid.source_business(biz_avoid),
                biz_avoid.is_avoid(),
            ),
            name=["block_avoid", op_avoid.id],
        )

    # Constraint (scenario): disable operations from the most critical site.
    if exclude_critical_site:
        excl_site = Site.ref()
        op_excl = Operation.ref()
        problem.satisfy(
            model.require(op_excl.x_flow == 0).where(
                op_excl.source_site(excl_site),
                excl_site.is_most_critical(),
            ),
            name=["site_offline", op_excl.id],
        )

    # Objective: minimize transport cost + risk surcharge + centrality penalty
    # + unmet demand penalty.
    transport_cost = sum(Operation.cost_per_unit * Operation.x_flow)

    # Risk surcharge: extra cost for "watch"-level supplier operations
    # (unreliable or high delay risk, but not necessarily blocked).
    op_watch = Operation.ref()
    biz_watch = Business.ref()
    risk_cost = RISK_SURCHARGE * sum(op_watch.x_flow).where(
        op_watch.source_business(biz_watch),
        biz_watch.is_watch_level(),
    )

    # Centrality penalty: discourage over-reliance on bottleneck sites.
    op_cent = Operation.ref()
    site_cent = Site.ref()
    cent_val = Float.ref()
    centrality_cost = CENTRALITY_WEIGHT * sum(
        op_cent.x_flow * cent_val
    ).where(
        op_cent.output_site(site_cent),
        site_cent.centrality(cent_val),
    )

    unmet_cost = UNMET_PENALTY * sum(Demand.x_unmet)

    # The risk sum is empty with no watch-level supplier, and the centrality sum
    # with no operation into a scored site (stores and offices are unscored);
    # `| 0.0` makes an empty sum zero.
    problem.minimize(
        transport_cost + (risk_cost | 0.0) + (centrality_cost | 0.0) + unmet_cost
    )

    # Each refresh of the deployed model runs this solve.
    problem.configure("highs", time_limit_sec=120)

    # The solve's status and objective, which the deployed model publishes for the queries.
    status = model.Relationship(f"{name} solve status is {String:status}")
    cost = model.Relationship(f"{name} total cost is {Float:cost}")
    model.define(status(problem.termination_status()), cost(problem.objective_value()))

    # The solved flows and unmet demand, which the deployed model publishes for the queries.
    routes = model.Relationship(f"{name} routes {Float:flow} on operation {String:operation_id}")
    unmet = model.Relationship(f"{name} leaves {Float:unmet} unmet for demand {String:demand_id}")
    value = Float.ref()
    model.where(flow_var.values(0, value)).define(routes(value, flow_var.operation.id))
    model.where(unmet_var.values(0, value)).define(unmet(value, unmet_var.demand.id))

    # The solve's active flows, unmet orders, and unmet units, which the deployed model
    # publishes for the queries; each is zero when nothing exceeds FLOW_TOLERANCE.
    active_flows = model.Relationship(f"{name} has {Integer:active_flows} active flows")
    unmet_orders = model.Relationship(f"{name} leaves {Integer:unmet_orders} orders unmet")
    unmet_units = model.Relationship(f"{name} leaves {Float:unmet_units} units unmet")
    route_value, route_op = Float.ref(), String.ref()
    unmet_value, unmet_demand = Float.ref(), String.ref()
    model.define(active_flows(
        aggs.count(route_op).where(routes(route_value, route_op), route_value > FLOW_TOLERANCE) | 0
    ))
    model.define(unmet_orders(
        aggs.count(unmet_demand).where(unmet(unmet_value, unmet_demand), unmet_value > FLOW_TOLERANCE)
        | 0
    ))
    model.define(unmet_units(
        aggs.sum(unmet_demand, unmet_value).where(
            unmet(unmet_value, unmet_demand), unmet_value > FLOW_TOLERANCE
        )
        | 0.0
    ))

    return Flow(name, problem, routes, unmet, status, cost, active_flows, unmet_orders, unmet_units)


# Baseline solve: block only "avoid" suppliers (both unreliable AND high delay)
# via the Business.is_avoid() Relationship from the ontology.
baseline = build_flow("supply_chain_resilience_baseline")

# Scenario 1: Take the highest-centrality site offline.
site_offline = build_flow("supply_chain_resilience_site_offline", exclude_critical_site=True)

# Scenario 2: Downgrade all "watch" suppliers to "avoid" — block any
# supplier that is unreliable OR has high delay risk.
watch_avoid = build_flow("supply_chain_resilience_watch_avoid", block_watch_level=True)

# How much more each scenario costs than the baseline, in percent; there is none when
# the baseline cost is zero.
CostChangePct = model.Relationship(
    f"scenario {String:scenario} costs {Float:pct_change} percent more than the baseline"
)
baseline_cost, scenario_cost = Float.ref(), Float.ref()
for scenario in (site_offline, watch_avoid):
    model.where(
        baseline.cost(baseline_cost),
        scenario.cost(scenario_cost),
        baseline_cost != 0,
    ).define(CostChangePct(scenario.name, (scenario_cost - baseline_cost) / baseline_cost * 100))
