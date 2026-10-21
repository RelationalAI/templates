"""Optimize tower upgrade selection on deployed ontology and reasoner outputs.

Inputs:
  BERTOLANI.TELCO_NETWORK_RECOVERY.{CELLTOWER, CELLTOWER_OPERATIONAL_CRITICAL_RESTORE,
  TOWERUPGRADEOPTION}
  BERTOLANI.TELCO_NETWORK_RECOVERY_RESULTS.{TOWER_FAILURE_SCORE, TOWER_CUSTOMER_IMPACT}

Outputs:
  BERTOLANI.TELCO_NETWORK_RECOVERY_RESULTS.SELECTED_UPGRADES
  BERTOLANI.TELCO_NETWORK_RECOVERY_RESULTS.RESTORE_PLAN
"""

import pandas as pd
from relationalai.config import create_config
from relationalai.semantics import Float, Model
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.std import aggregates as aggs

from deployed_ontology import bind_optimization_base, table_sources
from reasoner_common import RESULTS_SCHEMA, replace_table, table

BUDGET_USD = 5_000_000
INSTALL_WEEKS_BUDGET = 200
FAILURE_INTENSITY_THRESHOLD = 1.5


def build_model(config=None):
    eager_config = (config if config is not None else create_config()).model_copy()
    eager_config.deployment = None
    model = Model("Telco Upgrade Optimization From Deployed Tables", config=eager_config)
    ontology = bind_optimization_base(
        model,
        table_sources(
            model,
            [
                "CELLTOWER",
                "CELLTOWER_OPERATIONAL_CRITICAL_RESTORE",
                "TOWERUPGRADEOPTION",
            ],
        ),
    )
    CellTower = ontology.CellTower
    TowerUpgradeOption = ontology.TowerUpgradeOption

    CellTower.failure_intensity = model.Property(
        f"{CellTower} has {Float:failure_intensity}"
    )
    CellTower.weighted_impact = model.Property(
        f"{CellTower} has {Float:weighted_impact}"
    )
    CellTower.is_critical_restore = model.Relationship(
        f"{CellTower} is critical restore"
    )

    failure_src = model.Table(table("TOWER_FAILURE_SCORE", RESULTS_SCHEMA))
    model.define(
        CellTower.lookup(id=failure_src.TOWER_ID).failure_intensity(
            failure_src.FAILURE_INTENSITY
        )
    )

    impact_src = model.Table(table("TOWER_CUSTOMER_IMPACT", RESULTS_SCHEMA))
    model.define(
        CellTower.lookup(id=impact_src.TOWER_ID).weighted_impact(
            impact_src.WEIGHTED_IMPACT
        )
    )

    model.where(CellTower.operational_critical_restore()).define(
        CellTower.is_critical_restore()
    )
    model.where(CellTower.failure_intensity > FAILURE_INTENSITY_THRESHOLD).define(
        CellTower.is_critical_restore()
    )

    TowerUpgradeOption.selected = model.Property(
        f"{TowerUpgradeOption} has {Float:selected}"
    )
    return model, CellTower, TowerUpgradeOption


def solve(model, CellTower, TowerUpgradeOption, budget_usd: int = BUDGET_USD):
    if type(budget_usd) is not int or budget_usd <= 0:
        raise ValueError("budget_usd must be a positive whole number of US dollars")
    problem = Problem(model, Float)
    problem.solve_for(
        TowerUpgradeOption.selected,
        where=[
            TowerUpgradeOption.tower == CellTower,
            CellTower.is_critical_restore(),
        ],
        name=["tower_id", "tier"],
        type="bin",
    )

    problem.satisfy(
        model.where(
            TowerUpgradeOption.tower == CellTower,
            CellTower.is_critical_restore(),
        ).require(aggs.sum(TowerUpgradeOption.selected).per(CellTower) <= 1)
    )
    problem.satisfy(
        model.where(
            TowerUpgradeOption.tower == CellTower,
            CellTower.is_critical_restore(),
        ).require(
            aggs.sum(TowerUpgradeOption.selected * TowerUpgradeOption.cost)
            <= budget_usd
        )
    )
    problem.satisfy(
        model.where(
            TowerUpgradeOption.tower == CellTower,
            CellTower.is_critical_restore(),
        ).require(
            aggs.sum(TowerUpgradeOption.selected * TowerUpgradeOption.install_weeks)
            <= INSTALL_WEEKS_BUDGET
        )
    )
    problem.maximize(
        aggs.sum(
            TowerUpgradeOption.selected
            * TowerUpgradeOption.capacity_increase_gbps
            * CellTower.weighted_impact
            * CellTower.failure_intensity
        ).where(
            TowerUpgradeOption.tower == CellTower,
            CellTower.is_critical_restore(),
        )
    )

    problem.solve("highs")
    return problem


