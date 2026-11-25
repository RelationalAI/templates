"""Critical towers: each tower's measured averages, the three restore branches that flag it critical, and
the counts of towers per branch and region."""

from relationalai.semantics import Float, Integer, String, not_
from relationalai.semantics.std import aggregates as aggs

from .equipment_failure import TowerFailureScore
from .schema import CellTower, EquipmentHealth, NetworkEquipment, NetworkPerformance, model

# Threshold for the predictive-driven critical-restore branch.
# failure_intensity is the per-tower SUM of equipment failure probs --
# effectively expected count of at-risk equipment items on the tower.
# 1.5 means "the GNN is confident at least ~2 pieces are at risk."
FAILURE_INTENSITY_THRESHOLD = 1.5

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
# Each branch is published on its own, so the report can say which ones fired.
CellTower.fires_degraded_branch = model.Relationship(f"{CellTower} fires the degraded-status restore branch")
CellTower.fires_packet_loss_branch = model.Relationship(f"{CellTower} fires the packet-loss restore branch")
CellTower.fires_predictive_branch = model.Relationship(f"{CellTower} fires the predictive restore branch")
CellTower.is_critical_restore = model.Relationship(f"{CellTower} is critical restore")

model.where(
    CellTower.region == "WEST",
    CellTower.status == "DEGRADED",
    CellTower.avg_health_score < 0.85,
).define(CellTower.fires_degraded_branch())

model.where(
    CellTower.region == "WEST",
    CellTower.avg_packet_loss > 5.0,
    CellTower.avg_health_score < 0.85,
).define(CellTower.fires_packet_loss_branch())

model.where(
    TowerFailureScore.tower_id == CellTower.id,
    TowerFailureScore.failure_intensity > FAILURE_INTENSITY_THRESHOLD,
).define(CellTower.fires_predictive_branch())

model.where(CellTower.fires_degraded_branch()).define(CellTower.is_critical_restore())
model.where(CellTower.fires_packet_loss_branch()).define(CellTower.is_critical_restore())
model.where(CellTower.fires_predictive_branch()).define(CellTower.is_critical_restore())

# The operational branches together, and the predictive branch with no operational one.
CellTower.fires_operational_branch = model.Relationship(f"{CellTower} fires an operational restore branch")
CellTower.fires_only_predictive_branch = model.Relationship(
    f"{CellTower} fires the predictive restore branch and no operational one"
)
model.where(CellTower.fires_degraded_branch()).define(CellTower.fires_operational_branch())
model.where(CellTower.fires_packet_loss_branch()).define(CellTower.fires_operational_branch())
model.where(CellTower.fires_predictive_branch(), not_(CellTower.fires_operational_branch())).define(
    CellTower.fires_only_predictive_branch()
)

# How many towers are critical, how many fire each branch (a tower can fire several), and
# how many fire only the predictive branch.
RestoreBranchCounts = model.Relationship(
    f"{Integer:critical} towers are critical restore; {Integer:degraded} fire the degraded-status branch, "
    f"{Integer:packet_loss} the packet-loss branch and {Integer:predictive} the predictive branch, "
    f"and {Integer:only_predictive} fire only the predictive branch"
)
model.define(
    RestoreBranchCounts(
        aggs.count(CellTower).where(CellTower.is_critical_restore()) | 0,
        aggs.count(CellTower).where(CellTower.fires_degraded_branch()) | 0,
        aggs.count(CellTower).where(CellTower.fires_packet_loss_branch()) | 0,
        aggs.count(CellTower).where(CellTower.fires_predictive_branch()) | 0,
        aggs.count(CellTower).where(CellTower.fires_only_predictive_branch()) | 0,
    )
)

# The critical towers in each region.
CriticalRegionCount = model.Relationship(f"{Integer:towers} critical-restore towers lie in region {String:region}")
_region = String.ref()
model.where(CellTower.is_critical_restore(), CellTower.region == _region).define(
    CriticalRegionCount(aggs.count(CellTower).per(_region), _region)
)
