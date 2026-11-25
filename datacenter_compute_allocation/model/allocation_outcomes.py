"""Allocation outcomes: each scenario cell's results from the solved assignments, the headline plan
and its chosen assignments, and the plan replayed under demand-risk scenarios."""

from relationalai.semantics import Float, Integer, String, not_, sum
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std import math, strings

from .compute_allocation import WORKLOAD_TYPES, Assignment, SolveStatus
from .schema import DemandScenario, DiversityCap, MarginFloor, PowerEnvelopeLevel, model
from .workload_eligibility import PRIORITY_TIERS

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

# Headline plan cell. The AllocationPlan singleton + Assignment.is_chosen
# flag persist this cell's outcome; tighter cells in the 24-cell sweep
# remain queryable via Assignment.x_assign but are diagnostic overlays
# rather than the operator-facing plan.
CHOSEN_ENVELOPE = "100pct"
CHOSEN_MARGIN = "unconstrained"
CHOSEN_DIVERSITY = "none"
PLAN_ID = "DCCA_BASELINE"

# --------------------------------------------------
# Stage 4 (cont.): Per-cell outcomes + headline-plan persistence
#   One ScenarioCell per (env, mar, div). Its aggregates are computed from the
#   solved Assignment.x_assign values (mirrors energy_grid_planning's
#   InvestmentPortfolio). An infeasible cell has no assignments, so its
#   aggregates have no value. The chosen baseline cell is persisted as an
#   AllocationPlan singleton + Assignment.is_chosen flag + DemandScenario
#   overlay so the plan is queryable as ontology.
# --------------------------------------------------

ScenarioCell = model.Concept(
    "ScenarioCell",
    identify_by={"envelope": PowerEnvelopeLevel, "margin": MarginFloor, "diversity": DiversityCap},
)
ScenarioCell.n_assigned = model.Property(f"{ScenarioCell} has {Integer:n_assigned}")
ScenarioCell.revenue_usd = model.Property(f"{ScenarioCell} has {Float:revenue_usd}")
ScenarioCell.anchor_revenue_usd = model.Property(f"{ScenarioCell} has {Float:anchor_revenue_usd}")
ScenarioCell.energy_cost_usd = model.Property(f"{ScenarioCell} has {Float:energy_cost_usd}")
ScenarioCell.dep_cost_usd = model.Property(f"{ScenarioCell} has {Float:dep_cost_usd}")
ScenarioCell.total_cost_usd = model.Property(f"{ScenarioCell} has {Float:total_cost_usd}")
ScenarioCell.realized_margin = model.Property(f"{ScenarioCell} has {Float:realized_margin}")
ScenarioCell.anchor_share = model.Property(f"{ScenarioCell} has {Float:anchor_share}")
ScenarioCell.n_by_type = model.Relationship(
    f"{ScenarioCell} has {String:workload_type} workload count {Integer:n}"
)
ScenarioCell.n_by_tier = model.Relationship(
    f"{ScenarioCell} has {String:priority_tier} workload count {Integer:n}"
)
ScenarioCell.status = model.Property(f"{ScenarioCell} has status {String:status}")

model.define(ScenarioCell.new(
    envelope=PowerEnvelopeLevel, margin=MarginFloor, diversity=DiversityCap,
))

xq = Float.ref("xq")


def _assigned_in_cell():
    """Conditions selecting the Assignments the solve placed in ScenarioCell."""
    return (
        Assignment.x_assign(ScenarioCell.envelope, ScenarioCell.margin, ScenarioCell.diversity, xq),
        xq > 0.5,
    )


model.define(ScenarioCell.n_assigned(
    aggs.count(Assignment).where(*_assigned_in_cell()).per(ScenarioCell) | 0
))
model.define(ScenarioCell.revenue_usd(
    sum(Assignment, Assignment.workload.strategic_value_usd)
    .where(*_assigned_in_cell()).per(ScenarioCell) | 0.0
))
model.define(ScenarioCell.anchor_revenue_usd(
    sum(Assignment, Assignment.workload.strategic_value_usd)
    .where(*_assigned_in_cell(), Assignment.workload.lab.is_strategic_anchor == True)
    .per(ScenarioCell) | 0.0
))
model.define(ScenarioCell.energy_cost_usd(
    sum(Assignment,
        Assignment.workload.gpu_count_required
        * Assignment.workload.duration_hours
        * Assignment.gpu_pool.power_per_gpu_kw
        * Assignment.gpu_pool.data_center.pue
        * Assignment.gpu_pool.data_center.dollars_per_mwh / 1000.0)
    .where(*_assigned_in_cell()).per(ScenarioCell) | 0.0
))
model.define(ScenarioCell.dep_cost_usd(
    sum(Assignment,
        Assignment.workload.gpu_count_required
        * Assignment.workload.duration_hours
        * Assignment.gpu_pool.hourly_depreciation_rate)
    .where(*_assigned_in_cell()).per(ScenarioCell) | 0.0
))
model.define(ScenarioCell.total_cost_usd(ScenarioCell.energy_cost_usd + ScenarioCell.dep_cost_usd))
# A cell with no revenue has no margin or anchor share.
model.where(ScenarioCell.revenue_usd > 0).define(
    ScenarioCell.realized_margin(
        (ScenarioCell.revenue_usd - ScenarioCell.total_cost_usd) / ScenarioCell.revenue_usd
    ),
    ScenarioCell.anchor_share(ScenarioCell.anchor_revenue_usd / ScenarioCell.revenue_usd),
)

