"""PyRel v1 model: Telco Knowledge Graph — full reference ontology

Entity relationship overview:
    PostalArea <── Subscriber ──> Contract
               <── CellTower       └──> BillingEvent
                                    └──> CallDetailRecord ──> CellTower
                                    └──> PromotionRedemption <── Campaign
    CellTower ──> NetworkEquipment ──> Part ──> SupplierOrder
              └──> NetworkEvent
              └──> EquipmentHealth (via NetworkEquipment)
    RevenueForecast (standalone regional analytics)

Source tables (replace <YOUR_DB>.<YOUR_SCHEMA> with your own Snowflake schema):
  REGIONAL_RISK, SUBSCRIBERS, PLANS_CONTRACTS, BILLING_EVENTS,
  CELL_TOWERS, PARTS_INVENTORY, NETWORK_EQUIPMENT, EQUIPMENT_HEALTH,
  NETWORK_EVENTS, CALL_DETAIL_RECORDS, SUPPLIER_ORDERS, CAMPAIGNS,
  PROMOTION_REDEMPTIONS, REVENUE_FORECAST, NETWORK_PERFORMANCE,
  SUPPORT_TICKETS, TIME_SERIES_METRICS, TOWER_UPGRADE_OPTIONS,
  REDEMPTION_CHURN_IMPACT
"""
from relationalai.semantics import Boolean, Date, DateTime, Float, Integer, Model, String

model = Model("Telco Network Recovery (full ontology)")

# ── Source Tables ─────────────────────────────────────────────────────────────
class Sources:
    class telco_enrichment:
        class public:
            regional_risk = model.Table("<YOUR_DB>.<YOUR_SCHEMA>.REGIONAL_RISK")
            subscribers = model.Table("<YOUR_DB>.<YOUR_SCHEMA>.SUBSCRIBERS")
            plans_contracts = model.Table("<YOUR_DB>.<YOUR_SCHEMA>.PLANS_CONTRACTS")
            billing_events = model.Table("<YOUR_DB>.<YOUR_SCHEMA>.BILLING_EVENTS")
            cell_towers = model.Table("<YOUR_DB>.<YOUR_SCHEMA>.CELL_TOWERS")
            parts_inventory = model.Table("<YOUR_DB>.<YOUR_SCHEMA>.PARTS_INVENTORY")
            network_equipment = model.Table("<YOUR_DB>.<YOUR_SCHEMA>.NETWORK_EQUIPMENT")
            equipment_health = model.Table("<YOUR_DB>.<YOUR_SCHEMA>.EQUIPMENT_HEALTH")
            network_events = model.Table("<YOUR_DB>.<YOUR_SCHEMA>.NETWORK_EVENTS")
            call_detail_records = model.Table("<YOUR_DB>.<YOUR_SCHEMA>.CALL_DETAIL_RECORDS")
            supplier_orders = model.Table("<YOUR_DB>.<YOUR_SCHEMA>.SUPPLIER_ORDERS")
            campaigns = model.Table("<YOUR_DB>.<YOUR_SCHEMA>.CAMPAIGNS")
            promotion_redemptions = model.Table("<YOUR_DB>.<YOUR_SCHEMA>.PROMOTION_REDEMPTIONS")
            revenue_forecast = model.Table("<YOUR_DB>.<YOUR_SCHEMA>.REVENUE_FORECAST")
            network_performance = model.Table("<YOUR_DB>.<YOUR_SCHEMA>.NETWORK_PERFORMANCE")
            support_tickets = model.Table("<YOUR_DB>.<YOUR_SCHEMA>.SUPPORT_TICKETS")
            tower_upgrade_options = model.Table("<YOUR_DB>.<YOUR_SCHEMA>.TOWER_UPGRADE_OPTIONS")
            redemption_churn_impact = model.Table("<YOUR_DB>.<YOUR_SCHEMA>.REDEMPTION_CHURN_IMPACT")
            time_series_metrics = model.Table("<YOUR_DB>.<YOUR_SCHEMA>.TIME_SERIES_METRICS")

raw = Sources.telco_enrichment.public

# ═══════════════════════════════════════════════════════════════════════════════
# POSTAL AREA  (Source: REGIONAL_RISK)
# ═══════════════════════════════════════════════════════════════════════════════
PostalArea = model.Concept("PostalArea", identify_by={"id": Integer})
PostalArea.region = model.Property(f"{PostalArea} has {String:region}")
PostalArea.flood_risk_index = model.Property(f"{PostalArea} has {Float:flood_risk_index}")
PostalArea.socioeconomic_score = model.Property(f"{PostalArea} has {Float:socioeconomic_score}")
PostalArea.population_density = model.Property(f"{PostalArea} has {Integer:population_density}")
PostalArea.business_density = model.Property(f"{PostalArea} has {Integer:business_density}")
PostalArea.last_updated = model.Property(f"{PostalArea} last updated {Date:last_updated}")

model.define(
    pa := PostalArea.new(id=raw.regional_risk.POSTAL_CODE),
    pa.region(raw.regional_risk.REGION),
    pa.flood_risk_index(raw.regional_risk.FLOOD_RISK_INDEX),
    pa.socioeconomic_score(raw.regional_risk.SOCIOECONOMIC_SCORE),
    pa.population_density(raw.regional_risk.POPULATION_DENSITY),
    pa.business_density(raw.regional_risk.BUSINESS_DENSITY),
    pa.last_updated(raw.regional_risk.LAST_UPDATED),
)

# ═══════════════════════════════════════════════════════════════════════════════
# PART  (Source: PARTS_INVENTORY)
# ═══════════════════════════════════════════════════════════════════════════════
Part = model.Concept("Part", identify_by={"id": String})
Part.name = model.Property(f"{Part} has {String:name}")
Part.category = model.Property(f"{Part} has {String:category}")
Part.quantity_on_hand = model.Property(f"{Part} has {Integer:quantity_on_hand}")
Part.reorder_point = model.Property(f"{Part} has {Integer:reorder_point}")
Part.unit_cost = model.Property(f"{Part} has {Float:unit_cost}")
Part.supplier_id = model.Property(f"{Part} has {String:supplier_id}")
Part.warehouse_location = model.Property(f"{Part} has {String:warehouse_location}")
Part.stock_status = model.Property(f"{Part} has {String:stock_status}")
Part.last_restock_date = model.Property(f"{Part} has {Date:last_restock_date}")

model.define(
    p := Part.new(id=raw.parts_inventory.PART_ID),
    p.name(raw.parts_inventory.PART_NAME),
    p.category(raw.parts_inventory.CATEGORY),
    p.quantity_on_hand(raw.parts_inventory.QUANTITY_ON_HAND),
    p.reorder_point(raw.parts_inventory.REORDER_POINT),
    p.unit_cost(raw.parts_inventory.UNIT_COST_USD),
    p.supplier_id(raw.parts_inventory.SUPPLIER_ID),
    p.warehouse_location(raw.parts_inventory.WAREHOUSE_LOCATION),
    p.stock_status(raw.parts_inventory.STOCK_STATUS),
    p.last_restock_date(raw.parts_inventory.LAST_RESTOCK_DATE),
)

