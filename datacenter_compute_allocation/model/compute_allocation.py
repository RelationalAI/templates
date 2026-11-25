"""Compute allocation: the allocation MIP that assigns workloads to GPU pools across the 24-cell
scenario sweep, and the solve's status, time and objective."""

from relationalai.semantics import Float, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

# Declares Workload.gating_score, the gating scores the objective reads.
from . import gating_scores  # noqa: F401
from .schema import (
    DataCenterRequest,
    DiversityCap,
    GpuPool,
    MarginFloor,
    PowerEnvelopeLevel,
    Workload,
    model,
)
from .utilization_forecast import WorkloadForecast
from .workload_eligibility import Compatibility

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

# Solver. HiGHS is the open-source default that ships with the
# prescriptive engine; switch to "gurobi" if your engine has a Gurobi
# license (faster convergence, tighter MIP gaps on the 24-cell sweep).
SOLVER = "highs"
SOLVER_TIME_LIMIT_SEC = 240

# The workload types the per-type floor (C7) and the per-cell type counts range over.
WORKLOAD_TYPES = ("pretrain", "finetune", "inference", "eval")

# --------------------------------------------------
# Stage 4: Prescriptive -- compute allocation MIP (24-cell sweep)
#   Decision variable: Assignment.x_assign(PowerEnvelopeLevel, MarginFloor,
#                      DiversityCap), binary. One per (Workload, GpuPool)
#                      in Compatibility, per scenario cell.
#
#   Constraints:
#     C1+C2 -- At most one assignment per workload per cell, P0 included:
#              priority_weight=100 in the objective weights P0 workloads
#              heavily but does not force them in, so a P0 workload left
#              unassigned in a cell is a diagnostic signal.
#     C3    -- Per-pool GPU-count capacity.
#     C4    -- Per-DC power envelope: gpu_count * power_per_gpu * pue <=
#              approved_mw * 1000 * envelope_multiplier.
#     C5    -- Gross-margin floor (linearized; skipped when fraction < 0).
#     C6    -- Anchor concentration cap (skipped when share < 0).
#     C7    -- Workload-type floor (one per type; skipped when floor < 0).
#
#   Objective: maximize sum over assignments of
#       priority_weight * gating_score * utilization_probability *
#       strategic_value_usd * (1 + under_provisioning_penalty)
# --------------------------------------------------

# Decision variable: Assignment indexed by the three scenario axes. A
# workload is assignable once it has a utilization forecast.
Assignment = model.Concept(
    "Assignment",
    identify_by={"workload": Workload, "gpu_pool": GpuPool},
)
model.define(
    Assignment.new(workload=Compatibility.workload, gpu_pool=Compatibility.gpu_pool)
).where(WorkloadForecast.workload_id == Compatibility.workload.id)

Assignment.x_assign = model.Property(
    f"{Assignment} per {PowerEnvelopeLevel} per {MarginFloor} per {DiversityCap} "
    f"assigned {Float:x_assign}"
)

problem = Problem(model, Float, name="datacenter_compute_allocation")

# Bind the decision variable. The Float ref pattern (mirrors upstream
# energy_grid_planning's x_a / x_u) lets constraints and objective
# reference the variable's value via the bound Float ref inside arithmetic.
x = Float.ref("x")
problem.solve_for(
    Assignment.x_assign(PowerEnvelopeLevel, MarginFloor, DiversityCap, x),
    type="bin",
    name=["assign", PowerEnvelopeLevel.name, MarginFloor.name, DiversityCap.name,
          Assignment.workload.id, Assignment.gpu_pool.id],
)

# C1+C2: at most one assignment per workload per cell
x2 = Float.ref()
Wany = Workload.ref()
problem.satisfy(model.where(
    Assignment.x_assign(PowerEnvelopeLevel, MarginFloor, DiversityCap, x2),
    Assignment.workload == Wany,
).require(
    sum(Assignment, x2).per(Wany, PowerEnvelopeLevel, MarginFloor, DiversityCap) <= 1.0
))

# C3: per-pool GPU count capacity
x3 = Float.ref()
G = GpuPool.ref()
problem.satisfy(model.where(
    Assignment.x_assign(PowerEnvelopeLevel, MarginFloor, DiversityCap, x3),
    Assignment.gpu_pool == G,
).require(
    sum(x3 * Assignment.workload.gpu_count_required)
        .per(G, PowerEnvelopeLevel, MarginFloor, DiversityCap)
    <= G.available_gpu_count
))