# Per-(cell, workload_type) and per-(cell, priority_tier) counts, zero for a kind with no
# assignment in the cell.
for workload_type in WORKLOAD_TYPES:
    model.define(ScenarioCell.n_by_type(
        workload_type,
        aggs.count(Assignment)
        .where(*_assigned_in_cell(), Assignment.workload.workload_type == workload_type)
        .per(ScenarioCell) | 0,
    ))
for priority_tier in PRIORITY_TIERS:
    model.define(ScenarioCell.n_by_tier(
        priority_tier,
        aggs.count(Assignment)
        .where(*_assigned_in_cell(), Assignment.workload.priority_tier == priority_tier)
        .per(ScenarioCell) | 0,
    ))

# Per-cell status: when the global solve proved optimality, cells with
# assignments are OPTIMAL and cells with none are INFEASIBLE. When the
# wall-clock ran out first, they are FEASIBLE and UNSOLVED.
solve_status = String.ref()
model.where(
    SolveStatus(solve_status), solve_status == "OPTIMAL", ScenarioCell.n_assigned > 0
).define(ScenarioCell.status("OPTIMAL"))
model.where(
    SolveStatus(solve_status), solve_status == "OPTIMAL", not_(ScenarioCell.n_assigned > 0)
).define(ScenarioCell.status("INFEASIBLE"))
model.where(
    SolveStatus(solve_status), solve_status != "OPTIMAL", ScenarioCell.n_assigned > 0
).define(ScenarioCell.status("FEASIBLE"))
model.where(
    SolveStatus(solve_status), solve_status != "OPTIMAL", not_(ScenarioCell.n_assigned > 0)
).define(ScenarioCell.status("UNSOLVED"))

# Cells per status label.
CellStatusCount = model.Relationship(
    f"{Integer:n_cells} scenario cells have status {String:status}"
)
_status = String.ref()
model.where(ScenarioCell.status == _status).define(
    CellStatusCount(aggs.count(ScenarioCell).per(_status), _status)
)

# The two one-axis sweeps through the headline plan's power envelope: the cells that vary the
# margin floor at the headline diversity cap, and the cells that vary the diversity cap at the
# headline margin floor.
ScenarioCell.in_margin_sweep = model.Relationship(f"{ScenarioCell} is in the margin-floor sweep")
ScenarioCell.in_diversity_sweep = model.Relationship(
    f"{ScenarioCell} is in the diversity-cap sweep"
)
model.where(
    ScenarioCell.envelope.name == CHOSEN_ENVELOPE,
    ScenarioCell.diversity.name == CHOSEN_DIVERSITY,
).define(ScenarioCell.in_margin_sweep())
model.where(
    ScenarioCell.envelope.name == CHOSEN_ENVELOPE,
    ScenarioCell.margin.name == CHOSEN_MARGIN,
).define(ScenarioCell.in_diversity_sweep())

# AllocationPlan is a singleton holding the operator-facing summary
# (revenue, cost, anchor share, n_assigned, status, binding axis) for
# the chosen cell; Assignment.is_chosen narrows the per-cell decision
# rows to the chosen scenario. Mirrors the telco_network_recovery
# RestorePlan / is_selected_upgrade pattern.
AllocationPlan = model.Concept("AllocationPlan", identify_by={"id": String})
AllocationPlan.chosen_envelope = model.Property(
    f"{AllocationPlan} has chosen envelope {String:chosen_envelope}"
)
AllocationPlan.chosen_margin = model.Property(
    f"{AllocationPlan} has chosen margin {String:chosen_margin}"
)
AllocationPlan.chosen_diversity = model.Property(
    f"{AllocationPlan} has chosen diversity {String:chosen_diversity}"
)
AllocationPlan.n_assigned = model.Property(f"{AllocationPlan} has {Integer:n_assigned}")
AllocationPlan.revenue_usd = model.Property(f"{AllocationPlan} has {Float:revenue_usd}")
AllocationPlan.total_cost_usd = model.Property(
    f"{AllocationPlan} has {Float:total_cost_usd}"
)
AllocationPlan.realized_margin = model.Property(
    f"{AllocationPlan} has {Float:realized_margin}"
)
AllocationPlan.anchor_share = model.Property(f"{AllocationPlan} has {Float:anchor_share}")
AllocationPlan.status = model.Property(f"{AllocationPlan} has status {String:status}")
AllocationPlan.binding_axis = model.Property(
    f"{AllocationPlan} has binding axis {String:binding_axis}"
)