# ═══════════════════════════════════════════════════════════════════════════════
# SUBSCRIBER  (Source: SUBSCRIBERS)
# ═══════════════════════════════════════════════════════════════════════════════
Subscriber = model.Concept("Subscriber", identify_by={"id": String})
Subscriber.first_name = model.Property(f"{Subscriber} has {String:first_name}")
Subscriber.last_name = model.Property(f"{Subscriber} has {String:last_name}")
Subscriber.email = model.Property(f"{Subscriber} has {String:email}")
Subscriber.phone = model.Property(f"{Subscriber} has {String:phone}")
Subscriber.subscriber_type = model.Property(f"{Subscriber} has {String:subscriber_type}")
Subscriber.segment = model.Property(f"{Subscriber} has {String:segment}")
Subscriber.signup_date = model.Property(f"{Subscriber} has {Date:signup_date}")
Subscriber.lifetime_value = model.Property(f"{Subscriber} has {Float:lifetime_value}")
Subscriber.churn_risk_score = model.Property(f"{Subscriber} has {Float:churn_risk_score}")
Subscriber.nps_score = model.Property(f"{Subscriber} has {Integer:nps_score}")
Subscriber.status = model.Property(f"{Subscriber} has {String:status}")
Subscriber.located_in = model.Relationship(f"{Subscriber} located in {PostalArea}", short_name="subscriber_located_in")
PostalArea.has_subscriber = model.Relationship(f"{PostalArea} has subscriber {Subscriber}", short_name="postal_area_has_subscriber")

model.define(
    s := Subscriber.new(id=raw.subscribers.SUB_ID),
    s.first_name(raw.subscribers.FIRST_NAME),
    s.last_name(raw.subscribers.LAST_NAME),
    s.email(raw.subscribers.EMAIL),
    s.phone(raw.subscribers.PHONE),
    s.subscriber_type(raw.subscribers.SUBSCRIBER_TYPE),
    s.segment(raw.subscribers.SEGMENT),
    s.signup_date(raw.subscribers.SIGNUP_DATE),
    s.lifetime_value(raw.subscribers.LIFETIME_VALUE_USD),
    s.churn_risk_score(raw.subscribers.CHURN_RISK_SCORE),
    s.nps_score(raw.subscribers.NPS_SCORE),
    s.status(raw.subscribers.STATUS),
)

model.define(Subscriber.located_in(PostalArea)).where(
    Subscriber.filter_by(id=raw.subscribers.SUB_ID),
    PostalArea.filter_by(id=raw.subscribers.POSTAL_CODE),
)

model.define(PostalArea.has_subscriber(Subscriber)).where(
    PostalArea.filter_by(id=raw.subscribers.POSTAL_CODE),
    Subscriber.filter_by(id=raw.subscribers.SUB_ID),
)

# ═══════════════════════════════════════════════════════════════════════════════
# CONTRACT  (Source: PLANS_CONTRACTS)
# ═══════════════════════════════════════════════════════════════════════════════
Contract = model.Concept("Contract", identify_by={"id": String})
Contract.plan_type = model.Property(f"{Contract} has {String:plan_type}")
Contract.monthly_rate = model.Property(f"{Contract} has {Float:monthly_rate}")
Contract.data_limit_gb = model.Property(f"{Contract} has {Integer:data_limit_gb}")
Contract.start_date = model.Property(f"{Contract} has {Date:start_date}")
Contract.end_date = model.Property(f"{Contract} has {Date:end_date}")
Contract.term_months = model.Property(f"{Contract} has {Integer:term_months}")
Contract.early_term_fee = model.Property(f"{Contract} has {Integer:early_term_fee}")
Contract.status = model.Property(f"{Contract} has {String:status}")
Contract.for_subscriber = model.Relationship(f"{Contract} for subscriber {Subscriber}", short_name="contract_for_subscriber")
Subscriber.has_contract = model.Relationship(f"{Subscriber} has contract {Contract}", short_name="subscriber_has_contract")

model.define(
    c := Contract.new(id=raw.plans_contracts.CONTRACT_ID),
    c.plan_type(raw.plans_contracts.PLAN_TYPE),
    c.monthly_rate(raw.plans_contracts.MONTHLY_RATE_USD),
    c.data_limit_gb(raw.plans_contracts.DATA_LIMIT_GB),
    c.start_date(raw.plans_contracts.CONTRACT_START_DATE),
    c.end_date(raw.plans_contracts.CONTRACT_END_DATE),
    c.term_months(raw.plans_contracts.TERM_MONTHS),
    c.early_term_fee(raw.plans_contracts.EARLY_TERMINATION_FEE_USD),
    c.status(raw.plans_contracts.STATUS),
)

model.define(Contract.for_subscriber(Subscriber)).where(
    Contract.filter_by(id=raw.plans_contracts.CONTRACT_ID),
    Subscriber.filter_by(id=raw.plans_contracts.SUB_ID),
)

model.define(Subscriber.has_contract(Contract)).where(
    Subscriber.filter_by(id=raw.plans_contracts.SUB_ID),
    Contract.filter_by(id=raw.plans_contracts.CONTRACT_ID),
)

# ═══════════════════════════════════════════════════════════════════════════════
# BILLING EVENT  (Source: BILLING_EVENTS)
# ═══════════════════════════════════════════════════════════════════════════════
BillingEvent = model.Concept("BillingEvent", identify_by={"id": String})
BillingEvent.billing_date = model.Property(f"{BillingEvent} has {Date:billing_date}")
BillingEvent.due_date = model.Property(f"{BillingEvent} has {Date:due_date}")
BillingEvent.amount = model.Property(f"{BillingEvent} has {Float:amount}")
BillingEvent.payment_status = model.Property(f"{BillingEvent} has {String:payment_status}")
BillingEvent.days_overdue = model.Property(f"{BillingEvent} has {Integer:days_overdue}")
BillingEvent.dispute_reason = model.Property(f"{BillingEvent} has {String:dispute_reason}")
BillingEvent.collection_status = model.Property(f"{BillingEvent} has {String:collection_status}")
BillingEvent.billed_to = model.Relationship(f"{BillingEvent} billed to {Subscriber}", short_name="billing_event_billed_to")
Subscriber.has_billing_event = model.Relationship(f"{Subscriber} has billing event {BillingEvent}", short_name="subscriber_has_billing_event")

