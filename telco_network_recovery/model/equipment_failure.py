"""Equipment failure: the GNN that scores each equipment item's failure risk, each tower's summed failure
intensity, and the figures that profile the training data and the scores."""

from relationalai.semantics import Float, Integer, String, not_
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.predictive import GNN, PropertyTransformer
from relationalai.semantics.std import aggregates as aggs

from .schema import (
    CellTower,
    EquipmentHealth,
    ModelAdvisory,
    NetworkEquipment,
    Test,
    TestEqTable,
    Train,
    TrainEqTable,
    Val,
    ValEqTable,
    model,
)
from .source import SEED

GNN_EPOCHS = 80
GNN_LR = 0.002

# Equipment with one of these statuses is at risk: the positive class of the GNN's
# binary label.
AT_RISK_STATUSES = ("FAILING", "WARNING")

# The standard probability cutoff for reading a positive prediction.
POSITIVE_PROBABILITY_CUTOFF = 0.5

# --------------------------------------------------
# Stage 1: Predictive -- equipment-failure binary GNN
# --------------------------------------------------

# The GNN's label: 1 for an at-risk status, 0 otherwise, including equipment without a status.
for _status in AT_RISK_STATUSES:
    model.where(NetworkEquipment.status == _status).define(NetworkEquipment.at_risk(1))
model.where(*(not_(NetworkEquipment.status == _status) for _status in AT_RISK_STATUSES)).define(
    NetworkEquipment.at_risk(0)
)

# Heterogeneous graph with three FK / shared-MODEL edges:
#   1. EquipmentHealth <-> NetworkEquipment  (per-equipment health features)
#   2. NetworkEquipment <-> CellTower        (tower-context features)
#   3. ModelAdvisory <-> NetworkEquipment    (recall/defect signal via MODEL)
# We use `directed=False` (undirected, bidirectional message passing)
# so the GNN can propagate signal across multi-hop paths: a piece of
# equipment whose own MODEL has no advisory can still inherit risk
# from a tower-mate whose MODEL does, via the path
#   ModelAdvisory -> tower_mate -> CellTower -> this_equipment.
gnn_graph = Graph(model, name="equipment_graph", directed=False, weighted=False)

model.define(gnn_graph.Edge.new(src=EquipmentHealth, dst=NetworkEquipment)).where(
    EquipmentHealth.equipment_id_fk == NetworkEquipment.id,
)
model.define(gnn_graph.Edge.new(src=NetworkEquipment, dst=CellTower)).where(
    NetworkEquipment.tower_id_fk == CellTower.id,
)
model.define(gnn_graph.Edge.new(src=ModelAdvisory, dst=NetworkEquipment)).where(
    ModelAdvisory.model == NetworkEquipment.eqp_model,
)

# Feature configuration. Drop identifier / FK columns, the label and the status it
# derives from, and high-cardinality free-text fields. Pull every other ontology
# property as a typed feature.
pt = PropertyTransformer(
    drop=[
        CellTower.id,
        CellTower.name,
        NetworkEquipment.id,
        NetworkEquipment.tower_id_fk,
        # The GNN target is at_risk, derived from status -- keeping either as a
        # feature would leak.
        NetworkEquipment.status,
        NetworkEquipment.at_risk,
        EquipmentHealth.id,
        EquipmentHealth.equipment_id_fk,
        ModelAdvisory.model,
    ],
    category=[
        NetworkEquipment.equipment_type,
        NetworkEquipment.manufacturer,
        NetworkEquipment.eqp_model,
        NetworkEquipment.firmware_version,
        CellTower.tower_type,
        CellTower.status,
        CellTower.region,
        ModelAdvisory.advisory_type,
    ],
    continuous=[
        EquipmentHealth.failure_rate,
        EquipmentHealth.temperature_avg_c,
        EquipmentHealth.power_consumption_kw,
        EquipmentHealth.health_score,
        ModelAdvisory.severity,
    ],
    integer=[
        EquipmentHealth.mtbf_hours,
        CellTower.capacity_gbps,
    ],
    datetime=[
        NetworkEquipment.install_date,
        EquipmentHealth.last_failure_date,
        EquipmentHealth.measurement_date,
        CellTower.install_date,
        ModelAdvisory.issued_date,
    ],
)

# `name` ties this GNN to the registered model and version that
# `reasoners.predictive.gnns.equipment_failure` names in raiconfig.yaml:
# train.py registers the trained run there, and every refresh scores all
# equipment with it.
gnn = GNN(
    name="equipment_failure",
    graph=gnn_graph,
    property_transformer=pt,
    train=Train,
    validation=Val,
    task_type="binary_classification",
    eval_metric="roc_auc",
    has_time_column=False,
    stream_logs=False,
    seed=SEED,
    n_epochs=GNN_EPOCHS,
    lr=GNN_LR,
)
NetworkEquipment.predictions = gnn.predictions(domain=Test)

