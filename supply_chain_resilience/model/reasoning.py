"""Supply chain reasoning: dependency graphs, supplier risk rules, and risk-adjusted network flow problems."""

from typing import Any, NamedTuple

from relationalai.semantics import Float, Integer, String, sum
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.std import aggregates as aggs

from .schema import (
    Business,
    DelayPrediction,
    Demand,
    Operation,
    Shipment,
    Site,
    model,
)

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

UNMET_PENALTY = 100.0  # penalty for unmet demand (kept moderate so routing costs are visible)
RISK_SURCHARGE = 5.0  # cost multiplier for "watch" supplier operations
CENTRALITY_WEIGHT = 2.0  # multiplier for bottleneck site penalty
DELAY_PROB_THRESHOLD = 0.15  # above this = high delay risk
RELIABILITY_THRESHOLD = 0.80  # below this = unreliable supplier
PREDICTION_QUARTER = "Q1-2025"  # which quarter's predictions to use

# Derived relationship: Operation's source business (via shared site).
Operation.source_business = model.Relationship(
    f"{Operation} sourced from {Business}"
)
model.define(Operation.source_business(Operation, Business)).where(
    Operation.source_site == Business.site
)

# Derived ships_to: supplier -> customer (collapses many shipments into edges).
Business.ships_to = model.Relationship(
    f"{Business:supplier} ships to {Business:customer}"
)
b_from, b_to = Business.ref(), Business.ref()
model.define(Business.ships_to(b_from, b_to)).where(
    Shipment.supplier(b_from),
    Shipment.customer(b_to),
)

# Flag businesses that hold at least one HIGH-priority demand — they are
# the customers whose blast-radius we care about most.
Business.is_high_priority_customer = model.Relationship(
    f"{Business} is a high-priority customer"
)
model.where(
    Demand.business(Business),
    Demand.priority == "HIGH",
).define(Business.is_high_priority_customer())

# --------------------------------------------------
# Stage 0: Blast-radius pre-analysis (directed Business graph)
# --------------------------------------------------
# Trace every supplier each high-priority customer transitively depends on.
# This surfaces the exposure footprint BEFORE the MILP runs, so the
# scenario analysis in Stage 3 can be read in context: "if supplier X is
# downgraded, the optimizer is rerouting around the demands listed here."

biz_graph = Graph(model, directed=True, weighted=False, node_concept=Business, name="business_graph")
b_src, b_dst = Business.ref(), Business.ref()
model.where(Business.ships_to(b_src, b_dst)).define(
    biz_graph.Edge.new(src=b_src, dst=b_dst)
)

# The business graph's size, which the deployed model publishes for the queries.
biz_node_count, biz_edge_count = Integer.ref(), Integer.ref()
biz_num_nodes = model.Relationship(f"the business graph has {Integer:num_nodes} nodes")
biz_num_edges = model.Relationship(f"the business graph has {Integer:num_edges} edges")
model.where(biz_graph.num_nodes()(biz_node_count)).define(biz_num_nodes(biz_node_count))
model.where(biz_graph.num_edges()(biz_edge_count)).define(biz_num_edges(biz_edge_count))

# Upstream reachability: which suppliers do high-priority customers depend on?
target_customer = model.Relationship(f"target customer {Business}")
model.where(Business.is_high_priority_customer()).define(target_customer(Business))

reachable_to = biz_graph.reachable(to=target_customer)
# Attach it to Business, so the deployed model publishes it for the queries.
Business.reaches_target_customer = reachable_to

# --------------------------------------------------
# Stage 1: Graph -- network criticality
# --------------------------------------------------

# Build undirected unweighted graph: Sites as nodes, SHIP operations as edges.
graph = Graph(
    model, directed=False, weighted=False, node_concept=Site, aggregator="sum", name="shipping_network"
)

s1, s2, op_ref = Site.ref(), Site.ref(), Operation.ref()
model.define(
    graph.Edge.new(src=s1, dst=s2)
).where(
    op_ref.source_site(s1),
    op_ref.output_site(s2),
    op_ref.op_type == "SHIP",
)

# The site graph's size, which the deployed model publishes for the queries.
node_count, edge_count = Integer.ref(), Integer.ref()
num_nodes = model.Relationship(f"the site graph has {Integer:num_nodes} nodes")
num_edges = model.Relationship(f"the site graph has {Integer:num_edges} edges")
model.where(graph.num_nodes()(node_count)).define(num_nodes(node_count))
model.where(graph.num_edges()(edge_count)).define(num_edges(edge_count))