model.define(
    b := BillingEvent.new(id=raw.billing_events.BILLING_ID),
    b.billing_date(raw.billing_events.BILLING_DATE),
    b.due_date(raw.billing_events.DUE_DATE),
    b.amount(raw.billing_events.AMOUNT_USD),
    b.payment_status(raw.billing_events.PAYMENT_STATUS),
    b.days_overdue(raw.billing_events.DAYS_OVERDUE),
    b.dispute_reason(raw.billing_events.DISPUTE_REASON),
    b.collection_status(raw.billing_events.COLLECTION_STATUS),
)

model.define(BillingEvent.billed_to(Subscriber)).where(
    BillingEvent.filter_by(id=raw.billing_events.BILLING_ID),
    Subscriber.filter_by(id=raw.billing_events.SUB_ID),
)

model.define(Subscriber.has_billing_event(BillingEvent)).where(
    Subscriber.filter_by(id=raw.billing_events.SUB_ID),
    BillingEvent.filter_by(id=raw.billing_events.BILLING_ID),
)

# ═══════════════════════════════════════════════════════════════════════════════
# CELL TOWER  (Source: CELL_TOWERS)
# ═══════════════════════════════════════════════════════════════════════════════
CellTower = model.Concept("CellTower", identify_by={"id": String})
CellTower.name = model.Property(f"{CellTower} has {String:name}")
CellTower.tower_type = model.Property(f"{CellTower} has {String:tower_type}")
CellTower.capacity_gbps = model.Property(f"{CellTower} has {Integer:capacity_gbps}")
CellTower.install_date = model.Property(f"{CellTower} has {Date:install_date}")
CellTower.status = model.Property(f"{CellTower} has {String:status}")
CellTower.region = model.Property(f"{CellTower} has {String:region}")
CellTower.latitude = model.Property(f"{CellTower} has {Float:latitude}")
CellTower.longitude = model.Property(f"{CellTower} has {Float:longitude}")
CellTower.located_in = model.Relationship(f"{CellTower} located in {PostalArea}", short_name="cell_tower_located_in")
PostalArea.has_cell_tower = model.Relationship(f"{PostalArea} has cell tower {CellTower}", short_name="postal_area_has_cell_tower")

model.define(
    t := CellTower.new(id=raw.cell_towers.TOWER_ID),
    t.name(raw.cell_towers.TOWER_NAME),
    t.tower_type(raw.cell_towers.TOWER_TYPE),
    t.capacity_gbps(raw.cell_towers.CAPACITY_GBPS),
    t.install_date(raw.cell_towers.INSTALL_DATE),
    t.status(raw.cell_towers.STATUS),
    t.region(raw.cell_towers.REGION),
    t.latitude(raw.cell_towers.LATITUDE),
    t.longitude(raw.cell_towers.LONGITUDE),
)

model.define(CellTower.located_in(PostalArea)).where(
    CellTower.filter_by(id=raw.cell_towers.TOWER_ID),
    PostalArea.filter_by(id=raw.cell_towers.POSTAL_CODE),
)

model.define(PostalArea.has_cell_tower(CellTower)).where(
    PostalArea.filter_by(id=raw.cell_towers.POSTAL_CODE),
    CellTower.filter_by(id=raw.cell_towers.TOWER_ID),
)

# ═══════════════════════════════════════════════════════════════════════════════
# NETWORK EQUIPMENT  (Source: NETWORK_EQUIPMENT)
# ═══════════════════════════════════════════════════════════════════════════════
NetworkEquipment = model.Concept("NetworkEquipment", identify_by={"id": String})
NetworkEquipment.equipment_type = model.Property(f"{NetworkEquipment} has {String:equipment_type}")
NetworkEquipment.manufacturer = model.Property(f"{NetworkEquipment} has {String:manufacturer}")
NetworkEquipment.equipment_model = model.Property(f"{NetworkEquipment} has {String:equipment_model}")
NetworkEquipment.serial_number = model.Property(f"{NetworkEquipment} has {String:serial_number}")
NetworkEquipment.install_date = model.Property(f"{NetworkEquipment} has {Date:install_date}")
NetworkEquipment.firmware_version = model.Property(f"{NetworkEquipment} has {String:firmware_version}")
NetworkEquipment.status = model.Property(f"{NetworkEquipment} has {String:status}")
NetworkEquipment.installed_at = model.Relationship(f"{NetworkEquipment} installed at {CellTower}", short_name="equipment_installed_at")
NetworkEquipment.uses_part = model.Relationship(f"{NetworkEquipment} uses part {Part}", short_name="equipment_uses_part")
CellTower.has_equipment = model.Relationship(f"{CellTower} has equipment {NetworkEquipment}", short_name="cell_tower_has_equipment")
Part.used_in_equipment = model.Relationship(f"{Part} used in equipment {NetworkEquipment}", short_name="part_used_in_equipment")

model.define(
    e := NetworkEquipment.new(id=raw.network_equipment.EQUIPMENT_ID),
    e.equipment_type(raw.network_equipment.EQUIPMENT_TYPE),
    e.manufacturer(raw.network_equipment.MANUFACTURER),
    e.equipment_model(raw.network_equipment.MODEL),
    e.serial_number(raw.network_equipment.SERIAL_NUMBER),
    e.install_date(raw.network_equipment.INSTALL_DATE),
    e.firmware_version(raw.network_equipment.FIRMWARE_VERSION),
    e.status(raw.network_equipment.STATUS),
)

model.define(NetworkEquipment.installed_at(CellTower)).where(
    NetworkEquipment.filter_by(id=raw.network_equipment.EQUIPMENT_ID),
    CellTower.filter_by(id=raw.network_equipment.TOWER_ID),
)

model.define(NetworkEquipment.uses_part(Part)).where(
    NetworkEquipment.filter_by(id=raw.network_equipment.EQUIPMENT_ID),
    Part.filter_by(id=raw.network_equipment.PART_ID),
)

model.define(CellTower.has_equipment(NetworkEquipment)).where(
    CellTower.filter_by(id=raw.network_equipment.TOWER_ID),
    NetworkEquipment.filter_by(id=raw.network_equipment.EQUIPMENT_ID),
)

model.define(Part.used_in_equipment(NetworkEquipment)).where(
    Part.filter_by(id=raw.network_equipment.PART_ID),
    NetworkEquipment.filter_by(id=raw.network_equipment.EQUIPMENT_ID),
)

