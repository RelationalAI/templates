"""Reusable bindings for the deployed telco base ontology.

Standalone reasoner jobs should build on these concept declarations instead
of redeclaring local copies. Sources can be either `model.Table(...)` handles
or `model.data(...)` handles populated from deployed semantic tables.
"""

from types import SimpleNamespace

from relationalai.semantics import Float, Integer, String

from reasoner_common import table


def table_sources(model, names):
    return SimpleNamespace(
        **{name: model.Table(table(name)) for name in names}
    )


def dataframe_sources(model, frames):
    return SimpleNamespace(
        **{name: model.data(frame) for name, frame in frames.items()}
    )


def bind_celltower(model, src):
    CellTower = model.Concept("CellTower", identify_by={"id": String})
    CellTower.name = model.Property(f"{CellTower} has {String:name}")
    CellTower.tower_type = model.Property(f"{CellTower} has {String:tower_type}")
    CellTower.capacity_gbps = model.Property(f"{CellTower} has {Integer:capacity_gbps}")
    CellTower.status = model.Property(f"{CellTower} has {String:status}")
    CellTower.region = model.Property(f"{CellTower} has {String:region}")
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
        tower := CellTower.new(id=src.ID),
        tower.name(src.NAME),
        tower.tower_type(src.TOWER_TYPE),
        tower.capacity_gbps(src.CAPACITY_GBPS),
        tower.status(src.STATUS),
        tower.region(src.REGION),
        tower.avg_packet_loss(src.AVG_PACKET_LOSS),
        tower.avg_latency_ms(src.AVG_LATENCY_MS),
        tower.avg_error_rate(src.AVG_ERROR_RATE),
        tower.avg_health_score(src.AVG_HEALTH_SCORE),
    )
    return CellTower


def bind_network_equipment(model, src, CellTower):
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
    NetworkEquipment.manufacturer = model.Property(
        f"{NetworkEquipment} has {String:manufacturer}"
    )
    NetworkEquipment.eqp_model = model.Property(
        f"{NetworkEquipment} has {String:eqp_model}"
    )
    NetworkEquipment.firmware_version = model.Property(
        f"{NetworkEquipment} has {String:firmware_version}"
    )
    NetworkEquipment.status = model.Property(f"{NetworkEquipment} has {String:status}")
    model.define(
        equipment := NetworkEquipment.new(id=src.ID),
        equipment.tower_id_fk(src.TOWER_ID_FK),
        equipment.tower(CellTower.lookup(id=src.TOWER)),
        equipment.equipment_type(src.EQUIPMENT_TYPE),
        equipment.manufacturer(src.MANUFACTURER),
        equipment.eqp_model(src.EQP_MODEL),
        equipment.firmware_version(src.FIRMWARE_VERSION),
        equipment.status(src.STATUS),
    )
    return NetworkEquipment


def bind_equipment_health(model, src, NetworkEquipment):
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
    EquipmentHealth.temperature_avg_c = model.Property(
        f"{EquipmentHealth} has {Float:temperature_avg_c}"
    )
    EquipmentHealth.power_consumption_kw = model.Property(
        f"{EquipmentHealth} has {Float:power_consumption_kw}"
    )
    EquipmentHealth.health_score = model.Property(
        f"{EquipmentHealth} has {Float:health_score}"
    )
    model.define(
        health := EquipmentHealth.new(id=src.ID),
        health.equipment_id_fk(src.EQUIPMENT_ID_FK),
        health.equipment(NetworkEquipment.lookup(id=src.EQUIPMENT)),
        health.mtbf_hours(src.MTBF_HOURS),
        health.failure_rate(src.FAILURE_RATE),
        health.temperature_avg_c(src.TEMPERATURE_AVG_C),
        health.power_consumption_kw(src.POWER_CONSUMPTION_KW),
        health.health_score(src.HEALTH_SCORE),
    )
    return EquipmentHealth