model.define(AllocationPlan.new(id=PLAN_ID))
chosen_cell = (
    AllocationPlan.id == PLAN_ID,
    ScenarioCell.envelope.name == CHOSEN_ENVELOPE,
    ScenarioCell.margin.name == CHOSEN_MARGIN,
    ScenarioCell.diversity.name == CHOSEN_DIVERSITY,
)
model.where(*chosen_cell).define(
    AllocationPlan.chosen_envelope(CHOSEN_ENVELOPE),
    AllocationPlan.chosen_margin(CHOSEN_MARGIN),
    AllocationPlan.chosen_diversity(CHOSEN_DIVERSITY),
)
model.where(*chosen_cell).define(AllocationPlan.n_assigned(ScenarioCell.n_assigned))
model.where(*chosen_cell).define(AllocationPlan.revenue_usd(ScenarioCell.revenue_usd))
model.where(*chosen_cell).define(AllocationPlan.total_cost_usd(ScenarioCell.total_cost_usd))
model.where(*chosen_cell).define(AllocationPlan.realized_margin(ScenarioCell.realized_margin))
model.where(*chosen_cell).define(AllocationPlan.anchor_share(ScenarioCell.anchor_share))
model.where(*chosen_cell).define(AllocationPlan.status(ScenarioCell.status))
model.where(*chosen_cell, ScenarioCell.n_assigned > 0).define(
    AllocationPlan.binding_axis("power_envelope")
)
model.where(*chosen_cell, not_(ScenarioCell.n_assigned > 0)).define(
    AllocationPlan.binding_axis(strings.lower(ScenarioCell.status))
)

Assignment.is_chosen = model.Relationship(f"{Assignment} is in chosen cell")
xc = Float.ref("xc")
chosen_env_c = PowerEnvelopeLevel.lookup(name=CHOSEN_ENVELOPE)
chosen_mar_c = MarginFloor.lookup(name=CHOSEN_MARGIN)
chosen_div_c = DiversityCap.lookup(name=CHOSEN_DIVERSITY)
model.where(
    Assignment.x_assign(chosen_env_c, chosen_mar_c, chosen_div_c, xc),
    xc > 0.5,
).define(Assignment.is_chosen())

# DemandScenario overlay: stranded-capacity exposure under risk.
# The chosen plan is locked in, but lab-side demand for the assigned
# workloads can soften from the GNN's point forecast. P0 revenue is
# contractual (factor = 1.0); P1/P2 realize only `factor`. The delta
# is stranded capacity: GPUs powered, depreciation accruing, no workload.
DemandScenarioOutlook = model.Concept(
    "DemandScenarioOutlook",
    identify_by={"scenario": DemandScenario},
)
DemandScenarioOutlook.realized_revenue_usd = model.Property(
    f"{DemandScenarioOutlook} has {Float:realized_revenue_usd}"
)
DemandScenarioOutlook.stranded_revenue_usd = model.Property(
    f"{DemandScenarioOutlook} has {Float:stranded_revenue_usd}"
)
DemandScenarioOutlook.stranded_share = model.Property(
    f"{DemandScenarioOutlook} has {Float:stranded_share}"
)
model.define(DemandScenarioOutlook.new(scenario=DemandScenario))

p0_revenue = sum(Assignment, Assignment.workload.strategic_value_usd).where(
    Assignment.is_chosen(), Assignment.workload.priority_tier == "P0"
) | 0.0
other_revenue = sum(Assignment, Assignment.workload.strategic_value_usd).where(
    Assignment.is_chosen(), Assignment.workload.priority_tier != "P0"
) | 0.0
model.where(DemandScenarioOutlook.scenario == DemandScenario).define(
    DemandScenarioOutlook.realized_revenue_usd(p0_revenue + other_revenue * DemandScenario.factor)
)
model.where(AllocationPlan.id == PLAN_ID).define(
    DemandScenarioOutlook.stranded_revenue_usd(
        math.maximum(AllocationPlan.revenue_usd - DemandScenarioOutlook.realized_revenue_usd, 0.0)
    )
)

# The stranded share of the chosen plan's revenue, zero for a plan without revenue.
model.where(AllocationPlan.id == PLAN_ID, AllocationPlan.revenue_usd > 0).define(
    DemandScenarioOutlook.stranded_share(
        DemandScenarioOutlook.stranded_revenue_usd / AllocationPlan.revenue_usd
    )
)
model.where(AllocationPlan.id == PLAN_ID, not_(AllocationPlan.revenue_usd > 0)).define(
    DemandScenarioOutlook.stranded_share(0.0)
)