# TowerFailureScore concept: bridge concept holding the per-tower SUM of
# the equipment failure probabilities (= expected count of at-risk
# equipment on the tower), joined onto CellTower by tower id. SUM (not max)
# preserves per-tower differentiation when individual predictions saturate
# near 0 or 1. It is a concept of its own, not a CellTower property: the
# GNN reads the CellTower table, so a CellTower property derived from the
# predictions would make the predictions depend on themselves.
TowerFailureScore = model.Concept("TowerFailureScore", identify_by={"tower_id": String})
TowerFailureScore.failure_intensity = model.Property(f"{TowerFailureScore} has {Float:failure_intensity}")
model.define(TowerFailureScore.new(tower_id=NetworkEquipment.tower_id_fk)).where(
    NetworkEquipment.predictions,
)
model.define(
    TowerFailureScore.failure_intensity(
        aggs.sum(NetworkEquipment, NetworkEquipment.predictions.probs)
        .where(NetworkEquipment.tower_id_fk == TowerFailureScore.tower_id)
        .per(TowerFailureScore)
    )
)

# --------------------------------------------------
# What the GNN trains on
# --------------------------------------------------

# How many equipment items each split holds.
EquipmentSplitSize = model.Relationship(
    f"the equipment split has {Integer:train_items} train, {Integer:validation_items} validation "
    f"and {Integer:test_items} test items"
)
model.define(EquipmentSplitSize(aggs.count(TrainEqTable), aggs.count(ValEqTable), aggs.count(TestEqTable)))

# The label's balance over all equipment: how many items, how many at risk, and the at-risk rate.
AtRiskBalance = model.Relationship(
    f"the equipment has {Integer:items} items, {Integer:at_risk_items} of them at risk, "
    f"an at-risk rate of {Float:at_risk_rate}"
)
model.define(
    AtRiskBalance(
        aggs.count(NetworkEquipment),
        aggs.sum(NetworkEquipment, NetworkEquipment.at_risk),
        aggs.avg(NetworkEquipment, NetworkEquipment.at_risk),
    )
)

# --------------------------------------------------
# What the GNN predicts
# --------------------------------------------------

# Towers ranked by failure intensity, highest first, ties broken by tower id. The
# intensity is negated so both keys sort ascending: the Logic engine's rank does not
# mix ascending and descending keys.
TowerFailureScore.failure_rank = model.Property(f"{TowerFailureScore} has {Integer:failure_rank}")
model.define(
    TowerFailureScore.failure_rank(aggs.rank(-TowerFailureScore.failure_intensity, TowerFailureScore.tower_id))
)

# The scored towers and the spread of their failure intensities.
FailureIntensitySpread = model.Relationship(
    f"{Integer:scored_towers} towers have failure intensities from {Float:minimum} "
    f"to {Float:maximum} with median {Float:median}"
)
model.define(
    FailureIntensitySpread(
        aggs.count(TowerFailureScore),
        aggs.min(TowerFailureScore.failure_intensity),
        aggs.max(TowerFailureScore.failure_intensity),
        aggs.median(TowerFailureScore, TowerFailureScore.failure_intensity),
    )
)

# How many at-risk equipment items the GNN catches: by its predicted label and by the
# probability cutoff.
GnnRecallCounts = model.Relationship(
    f"the GNN catches {Integer:by_label} at-risk equipment items by predicted label "
    f"and {Integer:by_cutoff} by the probability cutoff"
)
_scored_at_risk = (NetworkEquipment.predictions, NetworkEquipment.at_risk == 1)
model.define(
    GnnRecallCounts(
        aggs.count(NetworkEquipment).where(
            *_scored_at_risk, NetworkEquipment.predictions.predicted_labels == 1
        )
        | 0,
        aggs.count(NetworkEquipment).where(
            *_scored_at_risk, NetworkEquipment.predictions.probs >= POSITIVE_PROBABILITY_CUTOFF
        )
        | 0,
    )
)

# The scored equipment items and the spread of their positive-class probabilities.
PositiveProbabilitySpread = model.Relationship(
    f"{Integer:scored_items} equipment items have positive probabilities from {Float:minimum} "
    f"to {Float:maximum} with median {Float:median}, and {Integer:at_cutoff} reach the cutoff"
)
model.define(
    PositiveProbabilitySpread(
        aggs.count(NetworkEquipment).where(NetworkEquipment.predictions),
        aggs.min(NetworkEquipment.predictions.probs),
        aggs.max(NetworkEquipment.predictions.probs),
        aggs.median(NetworkEquipment, NetworkEquipment.predictions.probs),
        aggs.count(NetworkEquipment).where(NetworkEquipment.predictions.probs >= POSITIVE_PROBABILITY_CUTOFF)
        | 0,
    )
)