# ═══════════════════════════════════════════════════════════════════════════════
# EQUIPMENT HEALTH  (Source: EQUIPMENT_HEALTH)
# ═══════════════════════════════════════════════════════════════════════════════
EquipmentHealth = model.Concept("EquipmentHealth", identify_by={"id": String})
EquipmentHealth.mtbf_hours = model.Property(f"{EquipmentHealth} has {Integer:mtbf_hours}")
EquipmentHealth.failure_rate = model.Property(f"{EquipmentHealth} has {Float:failure_rate}")
EquipmentHealth.last_failure_date = model.Property(f"{EquipmentHealth} has {Date:last_failure_date}")
EquipmentHealth.temperature_avg_c = model.Property(f"{EquipmentHealth} has {Float:temperature_avg_c}")
EquipmentHealth.power_consumption_kw = model.Property(f"{EquipmentHealth} has {Float:power_consumption_kw}")
EquipmentHealth.health_score = model.Property(f"{EquipmentHealth} has {Float:health_score}")
EquipmentHealth.measurement_date = model.Property(f"{EquipmentHealth} has {Date:measurement_date}")
EquipmentHealth.for_equipment = model.Relationship(f"{EquipmentHealth} for equipment {NetworkEquipment}", short_name="health_for_equipment")
NetworkEquipment.has_health_record = model.Relationship(f"{NetworkEquipment} has health record {EquipmentHealth}", short_name="equipment_has_health_record")

model.define(
    h := EquipmentHealth.new(id=raw.equipment_health.HEALTH_ID),
    h.mtbf_hours(raw.equipment_health.MTBF_HOURS),
    h.failure_rate(raw.equipment_health.FAILURE_RATE),
    h.last_failure_date(raw.equipment_health.LAST_FAILURE_DATE),
    h.temperature_avg_c(raw.equipment_health.TEMPERATURE_AVG_C),
    h.power_consumption_kw(raw.equipment_health.POWER_CONSUMPTION_KW),
    h.health_score(raw.equipment_health.HEALTH_SCORE),
    h.measurement_date(raw.equipment_health.MEASUREMENT_DATE),
)

model.define(EquipmentHealth.for_equipment(NetworkEquipment)).where(
    EquipmentHealth.filter_by(id=raw.equipment_health.HEALTH_ID),
    NetworkEquipment.filter_by(id=raw.equipment_health.EQUIPMENT_ID),
)

model.define(NetworkEquipment.has_health_record(EquipmentHealth)).where(
    NetworkEquipment.filter_by(id=raw.equipment_health.EQUIPMENT_ID),
    EquipmentHealth.filter_by(id=raw.equipment_health.HEALTH_ID),
)

# ═══════════════════════════════════════════════════════════════════════════════
# NETWORK EVENT  (Source: NETWORK_EVENTS)
# ═══════════════════════════════════════════════════════════════════════════════
NetworkEvent = model.Concept("NetworkEvent", identify_by={"id": String})
NetworkEvent.event_type = model.Property(f"{NetworkEvent} has {String:event_type}")
NetworkEvent.severity = model.Property(f"{NetworkEvent} has {String:severity}")
NetworkEvent.start_time = model.Property(f"{NetworkEvent} has {DateTime:start_time}")
NetworkEvent.end_time = model.Property(f"{NetworkEvent} has {DateTime:end_time}")
NetworkEvent.duration_minutes = model.Property(f"{NetworkEvent} has {Integer:duration_minutes}")
NetworkEvent.affected_subscribers = model.Property(f"{NetworkEvent} has {Integer:affected_subscribers}")
NetworkEvent.root_cause = model.Property(f"{NetworkEvent} has {String:root_cause}")
NetworkEvent.resolution = model.Property(f"{NetworkEvent} has {String:resolution}")
NetworkEvent.ticket_id = model.Property(f"{NetworkEvent} has {String:ticket_id}")
NetworkEvent.affects_tower = model.Relationship(f"{NetworkEvent} affects tower {CellTower}", short_name="event_affects_tower")
CellTower.has_event = model.Relationship(f"{CellTower} has event {NetworkEvent}", short_name="cell_tower_has_event")

model.define(
    ev := NetworkEvent.new(id=raw.network_events.EVENT_ID),
    ev.event_type(raw.network_events.EVENT_TYPE),
    ev.severity(raw.network_events.SEVERITY),
    ev.start_time(raw.network_events.START_TIME),
    ev.end_time(raw.network_events.END_TIME),
    ev.duration_minutes(raw.network_events.DURATION_MINUTES),
    ev.affected_subscribers(raw.network_events.AFFECTED_SUBSCRIBERS),
    ev.root_cause(raw.network_events.ROOT_CAUSE),
    ev.resolution(raw.network_events.RESOLUTION),
    ev.ticket_id(raw.network_events.TICKET_ID),
)

model.define(NetworkEvent.affects_tower(CellTower)).where(
    NetworkEvent.filter_by(id=raw.network_events.EVENT_ID),
    CellTower.filter_by(id=raw.network_events.TOWER_ID),
)

model.define(CellTower.has_event(NetworkEvent)).where(
    CellTower.filter_by(id=raw.network_events.TOWER_ID),
    NetworkEvent.filter_by(id=raw.network_events.EVENT_ID),
)

# ═══════════════════════════════════════════════════════════════════════════════
# CALL DETAIL RECORD  (Source: CALL_DETAIL_RECORDS)
# Self-referential: both CALLER_SUB_ID and CALLEE_SUB_ID reference Subscriber
# ═══════════════════════════════════════════════════════════════════════════════
CallDetailRecord = model.Concept("CallDetailRecord", identify_by={"id": String})
CallDetailRecord.call_type = model.Property(f"{CallDetailRecord} has {String:call_type}")
CallDetailRecord.start_time = model.Property(f"{CallDetailRecord} has {DateTime:start_time}")
CallDetailRecord.duration_seconds = model.Property(f"{CallDetailRecord} has {Integer:duration_seconds}")
CallDetailRecord.call_status = model.Property(f"{CallDetailRecord} has {String:call_status}")
CallDetailRecord.data_used_mb = model.Property(f"{CallDetailRecord} has {Float:data_used_mb}")
CallDetailRecord.quality_score = model.Property(f"{CallDetailRecord} has {Float:quality_score}")
CallDetailRecord.caller = model.Relationship(f"{CallDetailRecord} has caller {Subscriber}", short_name="cdr_caller")
CallDetailRecord.callee = model.Relationship(f"{CallDetailRecord} has callee {Subscriber}", short_name="cdr_callee")
CallDetailRecord.routed_through = model.Relationship(f"{CallDetailRecord} routed through {CellTower}", short_name="cdr_routed_through")
Subscriber.made_call = model.Relationship(f"{Subscriber} made call {CallDetailRecord}", short_name="subscriber_made_call")
Subscriber.received_call = model.Relationship(f"{Subscriber} received call {CallDetailRecord}", short_name="subscriber_received_call")
CellTower.handled_call = model.Relationship(f"{CellTower} handled call {CallDetailRecord}", short_name="cell_tower_handled_call")

