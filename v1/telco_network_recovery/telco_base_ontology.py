"""Deployable base ontology for the telco network recovery template.

This module is intentionally limited to the stable domain layer:
source-table mappings, core concepts, functional relationships, and
rules-based derived properties. Predictive, graph, path, and prescriptive
calculations should run as standalone jobs on top of the deployed tables.
"""

from relationalai.semantics import Float, Integer, Model, String
from relationalai.semantics.std import aggregates as aggs

RAW_SCHEMA = "BERTOLANI.TELCO_NETWORK_RECOVERY_SOURCE"

model = Model("Telco Network Recovery Base")


def raw_table(name: str):
    return model.Table(f"{RAW_SCHEMA}.{name}")


# ---------------------------------------------------------------------------
# Source tables
# ---------------------------------------------------------------------------

cell_towers_src = raw_table("CELL_TOWERS")
network_equipment_src = raw_table("NETWORK_EQUIPMENT")
equipment_health_src = raw_table("EQUIPMENT_HEALTH")
model_advisories_src = raw_table("MODEL_ADVISORIES")
network_performance_src = raw_table("NETWORK_PERFORMANCE")
subscribers_src = raw_table("SUBSCRIBERS")
cdr_src = raw_table("CALL_DETAIL_RECORDS")
upgrade_options_src = raw_table("TOWER_UPGRADE_OPTIONS")


# ---------------------------------------------------------------------------
# Concepts and source properties
# ---------------------------------------------------------------------------

CellTower = model.Concept("CellTower", identify_by={"id": String})
CellTower.name = model.Property(f"{CellTower} has {String:name}")
CellTower.postal_code = model.Property(f"{CellTower} has {Integer:postal_code}")
CellTower.latitude = model.Property(f"{CellTower} has {Float:latitude}")
CellTower.longitude = model.Property(f"{CellTower} has {Float:longitude}")
CellTower.tower_type = model.Property(f"{CellTower} has {String:tower_type}")
CellTower.capacity_gbps = model.Property(f"{CellTower} has {Integer:capacity_gbps}")
CellTower.install_date = model.Property(f"{CellTower} has {String:install_date}")
CellTower.status = model.Property(f"{CellTower} has {String:status}")
CellTower.region = model.Property(f"{CellTower} has {String:region}")

model.define(
    tower := CellTower.new(id=cell_towers_src.TOWER_ID),
    tower.name(cell_towers_src.TOWER_NAME),
    tower.postal_code(cell_towers_src.POSTAL_CODE),
    tower.latitude(cell_towers_src.LATITUDE),
    tower.longitude(cell_towers_src.LONGITUDE),
    tower.tower_type(cell_towers_src.TOWER_TYPE),
    tower.capacity_gbps(cell_towers_src.CAPACITY_GBPS),
    tower.install_date(cell_towers_src.INSTALL_DATE),
    tower.status(cell_towers_src.STATUS),
    tower.region(cell_towers_src.REGION),
)


NetworkEquipment = model.Concept("NetworkEquipment", identify_by={"id": String})
NetworkEquipment.tower_id_fk = model.Property(
    f"{NetworkEquipment} has {String:tower_id_fk}"
)
NetworkEquipment.tower = model.Property(
    f"{NetworkEquipment} installed on {CellTower:tower}"
)
NetworkEquipment.equipment_type = model.Property(
    f"{NetworkEquipment} has {String:equipment_type}"
)
NetworkEquipment.part_id = model.Property(f"{NetworkEquipment} has {String:part_id}")
NetworkEquipment.manufacturer = model.Property(
    f"{NetworkEquipment} has {String:manufacturer}"
)
NetworkEquipment.eqp_model = model.Property(
    f"{NetworkEquipment} has {String:eqp_model}"
)
NetworkEquipment.serial_number = model.Property(
    f"{NetworkEquipment} has {String:serial_number}"
)
NetworkEquipment.install_date = model.Property(
    f"{NetworkEquipment} has {String:install_date}"
)
NetworkEquipment.firmware_version = model.Property(
    f"{NetworkEquipment} has {String:firmware_version}"
)
NetworkEquipment.status = model.Property(f"{NetworkEquipment} has {String:status}")