# Weakly connected components.
wcc = graph.weakly_connected_component()

# Eigenvector centrality: identify most critical sites.
eigenvector = graph.eigenvector_centrality()

# Attach both results to Site, so the deployed model publishes them for the queries.
Site.component = wcc
Site.eigenvector_centrality = eigenvector

# Store centrality on Site for use in optimization objective: the eigenvector score
# of each site other than stores and offices, divided by the largest such score. When
# the largest score is 0, every score is 0 and is kept as is.
Site.centrality = model.Property(f"{Site} has centrality {Float:centrality}")
MaxCentrality = model.Relationship(f"max eigenvector centrality is {Float:max_score}")
site_max, score_max = Site.ref(), Float.ref()
model.define(MaxCentrality(aggs.max(score_max))).where(
    eigenvector(site_max, score_max),
    site_max.site_type != "STORE",
    site_max.site_type != "OFFICE",
)
site_eig, score_eig, max_score = Site.ref(), Float.ref(), Float.ref()
model.where(
    eigenvector(site_eig, score_eig),
    site_eig.site_type != "STORE",
    site_eig.site_type != "OFFICE",
    MaxCentrality(max_score),
    max_score > 0,
).define(site_eig.centrality(score_eig / max_score))
model.where(
    eigenvector(site_eig, score_eig),
    site_eig.site_type != "STORE",
    site_eig.site_type != "OFFICE",
    MaxCentrality(0.0),
).define(site_eig.centrality(score_eig))

# The site with the highest centrality, the lowest ID among ties; the site-offline
# scenario takes this one site offline.
MostCriticalSiteId = model.Relationship(f"the most critical site has id {String:site_id}")
site_top, score_top = Site.ref(), Float.ref()
model.define(MostCriticalSiteId(aggs.min(site_top.id))).where(
    eigenvector(site_top, score_top),
    site_top.site_type != "STORE",
    site_top.site_type != "OFFICE",
    MaxCentrality(score_top),
)
Site.is_most_critical = model.Relationship(f"{Site} is the most critical site")
model.where(MostCriticalSiteId(Site.id)).define(Site.is_most_critical())

# --------------------------------------------------
# Stage 2: Rules -- supplier risk classification
# --------------------------------------------------

# Rule 2: Business is unreliable when reliability_score < threshold.
Business.is_unreliable = model.Relationship(f"{Business} is unreliable")
model.where(
    Business.reliability_score < RELIABILITY_THRESHOLD
).define(Business.is_unreliable())

# Rule 3: Business has high delay risk from ML predictions.
Business.has_high_delay_risk = model.Relationship(
    f"{Business} has high delay risk"
)
dp_ref = DelayPrediction.ref()
model.where(
    dp_ref.supplier_business(Business),
    dp_ref.fiscal_quarter == PREDICTION_QUARTER,
    dp_ref.predicted_delay_prob > DELAY_PROB_THRESHOLD,
).define(Business.has_high_delay_risk())

# Rule: Business is watch-level when it has either risk flag.
# "Avoid" businesses (both flags) are hard-blocked in Stage 3; watch-level
# businesses get a soft risk surcharge in the objective.
Business.is_watch_level = model.Relationship(f"{Business} is watch level")
model.where(Business.is_unreliable()).define(Business.is_watch_level())
model.where(Business.has_high_delay_risk()).define(Business.is_watch_level())

# Rule: Business is avoid when BOTH unreliable AND high delay risk fire.
Business.is_avoid = model.Relationship(f"{Business} is avoid")
model.define(Business.is_avoid()).where(
    Business.is_unreliable(),
    Business.has_high_delay_risk(),
)

# Rule 4: Demand is escalated when priority is HIGH.
Demand.is_escalated = model.Relationship(f"{Demand} is escalated")
model.where(Demand.priority == "HIGH").define(Demand.is_escalated())

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

    return Flow(name, problem, routes, unmet, status, cost)


# Baseline solve: block only "avoid" suppliers (both unreliable AND high delay)
# via the Business.is_avoid() Relationship from the ontology.
baseline = build_flow("supply_chain_resilience_baseline")

# Scenario 1: Take the highest-centrality site offline.
site_offline = build_flow("supply_chain_resilience_site_offline", exclude_critical_site=True)

# Scenario 2: Downgrade all "watch" suppliers to "avoid" — block any
# supplier that is unreliable OR has high delay risk.
watch_avoid = build_flow("supply_chain_resilience_watch_avoid", block_watch_level=True)
