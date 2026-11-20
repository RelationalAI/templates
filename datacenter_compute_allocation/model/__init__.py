"""Datacenter compute allocation (multi-reasoner) template: the model.

Inside-the-fence GPU allocation: assigns AI lab workloads (pretrains,
finetunes, inference, evals) to GPU pools across 5 hyperscaler campuses
that a prior interconnection-planning step (see `energy_grid_planning`)
has approved and energized. The bundled `data_centers.csv` is a snapshot
of that approved campus set at a $300M investment level; this template
demonstrates the operator-side allocation decision that picks up after.

Four reasoner stages on a shared ontology:

  Stage 1 -- Predictive: heterogeneous-graph GNN binary-classifies per-workload
             utilization probability (will this workload actually use its
             allocated capacity at high duty cycle, or stall / be repaced?).
  Stage 2 -- Rules: hardware compatibility (memory + GPU type allowlist) +
             priority-tier classification (P0/P1/P2 from contract_tier).
             Populates Compatibility(workload, gpu_pool).
  Stage 3 -- Graph: reverse-PageRank on the WorkloadDependency.blocks DAG
             writes Workload.gating_score (frontier pretrains gating long
             chains land high; isolated inference workloads land at baseline).
  Stage 4 -- Prescriptive MIP: assigns workloads under power, GPU-count,
             gross-margin-floor, and anchor-concentration-cap constraints,
             across a scenario sweep (PowerEnvelopeLevel x MarginFloor x
             DiversityCap = 2 x 3 x 4 = 24 cells). Maximizes a four-factor strategic
             value: priority * gating * utilization_probability * strategic_value_usd,
             amplified by (1 + under_provisioning_penalty) for asymmetric
             failure-mode pricing.

The headline plan persists as an AllocationPlan singleton plus an
Assignment.is_chosen unary Relationship over the chosen-cell decision rows, the
24 cells as ScenarioCell rows, and the demand overlay as a DemandScenarioOutlook
per scenario -- all queryable as ontology.

Run:
    `rai models deploy --path model` deploys this package to the schemas in
    raiconfig.yaml, and `python train.py` trains and registers the GNN. After a
    refresh, `python -m queries.allocation_report` prints the per-stage
    diagnostics, the per-cell summary, two Pareto frontiers, and the demand overlay.
"""

from .reasoning import (
    CHOSEN_DIVERSITY,
    CHOSEN_ENVELOPE,
    CHOSEN_MARGIN,
    WORKLOAD_TYPES,
    AllocationPlan,
    Assignment,
    Compatibility,
    DemandScenarioOutlook,
    ScenarioCell,
    SolveObjective,
    SolveStatus,
    SolveTime,
    WorkloadForecast,
    gnn,
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

__all__ = [
    "CHOSEN_DIVERSITY",
    "CHOSEN_ENVELOPE",
    "CHOSEN_MARGIN",
    "DATA_DIR",
    "WORKLOAD_TYPES",
    "AILab",
    "AllocationPlan",
    "Assignment",
    "Compatibility",
    "DataCenterRequest",
    "DemandScenario",
    "DemandScenarioOutlook",
    "DiversityCap",
    "GpuPool",
    "MarginFloor",
    "PowerEnvelopeLevel",
    "ScenarioCell",
    "SolveObjective",
    "SolveStatus",
    "SolveTime",
    "Workload",
    "WorkloadDependency",
    "WorkloadForecast",
    "gnn",
    "model",
    "problem",
]
