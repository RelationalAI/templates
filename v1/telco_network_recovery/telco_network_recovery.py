"""Telco network recovery (multi-reasoner) template.

Four-stage RelationalAI pipeline that produces a defensible tower-upgrade
plan from a heterogeneous telco ontology. The narrative: a regional
operator must allocate a fixed capex budget across cell towers in the
face of two distinct risk signals -- in-region operational degradation
(captured by declarative rules) and predicted equipment failure driven
by manufacturer advisories (captured by a GNN). Neither signal is
recoverable from the other alone, so the chain integrates both.

- Stage 1 -- Predictive: train a binary classification GNN on
  NetworkEquipment.STATUS over a heterogeneous *undirected* graph
  that includes EquipmentHealth <-> NetworkEquipment, NetworkEquipment
  <-> CellTower, and ModelAdvisory <-> NetworkEquipment (the
  recall/defect edge). The undirected setting enables 2-hop message
  passing across Equipment <-> Tower <-> Equipment, so the GNN learns
  that a piece of equipment is at elevated risk when its tower-mate
  sits on a recalled MODEL -- a pattern a SQL `JOIN model_advisories`
  query cannot easily reproduce. Per-equipment predicted-failure
  probability is summed per tower into `CellTower.failure_intensity`.
- Stage 2 -- Rules: derive per-tower averages from NetworkPerformance
  and EquipmentHealth, then flag `CellTower.is_critical_restore` via
  three branches: WEST + DEGRADED + low equipment health; WEST + high
  packet loss + low health; or `failure_intensity > threshold` (any
  region). The third branch broadens upgrade scope beyond WEST when
  the GNN flags concentrated equipment failure elsewhere.
- Stage 3 -- Graph: Customer impact analysis. PageRank on a directed
  Subscriber -> Subscriber call graph (caller -> callee) is the
  graph-reasoner signal. Per-critical-tower `weighted_impact`
  aggregates the *customer value* (revenue weighted by churn risk)
  of ACTIVE subscribers whose calls route through the tower;
  PageRank-weighted impact is exposed alongside as a secondary
  network-effect signal.
- Stage 4 -- Prescriptive: tower-upgrade MIP. Decision variable
  `TowerUpgradeOption.selected` is binary (one of three tiers per
  tower). Constraints: at most one tier per tower, total cost <=
  budget, total install crew-weeks <= 200. Objective maximizes
  selected x capacity_increase x weighted_impact x failure_intensity.

Each stage enriches the shared ontology, and downstream stages consume
those enrichments as first-class properties -- the accretive enrichment
pattern.

Run:
    `python telco_network_recovery.py`

Output:
    Prints per-stage diagnostics -- equipment split, advisory landscape,
    GNN per-tower failure_intensity distribution and recall, three-branch
    critical-restore rule firings, top subscribers by customer value
    (with PageRank shown alongside), per-critical-tower customer
    impact, MIP termination status -- and a final
    RestorePlan singleton row (total cost, install-weeks, capacity
    restored, tier mix, towers covered, binding constraint) showing the
    plan as queryable ontology.
"""

from pathlib import Path

import pandas as pd
from relationalai.semantics import (
    Any,
    DateTime,
    Float,
    Integer,
    Model,
    String,
    distinct,
    select,
)
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.predictive import GNN, PropertyTransformer
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.std import aggregates as aggs

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"

SEED = 42
GNN_EPOCHS = 80
GNN_LR = 0.002

# Stage 4 budget envelope.
BUDGET_USD = 5_000_000
INSTALL_WEEKS_BUDGET = 200

# Stage 4 MIP solver. Defaults to gurobi; if the prescriptive engine
# isn't gurobi-enabled/licensed, the solve below automatically falls
# back to the bundled open-source "highs" solver -- no config change
# needed (see raiconfig.yaml `reasoners.prescriptive.settings.gurobi`).
MIP_SOLVER = "gurobi"

# Stage 2 threshold for the predictive-driven critical-restore branch.
# failure_intensity is the per-tower SUM of equipment failure probs --
# effectively expected count of at-risk equipment items on the tower.
# 1.5 means "the GNN is confident at least ~2 pieces are at risk."
FAILURE_INTENSITY_THRESHOLD = 1.5

# RelationalAI's predictive reasoner writes GNN experiment artifacts to
# a Snowflake schema the RELATIONALAI native app must have write access
# to. Set EXP_DATABASE to a database you own; the schema EXPERIMENTS
# will be created on first run.
EXP_DATABASE = "TELCO_ENRICHMENT"
EXP_SCHEMA = "EXPERIMENTS"

pd.set_option("display.float_format", lambda v: f"{v:,.4f}")

# --------------------------------------------------
# Load CSV data
# --------------------------------------------------

cell_towers_df = pd.read_csv(DATA_DIR / "cell_towers.csv", parse_dates=["INSTALL_DATE"])
subscribers_df = pd.read_csv(DATA_DIR / "subscribers.csv")
# Per-subscriber customer_value = lifetime value weighted by churn risk:
# at-risk subscribers (high churn_risk_score) get up to ~1.9x the weight
# of stable ones. Precomputed in pandas to keep loading straightforward;
# downstream PyRel just reads it as another Float Property on Subscriber.
# Refinements deferred to a later v2: SLA-tier and emergency-service
# multipliers; NPS-deterioration weighting; log-scaling to compress the
# enterprise-vs-consumer LTV gap (~130x in the bundled corpus).
subscribers_df["CUSTOMER_VALUE"] = (
    subscribers_df["LIFETIME_VALUE_USD"]
    * (1.0 + subscribers_df["CHURN_RISK_SCORE"])
)
cdr_df = pd.read_csv(DATA_DIR / "call_detail_records.csv")
network_perf_df = pd.read_csv(DATA_DIR / "network_performance.csv")
network_equipment_df = pd.read_csv(DATA_DIR / "network_equipment.csv", parse_dates=["INSTALL_DATE"])
equipment_health_df = pd.read_csv(
    DATA_DIR / "equipment_health.csv",
    parse_dates=["LAST_FAILURE_DATE", "MEASUREMENT_DATE"],
)
upgrade_options_df = pd.read_csv(DATA_DIR / "tower_upgrade_options.csv")
advisories_df = pd.read_csv(DATA_DIR / "model_advisories.csv", parse_dates=["ISSUED_DATE"])

