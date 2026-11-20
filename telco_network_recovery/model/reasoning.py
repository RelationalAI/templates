"""Telco reasoning chain: equipment-failure GNN, critical-tower rules, customer-impact graph, call paths, and the upgrade MIP."""

from relationalai.semantics import Float, Integer, String, distinct, not_, where
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.predictive import GNN, PropertyTransformer
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.std import aggregates as aggs

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
    TowerUpgradeOption,
    Train,
    Val,
    model,
)
from .source import SEED

GNN_EPOCHS = 80
GNN_LR = 0.002

# Stage 5 budget envelope.
BUDGET_USD = 5_000_000
INSTALL_WEEKS_BUDGET = 200

# Stage 2 threshold for the predictive-driven critical-restore branch.
# failure_intensity is the per-tower SUM of equipment failure probs --
# effectively expected count of at-risk equipment items on the tower.
# 1.5 means "the GNN is confident at least ~2 pieces are at risk."
FAILURE_INTENSITY_THRESHOLD = 1.5

# --------------------------------------------------
# Stage 1: Predictive -- equipment-failure binary GNN
# --------------------------------------------------

# Heterogeneous graph with three FK / shared-MODEL edges:
#   1. EquipmentHealth <-> NetworkEquipment  (per-equipment health features)
#   2. NetworkEquipment <-> CellTower        (tower-context features)
#   3. ModelAdvisory <-> NetworkEquipment    (recall/defect signal via MODEL)
# We use `directed=False` (undirected, bidirectional message passing)
# so the GNN can propagate signal across multi-hop paths: a piece of
# equipment whose own MODEL has no advisory can still inherit risk
# from a tower-mate whose MODEL does, via the path
#   ModelAdvisory -> tower_mate -> CellTower -> this_equipment.
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

