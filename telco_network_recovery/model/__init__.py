"""Telco network recovery (multi-reasoner) template: the model.

Five-stage RelationalAI pipeline that produces a defensible tower-upgrade
plan from a heterogeneous telco ontology. The narrative: a regional
operator must allocate a fixed capex budget across cell towers in the
face of two distinct risk signals -- in-region operational degradation
(captured by declarative rules) and predicted equipment failure driven
by manufacturer advisories (captured by a GNN). Neither signal is
recoverable from the other alone, so the chain integrates both.

- Stage 1 -- Predictive (`equipment_failure.py`, with `advisory_signals.py` for how much of the
  equipment the advisories cover): a binary classification GNN on
  NetworkEquipment.at_risk (status FAILING or WARNING) over a heterogeneous *undirected* graph
  that includes EquipmentHealth <-> NetworkEquipment, NetworkEquipment
  <-> CellTower, and ModelAdvisory <-> NetworkEquipment (the
  recall/defect edge). The undirected setting enables 2-hop message
  passing across Equipment <-> Tower <-> Equipment, so the GNN learns
  that a piece of equipment is at elevated risk when its tower-mate
  sits on a recalled MODEL. Per-equipment predicted-failure
  probability is summed per tower into `TowerFailureScore.failure_intensity`.
- Stage 2 -- Rules (`critical_towers.py`): derive per-tower averages from NetworkPerformance
  and EquipmentHealth, then flag `CellTower.is_critical_restore` via
  three branches: WEST + DEGRADED + low equipment health; WEST + high
  packet loss + low health; or `failure_intensity > threshold` (any
  region). The third branch broadens upgrade scope beyond WEST when
  the GNN flags concentrated equipment failure elsewhere.
- Stage 3 -- Graph (`customer_impact.py`): Customer impact analysis. PageRank on a directed
  Subscriber -> Subscriber call graph (caller -> callee) is the
  graph-reasoner signal. Per-critical-tower `weighted_impact`
  aggregates the *customer value* (revenue weighted by churn risk)
  of the distinct ACTIVE subscribers whose calls route through the tower;
  PageRank-weighted impact is exposed alongside as a secondary
  network-effect signal.
- Stage 4 -- Paths (PREVIEW, `call_paths.py`): the arity-3
  `{Subscriber} via {CellTower} calls {Subscriber}` edge; the model
  enumerates caller -> callee call paths over it (<=3 hops, simple, from
  the highest-PageRank subscriber), counts the paths and the routing
  towers on each hop via `relationship_fields`, keeps the highest
  influence load (PageRank summed along a path), and publishes that
  winning route with its routing towers.
- Stage 5 -- Prescriptive (`tower_upgrades.py`): tower-upgrade MIP. Decision variable
  `TowerUpgradeOption.selected` is binary (one of three tiers per
  tower). Constraints: at most one tier per tower, total cost <=
  budget, total install crew-weeks <= 200. Objective maximizes
  selected x capacity_increase x weighted_impact x failure_intensity.

Each stage enriches the shared ontology, and downstream stages consume
those enrichments as first-class properties -- the accretive enrichment
pattern. Each module imports the modules whose declarations it reads.

Subscriber account status is modelled as a `model.Enum`: CSV strings
map to members by name on load, and the
Stage 3 aggregates filter on `SubscriberStatus.ACTIVE` instead of a raw
string. Tower status intentionally stays a String property -- it feeds
the Stage 1 GNN's PropertyTransformer as a categorical feature.

Run:
    `rai models deploy --path model` deploys this package to the schemas in
    raiconfig.yaml, and `python train.py` trains and registers the GNN. After a
    refresh, `python -m queries.recovery_report` prints the per-stage
    diagnostics and the plan.
"""

from .advisory_signals import AdvisedEquipmentCount, AdvisedModelEquipment, AdvisoryCount
from .call_paths import (
    PATH_MAX_HOPS,
    RoutingTowerCount,
    SimplePathCount,
    TopCallPathHop,
    TopCallPathStep,
)
from .critical_towers import (
    FAILURE_INTENSITY_THRESHOLD,
    CriticalRegionCount,
    IntenseTowerCount,
    RestoreBranchCounts,
)
from .equipment_failure import (
    POSITIVE_PROBABILITY_CUTOFF,
    AtRiskBalance,
    EquipmentSplitSize,
    FailureIntensitySpread,
    GnnRecallCounts,
    PositiveProbabilitySpread,
    TowerFailureScore,
    gnn,
)
from .schema import (
    CallDetailRecord,
    CellTower,
    EquipmentHealth,
    ModelAdvisory,
    NetworkEquipment,
    NetworkPerformance,
    Subscriber,
    SubscriberStatus,
    TestEqTable,
    TowerUpgradeOption,
    TrainEqTable,
    ValEqTable,
    model,
)
from .source import DATA_DIR
from .tower_upgrades import (
    RationaleTally,
    RestorePlan,
    SelectedRegionCount,
    SolveObjective,
    SolveStatus,
    problem,
)

__all__ = [
    "DATA_DIR",
    "FAILURE_INTENSITY_THRESHOLD",
    "PATH_MAX_HOPS",
    "POSITIVE_PROBABILITY_CUTOFF",
    "AdvisedEquipmentCount",
    "AdvisedModelEquipment",
    "AdvisoryCount",
    "AtRiskBalance",
    "CallDetailRecord",
    "CellTower",
    "CriticalRegionCount",
    "EquipmentHealth",
    "EquipmentSplitSize",
    "FailureIntensitySpread",
    "GnnRecallCounts",
    "IntenseTowerCount",
    "ModelAdvisory",
    "NetworkEquipment",
    "NetworkPerformance",
    "PositiveProbabilitySpread",
    "RationaleTally",
    "RestoreBranchCounts",
    "RestorePlan",
    "RoutingTowerCount",
    "SelectedRegionCount",
    "SimplePathCount",
    "SolveObjective",
    "SolveStatus",
    "Subscriber",
    "SubscriberStatus",
    "TestEqTable",
    "TopCallPathHop",
    "TopCallPathStep",
    "TowerFailureScore",
    "TowerUpgradeOption",
    "TrainEqTable",
    "ValEqTable",
    "gnn",
    "model",
    "problem",
]
