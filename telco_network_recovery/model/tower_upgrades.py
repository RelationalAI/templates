"""Tower upgrades: the upgrade MIP over the critical towers, the plan it yields, and how many selected
upgrades each restore signal flagged."""

from relationalai.semantics import Float, Integer, String
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.std import aggregates as aggs

# Declare CellTower.is_critical_restore and the branch flags, and CellTower.weighted_impact and
# CellTower.is_high_value: the decision scope, the objective's weight and the signals the tally counts.
from . import critical_towers, customer_impact  # noqa: F401
from .equipment_failure import TowerFailureScore
from .schema import CellTower, TowerUpgradeOption, model

# Stage 5 budget envelope.
BUDGET_USD = 5_000_000
INSTALL_WEEKS_BUDGET = 200

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
# the cap is effectively hit.
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

# --------------------------------------------------
# Why each upgrade was selected
# --------------------------------------------------

# How many selected upgrades each signal that flags a critical tower fired on: an operational
# branch, the predictive branch, and a high-value tower (an upgrade can fire on several).
RationaleTally = model.Relationship(
    f"selected upgrades fire {Integer:operational} operational, {Integer:predictive} advisory/predicted "
    f"and {Integer:high_value} high-value signals"
)
model.define(
    RationaleTally(
        *(
            aggs.count(TowerUpgradeOption).where(
                selected_option, TowerUpgradeOption.for_tower(CellTower), signal()
            )
            | 0
            for signal in (
                CellTower.fires_operational_branch,
                CellTower.fires_predictive_branch,
                CellTower.is_high_value,
            )
        )
    )
)

# The selected upgrades in each region.
SelectedRegionCount = model.Relationship(f"{Integer:upgrades} selected upgrades lie in region {String:region}")
_region = String.ref()
model.where(selected_option, TowerUpgradeOption.for_tower(CellTower), CellTower.region == _region).define(
    SelectedRegionCount(aggs.count(TowerUpgradeOption).per(_region), _region)
)