def optimize(budget_usd: int = BUDGET_USD, config=None):
    """Solve a budget scenario without changing the materialized $5M plan."""
    if type(budget_usd) is not int or budget_usd <= 0:
        raise ValueError("budget_usd must be a positive whole number of US dollars")
    model, CellTower, TowerUpgradeOption = build_model(config=config)
    problem = solve(model, CellTower, TowerUpgradeOption, budget_usd)
    solve_info = problem.solve_info()
    status = solve_info.termination_status
    if status != "OPTIMAL":
        raise RuntimeError(
            f"Upgrade optimization did not reach an optimal solution: "
            f"{status}"
        )

    selected = (
        model.where(TowerUpgradeOption.selected > 0.5)
        .select(
            TowerUpgradeOption.tower_id.alias("TOWER_ID"),
            TowerUpgradeOption.tier.alias("TIER"),
            CellTower.region.alias("REGION"),
            TowerUpgradeOption.capacity_increase_gbps.alias("CAPACITY_GBPS"),
            TowerUpgradeOption.cost.alias("COST"),
            TowerUpgradeOption.install_weeks.alias("INSTALL_WEEKS"),
            CellTower.failure_intensity.alias("FAILURE_INTENSITY"),
            CellTower.weighted_impact.alias("WEIGHTED_IMPACT"),
        )
        .where(TowerUpgradeOption.tower == CellTower)
        .to_df()
    )
    for col in ("CAPACITY_GBPS", "COST", "INSTALL_WEEKS"):
        if col in selected:
            selected[col] = selected[col].astype("int64")

    total_cost = int(selected["COST"].sum()) if not selected.empty else 0
    total_weeks = int(selected["INSTALL_WEEKS"].sum()) if not selected.empty else 0
    capacity = int(selected["CAPACITY_GBPS"].sum()) if not selected.empty else 0
    tier_counts = selected["TIER"].value_counts().to_dict() if not selected.empty else {}
    binding = (
        "budget"
        if total_cost > budget_usd * 0.995
        else "install_weeks"
        if total_weeks >= INSTALL_WEEKS_BUDGET - 1
        else "none"
    )
    plan = pd.DataFrame(
        [
            {
                "PLAN_ID": "TELCO_RECOVERY_STANDALONE",
                "BUDGET_USD": budget_usd,
                "TERMINATION_STATUS": status,
                "OBJECTIVE_VALUE": solve_info.objective_value,
                "TOTAL_COST": total_cost,
                "TOTAL_INSTALL_WEEKS": total_weeks,
                "CAPACITY_RESTORED_GBPS": capacity,
                "GOLD_COUNT": int(tier_counts.get("GOLD", 0)),
                "SILVER_COUNT": int(tier_counts.get("SILVER", 0)),
                "BRONZE_COUNT": int(tier_counts.get("BRONZE", 0)),
                "TOWERS_COVERED": int(len(selected)),
                "BINDING_CONSTRAINT": binding,
            }
        ]
    )
    if total_cost > budget_usd or total_weeks > INSTALL_WEEKS_BUDGET:
        raise RuntimeError("Selected upgrades violate a budget or install-week constraint")
    if selected["TOWER_ID"].duplicated().any():
        raise RuntimeError("Selected upgrades include multiple tiers for one tower")
    return selected, plan


def main():
    selected, plan = optimize()
    replace_table(selected, "SELECTED_UPGRADES")
    replace_table(plan.drop(columns=["BUDGET_USD"]), "RESTORE_PLAN")


if __name__ == "__main__":
    main()
