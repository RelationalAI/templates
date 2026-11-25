"""Investment solve: the joint data center approval and substation upgrade problem, solved once for all
investment levels, and its status and objective."""

from relationalai.semantics import Float, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

# Declares Substation.predicted_load, the load the capacity constraint reads.
from . import load_forecast  # noqa: F401
from .schema import (
    DataCenterRequest,
    InvestmentLevel,
    Substation,
    SubstationUpgrade,
    model,
)

# --------------------------------------------------
# Stage 5: Optimize -- Joint DC Approval + Grid Upgrade
#   Accretive chain: the capacity constraint uses predicted_load from Stage 1
#   (via the | fallback pattern), matching the rules engine. All solve results
#   (x_approve, x_upgrade per InvestmentLevel) are written to the ontology —
#   queryable via model.select(), not parsed from solver output.
#   One solve across 5 InvestmentLevel scenarios produces the Pareto frontier.
# --------------------------------------------------

# Annual revenue of a request if approved: its megawatts times its revenue per megawatt. The objective
# and each portfolio's revenue read it.
DataCenterRequest.annual_revenue = model.Property(f"{DataCenterRequest} earns {Float:annual_revenue} a year")
model.define(
    DataCenterRequest.annual_revenue(DataCenterRequest.requested_mw * DataCenterRequest.annual_revenue_per_mw)
)

# Decision variables indexed by InvestmentLevel
DataCenterRequest.x_approve = model.Property(
    f"{DataCenterRequest} in {InvestmentLevel} has {Float:x_approve}"
)
SubstationUpgrade.x_upgrade = model.Property(
    f"{SubstationUpgrade} in {InvestmentLevel} has {Float:x_upgrade}"
)

# Float refs for variable binding in constraints/objective
x_a = Float.ref("xa")
x_u = Float.ref("xu")

# Refs for aggregation joins
DCRef = DataCenterRequest.ref()
UpgRef = SubstationUpgrade.ref()

# Problem formulation
problem = Problem(model, Float, name="energy_grid_planning")

problem.solve_for(DataCenterRequest.x_approve(InvestmentLevel, x_a), type="bin",
            name=["approve", InvestmentLevel.name, DataCenterRequest.id])
problem.solve_for(SubstationUpgrade.x_upgrade(InvestmentLevel, x_u), type="bin",
            name=["upgrade", InvestmentLevel.name, SubstationUpgrade.id])

# C1: Substation capacity per investment level
# Uses predicted_load from Stage 1 (with current_load fallback) — the accretive chain.
x_a_c = Float.ref("xa_c")
x_u_c = Float.ref("xu_c")
effective_load = Substation.predicted_load | Substation.current_load_mw

# Each upgrade's capacity and each request's MW is weighted by its own variable.
# A substation with no upgrade options adds no capacity (`| 0.0`).
problem.satisfy(
    model.where(
        InvestmentLevel,
        DataCenterRequest.substation(Substation),
    ).require(
        Substation.max_capacity_mw
        - effective_load
        + (
            sum(UpgRef, x_u_c * UpgRef.capacity_increase_mw)
            .where(
                UpgRef.substation == Substation,
                UpgRef.x_upgrade(InvestmentLevel, x_u_c),
            )
            .per(Substation, InvestmentLevel)
            | 0.0
        )
        >= sum(DCRef, x_a_c * DCRef.requested_mw)
        .where(
            DCRef.substation == Substation,
            DCRef.x_approve(InvestmentLevel, x_a_c),
        )
        .per(Substation, InvestmentLevel)
    )
)

# C2: Budget per investment level
problem.satisfy(model.where(
    SubstationUpgrade.x_upgrade(InvestmentLevel, x_u),
).require(
    sum(x_u * SubstationUpgrade.cost_million).per(InvestmentLevel) <= InvestmentLevel.budget_cap
))

# Objective: maximize total DC revenue across all levels
problem.maximize(
    sum(InvestmentLevel, x_a * DataCenterRequest.annual_revenue).where(
        DataCenterRequest.x_approve(InvestmentLevel, x_a)
    )
)

# Each refresh of the deployed model runs this solve (one solve for all levels).
problem.configure("highs", time_limit_sec=120)

# The solve's status and objective, which the deployed model publishes for the queries.
SolveStatus = model.Relationship(f"energy grid solve status is {String:status}")
SolveObjective = model.Relationship(f"energy grid solve objective is {Float:objective}")
model.define(SolveStatus(problem.termination_status()), SolveObjective(problem.objective_value()))
