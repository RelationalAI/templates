"""Inventory allocation: the linear program that allocates inventory across sites at minimum holding
cost, with a centrality-proportional floor on the warehouses."""

from relationalai.semantics import Float, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

# Declares Site.centrality, the eigenvector centrality the warehouse floors read.
from . import network_analysis  # noqa: F401
from .schema import Demand, Property, Site, model

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