# C4: per-DC power envelope
x4 = Float.ref()
DC = DataCenterRequest.ref()
problem.satisfy(model.where(
    Assignment.x_assign(PowerEnvelopeLevel, MarginFloor, DiversityCap, x4),
    Assignment.gpu_pool.data_center == DC,
).require(
    sum(x4
        * Assignment.workload.gpu_count_required
        * Assignment.gpu_pool.power_per_gpu_kw
        * DC.pue)
        .per(DC, PowerEnvelopeLevel, MarginFloor, DiversityCap)
    <= DC.approved_mw * 1000.0 * PowerEnvelopeLevel.envelope_multiplier
))

# C5: gross-margin floor (linearized; skipped when fraction < 0)
# revenue * (1 - fraction) >= total_cost
# total_cost = energy_cost + depreciation_cost  (per workload, per duration)
# Energy alone clears at ~99% margin; depreciation is the SemiAnalysis
# 14-16% net BMaaS pressure source.
x5 = Float.ref()
problem.satisfy(model.where(
    Assignment.x_assign(PowerEnvelopeLevel, MarginFloor, DiversityCap, x5),
    MarginFloor.fraction >= 0.0,
).require(
    sum(x5 * Assignment.workload.strategic_value_usd
            * (1.0 - MarginFloor.fraction))
        .per(PowerEnvelopeLevel, MarginFloor, DiversityCap)
    >= sum(x5 * Assignment.workload.gpu_count_required
              * Assignment.workload.duration_hours
              * (Assignment.gpu_pool.power_per_gpu_kw
                   * Assignment.gpu_pool.data_center.pue
                   * Assignment.gpu_pool.data_center.dollars_per_mwh / 1000.0
                 + Assignment.gpu_pool.hourly_depreciation_rate))
        .per(PowerEnvelopeLevel, MarginFloor, DiversityCap)
))

# C6: anchor concentration cap (skipped when share < 0)
x6 = Float.ref()
problem.satisfy(model.where(
    Assignment.x_assign(PowerEnvelopeLevel, MarginFloor, DiversityCap, x6),
    DiversityCap.anchor_max_share >= 0.0,
).require(
    sum(x6 * Assignment.workload.strategic_value_usd)
        .where(Assignment.workload.lab.is_strategic_anchor == True)
        .per(PowerEnvelopeLevel, MarginFloor, DiversityCap)
    <= DiversityCap.anchor_max_share
        * sum(x6 * Assignment.workload.strategic_value_usd)
            .per(PowerEnvelopeLevel, MarginFloor, DiversityCap)
))

# C7: workload-type floor (one constraint per type; skipped when floor < 0)
for wt in WORKLOAD_TYPES:
    x7 = Float.ref()
    problem.satisfy(model.where(
        Assignment.x_assign(PowerEnvelopeLevel, MarginFloor, DiversityCap, x7),
        DiversityCap.workload_type_floor >= 0.0,
    ).require(
        sum(Assignment, x7)
            .where(Assignment.workload.workload_type == wt)
            .per(PowerEnvelopeLevel, MarginFloor, DiversityCap)
        >= DiversityCap.workload_type_floor
            * sum(Assignment, x7).per(PowerEnvelopeLevel, MarginFloor, DiversityCap)
    ))

# Objective: four-factor strategic value, amplified by under-provisioning penalty
# The (1 + under_provisioning_penalty) multiplier captures asymmetric failure modes:
# an unfilled anchor seat (P0) costs more than the foregone revenue, while an
# unfilled research eval costs only the revenue. P0 = 1.0 (2x amp), P1 = 0.3, P2 = 0.0.
x_obj = Float.ref()
problem.maximize(
    sum(PowerEnvelopeLevel, MarginFloor, DiversityCap,
        x_obj
        * Assignment.workload.priority_weight
        * Assignment.workload.gating_score
        * WorkloadForecast.utilization_probability
        * Assignment.workload.strategic_value_usd
        * (1.0 + Assignment.workload.under_provisioning_penalty))
    .where(
        Assignment.x_assign(PowerEnvelopeLevel, MarginFloor, DiversityCap, x_obj),
        WorkloadForecast.workload_id == Assignment.workload.id,
    )
)

# Each refresh of the deployed model runs this solve.
problem.configure(SOLVER, time_limit_sec=SOLVER_TIME_LIMIT_SEC)

# The solve's status, time and objective, which the deployed model publishes for the queries.
SolveStatus = model.Relationship(f"datacenter allocation solve status is {String:status}")
SolveTime = model.Relationship(f"datacenter allocation solve time is {Float:seconds}")
SolveObjective = model.Relationship(f"datacenter allocation objective is {Float:objective}")
model.define(
    SolveStatus(problem.termination_status()),
    SolveTime(problem.solve_time_sec()),
    SolveObjective(problem.objective_value()),
)
