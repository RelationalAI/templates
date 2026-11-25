"""Datacenter compute allocation (multi-reasoner) template: the model.

Inside-the-fence GPU allocation: assigns AI lab workloads (pretrains,
finetunes, inference, evals) to GPU pools across 5 hyperscaler campuses
that a prior interconnection-planning step (see `energy_grid_planning`)
has approved and energized. The bundled `data_centers.csv` is a snapshot
of that approved campus set at a $300M investment level; this template
demonstrates the operator-side allocation decision that picks up after.

Four reasoner stages on a shared ontology, in five modules, each of which
imports the modules whose declarations it reads:

  Stage 1 -- Predictive: heterogeneous-graph GNN binary-classifies per-workload
             utilization probability (will this workload actually use its
             allocated capacity at high duty cycle, or stall / be repaced?)
             (`utilization_forecast.py`).
  Stage 2 -- Rules: hardware compatibility (memory + GPU type allowlist) +
             priority-tier classification (P0/P1/P2 from contract_tier).
             Populates Compatibility(workload, gpu_pool)
             (`workload_eligibility.py`).
  Stage 3 -- Graph: reverse-PageRank on the WorkloadDependency.blocks DAG
             writes Workload.gating_score (frontier pretrains gating long
             chains land high; isolated inference workloads land at baseline)
             (`gating_scores.py`).
  Stage 4 -- Prescriptive MIP: assigns workloads under power, GPU-count,
             gross-margin-floor, and anchor-concentration-cap constraints,
             across a scenario sweep (PowerEnvelopeLevel x MarginFloor x
             DiversityCap = 2 x 3 x 4 = 24 cells). Maximizes a four-factor strategic
             value: priority * gating * utilization_probability * strategic_value_usd,
             amplified by (1 + under_provisioning_penalty) for asymmetric
             failure-mode pricing (`compute_allocation.py`).

The headline plan persists as an AllocationPlan singleton plus an
Assignment.is_chosen unary Relationship over the chosen-cell decision rows, the
24 cells as ScenarioCell rows, and the demand overlay as a DemandScenarioOutlook
per scenario -- all queryable as ontology (`allocation_outcomes.py`).

Run:
    `rai models deploy --path model` deploys this package to the schemas in
    raiconfig.yaml, and `python train.py` trains and registers the GNN. After a
    refresh, `python -m queries.allocation_report` prints the per-stage
    diagnostics, the per-cell summary, two Pareto frontiers, and the demand overlay.
"""

from .allocation_outcomes import (
    CHOSEN_DIVERSITY,
    CHOSEN_ENVELOPE,
    CHOSEN_MARGIN,
    AllocationPlan,
    CellStatusCount,
    DemandScenarioOutlook,
    ScenarioCell,
)
from .compute_allocation import (
    WORKLOAD_TYPES,
    Assignment,
    SolveObjective,
    SolveStatus,
    SolveTime,
    problem,
)
from .schema import (
    AILab,
    DataCenterRequest,
    DemandScenario,
    DiversityCap,
    GpuPool,
    MarginFloor,
    PowerEnvelopeLevel,
    Workload,
    WorkloadDependency,
    model,
)
from .source import DATA_DIR
from .utilization_forecast import HIGH_UTILIZATION, UtilizationSplit, WorkloadForecast, gnn
from .workload_eligibility import PRIORITY_TIERS, Compatibility, PriorityTierCount

__all__ = [
    "CHOSEN_DIVERSITY",
    "CHOSEN_ENVELOPE",
    "CHOSEN_MARGIN",
    "DATA_DIR",
    "HIGH_UTILIZATION",
    "PRIORITY_TIERS",
    "WORKLOAD_TYPES",
    "AILab",
    "AllocationPlan",
    "Assignment",
    "CellStatusCount",
    "Compatibility",
    "DataCenterRequest",
    "DemandScenario",
    "DemandScenarioOutlook",
    "DiversityCap",
    "GpuPool",
    "MarginFloor",
    "PowerEnvelopeLevel",
    "PriorityTierCount",
    "ScenarioCell",
    "SolveObjective",
    "SolveStatus",
    "SolveTime",
    "UtilizationSplit",
    "Workload",
    "WorkloadDependency",
    "WorkloadForecast",
    "gnn",
    "model",
    "problem",
]
