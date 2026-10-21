"""Agent-facing ontology over deployed telco semantic/result tables."""

from types import SimpleNamespace

from relationalai.semantics import Float, Integer, Model, String

DEPLOYED_SCHEMA = "BERTOLANI.TELCO_NETWORK_RECOVERY"
RESULTS_SCHEMA = "BERTOLANI.TELCO_NETWORK_RECOVERY_RESULTS"


def _table(model: Model, schema: str, name: str):
    return model.Table(f"{schema}.{name}")


def initialize_upgrade_plan(model: Model) -> SimpleNamespace:
    """Expose the materialized upgrade decision without loading unrelated sources."""
    RestorePlan = model.Concept("RestorePlan", identify_by={"plan_id": String})
    RestorePlan.status = model.Property(f"{RestorePlan} has {String:status}")
    RestorePlan.total_cost = model.Property(f"{RestorePlan} has {Integer:total_cost}")
    RestorePlan.install_weeks = model.Property(
        f"{RestorePlan} has {Integer:install_weeks}"
    )
    RestorePlan.capacity_restored_gbps = model.Property(
        f"{RestorePlan} has {Integer:capacity_restored_gbps}"
    )
    RestorePlan.towers_covered = model.Property(
        f"{RestorePlan} has {Integer:towers_covered}"
    )
    RestorePlan.binding_constraint = model.Property(
        f"{RestorePlan} has {String:binding_constraint}"
    )
    plan_src = _table(model, RESULTS_SCHEMA, "RESTORE_PLAN")
    model.define(
        plan := RestorePlan.new(plan_id=plan_src.PLAN_ID),
        plan.status(plan_src.TERMINATION_STATUS),
        plan.total_cost(plan_src.TOTAL_COST),
        plan.install_weeks(plan_src.TOTAL_INSTALL_WEEKS),
        plan.capacity_restored_gbps(plan_src.CAPACITY_RESTORED_GBPS),
        plan.towers_covered(plan_src.TOWERS_COVERED),
        plan.binding_constraint(plan_src.BINDING_CONSTRAINT),
    )

    SelectedUpgrade = model.Concept(
        "SelectedUpgrade", identify_by={"tower_id": String, "tier": String}
    )
    SelectedUpgrade.region = model.Property(f"{SelectedUpgrade} has {String:region}")
    SelectedUpgrade.cost = model.Property(f"{SelectedUpgrade} has {Integer:cost}")
    SelectedUpgrade.capacity_gbps = model.Property(
        f"{SelectedUpgrade} has {Integer:capacity_gbps}"
    )
    SelectedUpgrade.install_weeks = model.Property(
        f"{SelectedUpgrade} has {Integer:install_weeks}"
    )
    SelectedUpgrade.failure_intensity = model.Property(
        f"{SelectedUpgrade} has {Float:failure_intensity}"
    )
    SelectedUpgrade.weighted_impact = model.Property(
        f"{SelectedUpgrade} has {Float:weighted_impact}"
    )
    upgrade_src = _table(model, RESULTS_SCHEMA, "SELECTED_UPGRADES")
    model.define(
        upgrade := SelectedUpgrade.new(
            tower_id=upgrade_src.TOWER_ID, tier=upgrade_src.TIER
        ),
        upgrade.region(upgrade_src.REGION),
        upgrade.cost(upgrade_src.COST),
        upgrade.capacity_gbps(upgrade_src.CAPACITY_GBPS),
        upgrade.install_weeks(upgrade_src.INSTALL_WEEKS),
        upgrade.failure_intensity(upgrade_src.FAILURE_INTENSITY),
        upgrade.weighted_impact(upgrade_src.WEIGHTED_IMPACT),
    )
    return SimpleNamespace(RestorePlan=RestorePlan, SelectedUpgrade=SelectedUpgrade)


