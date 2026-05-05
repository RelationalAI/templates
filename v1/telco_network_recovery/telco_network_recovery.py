"""Telco network recovery (multi-reasoner) template.

This script demonstrates a four-stage multi-reasoner pipeline in RelationalAI,
combining predictive forecasting, declarative rules, graph analysis, and
prescriptive optimization on a single shared ontology. The narrative thread:
one region (WEST) is missing revenue targets while every other region grows;
the chain produces an actionable tower-upgrade plan.

- Stage 1 -- Predictive: train a regression GNN on per-region daily KPIs to
  forecast subscriber growth. Per-region predicted growth is bound back to
  each CellTower as `projected_demand_growth`, consumed by Stage 4's objective.
- Stage 2 -- Rules: derive per-tower averages from NetworkPerformance and
  EquipmentHealth aggregations, then flag `CellTower.is_critical_restore`
  for WEST DEGRADED towers with low equipment health.
- Stage 3 -- Graph: PageRank on a directed Subscriber -> Subscriber call
  graph (caller -> callee). Per-critical-tower `weighted_impact` aggregates
  the influence scores of subscribers whose calls route through that tower.
- Stage 4 -- Prescriptive: tower-upgrade MIP. Decision variable
  `TowerUpgradeOption.selected` is binary (one of three tiers per tower).
  Constraints: at most one tier per tower, total cost <= budget, total
  install crew-weeks <= 200. Objective maximizes
  selected x capacity_increase x weighted_impact x projected_demand_growth.

Each stage enriches the shared ontology, and downstream stages consume those
enrichments as first-class properties -- the accretive enrichment pattern.

Run:
    python telco_network_recovery.py

Output:
    Per-stage console summary including:
    - Per-region GNN-predicted subscriber growth (Dec test horizon)
    - 15 critical_restore towers with their derived health metrics
    - PageRank-based per-tower blast radius (distinct subs touched + total influence)
    - Optimal tower-upgrade plan: status, total cost, capacity restored, tier mix
"""

import datetime as dt
from pathlib import Path