model.define(
    cdr := CallDetailRecord.new(id=raw.call_detail_records.CDR_ID),
    cdr.call_type(raw.call_detail_records.CALL_TYPE),
    cdr.start_time(raw.call_detail_records.CALL_START_TIME),
    cdr.duration_seconds(raw.call_detail_records.CALL_DURATION_SECONDS),
    cdr.call_status(raw.call_detail_records.CALL_STATUS),
    cdr.data_used_mb(raw.call_detail_records.DATA_USED_MB),
    cdr.quality_score(raw.call_detail_records.CALL_QUALITY_SCORE),
)

model.define(CallDetailRecord.caller(Subscriber)).where(
    CallDetailRecord.filter_by(id=raw.call_detail_records.CDR_ID),
    Subscriber.filter_by(id=raw.call_detail_records.CALLER_SUB_ID),
)

model.define(CallDetailRecord.callee(Subscriber)).where(
    CallDetailRecord.filter_by(id=raw.call_detail_records.CDR_ID),
    Subscriber.filter_by(id=raw.call_detail_records.CALLEE_SUB_ID),
)

model.define(CallDetailRecord.routed_through(CellTower)).where(
    CallDetailRecord.filter_by(id=raw.call_detail_records.CDR_ID),
    CellTower.filter_by(id=raw.call_detail_records.TOWER_ID),
)

model.define(Subscriber.made_call(CallDetailRecord)).where(
    Subscriber.filter_by(id=raw.call_detail_records.CALLER_SUB_ID),
    CallDetailRecord.filter_by(id=raw.call_detail_records.CDR_ID),
)

model.define(Subscriber.received_call(CallDetailRecord)).where(
    Subscriber.filter_by(id=raw.call_detail_records.CALLEE_SUB_ID),
    CallDetailRecord.filter_by(id=raw.call_detail_records.CDR_ID),
)

model.define(CellTower.handled_call(CallDetailRecord)).where(
    CellTower.filter_by(id=raw.call_detail_records.TOWER_ID),
    CallDetailRecord.filter_by(id=raw.call_detail_records.CDR_ID),
)

# ═══════════════════════════════════════════════════════════════════════════════
# SUPPLIER ORDER  (Source: SUPPLIER_ORDERS)
# ═══════════════════════════════════════════════════════════════════════════════
SupplierOrder = model.Concept("SupplierOrder", identify_by={"id": String})
SupplierOrder.supplier_id = model.Property(f"{SupplierOrder} has {String:supplier_id}")
SupplierOrder.supplier_name = model.Property(f"{SupplierOrder} has {String:supplier_name}")
SupplierOrder.quantity = model.Property(f"{SupplierOrder} has {Integer:quantity}")
SupplierOrder.order_date = model.Property(f"{SupplierOrder} has {Date:order_date}")
SupplierOrder.expected_delivery = model.Property(f"{SupplierOrder} has {Date:expected_delivery}")
SupplierOrder.actual_delivery = model.Property(f"{SupplierOrder} has {Date:actual_delivery}")
SupplierOrder.status = model.Property(f"{SupplierOrder} has {String:status}")
SupplierOrder.delay_reason = model.Property(f"{SupplierOrder} has {String:delay_reason}")
SupplierOrder.unit_cost = model.Property(f"{SupplierOrder} has {Float:unit_cost}")
SupplierOrder.total_cost = model.Property(f"{SupplierOrder} has {Float:total_cost}")
SupplierOrder.for_part = model.Relationship(f"{SupplierOrder} for part {Part}", short_name="order_for_part")
Part.has_supplier_order = model.Relationship(f"{Part} has supplier order {SupplierOrder}", short_name="part_has_supplier_order")

model.define(
    o := SupplierOrder.new(id=raw.supplier_orders.ORDER_ID),
    o.supplier_id(raw.supplier_orders.SUPPLIER_ID),
    o.supplier_name(raw.supplier_orders.SUPPLIER_NAME),
    o.quantity(raw.supplier_orders.QUANTITY_ORDERED),
    o.order_date(raw.supplier_orders.ORDER_DATE),
    o.expected_delivery(raw.supplier_orders.EXPECTED_DELIVERY_DATE),
    o.actual_delivery(raw.supplier_orders.ACTUAL_DELIVERY_DATE),
    o.status(raw.supplier_orders.ORDER_STATUS),
    o.delay_reason(raw.supplier_orders.DELAY_REASON),
    o.unit_cost(raw.supplier_orders.UNIT_COST_USD),
    o.total_cost(raw.supplier_orders.TOTAL_COST_USD),
)

model.define(SupplierOrder.for_part(Part)).where(
    SupplierOrder.filter_by(id=raw.supplier_orders.ORDER_ID),
    Part.filter_by(id=raw.supplier_orders.PART_ID),
)

model.define(Part.has_supplier_order(SupplierOrder)).where(
    Part.filter_by(id=raw.supplier_orders.PART_ID),
    SupplierOrder.filter_by(id=raw.supplier_orders.ORDER_ID),
)

# ═══════════════════════════════════════════════════════════════════════════════
# CAMPAIGN  (Source: CAMPAIGNS)
# ═══════════════════════════════════════════════════════════════════════════════
Campaign = model.Concept("Campaign", identify_by={"id": String})
Campaign.name = model.Property(f"{Campaign} has {String:name}")
Campaign.campaign_type = model.Property(f"{Campaign} has {String:campaign_type}")
Campaign.target_region = model.Property(f"{Campaign} has {String:target_region}")
Campaign.target_segment = model.Property(f"{Campaign} has {String:target_segment}")
Campaign.target_postal_codes = model.Property(f"{Campaign} has {String:target_postal_codes}")
Campaign.start_date = model.Property(f"{Campaign} has {Date:start_date}")
Campaign.end_date = model.Property(f"{Campaign} has {Date:end_date}")
Campaign.budget = model.Property(f"{Campaign} has {Float:budget}")
Campaign.spend = model.Property(f"{Campaign} has {Float:spend}")
Campaign.target_conversions = model.Property(f"{Campaign} has {Integer:target_conversions}")
Campaign.actual_conversions = model.Property(f"{Campaign} has {Integer:actual_conversions}")
Campaign.conversion_rate = model.Property(f"{Campaign} has {Float:conversion_rate}")
Campaign.status = model.Property(f"{Campaign} has {String:status}")
Campaign.channel = model.Property(f"{Campaign} has {String:channel}")

model.define(
    ca := Campaign.new(id=raw.campaigns.CAMPAIGN_ID),
    ca.name(raw.campaigns.CAMPAIGN_NAME),
    ca.campaign_type(raw.campaigns.CAMPAIGN_TYPE),
    ca.target_region(raw.campaigns.TARGET_REGION),
    ca.target_segment(raw.campaigns.TARGET_SEGMENT),
    ca.target_postal_codes(raw.campaigns.TARGET_POSTAL_CODES),
    ca.start_date(raw.campaigns.START_DATE),
    ca.end_date(raw.campaigns.END_DATE),
    ca.budget(raw.campaigns.BUDGET_USD),
    ca.spend(raw.campaigns.SPEND_USD),
    ca.target_conversions(raw.campaigns.TARGET_CONVERSIONS),
    ca.actual_conversions(raw.campaigns.ACTUAL_CONVERSIONS),
    ca.conversion_rate(raw.campaigns.CONVERSION_RATE),
    ca.status(raw.campaigns.STATUS),
    ca.channel(raw.campaigns.CHANNEL),
)

