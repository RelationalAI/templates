"""Graph analysis of the distribution network, then the inventory allocation problem."""

from relationalai.semantics import Float, String, sum
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.prescriptive import Problem

from .schema import Demand, Property, Route, Site, model

# --------------------------------------------------
# Stage 1: Graph Analysis -- identify critical network hubs
# --------------------------------------------------

graph = Graph(model, directed=False, weighted=True, node_concept=Site, aggregator="sum")

# Build edges from routes (undirected, weighted by capacity)
route_ref = Route.ref()
src, dst = Site.ref(), Site.ref()
model.where(route_ref.source(src), route_ref.dest(dst)).define(
    graph.Edge.new(src=src, dst=dst, weight=route_ref.capacity),
)

# Eigenvector centrality: stored directly on Site (via node_concept)
Site.centrality = graph.eigenvector_centrality()

# --------------------------------------------------
# Stage 1b: Weakly Connected Components -- surface fragmentation
# --------------------------------------------------

# Each site's component, named by one of its sites, which the deployed model publishes for the queries.
wcc = graph.weakly_connected_component()
SiteComponent = model.Relationship(f"{Site} is in the component of {Site:component}")
site_member, site_component = Site.ref(), Site.ref()
model.where(wcc(site_member, site_component)).define(SiteComponent(site_member, site_component))

# --------------------------------------------------
# Stage 1c: Bridge Routes -- cross-region connectors
# --------------------------------------------------
# Routes whose endpoints lie in different regions; losing one of these
# fragments the corresponding inter-region flow.

route_ref = Route.ref()
src, dst = Site.ref(), Site.ref()
Route.is_cross_region = Property(f"{Route} is cross-region {Float:is_cross_region}")
model.where(
    route_ref.source(src),
    route_ref.dest(dst),
    src.region != dst.region,
).define(Route.is_cross_region(route_ref, 1.0))

# --------------------------------------------------
# Stage 2: Prescriptive -- allocate inventory across sites
# --------------------------------------------------
# The centrality property computed by the graph reasoner above is
# referenced directly in the formulation below.

Site.x_inventory = Property(f"{Site} has inventory allocation {Float:x}")

problem = Problem(model, Float, name="warehouse_allocation")
problem.solve_for(Site.x_inventory, lower=0, name=["alloc", Site.name])

TOTAL_BUDGET = 2000  # total units to allocate

# Constraint: total allocation within budget
problem.satisfy(model.require(sum(Site.x_inventory) <= TOTAL_BUDGET))

# Constraint: demand satisfaction at each site
DemandRef = Demand.ref()
site_alloc = sum(Site.x_inventory).where(Site == DemandRef.site).per(DemandRef)
problem.satisfy(model.where(DemandRef).require(site_alloc >= DemandRef.quantity))

# Constraint: critical hubs get minimum allocation proportional to centrality
# Sites with higher centrality are more important to the network and should
# carry proportionally more inventory.
MIN_CENTRALITY_FACTOR = 200
problem.satisfy(model.require(
    Site.x_inventory >= Site.centrality * MIN_CENTRALITY_FACTOR
).where(Site.type("WAREHOUSE")))

# Objective: minimize total holding cost
problem.minimize(sum(Site.x_inventory * Site.holding_cost))

# --------------------------------------------------
# Solve
# --------------------------------------------------

# Each refresh of the deployed model runs the graph analysis, then this solve.
problem.configure("highs", time_limit_sec=60)

# The solve's status and objective, which the deployed model publishes for the queries.
SolveStatus = model.Relationship(f"warehouse allocation solve status is {String:status}")
TotalHoldingCost = model.Relationship(f"warehouse allocation total holding cost is {Float:holding_cost}")
model.define(SolveStatus(problem.termination_status()), TotalHoldingCost(problem.objective_value()))
