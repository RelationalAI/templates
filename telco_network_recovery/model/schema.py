"""Semantic schema for the telco network recovery template: towers, equipment, advisories, subscribers, calls, and upgrade options."""

from relationalai.semantics import DateTime, Float, Integer, Model, String

model = Model("telco_network_recovery")
Concept, Property, Relationship = model.Concept, model.Property, model.Relationship

# CellTower concept: a physical radio tower in a region. The GNN
# reaches it from each NetworkEquipment via the tower_id_fk
# property-equality edge.
CellTower = Concept("CellTower", identify_by={"id": String})
CellTower.name = Property(f"{CellTower} has {String:name}")
CellTower.tower_type = Property(f"{CellTower} has {String:tower_type}")
CellTower.capacity_gbps = Property(f"{CellTower} has {Integer:capacity_gbps}")
# status stays a String (not a model.Enum): the GNN's PropertyTransformer
# consumes it as a categorical feature.
CellTower.status = Property(f"{CellTower} has {String:status}")
CellTower.region = Property(f"{CellTower} has {String:region}")
CellTower.install_date = Property(f"{CellTower} has {DateTime:install_date}")

# NetworkEquipment concept: equipment items (radios, antennas, BBUs,
# amplifiers, ...) installed on cell towers; the GNN's prediction
# target. tower_id_fk is an explicit FK property used by the GNN
# graph via property equality, so heterogeneous edges are expressed as
# property-level equality conditions rather than `Relationship`
# traversal. at_risk is the label (1 if STATUS is FAILING or WARNING);
# the GNN drops it from the features to prevent leakage.
NetworkEquipment = Concept("NetworkEquipment", identify_by={"id": String})
NetworkEquipment.equipment_type = Property(f"{NetworkEquipment} has {String:equipment_type}")
NetworkEquipment.manufacturer = Property(f"{NetworkEquipment} has {String:manufacturer}")
NetworkEquipment.eqp_model = Property(f"{NetworkEquipment} has {String:eqp_model}")
NetworkEquipment.firmware_version = Property(f"{NetworkEquipment} has {String:firmware_version}")
NetworkEquipment.install_date = Property(f"{NetworkEquipment} has {DateTime:install_date}")
NetworkEquipment.tower_id_fk = Property(f"{NetworkEquipment} has {String:tower_id_fk}")
NetworkEquipment.at_risk = Property(f"{NetworkEquipment} has {Integer:at_risk}")

# EquipmentHealth concept: per-equipment health snapshot (MTBF, failure
# rate, temperature, power consumption, health score). All numeric
# columns flow into the GNN via the equipment_id_fk property-equality
# edge.
EquipmentHealth = Concept("EquipmentHealth", identify_by={"id": String})
EquipmentHealth.mtbf_hours = Property(f"{EquipmentHealth} has {Integer:mtbf_hours}")
EquipmentHealth.failure_rate = Property(f"{EquipmentHealth} has {Float:failure_rate}")
EquipmentHealth.last_failure_date = Property(f"{EquipmentHealth} has {DateTime:last_failure_date}")
EquipmentHealth.temperature_avg_c = Property(f"{EquipmentHealth} has {Float:temperature_avg_c}")
EquipmentHealth.power_consumption_kw = Property(f"{EquipmentHealth} has {Float:power_consumption_kw}")
EquipmentHealth.health_score = Property(f"{EquipmentHealth} has {Float:health_score}")
EquipmentHealth.measurement_date = Property(f"{EquipmentHealth} has {DateTime:measurement_date}")
EquipmentHealth.equipment_id_fk = Property(f"{EquipmentHealth} has {String:equipment_id_fk}")

# ModelAdvisory concept: a manufacturer-issued recall / defect batch /
# firmware bug / EOL / security-patch notice that applies to an
# equipment MODEL. The relational signal the GNN propagates to every
# NetworkEquipment sharing the affected MODEL. Multiple advisories on
# the same MODEL collapse to one row (the max severity) so the GNN sees
# one ModelAdvisory node per affected fleet.
ModelAdvisory = Concept("ModelAdvisory", identify_by={"model": String})
ModelAdvisory.advisory_type = Property(f"{ModelAdvisory} has {String:advisory_type}")
ModelAdvisory.severity = Property(f"{ModelAdvisory} has {Float:severity}")
ModelAdvisory.issued_date = Property(f"{ModelAdvisory} has {DateTime:issued_date}")