# ═══════════════════════════════════════════════════════════════════════════════
# PROMOTION REDEMPTION  (Source: PROMOTION_REDEMPTIONS)
# ═══════════════════════════════════════════════════════════════════════════════
PromotionRedemption = model.Concept("PromotionRedemption", identify_by={"id": String})
PromotionRedemption.offer_sent_date = model.Property(f"{PromotionRedemption} has {Date:offer_sent_date}")
PromotionRedemption.offer_type = model.Property(f"{PromotionRedemption} has {String:offer_type}")
PromotionRedemption.offer_value = model.Property(f"{PromotionRedemption} has {Float:offer_value}")
PromotionRedemption.status = model.Property(f"{PromotionRedemption} has {String:status}")
PromotionRedemption.redemption_date = model.Property(f"{PromotionRedemption} has {Date:redemption_date}")
PromotionRedemption.feedback = model.Property(f"{PromotionRedemption} has {String:feedback}")
PromotionRedemption.from_campaign = model.Relationship(f"{PromotionRedemption} from campaign {Campaign}", short_name="redemption_from_campaign")
PromotionRedemption.for_subscriber = model.Relationship(f"{PromotionRedemption} for subscriber {Subscriber}", short_name="redemption_for_subscriber")
Campaign.has_redemption = model.Relationship(f"{Campaign} has redemption {PromotionRedemption}", short_name="campaign_has_redemption")
Subscriber.has_redemption = model.Relationship(f"{Subscriber} has redemption {PromotionRedemption}", short_name="subscriber_has_redemption")

model.define(
    r := PromotionRedemption.new(id=raw.promotion_redemptions.REDEMPTION_ID),
    r.offer_sent_date(raw.promotion_redemptions.OFFER_SENT_DATE),
    r.offer_type(raw.promotion_redemptions.OFFER_TYPE),
    r.offer_value(raw.promotion_redemptions.OFFER_VALUE_USD),
    r.status(raw.promotion_redemptions.REDEMPTION_STATUS),
    r.redemption_date(raw.promotion_redemptions.REDEMPTION_DATE),
    r.feedback(raw.promotion_redemptions.FEEDBACK),
)

model.define(PromotionRedemption.from_campaign(Campaign)).where(
    PromotionRedemption.filter_by(id=raw.promotion_redemptions.REDEMPTION_ID),
    Campaign.filter_by(id=raw.promotion_redemptions.CAMPAIGN_ID),
)

model.define(PromotionRedemption.for_subscriber(Subscriber)).where(
    PromotionRedemption.filter_by(id=raw.promotion_redemptions.REDEMPTION_ID),
    Subscriber.filter_by(id=raw.promotion_redemptions.SUB_ID),
)

model.define(Campaign.has_redemption(PromotionRedemption)).where(
    Campaign.filter_by(id=raw.promotion_redemptions.CAMPAIGN_ID),
    PromotionRedemption.filter_by(id=raw.promotion_redemptions.REDEMPTION_ID),
)

model.define(Subscriber.has_redemption(PromotionRedemption)).where(
    Subscriber.filter_by(id=raw.promotion_redemptions.SUB_ID),
    PromotionRedemption.filter_by(id=raw.promotion_redemptions.REDEMPTION_ID),
)

# ═══════════════════════════════════════════════════════════════════════════════
# REVENUE FORECAST  (Source: REVENUE_FORECAST)
# ═══════════════════════════════════════════════════════════════════════════════
RevenueForecast = model.Concept("RevenueForecast", identify_by={"id": String})
RevenueForecast.region = model.Property(f"{RevenueForecast} has {String:region}")
RevenueForecast.forecast_month = model.Property(f"{RevenueForecast} has {Date:forecast_month}")
RevenueForecast.forecast_revenue = model.Property(f"{RevenueForecast} has {Float:forecast_revenue}")
RevenueForecast.actual_revenue = model.Property(f"{RevenueForecast} has {Float:actual_revenue}")
RevenueForecast.variance_pct = model.Property(f"{RevenueForecast} has {Float:variance_pct}")
RevenueForecast.status = model.Property(f"{RevenueForecast} has {String:status}")
RevenueForecast.subscriber_count = model.Property(f"{RevenueForecast} has {Integer:subscriber_count}")
RevenueForecast.arpu = model.Property(f"{RevenueForecast} has {Float:arpu}")

model.define(
    f := RevenueForecast.new(id=raw.revenue_forecast.FORECAST_ID),
    f.region(raw.revenue_forecast.REGION),
    f.forecast_month(raw.revenue_forecast.FORECAST_MONTH),
    f.forecast_revenue(raw.revenue_forecast.FORECAST_REVENUE_USD),
    f.actual_revenue(raw.revenue_forecast.ACTUAL_REVENUE_USD),
    f.variance_pct(raw.revenue_forecast.VARIANCE_PCT),
    f.status(raw.revenue_forecast.STATUS),
    f.subscriber_count(raw.revenue_forecast.SUBSCRIBER_COUNT),
    f.arpu(raw.revenue_forecast.ARPU_USD),
)

# ═══════════════════════════════════════════════════════════════════════════════
# CONTRACT AUTO-RENEW FLAG  (Source: PLANS_CONTRACTS.AUTO_RENEW — BOOLEAN in Snowflake)
# Modeled as String in PyRel (RAI auto-coerces BOOLEAN read to "true"/"false");
# declaring Boolean here triggers TyperError. To filter: Contract.auto_renew == "true".
# ═══════════════════════════════════════════════════════════════════════════════
Contract.auto_renew = model.Property(f"{Contract} has {String:auto_renew}")

model.define(Contract.auto_renew(raw.plans_contracts.AUTO_RENEW)).where(
    Contract.filter_by(id=raw.plans_contracts.CONTRACT_ID),
)

# ═══════════════════════════════════════════════════════════════════════════════
# PROMOTION REDEMPTION CHURN IMPACT  (Source: REDEMPTION_CHURN_IMPACT — 1:1 by REDEMPTION_ID)
# ═══════════════════════════════════════════════════════════════════════════════
PromotionRedemption.churn_reduction_pct = model.Property(f"{PromotionRedemption} has {Float:churn_reduction_pct}")

