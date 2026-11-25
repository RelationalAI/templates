"""Bundled telco CSVs, the equipment train / validation / test split, and the base-fact mappings."""

from pathlib import Path

import pandas as pd

from .schema import (
    CallDetailRecord,
    CellTower,
    EquipmentHealth,
    ModelAdvisory,
    NetworkEquipment,
    NetworkPerformance,
    Subscriber,
    SubscriberStatus,
    Test,
    TestEqTable,
    TowerUpgradeOption,
    Train,
    TrainEqTable,
    Val,
    ValEqTable,
    model,
)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

SEED = 42

cell_towers_df = pd.read_csv(DATA_DIR / "cell_towers.csv", parse_dates=["INSTALL_DATE"])
subscribers_df = pd.read_csv(DATA_DIR / "subscribers.csv")
cdr_df = pd.read_csv(DATA_DIR / "call_detail_records.csv")
network_perf_df = pd.read_csv(DATA_DIR / "network_performance.csv")
network_equipment_df = pd.read_csv(DATA_DIR / "network_equipment.csv", parse_dates=["INSTALL_DATE"])
equipment_health_df = pd.read_csv(
    DATA_DIR / "equipment_health.csv",
    parse_dates=["LAST_FAILURE_DATE", "MEASUREMENT_DATE"],
)
upgrade_options_df = pd.read_csv(DATA_DIR / "tower_upgrade_options.csv")
advisories_df = pd.read_csv(DATA_DIR / "model_advisories.csv", parse_dates=["ISSUED_DATE"])

# Train/val/test split. Train + val carry labels for fit + evaluation;
# test = ALL equipment so every item receives a prediction (inference
# domain) for the chain's per-tower aggregation. The shuffle runs in pandas
# because PyRel 2.3.0 has no seeded random shuffle.
eq_shuf = network_equipment_df.sample(frac=1, random_state=SEED).reset_index(drop=True)
n = len(eq_shuf)
train_n = int(n * 0.70)
val_n = int(n * 0.15)
train_eq_df = eq_shuf.iloc[:train_n][["EQUIPMENT_ID"]].rename(
    columns={"EQUIPMENT_ID": "equipment_id"}
).reset_index(drop=True)
val_eq_df = eq_shuf.iloc[train_n:train_n + val_n][["EQUIPMENT_ID"]].rename(
    columns={"EQUIPMENT_ID": "equipment_id"}
).reset_index(drop=True)
test_eq_df = network_equipment_df[["EQUIPMENT_ID"]].rename(
    columns={"EQUIPMENT_ID": "equipment_id"}
).reset_index(drop=True)

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

src = model.data(network_equipment_df)
model.define(NetworkEquipment.new(
    id=src.EQUIPMENT_ID,
    equipment_type=src.EQUIPMENT_TYPE,
    manufacturer=src.MANUFACTURER,
    eqp_model=src.MODEL,
    firmware_version=src.FIRMWARE_VERSION,
    install_date=src.INSTALL_DATE,
    tower_id_fk=src.TOWER_ID,
    status=src.STATUS,
))

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

# The most severe advisory per MODEL is picked in pandas: the advisory rows carry no id, so a
# rule could not tell apart two notices with the same MODEL and type.
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

model.define(TrainEqTable.new(model.data(train_eq_df).to_schema()))
model.define(ValEqTable.new(model.data(val_eq_df).to_schema()))
model.define(TestEqTable.new(model.data(test_eq_df).to_schema()))

model.define(Train(NetworkEquipment, NetworkEquipment.at_risk)).where(
    NetworkEquipment.id == TrainEqTable.equipment_id,
)
model.define(Val(NetworkEquipment, NetworkEquipment.at_risk)).where(
    NetworkEquipment.id == ValEqTable.equipment_id,
)
model.define(Test(NetworkEquipment)).where(
    NetworkEquipment.id == TestEqTable.equipment_id,
)

src = model.data(network_perf_df)
model.define(NetworkPerformance.new(
    id=src.METRIC_ID,
    packet_loss_pct=src.PACKET_LOSS_PCT,
    latency_ms=src.LATENCY_MS,
    error_rate=src.ERROR_RATE,
    for_tower=CellTower.lookup(id=src.TOWER_ID),
))

src = model.data(subscribers_df)
model.define(
    sub := Subscriber.new(
        id=src.SUB_ID,
        subscriber_type=src.SUBSCRIBER_TYPE,
        segment=src.SEGMENT,
        lifetime_value=src.LIFETIME_VALUE_USD,
        churn_risk_score=src.CHURN_RISK_SCORE,
    ),
    sub.status(SubscriberStatus.lookup(src.STATUS)),
)

src = model.data(cdr_df)
model.define(CallDetailRecord.new(
    id=src.CDR_ID,
    caller=Subscriber.lookup(id=src.CALLER_SUB_ID),
    callee=Subscriber.lookup(id=src.CALLEE_SUB_ID),
    routed_through=CellTower.lookup(id=src.TOWER_ID),
))

src = model.data(upgrade_options_df)
model.define(TowerUpgradeOption.new(
    tower_id=src.TOWER_ID,
    tier=src.UPGRADE_TIER,
    capacity_increase_gbps=src.CAPACITY_INCREASE_GBPS,
    cost=src.COST_USD,
    install_weeks=src.INSTALL_WEEKS,
    for_tower=CellTower.lookup(id=src.TOWER_ID),
))