model.define(
    equipment := NetworkEquipment.new(id=network_equipment_src.EQUIPMENT_ID),
    equipment.tower_id_fk(network_equipment_src.TOWER_ID),
    equipment.tower(CellTower.lookup(id=network_equipment_src.TOWER_ID)),
    equipment.equipment_type(network_equipment_src.EQUIPMENT_TYPE),
    equipment.part_id(network_equipment_src.PART_ID),
    equipment.manufacturer(network_equipment_src.MANUFACTURER),
    equipment.eqp_model(network_equipment_src.MODEL),
    equipment.serial_number(network_equipment_src.SERIAL_NUMBER),
    equipment.install_date(network_equipment_src.INSTALL_DATE),
    equipment.firmware_version(network_equipment_src.FIRMWARE_VERSION),
    equipment.status(network_equipment_src.STATUS),
)


EquipmentHealth = model.Concept("EquipmentHealth", identify_by={"id": String})
EquipmentHealth.equipment_id_fk = model.Property(
    f"{EquipmentHealth} has {String:equipment_id_fk}"
)
EquipmentHealth.equipment = model.Property(
    f"{EquipmentHealth} measured for {NetworkEquipment:equipment}"
)
EquipmentHealth.mtbf_hours = model.Property(
    f"{EquipmentHealth} has {Integer:mtbf_hours}"
)
EquipmentHealth.failure_rate = model.Property(
    f"{EquipmentHealth} has {Float:failure_rate}"
)
EquipmentHealth.last_failure_date = model.Property(
    f"{EquipmentHealth} has {String:last_failure_date}"
)
EquipmentHealth.temperature_avg_c = model.Property(
    f"{EquipmentHealth} has {Float:temperature_avg_c}"
)
EquipmentHealth.power_consumption_kw = model.Property(
    f"{EquipmentHealth} has {Float:power_consumption_kw}"
)
EquipmentHealth.health_score = model.Property(
    f"{EquipmentHealth} has {Float:health_score}"
)
EquipmentHealth.measurement_date = model.Property(
    f"{EquipmentHealth} has {String:measurement_date}"
)

model.define(
    health := EquipmentHealth.new(id=equipment_health_src.HEALTH_ID),
    health.equipment_id_fk(equipment_health_src.EQUIPMENT_ID),
    health.equipment(NetworkEquipment.lookup(id=equipment_health_src.EQUIPMENT_ID)),
    health.mtbf_hours(equipment_health_src.MTBF_HOURS),
    health.failure_rate(equipment_health_src.FAILURE_RATE),
    health.last_failure_date(equipment_health_src.LAST_FAILURE_DATE),
    health.temperature_avg_c(equipment_health_src.TEMPERATURE_AVG_C),
    health.power_consumption_kw(equipment_health_src.POWER_CONSUMPTION_KW),
    health.health_score(equipment_health_src.HEALTH_SCORE),
    health.measurement_date(equipment_health_src.MEASUREMENT_DATE),
)


ModelAdvisory = model.Concept(
    "ModelAdvisory",
    identify_by={"model": String, "advisory_type": String, "issued_date": String},
)
ModelAdvisory.severity = model.Property(f"{ModelAdvisory} has {Float:severity}")
ModelAdvisory.applies_to = model.Relationship(
    f"{ModelAdvisory} applies to {NetworkEquipment}"
)

model.define(
    advisory := ModelAdvisory.new(
        model=model_advisories_src.MODEL,
        advisory_type=model_advisories_src.ADVISORY_TYPE,
        issued_date=model_advisories_src.ISSUED_DATE,
    ),
    advisory.severity(model_advisories_src.SEVERITY),
)
model.define(ModelAdvisory.applies_to(NetworkEquipment)).where(
    ModelAdvisory.model == NetworkEquipment.eqp_model
)


NetworkPerformance = model.Concept("NetworkPerformance", identify_by={"id": String})
NetworkPerformance.tower = model.Property(
    f"{NetworkPerformance} measured for {CellTower:tower}"
)
NetworkPerformance.timestamp = model.Property(
    f"{NetworkPerformance} has {String:timestamp}"
)
NetworkPerformance.latency_ms = model.Property(
    f"{NetworkPerformance} has {Float:latency_ms}"
)
NetworkPerformance.throughput_mbps = model.Property(
    f"{NetworkPerformance} has {Float:throughput_mbps}"
)
NetworkPerformance.packet_loss_pct = model.Property(
    f"{NetworkPerformance} has {Float:packet_loss_pct}"
)
NetworkPerformance.jitter_ms = model.Property(
    f"{NetworkPerformance} has {Float:jitter_ms}"
)
NetworkPerformance.signal_strength_dbm = model.Property(
    f"{NetworkPerformance} has {Integer:signal_strength_dbm}"
)
NetworkPerformance.active_connections = model.Property(
    f"{NetworkPerformance} has {Integer:active_connections}"
)
NetworkPerformance.bandwidth_utilization_pct = model.Property(
    f"{NetworkPerformance} has {Float:bandwidth_utilization_pct}"
)
NetworkPerformance.error_rate = model.Property(
    f"{NetworkPerformance} has {Float:error_rate}"
)