model.define(PromotionRedemption.churn_reduction_pct(raw.redemption_churn_impact.CHURN_REDUCTION_PCT)).where(
    PromotionRedemption.filter_by(id=raw.redemption_churn_impact.REDEMPTION_ID),
)

# ═══════════════════════════════════════════════════════════════════════════════
# NETWORK PERFORMANCE  (Source: NETWORK_PERFORMANCE — per-tower time series, ~76K rows)
# Note: 250 distinct TOWER_IDs in NETWORK_PERFORMANCE but only 120 in CELL_TOWERS.
#       FK binding only resolves matched towers; the other ~130 are orphaned.
# ═══════════════════════════════════════════════════════════════════════════════
NetworkPerformance = model.Concept("NetworkPerformance", identify_by={"id": String})
NetworkPerformance.timestamp = model.Property(f"{NetworkPerformance} has {DateTime:timestamp}")
NetworkPerformance.latency_ms = model.Property(f"{NetworkPerformance} has {Float:latency_ms}")
NetworkPerformance.throughput_mbps = model.Property(f"{NetworkPerformance} has {Float:throughput_mbps}")
NetworkPerformance.packet_loss_pct = model.Property(f"{NetworkPerformance} has {Float:packet_loss_pct}")
NetworkPerformance.jitter_ms = model.Property(f"{NetworkPerformance} has {Float:jitter_ms}")
NetworkPerformance.signal_strength_dbm = model.Property(f"{NetworkPerformance} has {Integer:signal_strength_dbm}")
NetworkPerformance.active_connections = model.Property(f"{NetworkPerformance} has {Integer:active_connections}")
NetworkPerformance.bandwidth_utilization_pct = model.Property(f"{NetworkPerformance} has {Float:bandwidth_utilization_pct}")
NetworkPerformance.error_rate = model.Property(f"{NetworkPerformance} has {Float:error_rate}")
NetworkPerformance.for_tower = model.Relationship(f"{NetworkPerformance} for tower {CellTower}", short_name="performance_for_tower")
CellTower.has_performance = model.Relationship(f"{CellTower} has performance {NetworkPerformance}", short_name="cell_tower_has_performance")

model.define(
    np := NetworkPerformance.new(id=raw.network_performance.METRIC_ID),
    np.timestamp(raw.network_performance.TIMESTAMP),
    np.latency_ms(raw.network_performance.LATENCY_MS),
    np.throughput_mbps(raw.network_performance.THROUGHPUT_MBPS),
    np.packet_loss_pct(raw.network_performance.PACKET_LOSS_PCT),
    np.jitter_ms(raw.network_performance.JITTER_MS),
    np.signal_strength_dbm(raw.network_performance.SIGNAL_STRENGTH_DBM),
    np.active_connections(raw.network_performance.ACTIVE_CONNECTIONS),
    np.bandwidth_utilization_pct(raw.network_performance.BANDWIDTH_UTILIZATION_PCT),
    np.error_rate(raw.network_performance.ERROR_RATE),
)

model.define(NetworkPerformance.for_tower(CellTower)).where(
    NetworkPerformance.filter_by(id=raw.network_performance.METRIC_ID),
    CellTower.filter_by(id=raw.network_performance.TOWER_ID),
)

model.define(CellTower.has_performance(NetworkPerformance)).where(
    CellTower.filter_by(id=raw.network_performance.TOWER_ID),
    NetworkPerformance.filter_by(id=raw.network_performance.METRIC_ID),
)

# ═══════════════════════════════════════════════════════════════════════════════
# SUPPORT TICKET  (Source: SUPPORT_TICKETS)
# RELATED_EVENT_ID is optional (206/2000 linked) — bind with filter_by, sparse FK.
# ═══════════════════════════════════════════════════════════════════════════════
SupportTicket = model.Concept("SupportTicket", identify_by={"id": String})
SupportTicket.category = model.Property(f"{SupportTicket} has {String:category}")
SupportTicket.subcategory = model.Property(f"{SupportTicket} has {String:subcategory}")
SupportTicket.priority = model.Property(f"{SupportTicket} has {String:priority}")
SupportTicket.status = model.Property(f"{SupportTicket} has {String:status}")
SupportTicket.channel = model.Property(f"{SupportTicket} has {String:channel}")
SupportTicket.created_date = model.Property(f"{SupportTicket} has {DateTime:created_date}")
SupportTicket.resolved_date = model.Property(f"{SupportTicket} has {DateTime:resolved_date}")
SupportTicket.resolution_time_hours = model.Property(f"{SupportTicket} has {Float:resolution_time_hours}")
SupportTicket.first_response_minutes = model.Property(f"{SupportTicket} has {Integer:first_response_minutes}")
SupportTicket.csat_score = model.Property(f"{SupportTicket} has {Float:csat_score}")
SupportTicket.sla_breached = model.Property(f"{SupportTicket} has {Boolean:sla_breached}")
SupportTicket.escalated = model.Property(f"{SupportTicket} has {Boolean:escalated}")
SupportTicket.agent_id = model.Property(f"{SupportTicket} has {String:agent_id}")
SupportTicket.notes = model.Property(f"{SupportTicket} has {String:notes}")
SupportTicket.for_subscriber = model.Relationship(f"{SupportTicket} for subscriber {Subscriber}", short_name="ticket_for_subscriber")
SupportTicket.related_event = model.Relationship(f"{SupportTicket} related to event {NetworkEvent}", short_name="ticket_related_event")
Subscriber.has_ticket = model.Relationship(f"{Subscriber} has ticket {SupportTicket}", short_name="subscriber_has_ticket")
NetworkEvent.has_ticket = model.Relationship(f"{NetworkEvent} has ticket {SupportTicket}", short_name="event_has_ticket")

model.define(
    st := SupportTicket.new(id=raw.support_tickets.TICKET_ID),
    st.category(raw.support_tickets.CATEGORY),
    st.subcategory(raw.support_tickets.SUBCATEGORY),
    st.priority(raw.support_tickets.PRIORITY),
    st.status(raw.support_tickets.STATUS),
    st.channel(raw.support_tickets.CHANNEL),
    st.created_date(raw.support_tickets.CREATED_DATE),
    st.resolved_date(raw.support_tickets.RESOLVED_DATE),
    st.resolution_time_hours(raw.support_tickets.RESOLUTION_TIME_HOURS),
    st.first_response_minutes(raw.support_tickets.FIRST_RESPONSE_MINUTES),
    st.csat_score(raw.support_tickets.CSAT_SCORE),
    st.sla_breached(raw.support_tickets.SLA_BREACHED),
    st.escalated(raw.support_tickets.ESCALATED),
    st.agent_id(raw.support_tickets.AGENT_ID),
    st.notes(raw.support_tickets.NOTES),
)