import pandas as pd
from relationalai.semantics import (
    Any,
    Date,
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

# Stage 4 budget envelope (matches the source-demo numbers).
BUDGET_USD = 5_000_000
INSTALL_WEEKS_BUDGET = 200

# RelationalAI's predictive reasoner writes GNN experiment artifacts to a
# Snowflake schema that the RELATIONALAI native app must have write access
# to. Set EXP_DATABASE to a database you own; the schema EXPERIMENTS will
# be created on first run. See README "Prerequisites" for the one-time
# setup DDL.
EXP_DATABASE = "TELCO_ENRICHMENT"
EXP_SCHEMA = "EXPERIMENTS"

pd.set_option("display.float_format", lambda v: f"{v:,.4f}")

# --------------------------------------------------
# Load CSV data
# --------------------------------------------------

cell_towers_df = pd.read_csv(DATA_DIR / "cell_towers.csv")
subscribers_df = pd.read_csv(DATA_DIR / "subscribers.csv")
cdr_df = pd.read_csv(DATA_DIR / "call_detail_records.csv")
network_perf_df = pd.read_csv(DATA_DIR / "network_performance.csv")
network_equipment_df = pd.read_csv(DATA_DIR / "network_equipment.csv")
equipment_health_df = pd.read_csv(DATA_DIR / "equipment_health.csv")
upgrade_options_df = pd.read_csv(DATA_DIR / "tower_upgrade_options.csv")
tsm_df = pd.read_csv(DATA_DIR / "time_series_metrics.csv", parse_dates=["METRIC_DATE"])

# Compute per-region temporal lag features for the GNN. The source pipeline
# precomputed these in Snowflake via window functions; here we do the same
# transformation in pandas before loading the rows into PyRel.
tsm_df = tsm_df.sort_values(["REGION", "METRIC_DATE"]).reset_index(drop=True)
tsm_df["PREV_DAY_GROWTH"] = tsm_df.groupby("REGION")["SUBSCRIBER_GROWTH_RATE"].shift(1).fillna(0.0)
tsm_df["PREV_WEEK_GROWTH"] = tsm_df.groupby("REGION")["SUBSCRIBER_GROWTH_RATE"].shift(7).fillna(0.0)
tsm_df["GROWTH_7D_MEAN"] = (
    tsm_df.groupby("REGION")["SUBSCRIBER_GROWTH_RATE"]
    .shift(1)
    .rolling(7, min_periods=1)
    .mean()
    .fillna(0.0)
    .reset_index(level=0, drop=True)
)
tsm_df["REGION_FEAT"] = tsm_df["REGION"]

# Same-region 1-day-lag temporal edges drive GNN message passing along time.
edge_df = tsm_df[["METRIC_DATE", "REGION"]].copy()
edge_df["PREV_DATE"] = edge_df.groupby("REGION")["METRIC_DATE"].shift(1)
edge_df = edge_df.dropna(subset=["PREV_DATE"]).reset_index(drop=True)
edge_df = edge_df.rename(columns={"METRIC_DATE": "DST_DATE", "REGION": "DST_REGION", "PREV_DATE": "SRC_DATE"})
edge_df["SRC_REGION"] = edge_df["DST_REGION"]
edge_df = edge_df[["SRC_DATE", "SRC_REGION", "DST_DATE", "DST_REGION"]]
edge_df["SRC_DATE"] = pd.to_datetime(edge_df["SRC_DATE"]).dt.date
edge_df["DST_DATE"] = pd.to_datetime(edge_df["DST_DATE"]).dt.date

tsm_df["METRIC_DATE"] = tsm_df["METRIC_DATE"].dt.date

# Train < Nov 2024 (covers WEST's Sep-Oct decline onset).
# Val = Nov 2024. Test = Dec 2024.
val_start = dt.date(2024, 11, 1)
test_start = dt.date(2024, 12, 1)
train_df = tsm_df.loc[tsm_df["METRIC_DATE"] < val_start, ["METRIC_DATE", "REGION", "SUBSCRIBER_GROWTH_RATE"]].reset_index(drop=True)
val_df = tsm_df.loc[(tsm_df["METRIC_DATE"] >= val_start) & (tsm_df["METRIC_DATE"] < test_start),
                     ["METRIC_DATE", "REGION", "SUBSCRIBER_GROWTH_RATE"]].reset_index(drop=True)
test_df = tsm_df.loc[tsm_df["METRIC_DATE"] >= test_start, ["METRIC_DATE", "REGION"]].reset_index(drop=True)

print(f"RegionMetric rows: {len(tsm_df):,}  (9 regions x 365 days)")
print(f"Cell towers: {len(cell_towers_df)}  Subscribers: {len(subscribers_df)}  CDRs: {len(cdr_df):,}")
print(f"NetworkPerformance: {len(network_perf_df):,}  NetworkEquipment: {len(network_equipment_df)}  EquipmentHealth: {len(equipment_health_df)}")
print(f"TowerUpgradeOptions: {len(upgrade_options_df)}  (3 tiers per tower)")
print(f"GNN splits: train={len(train_df):,} (<{val_start})  val={len(val_df)} (Nov)  test={len(test_df)} (Dec)")

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

model = Model("Telco Network Recovery")

# CellTower concept: physical radio tower in a region. Status = ACTIVE /
# DEGRADED / MAINTENANCE; capacity_gbps caps total throughput.
CellTower = model.Concept("CellTower", identify_by={"id": String})
CellTower.name = model.Property(f"{CellTower} has {String:name}")
CellTower.tower_type = model.Property(f"{CellTower} has {String:tower_type}")
CellTower.capacity_gbps = model.Property(f"{CellTower} has {Integer:capacity_gbps}")
CellTower.status = model.Property(f"{CellTower} has {String:status}")
CellTower.region = model.Property(f"{CellTower} has {String:region}")

src = model.data(cell_towers_df)
model.define(CellTower.new(
    id=src.TOWER_ID,
    name=src.TOWER_NAME,
    tower_type=src.TOWER_TYPE,
    capacity_gbps=src.CAPACITY_GBPS,
    status=src.STATUS,
    region=src.REGION,
))

# NetworkEquipment concept: radio / antenna / baseband installed at a tower.
NetworkEquipment = model.Concept("NetworkEquipment", identify_by={"id": String})
NetworkEquipment.installed_at = model.Relationship(
    f"{NetworkEquipment} installed at {CellTower}", short_name="equipment_installed_at"
)
src = model.data(network_equipment_df)
model.define(NetworkEquipment.new(
    id=src.EQUIPMENT_ID,
    installed_at=CellTower.filter_by(id=src.TOWER_ID),
))

# EquipmentHealth concept: per-equipment health snapshot. health_score is
# 0-1; below 0.85 is the threshold for degraded health in Stage 2.
EquipmentHealth = model.Concept("EquipmentHealth", identify_by={"id": String})
EquipmentHealth.health_score = model.Property(f"{EquipmentHealth} has {Float:health_score}")
EquipmentHealth.for_equipment = model.Relationship(
    f"{EquipmentHealth} for equipment {NetworkEquipment}", short_name="health_for_equipment"
)
src = model.data(equipment_health_df)
model.define(EquipmentHealth.new(
    id=src.HEALTH_ID,
    health_score=src.HEALTH_SCORE,
    for_equipment=NetworkEquipment.filter_by(id=src.EQUIPMENT_ID),
))

# NetworkPerformance concept: per-tower performance measurement. Stage 2
# aggregates these into per-tower averages (packet loss, latency, error rate).
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

# Subscriber concept: account holder. Used as nodes in the call graph.
Subscriber = model.Concept("Subscriber", identify_by={"id": String})
Subscriber.subscriber_type = model.Property(f"{Subscriber} has {String:subscriber_type}")
Subscriber.lifetime_value = model.Property(f"{Subscriber} has {Float:lifetime_value}")
src = model.data(subscribers_df)
model.define(Subscriber.new(
    id=src.SUB_ID,
    subscriber_type=src.SUBSCRIBER_TYPE,
    lifetime_value=src.LIFETIME_VALUE_USD,
))

# CallDetailRecord concept: directed call between two subscribers, routed
# through a single tower. Acts as the edge concept for the call graph.
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

# TowerUpgradeOption concept: junction with compound identity (tower, tier).
# Each critical tower has 3 options (BRONZE / SILVER / GOLD) with different
# capacity, cost, and install-time tradeoffs. Stage 4's binary decision
# variable is the `selected` property.
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

# RegionMetric concept: composite-key (date, region) daily KPI row. Target
# of the Stage 1 GNN regression.
RegionMetric = model.Concept(
    "RegionMetric", identify_by={"metric_date": Date, "region": String}
)
tsm_src = model.data(tsm_df)
model.define(RegionMetric.new(tsm_src.to_schema()))

# TemporalEdge concept: same-region 1-day-lag pair connecting consecutive
# RegionMetric rows. The Graph reasoner builds edges from these pairs.
TemporalEdge = model.Concept(
    "TemporalEdge",
    identify_by={"src_date": Date, "src_region": String, "dst_date": Date, "dst_region": String},
)
te_src = model.data(edge_df)
model.define(TemporalEdge.new(te_src.to_schema()))

# --------------------------------------------------
# Stage 1: Predictive -- per-region growth GNN
# --------------------------------------------------

print(f"\n{'=' * 60}")
print("STAGE 1: PREDICTIVE -- per-region subscriber-growth GNN")
print("=" * 60)

# Build a directed graph over RegionMetric where each edge connects a metric
# to its same-region predecessor (1-day lag). The GNN propagates signal
# along these temporal edges plus the region category.
gnn_graph = Graph(model, directed=True, weighted=False)
src_rm = RegionMetric.ref()
dst_rm = RegionMetric.ref()
te_ref = TemporalEdge.ref()
model.define(gnn_graph.Edge.new(src=src_rm, dst=dst_rm)).where(
    te_ref.src_region == src_rm.region,
    te_ref.src_date == src_rm.metric_date,
    te_ref.dst_region == dst_rm.region,
    te_ref.dst_date == dst_rm.metric_date,
)

# Feature scopes for the GNN. Drop the date (encoded by edges), the target,
# and high-cardinality compound identity columns.
pt = PropertyTransformer(
    drop=[RegionMetric.metric_date, RegionMetric.subscriber_growth_rate],
    category=[RegionMetric.region, RegionMetric.region_feat],
    continuous=[
        RegionMetric.daily_revenue_usd,
        RegionMetric.avg_call_quality,
        RegionMetric.network_availability_pct,
        RegionMetric.data_consumed_tb,
        RegionMetric.avg_latency_ms,
        RegionMetric.churn_rate,
        RegionMetric.nps_daily_avg,
        RegionMetric.marketing_spend_usd,
        RegionMetric.prev_day_growth,
        RegionMetric.prev_week_growth,
        RegionMetric.growth_7d_mean,
    ],
    integer=[
        RegionMetric.active_subscribers,
        RegionMetric.total_calls,
        RegionMetric.support_tickets_opened,
        RegionMetric.support_tickets_resolved,
    ],
)

TrainTable = model.Concept("TrainTable")
ValTable = model.Concept("ValTable")
TestTable = model.Concept("TestTable")
model.define(TrainTable.new(model.data(train_df).to_schema()))
model.define(ValTable.new(model.data(val_df).to_schema()))
model.define(TestTable.new(model.data(test_df).to_schema()))

Train = model.Relationship(f"{RegionMetric} has {Any:value}")
model.define(Train(RegionMetric, TrainTable.subscriber_growth_rate)).where(
    RegionMetric.metric_date == TrainTable.metric_date,
    RegionMetric.region == TrainTable.region,
)
Val = model.Relationship(f"{RegionMetric} has {Any:value}")
model.define(Val(RegionMetric, ValTable.subscriber_growth_rate)).where(
    RegionMetric.metric_date == ValTable.metric_date,
    RegionMetric.region == ValTable.region,
)
Test = model.Relationship(f"{RegionMetric}")
model.define(Test(RegionMetric)).where(
    RegionMetric.metric_date == TestTable.metric_date,
    RegionMetric.region == TestTable.region,
)

gnn = GNN(
    exp_database=EXP_DATABASE,
    exp_schema=EXP_SCHEMA,
    graph=gnn_graph,
    property_transformer=pt,
    train=Train,
    validation=Val,
    task_type="regression",
    eval_metric="rmse",
    has_time_column=False,
    stream_logs=False,
    seed=SEED,
    device="cpu",
    n_epochs=GNN_EPOCHS,
    lr=GNN_LR,
)
gnn.fit()
RegionMetric.predictions = gnn.predictions(domain=Test)

predictions_df = (
    select(
        RegionMetric.metric_date.alias("date"),
        RegionMetric.region.alias("region"),
        RegionMetric.predictions.predicted_value.alias("predicted_growth"),
    )
    .where(RegionMetric.predictions)
    .to_df()
)
predictions_df["predicted_growth"] = predictions_df["predicted_growth"].astype(float)

per_region = (
    predictions_df.groupby("region")["predicted_growth"]
    .mean()
    .reset_index()
    .rename(columns={"predicted_growth": "MEAN_PREDICTED_GROWTH"})
    .sort_values("MEAN_PREDICTED_GROWTH")
)
per_region["MULTIPLIER"] = 1.0 + per_region["MEAN_PREDICTED_GROWTH"]
per_region.columns = ["REGION_ID", "MEAN_PREDICTED_GROWTH", "MULTIPLIER"]
print("\n  Per-region GNN-predicted SUBSCRIBER_GROWTH_RATE (Dec 2024 test horizon):")
print(per_region.to_string(index=False))

# Bind per-region multiplier back to each CellTower as projected_demand_growth.
# Loaded as a small RegionGrowth concept and joined to CellTower via region.
RegionGrowth = model.Concept("RegionGrowth", identify_by={"region": String})
RegionGrowth.multiplier = model.Property(f"{RegionGrowth} has {Float:multiplier}")
rg_src = model.data(per_region[["REGION_ID", "MULTIPLIER"]])
model.define(RegionGrowth.new(
    region=rg_src.REGION_ID,
    multiplier=rg_src.MULTIPLIER,
))

# CellTower.projected_demand_growth: the per-tower demand multiplier
# inherited from its region's GNN forecast. Stage 4's objective reads this.
CellTower.projected_demand_growth = model.Property(
    f"{CellTower} has {Float:projected_demand_growth}"
)
model.define(CellTower.projected_demand_growth(RegionGrowth.multiplier)).where(
    RegionGrowth.region == CellTower.region,
)

# --------------------------------------------------
# Stage 2: Rules -- flag is_critical_restore towers
# --------------------------------------------------

print(f"\n{'=' * 60}")
print("STAGE 2: RULES -- flag is_critical_restore towers")
print("=" * 60)

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

# Per-tower equipment health average across all attached equipment (two-hop
# join: NetworkPerformance / EquipmentHealth -> NetworkEquipment -> CellTower).
CellTower.avg_health_score = model.Property(f"{CellTower} has {Float:avg_health_score}")
model.define(
    CellTower.avg_health_score(
        aggs.avg(EquipmentHealth.health_score)
        .where(
            EquipmentHealth.for_equipment(NetworkEquipment),
            NetworkEquipment.installed_at(CellTower),
        )
        .per(CellTower)
    )
)

# is_critical_restore flag. Two branches (OR semantics):
#   1. WEST + DEGRADED status + low equipment health
#   2. WEST + high packet loss + low equipment health (catches ACTIVE-but-failing)
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

flagged_df = (
    model.where(CellTower.is_critical_restore())
    .select(
        CellTower.id.alias("tower_id"),
        CellTower.status.alias("status"),
        CellTower.capacity_gbps.alias("capacity_gbps"),
        CellTower.avg_packet_loss.alias("avg_loss"),
        CellTower.avg_latency_ms.alias("avg_lat"),
        CellTower.avg_health_score.alias("avg_health"),
    )
    .to_df()
    .sort_values("avg_health")
)
print(f"\n  Flagged critical_restore towers: {len(flagged_df)}")
print(flagged_df.to_string(index=False))

# --------------------------------------------------
# Stage 3: Graph -- PageRank + per-tower blast radius
# --------------------------------------------------

print(f"\n{'=' * 60}")
print("STAGE 3: GRAPH -- PageRank + per-critical-tower blast radius")
print("=" * 60)

# Directed Subscriber -> Subscriber call graph. CallDetailRecord IS the
# edge concept; aggregator="sum" collapses parallel calls between the same
# pair. Pattern 3 (edge_concept) from rai-graph-analysis.
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

# PageRank on the call graph -- result lands directly on Subscriber
# because node_concept=Subscriber.
call_graph.Node.influence_score = call_graph.pagerank()

top_subs = (
    model.select(
        Subscriber.id.alias("sub_id"),
        Subscriber.subscriber_type.alias("type"),
        Subscriber.lifetime_value.alias("ltv"),
        Subscriber.influence_score.alias("influence"),
    )
    .to_df()
    .sort_values("influence", ascending=False)
    .head(10)
)
print("\n  Top 10 subscribers by PageRank:")
print(top_subs.to_string(index=False))

# Per-critical-tower blast radius: distinct subscribers whose calls route
# through the tower, plus the sum of their PageRank.
CellTower.impact_count = model.Property(f"{CellTower} has {Float:impact_count}")
CellTower.weighted_impact = model.Property(f"{CellTower} has {Float:weighted_impact}")

model.define(
    CellTower.impact_count(
        aggs.count(distinct(Subscriber))
        .where(
            CallDetailRecord.routed_through(CellTower),
            CallDetailRecord.caller(Subscriber),
        )
        .per(CellTower)
    )
)
model.define(
    CellTower.weighted_impact(
        aggs.sum(Subscriber.influence_score)
        .where(
            CallDetailRecord.routed_through(CellTower),
            CallDetailRecord.caller(Subscriber),
        )
        .per(CellTower)
    )
)

blast_df = (
    model.where(CellTower.is_critical_restore())
    .select(
        CellTower.id.alias("tower_id"),
        CellTower.impact_count.alias("impact_count"),
        CellTower.weighted_impact.alias("weighted_impact"),
        CellTower.projected_demand_growth.alias("growth_mult"),
    )
    .to_df()
    .sort_values("weighted_impact", ascending=False)
)
print("\n  Per-critical-tower blast radius (impact_count, weighted_impact, growth_mult from Stage 1):")
print(blast_df.to_string(index=False))

# --------------------------------------------------
# Stage 4: Prescriptive -- tower upgrade MIP
# --------------------------------------------------

print(f"\n{'=' * 60}")
print("STAGE 4: PRESCRIPTIVE -- tower upgrade selection MIP")
print("=" * 60)

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

# Objective: maximize three-factor weighted capacity gain. The three
# coefficients each come from a different upstream stage:
#   capacity_increase_gbps -- raw upgrade attribute
#   weighted_impact        -- Stage 3 graph (subscriber influence)
#   projected_demand_growth -- Stage 1 GNN (regional forecast)
problem.maximize(
    aggs.sum(
        TowerUpgradeOption.selected
        * TowerUpgradeOption.capacity_increase_gbps
        * CellTower.weighted_impact
        * CellTower.projected_demand_growth
    ).where(
        TowerUpgradeOption.for_tower(CellTower),
        CellTower.is_critical_restore(),
    )
)

print("\n  Solving...")
problem.solve(solver="gurobi")
problem.display()

# Extract the selected upgrades.
plan_df = (
    model.where(
        TowerUpgradeOption.for_tower(CellTower),
        CellTower.is_critical_restore(),
    )
    .select(
        CellTower.id.alias("tower_id"),
        TowerUpgradeOption.tier.alias("tier"),
        TowerUpgradeOption.cost.alias("cost"),
        TowerUpgradeOption.capacity_increase_gbps.alias("cap_gbps"),
        TowerUpgradeOption.install_weeks.alias("weeks"),
        CellTower.weighted_impact.alias("wgt_impact"),
        CellTower.projected_demand_growth.alias("growth"),
        TowerUpgradeOption.selected.alias("x"),
    )
    .to_df()
)
plan_df["x"] = plan_df["x"].astype(float)
selected = plan_df[plan_df["x"] > 0.5].copy().sort_values("wgt_impact", ascending=False)

print("\n  OPTIMAL plan -- selected upgrades:")
print(selected[["tower_id", "tier", "cost", "cap_gbps", "weeks", "wgt_impact", "growth"]].to_string(index=False))
print()
print(f"  Total cost:               ${selected['cost'].astype(float).sum():,.0f}  (budget ${BUDGET_USD:,})")
print(f"  Total install crew-weeks: {selected['weeks'].astype(int).sum()}  (budget {INSTALL_WEEKS_BUDGET})")
print(f"  Capacity restored:        {selected['cap_gbps'].astype(int).sum()} Gbps")
print(f"  Tier mix:                 {selected['tier'].value_counts().to_dict()}")
print(f"  Towers covered:           {len(selected)} of {plan_df['tower_id'].nunique()} critical")

print(f"\n{'=' * 60}")
print("PIPELINE COMPLETE: 4 stages executed on the shared Telco ontology")
print("=" * 60)
