"""Coverage report: reads the deployed cell_tower_coverage model.

Run `python -m queries.coverage_report` after `rai models deploy --path model`. Prints the
status and objective of the latest refresh's solve, the selected tower sites, assigned demand
zones, tower utilization and coverage summary, and writes data/coverage_solution.csv for
downstream mapping or reporting.
"""

import pandas as pd
from model import (
    DATA_DIR,
    BuildBudget,
    CandidateSiteCount,
    CoveragePairCount,
    CoverageRate,
    CoveredPopulation,
    DemandZone,
    DemandZoneCount,
    MaxNewTowers,
    SelectedBuildCost,
    SolveStatus,
    TotalPopulation,
    TowerLoad,
    TowerSite,
    UncoveredPopulation,
    ZoneAssignment,
    covered,
    model,
    selected,
)
from relationalai.semantics import String


def _scalar(relationship, default=None):
    """The single value of a published scalar relationship, or `default` when it has none."""
    values = model.select(relationship).to_df().iloc[:, 0].tolist()
    return values[0] if values else default


if __name__ == "__main__":
    build_budget = _scalar(BuildBudget)

    print("=" * 70)
    print("CELL TOWER COVERAGE")
    print("=" * 70)
    print(f"Candidate tower sites: {_scalar(CandidateSiteCount)}")
    print(f"Demand zones: {_scalar(DemandZoneCount)}")
    print(f"Coverage pairs: {_scalar(CoveragePairCount)}")
    print(f"Build budget: ${build_budget:,.0f}")
    print(f"Max new towers: {_scalar(MaxNewTowers)}")

    status = model.select(SolveStatus).to_df().iloc[:, 0].tolist()
    print(f"\nSolve result:\n• status: {', '.join(status)}")
    if status not in (["OPTIMAL"], ["TIME_LIMIT"]):
        raise SystemExit(f"termination status {status}")
    covered_population = _scalar(CoveredPopulation)
    if covered_population is None:
        raise SystemExit(f"termination status {status}: the solve published no objective value")
    print(f"• objective: {round(covered_population, 9)}\n")

    # --------------------------------------------------
    # Evaluate and report
    # --------------------------------------------------

    selected_sites_df = (
        model.select(
            TowerSite.site_id.alias("site_id"),
            TowerSite.name.alias("name"),
            TowerSite.site_type.alias("site_type"),
            TowerSite.region.alias("region"),
            TowerSite.build_cost.alias("build_cost"),
            TowerSite.capacity.alias("capacity"),
        )
        .where(
            TowerSite.x_selected(selected),
            selected > 0.5,
        )
        .to_df()
        .sort_values(["region", "site_id"])
    )
    selected_sites_df["build_cost"] = pd.to_numeric(selected_sites_df["build_cost"])
    tower_load_df = model.select(
        TowerLoad.site_id.alias("site_id"),
        TowerLoad.assigned_population.alias("assigned_population"),
        TowerLoad.utilization.alias("utilization"),
    ).to_df()

    zone_solution_df = (
        model.select(
            DemandZone.zone_id.alias("zone_id"),
            DemandZone.name.alias("name"),
            DemandZone.region.alias("region"),
            DemandZone.population.alias("population"),
            covered.alias("covered"),
        )
        .where(DemandZone.y_covered(covered))
        .to_df()
    )
    zone_solution_df["covered"] = (
        pd.to_numeric(zone_solution_df["covered"]) > 0.5
    ).astype(int)
    zone_solution_df = zone_solution_df.sort_values(
        ["covered", "population"], ascending=[False, False]
    )

    zone_id, site_id, site_name = String.ref(), String.ref(), String.ref()
    assignment_df = (
        model.select(
            site_id.alias("assigned_site_id"),
            site_name.alias("assigned_site"),
            zone_id.alias("zone_id"),
        )
        .where(ZoneAssignment(zone_id, site_id, site_name))
        .to_df()
    )

    zone_solution_df = zone_solution_df.merge(assignment_df, on="zone_id", how="left")
    zone_solution_df["assigned_site_id"] = zone_solution_df["assigned_site_id"].fillna("")
    zone_solution_df["assigned_site"] = zone_solution_df["assigned_site"].fillna("")

    selected_sites_df = selected_sites_df.merge(tower_load_df, on="site_id", how="left")

    print("\n=== Selected Tower Sites ===")
    print(
        selected_sites_df[
            [
                "site_id",
                "name",
                "site_type",
                "region",
                "build_cost",
                "capacity",
                "assigned_population",
                "utilization",
            ]
        ].to_string(
            index=False,
            formatters={
                "build_cost": "${:,.0f}".format,
                "capacity": "{:,.0f}".format,
                "assigned_population": "{:,.0f}".format,
                "utilization": "{:.1%}".format,
            },
        )
    )

    print("\n=== Assigned Demand Zones ===")
    print(
        zone_solution_df[
            zone_solution_df["covered"] > 0.5
        ][
            ["zone_id", "name", "region", "population", "assigned_site"]
        ].to_string(
            index=False,
            formatters={"population": "{:,.0f}".format},
        )
    )

    uncovered_zones_df = zone_solution_df[zone_solution_df["covered"] <= 0.5]
    if not uncovered_zones_df.empty:
        print("\n=== Uncovered Demand Zones ===")
        print(
            uncovered_zones_df[
                ["zone_id", "name", "region", "population"]
            ].to_string(
                index=False,
                formatters={"population": "{:,.0f}".format},
            )
        )

    total_population = _scalar(TotalPopulation)
    print("\n=== Coverage Summary ===")
    print(f"Selected build cost: ${_scalar(SelectedBuildCost, 0):,.0f} of ${build_budget:,.0f}")
    print(f"Covered population: {covered_population:,.0f} of {total_population:,.0f}")
    print(f"Coverage rate: {_scalar(CoverageRate):.2%}")
    print(f"Uncovered population: {_scalar(UncoveredPopulation):,.0f}")

    coverage_solution_csv = DATA_DIR / "coverage_solution.csv"
    zone_solution_df[
        [
            "zone_id",
            "name",
            "region",
            "population",
            "covered",
            "assigned_site_id",
            "assigned_site",
        ]
    ].to_csv(coverage_solution_csv, index=False)
    print(f"\nWrote coverage solution to: {coverage_solution_csv}")