# Binary at_risk label for the GNN: STATUS in {FAILING, WARNING} are
# the positive class (~20% of equipment). OPERATIONAL is the negative
# class. STATUS itself is dropped from the feature set to prevent leak.
network_equipment_df["AT_RISK"] = (
    network_equipment_df["STATUS"].isin(["FAILING", "WARNING"]).astype(int)
)

# Train/val/test split. Train + val carry labels for fit + evaluation;
# test = ALL equipment so every item receives a prediction (inference
# domain) for the chain's per-tower aggregation.
eq_shuf = network_equipment_df.sample(frac=1, random_state=SEED).reset_index(drop=True)
n = len(eq_shuf)
train_n = int(n * 0.70)
val_n = int(n * 0.15)
# reset_index(drop=True) on every split: model.data() infers column
# types via df[col][0], a 0-based label lookup. An .iloc slice keeps
# the parent index (val/test start mid-frame), so without this reset
# the val split has no row labeled 0 -> KeyError: 0.
train_eq_df = eq_shuf.iloc[:train_n][["EQUIPMENT_ID", "AT_RISK"]].rename(
    columns={"EQUIPMENT_ID": "equipment_id", "AT_RISK": "at_risk"}
).reset_index(drop=True)
val_eq_df = eq_shuf.iloc[train_n:train_n + val_n][["EQUIPMENT_ID", "AT_RISK"]].rename(
    columns={"EQUIPMENT_ID": "equipment_id", "AT_RISK": "at_risk"}
).reset_index(drop=True)
test_eq_df = network_equipment_df[["EQUIPMENT_ID"]].rename(
    columns={"EQUIPMENT_ID": "equipment_id"}
).reset_index(drop=True)

print(f"Equipment split: train={len(train_eq_df)} val={len(val_eq_df)} test={len(test_eq_df)} (all)")
print(f"Label distribution: at_risk=1 {network_equipment_df['AT_RISK'].sum()} / "
      f"{len(network_equipment_df)} ({network_equipment_df['AT_RISK'].mean():.1%})")
print(f"Advisories: {len(advisories_df)} on {advisories_df['MODEL'].nunique()} distinct models")

# Descriptive: advisory landscape -- which MODELs are affected, severity,
# and how many equipment items sit on each. This is the relational
# neighbor signal the GNN propagates in Stage 1.
print("\n  Advisory landscape -- equipment count per advised MODEL:")
_adv_landscape = (
    advisories_df
    .merge(network_equipment_df.groupby("MODEL").size().rename("eq_count").reset_index(), on="MODEL", how="left")
    .sort_values("SEVERITY", ascending=False)
    [["MODEL", "ADVISORY_TYPE", "SEVERITY", "ISSUED_DATE", "eq_count"]]
)
print(_adv_landscape.to_string(index=False))
_n_on_advised = int(network_equipment_df["MODEL"].isin(set(advisories_df["MODEL"])).sum())
print(f"  Equipment on an advised MODEL: {_n_on_advised} / {len(network_equipment_df)} "
      f"({_n_on_advised/len(network_equipment_df):.1%})")

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

model = Model("Telco Network Recovery")

# CellTower concept: a physical radio tower in a region. The GNN
# reaches it from each NetworkEquipment via the tower_id_fk
# property-equality edge.
CellTower = model.Concept("CellTower", identify_by={"id": String})
CellTower.name = model.Property(f"{CellTower} has {String:name}")
CellTower.tower_type = model.Property(f"{CellTower} has {String:tower_type}")
CellTower.capacity_gbps = model.Property(f"{CellTower} has {Integer:capacity_gbps}")
CellTower.status = model.Property(f"{CellTower} has {String:status}")
CellTower.region = model.Property(f"{CellTower} has {String:region}")
CellTower.install_date = model.Property(f"{CellTower} has {DateTime:install_date}")

src = model.data(cell_towers_df)
model.define(CellTower.new(
    id=src.TOWER_ID,
    name=src.TOWER_NAME,
    tower_type=src.TOWER_TYPE,
    capacity_gbps=src.CAPACITY_GBPS,
    status=src.STATUS,
    region=src.REGION,
    install_date=src.INSTALL_DATE,
))

# NetworkEquipment concept: equipment items (radios, antennas, BBUs,
# amplifiers, ...) installed on cell towers; the GNN's prediction
# target. tower_id_fk is an explicit FK property used by the GNN
# graph via property equality, so heterogeneous edges are expressed as
# property-level equality conditions rather than `model.Relationship`
# traversal.
NetworkEquipment = model.Concept("NetworkEquipment", identify_by={"id": String})
NetworkEquipment.equipment_type = model.Property(f"{NetworkEquipment} has {String:equipment_type}")
NetworkEquipment.manufacturer = model.Property(f"{NetworkEquipment} has {String:manufacturer}")
NetworkEquipment.eqp_model = model.Property(f"{NetworkEquipment} has {String:eqp_model}")
NetworkEquipment.firmware_version = model.Property(f"{NetworkEquipment} has {String:firmware_version}")
NetworkEquipment.install_date = model.Property(f"{NetworkEquipment} has {DateTime:install_date}")
NetworkEquipment.tower_id_fk = model.Property(f"{NetworkEquipment} has {String:tower_id_fk}")

src = model.data(network_equipment_df)
model.define(NetworkEquipment.new(
    id=src.EQUIPMENT_ID,
    equipment_type=src.EQUIPMENT_TYPE,
    manufacturer=src.MANUFACTURER,
    eqp_model=src.MODEL,
    firmware_version=src.FIRMWARE_VERSION,
    install_date=src.INSTALL_DATE,
    tower_id_fk=src.TOWER_ID,
))

# EquipmentHealth concept: per-equipment health snapshot (MTBF, failure
# rate, temperature, power consumption, health score). All numeric
# columns flow into the GNN via the equipment_id_fk property-equality
# edge.
EquipmentHealth = model.Concept("EquipmentHealth", identify_by={"id": String})
EquipmentHealth.mtbf_hours = model.Property(f"{EquipmentHealth} has {Integer:mtbf_hours}")
EquipmentHealth.failure_rate = model.Property(f"{EquipmentHealth} has {Float:failure_rate}")
EquipmentHealth.last_failure_date = model.Property(f"{EquipmentHealth} has {DateTime:last_failure_date}")
EquipmentHealth.temperature_avg_c = model.Property(f"{EquipmentHealth} has {Float:temperature_avg_c}")
EquipmentHealth.power_consumption_kw = model.Property(f"{EquipmentHealth} has {Float:power_consumption_kw}")
EquipmentHealth.health_score = model.Property(f"{EquipmentHealth} has {Float:health_score}")
EquipmentHealth.measurement_date = model.Property(f"{EquipmentHealth} has {DateTime:measurement_date}")
EquipmentHealth.equipment_id_fk = model.Property(f"{EquipmentHealth} has {String:equipment_id_fk}")