# Feature configuration. Drop identifier / FK columns, the label, and
# high-cardinality free-text fields. Pull every other ontology property
# as a typed feature.
pt = PropertyTransformer(
    drop=[
        CellTower.id,
        CellTower.name,
        NetworkEquipment.id,
        NetworkEquipment.tower_id_fk,
        # The GNN target is at_risk -- keeping it as a feature would leak.
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
# Stage 2: Rules -- flag is_critical_restore towers
# --------------------------------------------------

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
    TowerFailureScore.tower_id == CellTower.id,
    TowerFailureScore.failure_intensity > FAILURE_INTENSITY_THRESHOLD,
).define(CellTower.is_critical_restore())

# --------------------------------------------------
# Stage 3: Graph -- Customer impact analysis
# (PageRank as graph-reasoner signal; per-tower weighted_impact from
# customer_value (revenue x churn). PageRank-weighted impact retained
# as a secondary network-effect signal alongside the headline measure.)
# --------------------------------------------------

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

CellTower.impact_count = model.Property(f"{CellTower} has {Float:impact_count}")
# weighted_impact is the headline per-tower customer-impact score: the
# sum of customer_value (revenue x churn) over ACTIVE subscribers whose
# calls route through the tower. The Stage 5 MIP objective consumes
# this directly to prioritize towers by revenue-at-risk weighted by
# churn urgency.
#
# This is CDR-weighted (each call from a subscriber contributes their
# customer_value once), so a heavy-calling high-value account lifts a
# tower more than the same account calling once. A distinct-subscriber-
# per-tower variant is a defensible refinement.
CellTower.weighted_impact = model.Property(f"{CellTower} has {Float:weighted_impact}")
# Secondary signal: PageRank-weighted impact retained so the graph
# reasoner's network-effect view is still queryable alongside the
# revenue-based headline. Not consumed by the Stage 5 objective.
CellTower.weighted_pagerank = model.Property(f"{CellTower} has {Float:weighted_pagerank}")

model.define(
    CellTower.impact_count(
        aggs.count(distinct(Subscriber))
        .where(
            CallDetailRecord.routed_through(CellTower),
            CallDetailRecord.caller(Subscriber),
            Subscriber.status == SubscriberStatus.ACTIVE,
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
            Subscriber.status == SubscriberStatus.ACTIVE,
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
            Subscriber.status == SubscriberStatus.ACTIVE,
        )
        .per(CellTower)
    )
)

# --------------------------------------------------
# Stage 4: Paths -- Call-path enumeration through critical towers
#   PREVIEW capability; requires relationalai>=1.15.
# --------------------------------------------------
# Composes on Stage 3's Subscriber.influence_score (PageRank). Where
# PageRank scores a *node*, paths scores the *call route*: the model
# enumerates caller -> ... -> callee chains from the top-PageRank
# subscriber, recovers the routing tower on each hop, and ranks each
# route by total influence summed along the chain. The routing tower
# is the auxiliary middle field of an arity-3 edge, so each enumerated
# path also tells us which towers the influence flows through.

# Arity-3 call edge: {Subscriber:caller} via {CellTower:tower} calls {Subscriber:callee}.
# First/last fields (caller/callee) are the path endpoints; the tower is the
# auxiliary middle field (field_index 1), recoverable per hop via
# relationship_fields. Derived from CallDetailRecord's caller/callee/routed_through.
Subscriber.calls_via = model.Relationship(
    f"{Subscriber:caller} via {CellTower:tower} calls {Subscriber:callee}",
    short_name="calls_via",
)
cdr_edge = CallDetailRecord.ref()
caller_sub, callee_sub, via_tower = Subscriber.ref(), Subscriber.ref(), CellTower.ref()
model.where(
    cdr_edge.caller(caller_sub),
    cdr_edge.callee(callee_sub),
    cdr_edge.routed_through(via_tower),
).define(caller_sub.calls_via(via_tower, callee_sub))

# Path enumeration is declared here, in the model: a deployed model only has the
# path tables its own rules ask for, so a query cannot enumerate new paths. The
# scope is a deterministic seed -- the highest-PageRank subscriber, or each of
# them on an exact tie -- and call paths of up to PATH_MAX_HOPS hops, keeping
# simple paths only (the call graph is cyclic, so the negated existential drops
# walks that revisit a node).
PATH_MAX_HOPS = 3

hub_rival = Subscriber.ref()
Subscriber.is_seed_hub = model.Relationship(f"{Subscriber} is the seed hub")
model.define(Subscriber.is_seed_hub()).where(
    Subscriber.influence_score == aggs.max(hub_rival.influence_score)
)

seed = Subscriber.ref()
i, j = Integer.ref(), Integer.ref()
call_path = model.path(seed, Subscriber.calls_via.repeat(1, PATH_MAX_HOPS)).all().paths()
simple_hub_path = (seed.is_seed_hub(), call_path, not_(where(i < j, call_path.nodes(i) == call_path.nodes(j))))

SimplePathCount = model.Relationship(f"simple call paths from the seed hub number {Integer:paths}")
model.define(SimplePathCount(aggs.count(call_path).where(*simple_hub_path)))

# The routing tower on each hop is field_index 1 of the arity-3 edge
# (caller=0, tower=1, callee=2).
routing_tower = CellTower.ref()
RoutingTowerCount = model.Relationship(f"routing towers on those paths number {Integer:towers}")
model.define(
    RoutingTowerCount(
        aggs.count(routing_tower).where(
            *simple_hub_path,
            call_path.relationship_fields["field_index"] == 1,
            routing_tower == CellTower(call_path.relationship_fields["field"]),
        )
    )
)

# Rank the simple paths by influence load, the PageRank summed along each path's
# nodes, and keep the seed hub's highest.
Subscriber.top_call_path_influence = model.Property(f"{Subscriber} has {Float:top_call_path_influence}")
model.where(
    *simple_hub_path,
    total := aggs.sum(Subscriber(call_path.nodes).influence_score).per(call_path),
    top := aggs.max(total).per(seed),
).define(seed.top_call_path_influence(top))

# --------------------------------------------------
# Stage 5: Prescriptive -- tower upgrade MIP
# --------------------------------------------------

TowerUpgradeOption.selected = model.Property(f"{TowerUpgradeOption} has {Float:selected}")

problem = Problem(model, Float, name="telco_network_recovery")

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
# failure_intensity (TowerFailureScore).
problem.maximize(
    aggs.sum(
        TowerUpgradeOption.selected
        * TowerUpgradeOption.capacity_increase_gbps
        * CellTower.weighted_impact
        * TowerFailureScore.failure_intensity
    ).where(
        TowerUpgradeOption.for_tower(CellTower),
        CellTower.is_critical_restore(),
        TowerFailureScore.tower_id == CellTower.id,
    )
)

# Each refresh of the deployed model runs this solve. HiGHS is the bundled
# open-source solver; use solver "gurobi" where it is licensed.
problem.configure("highs")

# The solve's status and objective, which the deployed model publishes for the queries.
SolveStatus = model.Relationship(f"telco recovery solve status is {String:status}")
SolveObjective = model.Relationship(f"telco recovery objective is {Float:objective}")
model.define(SolveStatus(problem.termination_status()), SolveObjective(problem.objective_value()))

TowerUpgradeOption.is_selected_upgrade = model.Relationship(
    f"{TowerUpgradeOption} is selected upgrade"
)
model.where(TowerUpgradeOption.selected > 0.5).define(
    TowerUpgradeOption.is_selected_upgrade()
)

# --------------------------------------------------
# Plan summary: the RestorePlan singleton publishes the headline metrics
# (total cost, install weeks, capacity, tier mix, binding constraint).
# --------------------------------------------------

# RestorePlan concept: singleton holding the headline plan metrics
# (cost, install-weeks, capacity restored, tier mix, towers covered,
# binding constraint) -- the prescriptive output materialized as
# queryable ontology.
RESTORE_PLAN_ID = "TELCO_RECOVERY_2024Q4"
RestorePlan = model.Concept("RestorePlan", identify_by={"id": String})
RestorePlan.total_cost = model.Property(f"{RestorePlan} has {Float:total_cost}")
RestorePlan.total_install_weeks = model.Property(f"{RestorePlan} has {Integer:total_install_weeks}")
RestorePlan.capacity_restored_gbps = model.Property(f"{RestorePlan} has {Integer:capacity_restored_gbps}")
RestorePlan.gold_count = model.Property(f"{RestorePlan} has {Integer:gold_count}")
RestorePlan.silver_count = model.Property(f"{RestorePlan} has {Integer:silver_count}")
RestorePlan.bronze_count = model.Property(f"{RestorePlan} has {Integer:bronze_count}")
RestorePlan.towers_covered = model.Property(f"{RestorePlan} has {Integer:towers_covered}")
RestorePlan.binding_constraint = model.Property(f"{RestorePlan} has {String:binding_constraint}")

model.define(RestorePlan.new(id=RESTORE_PLAN_ID))

selected_option = TowerUpgradeOption.is_selected_upgrade()
model.where(RestorePlan.id == RESTORE_PLAN_ID).define(
    RestorePlan.total_cost(
        aggs.sum(TowerUpgradeOption, TowerUpgradeOption.cost).where(selected_option)
    ),
    RestorePlan.total_install_weeks(
        aggs.sum(TowerUpgradeOption, TowerUpgradeOption.install_weeks).where(selected_option)
    ),
    RestorePlan.capacity_restored_gbps(
        aggs.sum(TowerUpgradeOption, TowerUpgradeOption.capacity_increase_gbps).where(selected_option)
    ),
    RestorePlan.gold_count(
        aggs.count(TowerUpgradeOption).where(selected_option, TowerUpgradeOption.tier == "GOLD")
    ),
    RestorePlan.silver_count(
        aggs.count(TowerUpgradeOption).where(selected_option, TowerUpgradeOption.tier == "SILVER")
    ),
    RestorePlan.bronze_count(
        aggs.count(TowerUpgradeOption).where(selected_option, TowerUpgradeOption.tier == "BRONZE")
    ),
    RestorePlan.towers_covered(aggs.count(TowerUpgradeOption).where(selected_option)),
)

# 0.995: residual headroom below ~0.5% is too small to fit another
# whole-tier upgrade (cheapest BRONZE > $25k vs $25k of slack), so
# the cap is effectively hit. Earlier 0.999 misclassified clearly-
# budget-bound runs as "none" when the optimizer left ~$5-10k slack.
BINDING_COST = BUDGET_USD * 0.995
model.where(RestorePlan.total_cost > BINDING_COST).define(
    RestorePlan.binding_constraint("budget")
)
model.where(
    RestorePlan.total_cost <= BINDING_COST,
    RestorePlan.total_install_weeks >= INSTALL_WEEKS_BUDGET - 1,
).define(RestorePlan.binding_constraint("install_weeks"))
model.where(
    RestorePlan.total_cost <= BINDING_COST,
    RestorePlan.total_install_weeks < INSTALL_WEEKS_BUDGET - 1,
).define(RestorePlan.binding_constraint("none"))