model.define(
    perf := NetworkPerformance.new(id=network_performance_src.METRIC_ID),
    perf.tower(CellTower.lookup(id=network_performance_src.TOWER_ID)),
    perf.timestamp(network_performance_src.TIMESTAMP),
    perf.latency_ms(network_performance_src.LATENCY_MS),
    perf.throughput_mbps(network_performance_src.THROUGHPUT_MBPS),
    perf.packet_loss_pct(network_performance_src.PACKET_LOSS_PCT),
    perf.jitter_ms(network_performance_src.JITTER_MS),
    perf.signal_strength_dbm(network_performance_src.SIGNAL_STRENGTH_DBM),
    perf.active_connections(network_performance_src.ACTIVE_CONNECTIONS),
    perf.bandwidth_utilization_pct(network_performance_src.BANDWIDTH_UTILIZATION_PCT),
    perf.error_rate(network_performance_src.ERROR_RATE),
)


class SubscriberStatus(model.Enum):
    ACTIVE = 1
    SUSPENDED = 2


Subscriber = model.Concept("Subscriber", identify_by={"id": String})
Subscriber.first_name = model.Property(f"{Subscriber} has {String:first_name}")
Subscriber.last_name = model.Property(f"{Subscriber} has {String:last_name}")
Subscriber.email = model.Property(f"{Subscriber} has {String:email}")
Subscriber.phone = model.Property(f"{Subscriber} has {String:phone}")
Subscriber.postal_code = model.Property(f"{Subscriber} has {Integer:postal_code}")
Subscriber.subscriber_type = model.Property(
    f"{Subscriber} has {String:subscriber_type}"
)
Subscriber.segment = model.Property(f"{Subscriber} has {String:segment}")
Subscriber.signup_date = model.Property(f"{Subscriber} has {String:signup_date}")
Subscriber.lifetime_value = model.Property(
    f"{Subscriber} has {Float:lifetime_value}"
)
Subscriber.churn_risk_score = model.Property(
    f"{Subscriber} has {Float:churn_risk_score}"
)
Subscriber.nps_score = model.Property(f"{Subscriber} has {Integer:nps_score}")
Subscriber.status = model.Property(f"{Subscriber} has {SubscriberStatus:status}")
Subscriber.customer_value = model.Property(
    f"{Subscriber} has {Float:customer_value}"
)

model.define(
    subscriber := Subscriber.new(id=subscribers_src.SUB_ID),
    subscriber.first_name(subscribers_src.FIRST_NAME),
    subscriber.last_name(subscribers_src.LAST_NAME),
    subscriber.email(subscribers_src.EMAIL),
    subscriber.phone(subscribers_src.PHONE),
    subscriber.postal_code(subscribers_src.POSTAL_CODE),
    subscriber.subscriber_type(subscribers_src.SUBSCRIBER_TYPE),
    subscriber.segment(subscribers_src.SEGMENT),
    subscriber.signup_date(subscribers_src.SIGNUP_DATE),
    subscriber.lifetime_value(subscribers_src.LIFETIME_VALUE_USD),
    subscriber.churn_risk_score(subscribers_src.CHURN_RISK_SCORE),
    subscriber.nps_score(subscribers_src.NPS_SCORE),
    subscriber.status(SubscriberStatus.lookup(subscribers_src.STATUS)),
)
model.define(
    Subscriber.customer_value(
        Subscriber.lifetime_value * (1.0 + Subscriber.churn_risk_score)
    )
)


CallDetailRecord = model.Concept("CallDetailRecord", identify_by={"id": String})
CallDetailRecord.caller = model.Property(
    f"{CallDetailRecord} has caller {Subscriber:caller}"
)
CallDetailRecord.callee = model.Property(
    f"{CallDetailRecord} has callee {Subscriber:callee}"
)
CallDetailRecord.call_type = model.Property(
    f"{CallDetailRecord} has {String:call_type}"
)
CallDetailRecord.call_start_time = model.Property(
    f"{CallDetailRecord} has {String:call_start_time}"
)
CallDetailRecord.call_duration_seconds = model.Property(
    f"{CallDetailRecord} has {Integer:call_duration_seconds}"
)
CallDetailRecord.call_status = model.Property(
    f"{CallDetailRecord} has {String:call_status}"
)
CallDetailRecord.routed_through = model.Property(
    f"{CallDetailRecord} routed through {CellTower:tower}"
)
CallDetailRecord.data_used_mb = model.Property(
    f"{CallDetailRecord} has {Float:data_used_mb}"
)
CallDetailRecord.call_quality_score = model.Property(
    f"{CallDetailRecord} has {Float:call_quality_score}"
)