src = model.data(equipment_health_df)
model.define(EquipmentHealth.new(
    id=src.HEALTH_ID,
    mtbf_hours=src.MTBF_HOURS,
    failure_rate=src.FAILURE_RATE,
    last_failure_date=src.LAST_FAILURE_DATE,
    temperature_avg_c=src.TEMPERATURE_AVG_C,
    power_consumption_kw=src.POWER_CONSUMPTION_KW,
    health_score=src.HEALTH_SCORE,
    measurement_date=src.MEASUREMENT_DATE,
    equipment_id_fk=src.EQUIPMENT_ID,
))

# ModelAdvisory concept: a manufacturer-issued recall / defect batch /
# firmware bug / EOL / security-patch notice that applies to an
# equipment MODEL. The relational signal the GNN propagates to every
# NetworkEquipment sharing the affected MODEL. We collapse multiple
# advisories on the same MODEL to one row by taking the max severity
# so the GNN sees one ModelAdvisory node per affected fleet.
ModelAdvisory = model.Concept("ModelAdvisory", identify_by={"model": String})
ModelAdvisory.advisory_type = model.Property(f"{ModelAdvisory} has {String:advisory_type}")
ModelAdvisory.severity = model.Property(f"{ModelAdvisory} has {Float:severity}")
ModelAdvisory.issued_date = model.Property(f"{ModelAdvisory} has {DateTime:issued_date}")

adv_collapsed = (
    advisories_df.sort_values("SEVERITY", ascending=False)
    .drop_duplicates(subset=["MODEL"], keep="first")
)
src = model.data(adv_collapsed)
model.define(ModelAdvisory.new(
    model=src.MODEL,
    advisory_type=src.ADVISORY_TYPE,
    severity=src.SEVERITY,
    issued_date=src.ISSUED_DATE,
))

# Note: NetworkPerformance, Subscriber, CallDetailRecord, and
# TowerUpgradeOption are loaded just before their respective stages
# below. Loading them up front keeps gnn.fit()'s transaction payload
# small enough to avoid Snowflake's CREATE_TRANSACTION_V2 row-size
# limit.

# --------------------------------------------------
# Stage 1: Predictive -- equipment-failure binary GNN
# --------------------------------------------------

print(f"\n{'=' * 60}")
print("STAGE 1: PREDICTIVE -- equipment-failure binary classification GNN")
print("=" * 60)

# Heterogeneous graph with three FK / shared-MODEL edges:
#   1. EquipmentHealth <-> NetworkEquipment  (per-equipment health features)
#   2. NetworkEquipment <-> CellTower        (tower-context features)
#   3. ModelAdvisory <-> NetworkEquipment    (recall/defect signal via MODEL)
# We use `directed=False` (undirected, bidirectional message passing)
# so the GNN can propagate signal across multi-hop paths: a piece of
# equipment whose own MODEL has no advisory can still inherit risk
# from a tower-mate whose MODEL does, via the path
#   ModelAdvisory -> tower_mate -> CellTower -> this_equipment.
# That 2-hop neighbor pattern is the one a SQL `JOIN model_advisories`
# query cannot easily reproduce.
gnn_graph = Graph(model, directed=False, weighted=False)

model.define(gnn_graph.Edge.new(src=EquipmentHealth, dst=NetworkEquipment)).where(
    EquipmentHealth.equipment_id_fk == NetworkEquipment.id,
)
model.define(gnn_graph.Edge.new(src=NetworkEquipment, dst=CellTower)).where(
    NetworkEquipment.tower_id_fk == CellTower.id,
)
model.define(gnn_graph.Edge.new(src=ModelAdvisory, dst=NetworkEquipment)).where(
    ModelAdvisory.model == NetworkEquipment.eqp_model,
)