# TrainEqTable / ValEqTable / TestEqTable concepts: GNN task tables
# holding (equipment_id, at_risk) pairs for training / validation /
# inference. Test = all equipment so every NetworkEquipment receives
# a prediction, independent of train/val split.
TrainEqTable = Concept("TrainEqTable")
ValEqTable = Concept("ValEqTable")
TestEqTable = Concept("TestEqTable")

# Binary classification task relationships.
Train = Relationship(f"{NetworkEquipment} has {Integer:label}")
Val = Relationship(f"{NetworkEquipment} has {Integer:label}")
Test = Relationship(f"{NetworkEquipment}")

# NetworkPerformance concept: per-tower performance measurements
# (packet loss %, latency ms, error rate), aggregated into the
# avg_packet_loss / avg_latency_ms / avg_error_rate CellTower
# properties used by the critical-restore rule branches.
NetworkPerformance = Concept("NetworkPerformance", identify_by={"id": String})
NetworkPerformance.packet_loss_pct = Property(f"{NetworkPerformance} has {Float:packet_loss_pct}")
NetworkPerformance.latency_ms = Property(f"{NetworkPerformance} has {Float:latency_ms}")
NetworkPerformance.error_rate = Property(f"{NetworkPerformance} has {Float:error_rate}")
NetworkPerformance.for_tower = Relationship(f"{NetworkPerformance} for tower {CellTower}")


# Subscriber-account-status vocabulary. CSV status strings map to
# members BY NAME via `SubscriberStatus.lookup(...)`; the wrapped
# values are arbitrary distinct integers.
class SubscriberStatus(model.Enum):
    ACTIVE = 1
    SUSPENDED = 2


# Subscriber concept: customer accounts (consumer or enterprise) that
# place calls. Nodes of the PageRank graph AND the carriers of the
# customer-value signal that drives per-tower weighted_impact.
Subscriber = Concept("Subscriber", identify_by={"id": String})
Subscriber.subscriber_type = Property(f"{Subscriber} has {String:subscriber_type}")
Subscriber.segment = Property(f"{Subscriber} has {String:segment}")
Subscriber.lifetime_value = Property(f"{Subscriber} has {Float:lifetime_value}")
Subscriber.churn_risk_score = Property(f"{Subscriber} has {Float:churn_risk_score}")
Subscriber.status = Property(f"{Subscriber} has {SubscriberStatus:status}")
# Composite revenue-at-risk signal (LTV * (1 + churn)), derived in
# reasoning.py; this is the per-subscriber weight that sums into
# `CellTower.weighted_impact` and drives the upgrade objective.
Subscriber.customer_value = Property(f"{Subscriber} has {Float:customer_value}")

# CallDetailRecord concept: a directed call (caller -> callee routed
# through a specific CellTower). Used as the edge concept for the
# subscriber PageRank graph and for per-tower customer-impact aggregation.
CallDetailRecord = Concept("CallDetailRecord", identify_by={"id": String})
CallDetailRecord.caller = Relationship(f"{CallDetailRecord} has caller {Subscriber}")
CallDetailRecord.callee = Relationship(f"{CallDetailRecord} has callee {Subscriber}")
CallDetailRecord.routed_through = Relationship(f"{CallDetailRecord} routed through {CellTower}")

# TowerUpgradeOption concept: a (tower, tier) candidate upgrade with
# capacity, cost, and install-weeks; the MIP's decision space. Every
# tower carries three tier options (BRONZE / SILVER / GOLD).
TowerUpgradeOption = Concept("TowerUpgradeOption", identify_by={"tower_id": String, "tier": String})
TowerUpgradeOption.capacity_increase_gbps = Property(
    f"{TowerUpgradeOption} has {Integer:capacity_increase_gbps}"
)
TowerUpgradeOption.cost = Property(f"{TowerUpgradeOption} has {Float:cost}")
TowerUpgradeOption.install_weeks = Property(f"{TowerUpgradeOption} has {Integer:install_weeks}")
TowerUpgradeOption.for_tower = Relationship(f"{TowerUpgradeOption} for tower {CellTower}")