def bind_model_advisory(model, src, NetworkEquipment, define_applies_to=True):
    ModelAdvisory = model.Concept(
        "ModelAdvisory",
        identify_by={"model": String, "advisory_type": String, "issued_date": String},
    )
    ModelAdvisory.severity = model.Property(f"{ModelAdvisory} has {Float:severity}")
    model.define(
        advisory := ModelAdvisory.new(
            model=src.MODEL,
            advisory_type=src.ADVISORY_TYPE,
            issued_date=src.ISSUED_DATE,
        ),
        advisory.severity(src.SEVERITY),
    )
    if define_applies_to:
        ModelAdvisory.applies_to = model.Relationship(
            f"{ModelAdvisory} applies to {NetworkEquipment}"
        )
        model.define(ModelAdvisory.applies_to(NetworkEquipment)).where(
            ModelAdvisory.model == NetworkEquipment.eqp_model
        )
    return ModelAdvisory


def bind_tower_upgrade_option(model, src, CellTower):
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
        option := TowerUpgradeOption.new(tower_id=src.TOWER_ID, tier=src.TIER),
        option.tower(CellTower.lookup(id=src.TOWER)),
        option.capacity_increase_gbps(src.CAPACITY_INCREASE_GBPS),
        option.cost(src.COST),
        option.install_weeks(src.INSTALL_WEEKS),
    )
    return TowerUpgradeOption


def bind_operational_critical_restore(model, src, CellTower):
    model.define(
        CellTower.lookup(id=src.CELLTOWER).operational_critical_restore()
    )


def bind_subscriber(model, src):
    Subscriber = model.Concept("Subscriber", identify_by={"id": String})
    Subscriber.status = model.Property(f"{Subscriber} has {String:status}")
    Subscriber.customer_value = model.Property(
        f"{Subscriber} has {Float:customer_value}"
    )
    model.define(
        subscriber := Subscriber.new(id=src.ID),
        subscriber.status(src.STATUS),
        subscriber.customer_value(src.CUSTOMER_VALUE),
    )
    return Subscriber


def bind_call_detail_record(model, src, Subscriber, CellTower):
    CallDetailRecord = model.Concept("CallDetailRecord", identify_by={"id": String})
    CallDetailRecord.caller = model.Property(
        f"{CallDetailRecord} has caller {Subscriber:caller}"
    )
    CallDetailRecord.callee = model.Property(
        f"{CallDetailRecord} has callee {Subscriber:callee}"
    )
    CallDetailRecord.routed_through = model.Property(
        f"{CallDetailRecord} routed through {CellTower:tower}"
    )
    model.define(
        cdr := CallDetailRecord.new(id=src.ID),
        cdr.caller(Subscriber.lookup(id=src.CALLER)),
        cdr.callee(Subscriber.lookup(id=src.CALLEE)),
        cdr.routed_through(CellTower.lookup(id=src.ROUTED_THROUGH)),
    )
    return CallDetailRecord


def bind_predictive_base(model, sources):
    CellTower = bind_celltower(model, sources.CELLTOWER)
    NetworkEquipment = bind_network_equipment(
        model, sources.NETWORKEQUIPMENT, CellTower
    )
    EquipmentHealth = bind_equipment_health(
        model, sources.EQUIPMENTHEALTH, NetworkEquipment
    )
    ModelAdvisory = bind_model_advisory(
        model, sources.MODELADVISORY, NetworkEquipment, define_applies_to=False
    )
    return SimpleNamespace(
        model=model,
        CellTower=CellTower,
        NetworkEquipment=NetworkEquipment,
        EquipmentHealth=EquipmentHealth,
        ModelAdvisory=ModelAdvisory,
    )


def bind_optimization_base(model, sources):
    CellTower = bind_celltower(model, sources.CELLTOWER)
    bind_operational_critical_restore(
        model, sources.CELLTOWER_OPERATIONAL_CRITICAL_RESTORE, CellTower
    )
    TowerUpgradeOption = bind_tower_upgrade_option(
        model, sources.TOWERUPGRADEOPTION, CellTower
    )
    return SimpleNamespace(
        model=model,
        CellTower=CellTower,
        TowerUpgradeOption=TowerUpgradeOption,
    )


def bind_graph_base(model, sources):
    CellTower = bind_celltower(model, sources.CELLTOWER)
    Subscriber = bind_subscriber(model, sources.SUBSCRIBER)
    CallDetailRecord = bind_call_detail_record(
        model, sources.CALLDETAILRECORD, Subscriber, CellTower
    )
    return SimpleNamespace(
        model=model,
        CellTower=CellTower,
        Subscriber=Subscriber,
        CallDetailRecord=CallDetailRecord,
    )