model.define(SupportTicket.for_subscriber(Subscriber)).where(
    SupportTicket.filter_by(id=raw.support_tickets.TICKET_ID),
    Subscriber.filter_by(id=raw.support_tickets.SUB_ID),
)
model.define(Subscriber.has_ticket(SupportTicket)).where(
    Subscriber.filter_by(id=raw.support_tickets.SUB_ID),
    SupportTicket.filter_by(id=raw.support_tickets.TICKET_ID),
)
model.define(SupportTicket.related_event(NetworkEvent)).where(
    SupportTicket.filter_by(id=raw.support_tickets.TICKET_ID),
    NetworkEvent.filter_by(id=raw.support_tickets.RELATED_EVENT_ID),
)
model.define(NetworkEvent.has_ticket(SupportTicket)).where(
    NetworkEvent.filter_by(id=raw.support_tickets.RELATED_EVENT_ID),
    SupportTicket.filter_by(id=raw.support_tickets.TICKET_ID),
)

# ═══════════════════════════════════════════════════════════════════════════════
# TOWER UPGRADE OPTION  (Source: TOWER_UPGRADE_OPTIONS)
# Junction concept: compound identity (tower_id, tier). 360 = 120 towers × 3 tiers.
# ═══════════════════════════════════════════════════════════════════════════════
TowerUpgradeOption = model.Concept("TowerUpgradeOption", identify_by={"tower_id": String, "tier": String})
TowerUpgradeOption.capacity_increase_gbps = model.Property(f"{TowerUpgradeOption} has {Integer:capacity_increase_gbps}")
TowerUpgradeOption.cost = model.Property(f"{TowerUpgradeOption} has {Integer:cost}")
TowerUpgradeOption.install_weeks = model.Property(f"{TowerUpgradeOption} has {Integer:install_weeks}")
TowerUpgradeOption.for_tower = model.Relationship(f"{TowerUpgradeOption} for tower {CellTower}", short_name="upgrade_for_tower")
CellTower.has_upgrade_option = model.Relationship(f"{CellTower} has upgrade option {TowerUpgradeOption}", short_name="tower_has_upgrade_option")

model.define(
    u := TowerUpgradeOption.new(tower_id=raw.tower_upgrade_options.TOWER_ID, tier=raw.tower_upgrade_options.UPGRADE_TIER),
    u.capacity_increase_gbps(raw.tower_upgrade_options.CAPACITY_INCREASE_GBPS),
    u.cost(raw.tower_upgrade_options.COST_USD),
    u.install_weeks(raw.tower_upgrade_options.INSTALL_WEEKS),
)

model.define(TowerUpgradeOption.for_tower(CellTower)).where(
    TowerUpgradeOption.filter_by(tower_id=raw.tower_upgrade_options.TOWER_ID, tier=raw.tower_upgrade_options.UPGRADE_TIER),
    CellTower.filter_by(id=raw.tower_upgrade_options.TOWER_ID),
)

model.define(CellTower.has_upgrade_option(TowerUpgradeOption)).where(
    CellTower.filter_by(id=raw.tower_upgrade_options.TOWER_ID),
    TowerUpgradeOption.filter_by(tower_id=raw.tower_upgrade_options.TOWER_ID, tier=raw.tower_upgrade_options.UPGRADE_TIER),
)

# ═══════════════════════════════════════════════════════════════════════════════
# TIME SERIES METRIC  (Source: TIME_SERIES_METRICS — daily KPIs per region)
# Compound identity (metric_date, region). 3,285 rows = 365 days × 9 regions.
# ═══════════════════════════════════════════════════════════════════════════════
TimeSeriesMetric = model.Concept("TimeSeriesMetric", identify_by={"metric_date": Date, "region": String})
TimeSeriesMetric.active_subscribers = model.Property(f"{TimeSeriesMetric} has {Integer:active_subscribers}")
TimeSeriesMetric.subscriber_growth_rate = model.Property(f"{TimeSeriesMetric} has {Float:subscriber_growth_rate}")
TimeSeriesMetric.daily_revenue = model.Property(f"{TimeSeriesMetric} has {Float:daily_revenue}")
TimeSeriesMetric.total_calls = model.Property(f"{TimeSeriesMetric} has {Integer:total_calls}")
TimeSeriesMetric.avg_call_quality = model.Property(f"{TimeSeriesMetric} has {Float:avg_call_quality}")
TimeSeriesMetric.network_availability_pct = model.Property(f"{TimeSeriesMetric} has {Float:network_availability_pct}")
TimeSeriesMetric.data_consumed_tb = model.Property(f"{TimeSeriesMetric} has {Float:data_consumed_tb}")
TimeSeriesMetric.avg_latency_ms = model.Property(f"{TimeSeriesMetric} has {Float:avg_latency_ms}")
TimeSeriesMetric.support_tickets_opened = model.Property(f"{TimeSeriesMetric} has {Integer:support_tickets_opened}")
TimeSeriesMetric.support_tickets_resolved = model.Property(f"{TimeSeriesMetric} has {Integer:support_tickets_resolved}")
TimeSeriesMetric.churn_rate = model.Property(f"{TimeSeriesMetric} has {Float:churn_rate}")
TimeSeriesMetric.nps_daily_avg = model.Property(f"{TimeSeriesMetric} has {Float:nps_daily_avg}")
TimeSeriesMetric.marketing_spend = model.Property(f"{TimeSeriesMetric} has {Float:marketing_spend}")

model.define(
    tsm := TimeSeriesMetric.new(metric_date=raw.time_series_metrics.METRIC_DATE, region=raw.time_series_metrics.REGION),
    tsm.active_subscribers(raw.time_series_metrics.ACTIVE_SUBSCRIBERS),
    tsm.subscriber_growth_rate(raw.time_series_metrics.SUBSCRIBER_GROWTH_RATE),
    tsm.daily_revenue(raw.time_series_metrics.DAILY_REVENUE_USD),
    tsm.total_calls(raw.time_series_metrics.TOTAL_CALLS),
    tsm.avg_call_quality(raw.time_series_metrics.AVG_CALL_QUALITY),
    tsm.network_availability_pct(raw.time_series_metrics.NETWORK_AVAILABILITY_PCT),
    tsm.data_consumed_tb(raw.time_series_metrics.DATA_CONSUMED_TB),
    tsm.avg_latency_ms(raw.time_series_metrics.AVG_LATENCY_MS),
    tsm.support_tickets_opened(raw.time_series_metrics.SUPPORT_TICKETS_OPENED),
    tsm.support_tickets_resolved(raw.time_series_metrics.SUPPORT_TICKETS_RESOLVED),
    tsm.churn_rate(raw.time_series_metrics.CHURN_RATE),
    tsm.nps_daily_avg(raw.time_series_metrics.NPS_DAILY_AVG),
    tsm.marketing_spend(raw.time_series_metrics.MARKETING_SPEND_USD),
)