# Feature configuration. Drop identifier / FK columns and high-cardinality
# free-text fields. Pull every other ontology property as a typed feature.
pt = PropertyTransformer(
    drop=[
        NetworkEquipment.tower_id_fk,
        EquipmentHealth.equipment_id_fk,
        CellTower.name,
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

# TrainEqTable / ValEqTable / TestEqTable concepts: GNN task tables
# holding (equipment_id, at_risk) pairs for training / validation /
# inference. Test = all equipment so every NetworkEquipment receives
# a prediction, independent of train/val split.
TrainEqTable = model.Concept("TrainEqTable")
ValEqTable = model.Concept("ValEqTable")
TestEqTable = model.Concept("TestEqTable")
model.define(TrainEqTable.new(model.data(train_eq_df).to_schema()))
model.define(ValEqTable.new(model.data(val_eq_df).to_schema()))
model.define(TestEqTable.new(model.data(test_eq_df).to_schema()))

Train = model.Relationship(f"{NetworkEquipment} has {Any:label}")
model.define(Train(NetworkEquipment, TrainEqTable.at_risk)).where(
    NetworkEquipment.id == TrainEqTable.equipment_id,
)
Val = model.Relationship(f"{NetworkEquipment} has {Any:label}")
model.define(Val(NetworkEquipment, ValEqTable.at_risk)).where(
    NetworkEquipment.id == ValEqTable.equipment_id,
)
Test = model.Relationship(f"{NetworkEquipment}")
model.define(Test(NetworkEquipment)).where(
    NetworkEquipment.id == TestEqTable.equipment_id,
)

gnn = GNN(
    exp_database=EXP_DATABASE,
    exp_schema=EXP_SCHEMA,
    graph=gnn_graph,
    property_transformer=pt,
    train=Train,
    validation=Val,
    task_type="binary_classification",
    eval_metric="roc_auc",
    has_time_column=False,
    stream_logs=False,
    seed=SEED,
    device="cpu",
    n_epochs=GNN_EPOCHS,
    lr=GNN_LR,
)
gnn.fit()
NetworkEquipment.predictions = gnn.predictions(domain=Test)

# Pull predictions to pandas; aggregate per tower as SUM of positive
# probabilities (= expected count of at-risk equipment on the tower);
# load back as a CellTower property the rest of the chain consumes.
# SUM (not max) preserves per-tower differentiation when individual
# predictions saturate near 0 or 1.
pred_df = (
    select(
        NetworkEquipment.id.alias("equipment_id"),
        NetworkEquipment.predictions.probs.alias("probs"),
        NetworkEquipment.predictions.predicted_labels.alias("predicted_label"),
    )
    .where(NetworkEquipment.predictions)
    .to_df()
)
def _pos_prob(p):
    if isinstance(p, (list, tuple)):
        return float(p[1]) if len(p) > 1 else float(p[0])
    return float(p)
pred_df["pos_prob"] = pred_df["probs"].apply(_pos_prob)
pred_df = pred_df.merge(
    network_equipment_df[["EQUIPMENT_ID", "TOWER_ID"]].rename(columns={"EQUIPMENT_ID": "equipment_id"}),
    on="equipment_id",
    how="left",
)

per_tower = (
    pred_df.groupby("TOWER_ID")["pos_prob"]
    .sum()
    .reset_index()
    .rename(columns={"pos_prob": "FAILURE_INTENSITY"})
    .sort_values("FAILURE_INTENSITY", ascending=False)
)
print("\n  Top 10 towers by predicted failure intensity (sum of equipment failure probs):")
print(per_tower.head(10).to_string(index=False))
print(
    f"\n  failure_intensity distribution: "
    f"min={per_tower['FAILURE_INTENSITY'].min():.2f}, "
    f"median={per_tower['FAILURE_INTENSITY'].median():.2f}, "
    f"max={per_tower['FAILURE_INTENSITY'].max():.2f}"
)
print(
    f"  Towers with failure_intensity > {FAILURE_INTENSITY_THRESHOLD}: "
    f"{int((per_tower['FAILURE_INTENSITY'] > FAILURE_INTENSITY_THRESHOLD).sum())} / {len(per_tower)}"
)

# Side-by-side check: how far different levels of SQL sophistication
# get on this data, vs the GNN's set. Three tiers:
#   1. Naive SQL on health columns -- catches the health-only tail.
#   2. Join-aware SQL also filtering on advised MODEL -- catches the
#      bulk, but misses 2-hop neighbor-driven and smooth-interaction
#      cases.
#   3. The GNN (the chain output) -- closes the remaining gap via
#      heterogeneous undirected message passing.
total_atrisk = int(network_equipment_df["AT_RISK"].sum())
sql_alt = network_equipment_df.merge(
    equipment_health_df[["EQUIPMENT_ID", "HEALTH_SCORE"]], on="EQUIPMENT_ID"
)
sql_naive = sql_alt[(sql_alt["AT_RISK"] == 1) & (sql_alt["HEALTH_SCORE"] < 0.5)].shape[0]
advised_models = set(advisories_df["MODEL"].tolist())
sql_joined = sql_alt[
    (sql_alt["AT_RISK"] == 1)
    & ((sql_alt["HEALTH_SCORE"] < 0.5) | (sql_alt["MODEL"].isin(advised_models)))
].shape[0]
# GNN end-to-end recall on at-risk items. Report two views:
#   - At the model's built-in argmax (predicted_label == 1).
#   - At the standard probability threshold (pos_prob >= 0.5).
# The argmax view answers "what the model says"; the 0.5-threshold view
# answers "what a downstream rule would catch using the GNN's calibrated
# probability." They can diverge if the model's calibration is shifted
# (the argmax can be conservative even when probs are well-separated).
gnn_flagged_atrisk = pred_df.merge(
    network_equipment_df[["EQUIPMENT_ID", "AT_RISK"]].rename(
        columns={"EQUIPMENT_ID": "equipment_id"}
    ),
    on="equipment_id",
    how="left",
)
gnn_recall_argmax = int(
    gnn_flagged_atrisk[
        (gnn_flagged_atrisk["AT_RISK"] == 1)
        & (gnn_flagged_atrisk["predicted_label"] == 1)
    ].shape[0]
)
gnn_recall_p05 = int(
    gnn_flagged_atrisk[
        (gnn_flagged_atrisk["AT_RISK"] == 1)
        & (gnn_flagged_atrisk["pos_prob"] >= 0.5)
    ].shape[0]
)
print(
    f"\n  SQL-vs-GNN comparison on {total_atrisk} true at-risk items:"
    f"\n    Naive SQL `WHERE health_score < 0.5`:                "
    f"{sql_naive:>4} ({sql_naive/total_atrisk:>5.1%})"
    f"\n    Join-aware SQL `... OR model IN advised_models`:    "
    f"{sql_joined:>4} ({sql_joined/total_atrisk:>5.1%})"
    f"\n    GNN-only opportunity (2-hop + smooth interaction):  "
    f"{total_atrisk - sql_joined:>4} ({(total_atrisk - sql_joined)/total_atrisk:>5.1%})"
    f"\n    GNN recall, argmax (predicted_label == 1):          "
    f"{gnn_recall_argmax:>4} ({gnn_recall_argmax/total_atrisk:>5.1%})"
    f"\n    GNN recall, p>=0.5 (probabilistic threshold):       "
    f"{gnn_recall_p05:>4} ({gnn_recall_p05/total_atrisk:>5.1%})"
)
# Per-equipment positive-prediction distribution for transparency.
print(
    f"\n  GNN per-equipment positive-prob distribution: "
    f"min={pred_df['pos_prob'].min():.3f}, "
    f"median={pred_df['pos_prob'].median():.3f}, "
    f"max={pred_df['pos_prob'].max():.3f}; "
    f"items with pos_prob>=0.5: {int((pred_df['pos_prob']>=0.5).sum())} / {len(pred_df)}"
)

# Bridge concept: load per-tower failure_intensity back as a CellTower
# property. Mirrors the bridge pattern used elsewhere in the template
# corpus (e.g. retail_planning) -- aggregate in pandas, then join onto
# the concept that hosts the downstream property.
# TowerFailureScore concept: bridge concept holding the per-tower SUM
# of GNN equipment-failure probabilities. Loaded from pandas after
# Stage 1 and joined onto CellTower to expose failure_intensity as a
# first-class Property the rules + MIP downstream consume.
TowerFailureScore = model.Concept("TowerFailureScore", identify_by={"tower_id": String})
TowerFailureScore.score = model.Property(f"{TowerFailureScore} has {Float:score}")
tfs_src = model.data(per_tower[["TOWER_ID", "FAILURE_INTENSITY"]])
model.define(TowerFailureScore.new(
    tower_id=tfs_src.TOWER_ID,
    score=tfs_src.FAILURE_INTENSITY,
))

CellTower.failure_intensity = model.Property(
    f"{CellTower} has {Float:failure_intensity}"
)
model.define(CellTower.failure_intensity(TowerFailureScore.score)).where(
    TowerFailureScore.tower_id == CellTower.id,
)

# --------------------------------------------------
# Stage 2: Rules -- flag is_critical_restore towers
# --------------------------------------------------

print(f"\n{'=' * 60}")
print("STAGE 2: RULES -- flag is_critical_restore towers")
print("=" * 60)

# NetworkPerformance concept: per-tower performance measurements
# (packet loss %, latency ms, error rate). Aggregated into Stage 2's
# avg_packet_loss / avg_latency_ms / avg_error_rate CellTower
# properties used by the critical-restore rule branches.
NetworkPerformance = model.Concept("NetworkPerformance", identify_by={"id": String})
NetworkPerformance.packet_loss_pct = model.Property(f"{NetworkPerformance} has {Float:packet_loss_pct}")
NetworkPerformance.latency_ms = model.Property(f"{NetworkPerformance} has {Float:latency_ms}")
NetworkPerformance.error_rate = model.Property(f"{NetworkPerformance} has {Float:error_rate}")
NetworkPerformance.for_tower = model.Relationship(
    f"{NetworkPerformance} for tower {CellTower}", short_name="performance_for_tower"
)
src = model.data(network_perf_df)
model.define(NetworkPerformance.new(
    id=src.METRIC_ID,
    packet_loss_pct=src.PACKET_LOSS_PCT,
    latency_ms=src.LATENCY_MS,
    error_rate=src.ERROR_RATE,
    for_tower=CellTower.filter_by(id=src.TOWER_ID),
))

# Per-tower averages from NetworkPerformance (one row per measurement).
CellTower.avg_packet_loss = model.Property(f"{CellTower} has {Float:avg_packet_loss}")
CellTower.avg_latency_ms = model.Property(f"{CellTower} has {Float:avg_latency_ms}")
CellTower.avg_error_rate = model.Property(f"{CellTower} has {Float:avg_error_rate}")

model.define(
    CellTower.avg_packet_loss(
        aggs.avg(NetworkPerformance.packet_loss_pct)
        .where(NetworkPerformance.for_tower(CellTower))
        .per(CellTower)
    )
)
model.define(
    CellTower.avg_latency_ms(
        aggs.avg(NetworkPerformance.latency_ms)
        .where(NetworkPerformance.for_tower(CellTower))
        .per(CellTower)
    )
)
model.define(
    CellTower.avg_error_rate(
        aggs.avg(NetworkPerformance.error_rate)
        .where(NetworkPerformance.for_tower(CellTower))
        .per(CellTower)
    )
)

# Per-tower equipment-health average (two-hop join via property
# equality: EquipmentHealth -> NetworkEquipment -> CellTower).
CellTower.avg_health_score = model.Property(f"{CellTower} has {Float:avg_health_score}")
model.define(
    CellTower.avg_health_score(
        aggs.avg(EquipmentHealth.health_score)
        .where(
            EquipmentHealth.equipment_id_fk == NetworkEquipment.id,
            NetworkEquipment.tower_id_fk == CellTower.id,
        )
        .per(CellTower)
    )
)

# is_critical_restore flag, three branches (OR semantics):
#   1. WEST + DEGRADED status + low equipment health  (operational)
#   2. WEST + high packet loss + low equipment health (ACTIVE-but-failing)
#   3. failure_intensity > threshold                  (predictive, any region)
CellTower.is_critical_restore = model.Relationship(f"{CellTower} is critical restore")

model.where(
    CellTower.region == "WEST",
    CellTower.status == "DEGRADED",
    CellTower.avg_health_score < 0.85,
).define(CellTower.is_critical_restore())

model.where(
    CellTower.region == "WEST",
    CellTower.avg_packet_loss > 5.0,
    CellTower.avg_health_score < 0.85,
).define(CellTower.is_critical_restore())

model.where(
    CellTower.failure_intensity > FAILURE_INTENSITY_THRESHOLD,
).define(CellTower.is_critical_restore())

flagged_df = (
    model.where(CellTower.is_critical_restore())
    .select(
        CellTower.id.alias("tower_id"),
        CellTower.region.alias("region"),
        CellTower.status.alias("status"),
        CellTower.capacity_gbps.alias("capacity_gbps"),
        CellTower.avg_packet_loss.alias("avg_loss"),
        CellTower.avg_health_score.alias("avg_health"),
        CellTower.failure_intensity.alias("failure_intensity"),
    )
    .to_df()
    .sort_values("failure_intensity", ascending=False)
)
print(f"\n  Flagged critical_restore towers: {len(flagged_df)}")
print("  Breakdown by region:")
print(flagged_df["region"].value_counts().to_string())

# Per-branch contribution. Each branch is independently evaluable
# against the per-tower properties already on the flagged_df rows, so
# we can attribute each flag to one or more branches.
_b1 = (flagged_df["region"] == "WEST") & (flagged_df["status"] == "DEGRADED") & (flagged_df["avg_health"] < 0.85)
_b2 = (flagged_df["region"] == "WEST") & (flagged_df["avg_loss"] > 5.0) & (flagged_df["avg_health"] < 0.85)
_b3 = flagged_df["failure_intensity"] > FAILURE_INTENSITY_THRESHOLD
print("\n  Per-branch contribution (a tower can fire on multiple branches):")
print(f"    Branch 1 (WEST + DEGRADED + low health):                  {int(_b1.sum())} towers")
print(f"    Branch 2 (WEST + high packet loss + low health):          {int(_b2.sum())} towers")
print(f"    Branch 3 (failure_intensity > {FAILURE_INTENSITY_THRESHOLD}, any region):  "
      f"{int(_b3.sum())} towers")
_only_predictive = (_b3 & ~_b1 & ~_b2).sum()
print(f"    Towers flagged ONLY by the predictive branch:             {int(_only_predictive)} "
      f"({_only_predictive/len(flagged_df):.0%} of flagged set)")

print("\n  Top 20 by predicted failure intensity:")
print(flagged_df.head(20).to_string(index=False))

# --------------------------------------------------
# Stage 3: Graph -- Customer impact analysis
# (PageRank as graph-reasoner signal; per-tower weighted_impact from
# customer_value (revenue x churn). PageRank-weighted impact retained
# as a secondary network-effect signal alongside the headline measure.)
# --------------------------------------------------

print(f"\n{'=' * 60}")
print("STAGE 3: GRAPH -- Customer impact (revenue x churn; PageRank shown alongside)")
print("=" * 60)

# Subscriber concept: customer accounts (consumer or enterprise) that
# place calls. Nodes of the Stage 3 PageRank graph AND the carriers of
# the customer-value signal that drives per-tower weighted_impact.
Subscriber = model.Concept("Subscriber", identify_by={"id": String})
Subscriber.subscriber_type = model.Property(f"{Subscriber} has {String:subscriber_type}")
Subscriber.segment = model.Property(f"{Subscriber} has {String:segment}")
Subscriber.lifetime_value = model.Property(f"{Subscriber} has {Float:lifetime_value}")
Subscriber.churn_risk_score = model.Property(f"{Subscriber} has {Float:churn_risk_score}")
Subscriber.status = model.Property(f"{Subscriber} has {String:status}")
# Composite revenue-at-risk signal (LTV * (1 + churn)), precomputed in
# pandas above; this is the per-subscriber weight that Stage 3 sums into
# `CellTower.weighted_impact` and Stage 4 uses in the objective.
Subscriber.customer_value = model.Property(f"{Subscriber} has {Float:customer_value}")
src = model.data(subscribers_df)
model.define(Subscriber.new(
    id=src.SUB_ID,
    subscriber_type=src.SUBSCRIBER_TYPE,
    segment=src.SEGMENT,
    lifetime_value=src.LIFETIME_VALUE_USD,
    churn_risk_score=src.CHURN_RISK_SCORE,
    status=src.STATUS,
    customer_value=src.CUSTOMER_VALUE,
))

# CallDetailRecord concept: a directed call (caller -> callee routed
# through a specific CellTower). Used as the edge concept for Stage 3's
# subscriber PageRank graph and for per-tower customer-impact aggregation.
CallDetailRecord = model.Concept("CallDetailRecord", identify_by={"id": String})
CallDetailRecord.caller = model.Relationship(
    f"{CallDetailRecord} has caller {Subscriber}", short_name="cdr_caller"
)
CallDetailRecord.callee = model.Relationship(
    f"{CallDetailRecord} has callee {Subscriber}", short_name="cdr_callee"
)
CallDetailRecord.routed_through = model.Relationship(
    f"{CallDetailRecord} routed through {CellTower}", short_name="cdr_routed_through"
)
src = model.data(cdr_df)
model.define(CallDetailRecord.new(
    id=src.CDR_ID,
    caller=Subscriber.filter_by(id=src.CALLER_SUB_ID),
    callee=Subscriber.filter_by(id=src.CALLEE_SUB_ID),
    routed_through=CellTower.filter_by(id=src.TOWER_ID),
))

call_graph = Graph(
    model,
    directed=True,
    weighted=False,
    node_concept=Subscriber,
    edge_concept=CallDetailRecord,
    edge_src_relationship=CallDetailRecord.caller,
    edge_dst_relationship=CallDetailRecord.callee,
    aggregator="sum",
)
call_graph.Node.influence_score = call_graph.pagerank()

top_subs = (
    model.select(
        Subscriber.id.alias("sub_id"),
        Subscriber.subscriber_type.alias("type"),
        Subscriber.segment.alias("segment"),
        Subscriber.lifetime_value.alias("ltv"),
        Subscriber.churn_risk_score.alias("churn"),
        Subscriber.customer_value.alias("customer_value"),
        Subscriber.influence_score.alias("pagerank"),
    )
    .to_df()
    .sort_values("customer_value", ascending=False)
    .head(10)
)
print("\n  Top 10 subscribers by customer_value (PageRank shown for reference):")
print(top_subs.to_string(index=False))

CellTower.impact_count = model.Property(f"{CellTower} has {Float:impact_count}")
# weighted_impact is the headline per-tower customer-impact score: the
# sum of customer_value (revenue x churn) over ACTIVE subscribers whose
# calls route through the tower. Stage 4's objective consumes this name
# unchanged; the *measure* underneath shifted from PageRank-influence
# sum to customer-value sum to answer the operator's prioritization
# question more directly (revenue at risk, churn urgency).
#
# Note: this is CDR-weighted (each call from a subscriber contributes
# their customer_value once), so a heavy-calling high-value account
# lifts a tower more than the same account calling once. A
# distinct-subscriber-per-tower variant is a defensible v2 refinement.
CellTower.weighted_impact = model.Property(f"{CellTower} has {Float:weighted_impact}")
# Secondary signal: PageRank-weighted impact retained so the graph
# reasoner's network-effect view is still queryable alongside the
# revenue-based headline. Not consumed by the Stage 4 objective.
CellTower.weighted_pagerank = model.Property(f"{CellTower} has {Float:weighted_pagerank}")

model.define(
    CellTower.impact_count(
        aggs.count(distinct(Subscriber))
        .where(
            CallDetailRecord.routed_through(CellTower),
            CallDetailRecord.caller(Subscriber),
            Subscriber.status == "ACTIVE",
        )
        .per(CellTower)
    )
)
model.define(
    CellTower.weighted_impact(
        aggs.sum(Subscriber.customer_value)
        .where(
            CallDetailRecord.routed_through(CellTower),
            CallDetailRecord.caller(Subscriber),
            Subscriber.status == "ACTIVE",
        )
        .per(CellTower)
    )
)
model.define(
    CellTower.weighted_pagerank(
        aggs.sum(Subscriber.influence_score)
        .where(
            CallDetailRecord.routed_through(CellTower),
            CallDetailRecord.caller(Subscriber),
            Subscriber.status == "ACTIVE",
        )
        .per(CellTower)
    )
)

blast_df = (
    model.where(CellTower.is_critical_restore())
    .select(
        CellTower.id.alias("tower_id"),
        CellTower.region.alias("region"),
        CellTower.impact_count.alias("impact_count"),
        CellTower.weighted_impact.alias("weighted_impact"),
        CellTower.weighted_pagerank.alias("weighted_pagerank"),
        CellTower.failure_intensity.alias("failure_intensity"),
    )
    .to_df()
    .sort_values("weighted_impact", ascending=False)
)
print("\n  Per-critical-tower customer impact "
      "(weighted_impact = sum of caller customer_value; "
      "weighted_pagerank shown as secondary):")
print(blast_df.to_string(index=False))

# --------------------------------------------------
# Stage 4: Prescriptive -- tower upgrade MIP
# --------------------------------------------------

print(f"\n{'=' * 60}")
print("STAGE 4: PRESCRIPTIVE -- tower upgrade selection MIP")
print("=" * 60)

# TowerUpgradeOption concept: a (tower, tier) candidate upgrade with
# capacity, cost, and install-weeks; the MIP's decision space. Every
# tower carries three tier options (BRONZE / SILVER / GOLD).
TowerUpgradeOption = model.Concept(
    "TowerUpgradeOption", identify_by={"tower_id": String, "tier": String}
)
TowerUpgradeOption.capacity_increase_gbps = model.Property(
    f"{TowerUpgradeOption} has {Integer:capacity_increase_gbps}"
)
TowerUpgradeOption.cost = model.Property(f"{TowerUpgradeOption} has {Float:cost}")
TowerUpgradeOption.install_weeks = model.Property(f"{TowerUpgradeOption} has {Integer:install_weeks}")
TowerUpgradeOption.for_tower = model.Relationship(
    f"{TowerUpgradeOption} for tower {CellTower}", short_name="upgrade_for_tower"
)
src = model.data(upgrade_options_df)
model.define(TowerUpgradeOption.new(
    tower_id=src.TOWER_ID,
    tier=src.UPGRADE_TIER,
    capacity_increase_gbps=src.CAPACITY_INCREASE_GBPS,
    cost=src.COST_USD,
    install_weeks=src.INSTALL_WEEKS,
    for_tower=CellTower.filter_by(id=src.TOWER_ID),
))

TowerUpgradeOption.selected = model.Property(f"{TowerUpgradeOption} has {Float:selected}")

problem = Problem(model, Float)

# Decision variable: binary 0/1 per (critical tower, tier).
problem.solve_for(
    TowerUpgradeOption.selected,
    where=[
        TowerUpgradeOption.for_tower(CellTower),
        CellTower.is_critical_restore(),
    ],
    name=["tower_id", "tier"],
    type="bin",
)

# Constraint 1: at most one tier selected per tower.
problem.satisfy(
    model.where(
        TowerUpgradeOption.for_tower(CellTower),
        CellTower.is_critical_restore(),
    ).require(
        aggs.sum(TowerUpgradeOption.selected).per(CellTower) <= 1
    )
)

# Constraint 2: total upgrade cost <= BUDGET_USD.
problem.satisfy(
    model.where(
        TowerUpgradeOption.for_tower(CellTower),
        CellTower.is_critical_restore(),
    ).require(
        aggs.sum(TowerUpgradeOption.selected * TowerUpgradeOption.cost) <= BUDGET_USD
    )
)

# Constraint 3: total install crew-weeks <= INSTALL_WEEKS_BUDGET.
problem.satisfy(
    model.where(
        TowerUpgradeOption.for_tower(CellTower),
        CellTower.is_critical_restore(),
    ).require(
        aggs.sum(TowerUpgradeOption.selected * TowerUpgradeOption.install_weeks)
        <= INSTALL_WEEKS_BUDGET
    )
)

# Objective: three-factor weighted capacity gain. Each factor comes
# from a different upstream stage; the third is the GNN's per-tower
# failure_intensity.
problem.maximize(
    aggs.sum(
        TowerUpgradeOption.selected
        * TowerUpgradeOption.capacity_increase_gbps
        * CellTower.weighted_impact
        * CellTower.failure_intensity
    ).where(
        TowerUpgradeOption.for_tower(CellTower),
        CellTower.is_critical_restore(),
    )
)

print(f"\n  Solving (MIP solver: {MIP_SOLVER})...")
try:
    problem.solve(solver=MIP_SOLVER)
except Exception as exc:
    # Fall back to the bundled open-source HiGHS solver when gurobi is
    # unavailable / unlicensed on the prescriptive engine.
    _msg = str(exc).lower()
    if "gurobi" in _msg and any(
        k in _msg for k in ("licen", "unavailable", "not enabled",
                             "not found", "disabled", "install")
    ):
        print(f"  Gurobi unavailable ({exc}); falling back to solver='highs'.")
        problem.solve(solver="highs")
    else:
        raise
problem.display()

# Extract selected upgrades. Cast int128 (returned by RAI select) to
# int64 so pandas .sum() works.
selected_df = (
    model.where(TowerUpgradeOption.selected == 1)
    .select(
        TowerUpgradeOption.tower_id.alias("tower_id"),
        TowerUpgradeOption.tier.alias("tier"),
        TowerUpgradeOption.capacity_increase_gbps.alias("capacity_gbps"),
        TowerUpgradeOption.cost.alias("cost"),
        TowerUpgradeOption.install_weeks.alias("install_weeks"),
    )
    .to_df()
)
for _col in ("capacity_gbps", "install_weeks"):
    if _col in selected_df.columns:
        selected_df[_col] = selected_df[_col].astype("int64")
selected_df["cost"] = selected_df["cost"].astype(float)

selected_df = selected_df.merge(
    flagged_df[["tower_id", "region", "failure_intensity"]],
    on="tower_id",
    how="left",
).sort_values(["region", "tier"])

# Per-tower selection rationale: tag which upstream signal(s) drove
# inclusion. The opening business question ends with "...and why?" --
# this turns the plan output into a defensible answer per tower.
#
# Three signal categories, OR-combined per tower:
#   - operational       : WEST tower in DEGRADED status (Stage 2 branches 1/2)
#   - advisory/predicted: failure_intensity > threshold (Stage 1 GNN -> Stage 2 branch 3)
#   - high-value        : weighted_impact in top quartile of critical towers
# (A future v2 G-full pass would extend this with GNN-confidence and
# data-quality annotations alongside the tag.)
selected_df = selected_df.merge(
    blast_df[["tower_id", "weighted_impact", "weighted_pagerank"]],
    on="tower_id",
    how="left",
)
selected_df = selected_df.merge(
    cell_towers_df[["TOWER_ID", "STATUS"]].rename(
        columns={"TOWER_ID": "tower_id", "STATUS": "tower_status"}
    ),
    on="tower_id",
    how="left",
)
selected_df["sig_operational"] = (
    (selected_df["region"] == "WEST") & (selected_df["tower_status"] == "DEGRADED")
)
selected_df["sig_predictive"] = (
    selected_df["failure_intensity"] > FAILURE_INTENSITY_THRESHOLD
)
_q75_impact = blast_df["weighted_impact"].quantile(0.75)
selected_df["sig_high_value"] = selected_df["weighted_impact"] >= _q75_impact


def _rationale(row):
    sigs = []
    if row["sig_operational"]:
        sigs.append("operational")
    if row["sig_predictive"]:
        sigs.append("advisory/predicted")
    if row["sig_high_value"]:
        sigs.append("high-value")
    return ", ".join(sigs) if sigs else "(low signal)"


selected_df["rationale"] = selected_df.apply(_rationale, axis=1)

print(f"\n  Selected upgrades: {len(selected_df)}")
print(
    selected_df[
        ["tower_id", "region", "tier", "capacity_gbps", "cost",
         "install_weeks", "failure_intensity", "weighted_impact",
         "rationale"]
    ].to_string(index=False)
)
print(
    f"\n  Rationale tally: "
    f"operational={int(selected_df['sig_operational'].sum())}, "
    f"advisory/predicted={int(selected_df['sig_predictive'].sum())}, "
    f"high-value={int(selected_df['sig_high_value'].sum())} "
    f"(towers can fire on multiple signals)"
)

if len(selected_df) > 0:
    print(f"\n  Total cost:               ${selected_df['cost'].sum():,.0f}")
    print(f"  Total install crew-weeks: {int(selected_df['install_weeks'].sum())}")
    print(f"  Capacity restored:        {int(selected_df['capacity_gbps'].sum())} Gbps")
    print(f"  Tier mix:                 {selected_df['tier'].value_counts().to_dict()}")
    print(f"  Towers covered:           {len(selected_df)} of {len(flagged_df)} critical")
    print(f"  Region breakdown:         {selected_df['region'].value_counts().to_dict()}")

# --------------------------------------------------
# Persist plan summary + selected view back to the ontology, so every
# headline metric (total cost, install weeks, capacity, tier mix,
# binding constraint) is first-class ontology -- not stage-local
# Python state. A downstream analyst (or Cortex Agent) can query
# RestorePlan and TowerUpgradeOption.is_selected_upgrade directly
# without re-running the chain.
# --------------------------------------------------

# RestorePlan concept: singleton holding the headline plan metrics
# (cost, install-weeks, capacity restored, tier mix, towers covered,
# binding constraint) -- the prescriptive output materialized as
# queryable ontology rather than stage-local Python state.
RestorePlan = model.Concept("RestorePlan", identify_by={"id": String})
RestorePlan.total_cost = model.Property(f"{RestorePlan} has {Float:total_cost}")
RestorePlan.total_install_weeks = model.Property(f"{RestorePlan} has {Integer:total_install_weeks}")
RestorePlan.capacity_restored_gbps = model.Property(f"{RestorePlan} has {Integer:capacity_restored_gbps}")
RestorePlan.gold_count = model.Property(f"{RestorePlan} has {Integer:gold_count}")
RestorePlan.silver_count = model.Property(f"{RestorePlan} has {Integer:silver_count}")
RestorePlan.bronze_count = model.Property(f"{RestorePlan} has {Integer:bronze_count}")
RestorePlan.towers_covered = model.Property(f"{RestorePlan} has {Integer:towers_covered}")
RestorePlan.binding_constraint = model.Property(f"{RestorePlan} has {String:binding_constraint}")

_total_cost = float(selected_df["cost"].sum()) if len(selected_df) else 0.0
_total_weeks = int(selected_df["install_weeks"].sum()) if len(selected_df) else 0
_capacity = int(selected_df["capacity_gbps"].sum()) if len(selected_df) else 0
_tier_counts = selected_df["tier"].value_counts().to_dict() if len(selected_df) else {}
_binding = (
    # 0.995: residual headroom below ~0.5% is too small to fit another
    # whole-tier upgrade (cheapest BRONZE > $25k vs $25k of slack), so
    # the cap is effectively hit. Earlier 0.999 misclassified clearly-
    # budget-bound runs as "none" when the optimizer left ~$5-10k slack.
    "budget" if _total_cost > BUDGET_USD * 0.995
    else "install_weeks" if _total_weeks >= INSTALL_WEEKS_BUDGET - 1
    else "none"
)

model.define(
    rp := RestorePlan.new(id="TELCO_RECOVERY_2024Q4"),
    rp.total_cost(_total_cost),
    rp.total_install_weeks(_total_weeks),
    rp.capacity_restored_gbps(_capacity),
    rp.gold_count(int(_tier_counts.get("GOLD", 0))),
    rp.silver_count(int(_tier_counts.get("SILVER", 0))),
    rp.bronze_count(int(_tier_counts.get("BRONZE", 0))),
    rp.towers_covered(len(selected_df)),
    rp.binding_constraint(_binding),
)

TowerUpgradeOption.is_selected_upgrade = model.Relationship(
    f"{TowerUpgradeOption} is selected upgrade"
)
model.where(TowerUpgradeOption.selected > 0.5).define(
    TowerUpgradeOption.is_selected_upgrade()
)

# Query the new ontology back to confirm everything is reachable.
print("\n  Plan (queryable as ontology):")
plan_df = (
    model.select(
        RestorePlan.id.alias("plan_id"),
        RestorePlan.total_cost.alias("total_cost"),
        RestorePlan.total_install_weeks.alias("install_weeks"),
        RestorePlan.capacity_restored_gbps.alias("capacity_gbps"),
        RestorePlan.gold_count.alias("gold"),
        RestorePlan.silver_count.alias("silver"),
        RestorePlan.bronze_count.alias("bronze"),
        RestorePlan.towers_covered.alias("towers"),
        RestorePlan.binding_constraint.alias("binding"),
    )
    .to_df()
)
print(plan_df.to_string(index=False))

print(f"\n{'=' * 60}")
print("PIPELINE COMPLETE: 4 stages executed on the shared Telco ontology")
print(f"Plan headline + {len(selected_df)}-row SelectedUpgrade view are now queryable")
print("as ontology -- RestorePlan and TowerUpgradeOption.is_selected_upgrade.")
print("=" * 60)