model.define(
    cdr := CallDetailRecord.new(id=cdr_src.CDR_ID),
    cdr.caller(Subscriber.lookup(id=cdr_src.CALLER_SUB_ID)),
    cdr.callee(Subscriber.lookup(id=cdr_src.CALLEE_SUB_ID)),
    cdr.call_type(cdr_src.CALL_TYPE),
    cdr.call_start_time(cdr_src.CALL_START_TIME),
    cdr.call_duration_seconds(cdr_src.CALL_DURATION_SECONDS),
    cdr.call_status(cdr_src.CALL_STATUS),
    cdr.routed_through(CellTower.lookup(id=cdr_src.TOWER_ID)),
    cdr.data_used_mb(cdr_src.DATA_USED_MB),
    cdr.call_quality_score(cdr_src.CALL_QUALITY_SCORE),
)


TowerUpgradeOption = model.Concept(
    "TowerUpgradeOption", identify_by={"tower_id": String, "tier": String}
)
TowerUpgradeOption.tower = model.Property(
    f"{TowerUpgradeOption} upgrades {CellTower:tower}"
)
TowerUpgradeOption.capacity_increase_gbps = model.Property(
    f"{TowerUpgradeOption} has {Integer:capacity_increase_gbps}"
)
TowerUpgradeOption.cost = model.Property(f"{TowerUpgradeOption} has {Integer:cost}")
TowerUpgradeOption.install_weeks = model.Property(
    f"{TowerUpgradeOption} has {Integer:install_weeks}"
)

model.define(
    option := TowerUpgradeOption.new(
        tower_id=upgrade_options_src.TOWER_ID,
        tier=upgrade_options_src.UPGRADE_TIER,
    ),
    option.tower(CellTower.lookup(id=upgrade_options_src.TOWER_ID)),
    option.capacity_increase_gbps(upgrade_options_src.CAPACITY_INCREASE_GBPS),
    option.cost(upgrade_options_src.COST_USD),
    option.install_weeks(upgrade_options_src.INSTALL_WEEKS),
)


# ---------------------------------------------------------------------------
# Rules-based base enrichments suitable for deployment
# ---------------------------------------------------------------------------

CellTower.avg_packet_loss = model.Property(
    f"{CellTower} has {Float:avg_packet_loss}"
)
CellTower.avg_latency_ms = model.Property(f"{CellTower} has {Float:avg_latency_ms}")
CellTower.avg_error_rate = model.Property(f"{CellTower} has {Float:avg_error_rate}")
CellTower.avg_health_score = model.Property(
    f"{CellTower} has {Float:avg_health_score}"
)
CellTower.operational_critical_restore = model.Relationship(
    f"{CellTower} is operational critical restore"
)

model.define(
    CellTower.avg_packet_loss(
        aggs.avg(NetworkPerformance.packet_loss_pct)
        .where(NetworkPerformance.tower == CellTower)
        .per(CellTower)
    )
)
model.define(
    CellTower.avg_latency_ms(
        aggs.avg(NetworkPerformance.latency_ms)
        .where(NetworkPerformance.tower == CellTower)
        .per(CellTower)
    )
)
model.define(
    CellTower.avg_error_rate(
        aggs.avg(NetworkPerformance.error_rate)
        .where(NetworkPerformance.tower == CellTower)
        .per(CellTower)
    )
)
model.define(
    CellTower.avg_health_score(
        aggs.avg(EquipmentHealth.health_score)
        .where(
            EquipmentHealth.equipment == NetworkEquipment,
            NetworkEquipment.tower == CellTower,
        )
        .per(CellTower)
    )
)

model.where(
    CellTower.region == "WEST",
    CellTower.status == "DEGRADED",
    CellTower.avg_health_score < 0.85,
).define(CellTower.operational_critical_restore())

model.where(
    CellTower.region == "WEST",
    CellTower.avg_packet_loss > 5.0,
    CellTower.avg_health_score < 0.85,
).define(CellTower.operational_critical_restore())