def initialize(model: Model) -> SimpleNamespace:
    """Bind deployed telco tables to an agent-queryable semantic surface."""

    CellTower = model.Concept("CellTower", identify_by={"id": String})
    CellTower.name = model.Property(f"{CellTower} has {String:name}")
    CellTower.region = model.Property(f"{CellTower} has {String:region}")
    CellTower.status = model.Property(f"{CellTower} has {String:status}")
    CellTower.capacity_gbps = model.Property(f"{CellTower} has {Integer:capacity_gbps}")
    CellTower.avg_packet_loss = model.Property(
        f"{CellTower} has {Float:avg_packet_loss}"
    )
    CellTower.avg_latency_ms = model.Property(f"{CellTower} has {Float:avg_latency_ms}")
    CellTower.avg_error_rate = model.Property(f"{CellTower} has {Float:avg_error_rate}")
    CellTower.avg_health_score = model.Property(
        f"{CellTower} has {Float:avg_health_score}"
    )

    src = _table(model, DEPLOYED_SCHEMA, "CELLTOWER")
    model.define(
        tower := CellTower.new(id=src.ID),
        tower.name(src.NAME),
        tower.region(src.REGION),
        tower.status(src.STATUS),
        tower.capacity_gbps(src.CAPACITY_GBPS),
        tower.avg_packet_loss(src.AVG_PACKET_LOSS),
        tower.avg_latency_ms(src.AVG_LATENCY_MS),
        tower.avg_error_rate(src.AVG_ERROR_RATE),
        tower.avg_health_score(src.AVG_HEALTH_SCORE),
    )

    NetworkEquipment = model.Concept("NetworkEquipment", identify_by={"id": String})
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
    NetworkEquipment.status = model.Property(f"{NetworkEquipment} has {String:status}")

    src = _table(model, DEPLOYED_SCHEMA, "NETWORKEQUIPMENT")
    model.define(
        equipment := NetworkEquipment.new(id=src.ID),
        equipment.tower(CellTower.lookup(id=src.TOWER)),
        equipment.equipment_type(src.EQUIPMENT_TYPE),
        equipment.manufacturer(src.MANUFACTURER),
        equipment.eqp_model(src.EQP_MODEL),
        equipment.status(src.STATUS),
    )

    ModelAdvisory = model.Concept(
        "ModelAdvisory",
        identify_by={"model": String, "advisory_type": String, "issued_date": String},
    )
    ModelAdvisory.severity = model.Property(f"{ModelAdvisory} has {Float:severity}")
    ModelAdvisory.applies_to = model.Relationship(
        f"{ModelAdvisory} applies to {NetworkEquipment}"
    )
    src = _table(model, DEPLOYED_SCHEMA, "MODELADVISORY")
    model.define(
        advisory := ModelAdvisory.new(
            model=src.MODEL,
            advisory_type=src.ADVISORY_TYPE,
            issued_date=src.ISSUED_DATE,
        ),
        advisory.severity(src.SEVERITY),
    )
    model.where(ModelAdvisory.model == NetworkEquipment.eqp_model).define(
        ModelAdvisory.applies_to(NetworkEquipment)
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
    src = _table(model, DEPLOYED_SCHEMA, "TOWERUPGRADEOPTION")
    model.define(
        option := TowerUpgradeOption.new(tower_id=src.TOWER_ID, tier=src.TIER),
        option.tower(CellTower.lookup(id=src.TOWER)),
        option.capacity_increase_gbps(src.CAPACITY_INCREASE_GBPS),
        option.cost(src.COST),
        option.install_weeks(src.INSTALL_WEEKS),
    )

    RestorePlan = model.Concept("RestorePlan", identify_by={"plan_id": String})
    RestorePlan.termination_status = model.Property(
        f"{RestorePlan} has {String:termination_status}"
    )
    RestorePlan.objective_value = model.Property(
        f"{RestorePlan} has {Float:objective_value}"
    )
    RestorePlan.total_cost = model.Property(f"{RestorePlan} has {Integer:total_cost}")
    RestorePlan.total_install_weeks = model.Property(
        f"{RestorePlan} has {Integer:total_install_weeks}"
    )
    RestorePlan.capacity_restored_gbps = model.Property(
        f"{RestorePlan} has {Integer:capacity_restored_gbps}"
    )
    RestorePlan.gold_count = model.Property(f"{RestorePlan} has {Integer:gold_count}")
    RestorePlan.silver_count = model.Property(
        f"{RestorePlan} has {Integer:silver_count}"
    )
    RestorePlan.bronze_count = model.Property(
        f"{RestorePlan} has {Integer:bronze_count}"
    )
    RestorePlan.towers_covered = model.Property(
        f"{RestorePlan} has {Integer:towers_covered}"
    )
    RestorePlan.binding_constraint = model.Property(
        f"{RestorePlan} has {String:binding_constraint}"
    )
    src = _table(model, RESULTS_SCHEMA, "RESTORE_PLAN")
    model.define(
        plan := RestorePlan.new(plan_id=src.PLAN_ID),
        plan.termination_status(src.TERMINATION_STATUS),
        plan.objective_value(src.OBJECTIVE_VALUE),
        plan.total_cost(src.TOTAL_COST),
        plan.total_install_weeks(src.TOTAL_INSTALL_WEEKS),
        plan.capacity_restored_gbps(src.CAPACITY_RESTORED_GBPS),
        plan.gold_count(src.GOLD_COUNT),
        plan.silver_count(src.SILVER_COUNT),
        plan.bronze_count(src.BRONZE_COUNT),
        plan.towers_covered(src.TOWERS_COVERED),
        plan.binding_constraint(src.BINDING_CONSTRAINT),
    )

    SelectedUpgrade = model.Concept(
        "SelectedUpgrade", identify_by={"tower_id": String, "tier": String}
    )
    SelectedUpgrade.tower = model.Property(
        f"{SelectedUpgrade} selected for {CellTower:tower}"
    )
    SelectedUpgrade.region = model.Property(f"{SelectedUpgrade} has {String:region}")
    SelectedUpgrade.capacity_gbps = model.Property(
        f"{SelectedUpgrade} has {Integer:capacity_gbps}"
    )
    SelectedUpgrade.cost = model.Property(f"{SelectedUpgrade} has {Integer:cost}")
    SelectedUpgrade.install_weeks = model.Property(
        f"{SelectedUpgrade} has {Integer:install_weeks}"
    )
    SelectedUpgrade.failure_intensity = model.Property(
        f"{SelectedUpgrade} has {Float:failure_intensity}"
    )
    SelectedUpgrade.weighted_impact = model.Property(
        f"{SelectedUpgrade} has {Float:weighted_impact}"
    )
    src = _table(model, RESULTS_SCHEMA, "SELECTED_UPGRADES")
    model.define(
        upgrade := SelectedUpgrade.new(tower_id=src.TOWER_ID, tier=src.TIER),
        upgrade.tower(CellTower.lookup(id=src.TOWER_ID)),
        upgrade.region(src.REGION),
        upgrade.capacity_gbps(src.CAPACITY_GBPS),
        upgrade.cost(src.COST),
        upgrade.install_weeks(src.INSTALL_WEEKS),
        upgrade.failure_intensity(src.FAILURE_INTENSITY),
        upgrade.weighted_impact(src.WEIGHTED_IMPACT),
    )

    TowerCustomerImpact = model.Concept(
        "TowerCustomerImpact", identify_by={"tower_id": String}
    )
    TowerCustomerImpact.tower = model.Property(
        f"{TowerCustomerImpact} describes {CellTower:tower}"
    )
    TowerCustomerImpact.impact_count = model.Property(
        f"{TowerCustomerImpact} has {Integer:impact_count}"
    )
    TowerCustomerImpact.weighted_impact = model.Property(
        f"{TowerCustomerImpact} has {Float:weighted_impact}"
    )
    TowerCustomerImpact.weighted_pagerank = model.Property(
        f"{TowerCustomerImpact} has {Float:weighted_pagerank}"
    )
    src = _table(model, RESULTS_SCHEMA, "TOWER_CUSTOMER_IMPACT")
    model.define(
        impact := TowerCustomerImpact.new(tower_id=src.TOWER_ID),
        impact.tower(CellTower.lookup(id=src.TOWER_ID)),
        impact.impact_count(src.IMPACT_COUNT),
        impact.weighted_impact(src.WEIGHTED_IMPACT),
        impact.weighted_pagerank(src.WEIGHTED_PAGERANK),
    )

    TowerFailureScore = model.Concept(
        "TowerFailureScore", identify_by={"tower_id": String}
    )
    TowerFailureScore.tower = model.Property(
        f"{TowerFailureScore} scores {CellTower:tower}"
    )
    TowerFailureScore.failure_intensity = model.Property(
        f"{TowerFailureScore} has {Float:failure_intensity}"
    )
    src = _table(model, RESULTS_SCHEMA, "TOWER_FAILURE_SCORE")
    model.define(
        score := TowerFailureScore.new(tower_id=src.TOWER_ID),
        score.tower(CellTower.lookup(id=src.TOWER_ID)),
        score.failure_intensity(src.FAILURE_INTENSITY),
    )

    EquipmentFailurePrediction = model.Concept(
        "EquipmentFailurePrediction", identify_by={"equipment_id": String}
    )
    EquipmentFailurePrediction.equipment = model.Property(
        f"{EquipmentFailurePrediction} predicts {NetworkEquipment:equipment}"
    )
    EquipmentFailurePrediction.pos_prob = model.Property(
        f"{EquipmentFailurePrediction} has {Float:pos_prob}"
    )
    EquipmentFailurePrediction.predicted_label = model.Property(
        f"{EquipmentFailurePrediction} has {Integer:predicted_label}"
    )
    src = _table(model, RESULTS_SCHEMA, "EQUIPMENT_FAILURE_PREDICTION")
    model.define(
        pred := EquipmentFailurePrediction.new(equipment_id=src.EQUIPMENT_ID),
        pred.equipment(NetworkEquipment.lookup(id=src.EQUIPMENT_ID)),
        pred.pos_prob(src.POS_PROB),
        pred.predicted_label(src.PREDICTED_LABEL),
    )

    TopCallPath = model.Concept(
        "TopCallPath", identify_by={"hub_subscriber_id": String}
    )
    TopCallPath.influence_load = model.Property(
        f"{TopCallPath} has {Float:influence_load}"
    )
    TopCallPath.subscriber_path = model.Property(
        f"{TopCallPath} has {String:subscriber_path}"
    )
    TopCallPath.tower_path = model.Property(f"{TopCallPath} has {String:tower_path}")
    src = _table(model, RESULTS_SCHEMA, "TOP_CALL_PATH")
    model.define(
        path := TopCallPath.new(hub_subscriber_id=src.HUB_SUBSCRIBER_ID),
        path.influence_load(src.INFLUENCE_LOAD),
        path.subscriber_path(src.SUBSCRIBER_PATH),
        path.tower_path(src.TOWER_PATH),
    )

    return SimpleNamespace(**locals())
