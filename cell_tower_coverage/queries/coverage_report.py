"""Coverage report: reads the deployed cell_tower_coverage model.

Run `python -m queries.coverage_report` after `rai models deploy --path model`. Prints the
selected tower sites, assigned demand zones, tower utilization and coverage summary of the
latest refresh's solve, and writes data/coverage_solution.csv for downstream mapping or
reporting.
"""

import pandas as pd
from model import (
    BUILD_BUDGET,
    DATA_DIR,
    MAX_NEW_TOWERS,
    CoveragePair,
    CoveredPopulation,
    DemandZone,
    SolveStatus,
    TowerSite,
    assigned,
    covered,
    model,
    selected,
)

if __name__ == "__main__":
    # Entity counts and total population come from the deployed model.
    sites_df = model.select(TowerSite.site_id).to_df()
    zones_df = model.select(DemandZone.zone_id, DemandZone.population).to_df()
    pairs_df = model.select(CoveragePair.site_id, CoveragePair.zone_id).to_df()

    print("=" * 70)
    print("CELL TOWER COVERAGE")
    print("=" * 70)
    print(f"Candidate tower sites: {len(sites_df)}")
    print(f"Demand zones: {len(zones_df)}")
    print(f"Coverage pairs: {len(pairs_df)}")
    print(f"Build budget: ${BUILD_BUDGET:,.0f}")
    print(f"Max new towers: {MAX_NEW_TOWERS}")

    # Status and objective of the latest refresh's solve. A refresh records any
    # termination status, so the report checks it.
    status = model.select(SolveStatus).to_df().iloc[:, 0].tolist()
    objective = model.select(CoveredPopulation).to_df().iloc[:, 0].tolist()
    if status not in (["OPTIMAL"], ["TIME_LIMIT"]):
        raise SystemExit(f"Solver did not find an optimal solution: {status}")

    print(f"\nStatus: {status[0]}")
    print(f"Objective: covered population = {objective[0]:,.0f}")

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
            selected.alias("selected"),
        )
        .where(
            TowerSite.x_selected(selected),
            selected > 0.5,
        )
        .to_df()
        .sort_values(["region", "site_id"])
    )
    selected_sites_df["build_cost"] = pd.to_numeric(selected_sites_df["build_cost"])
    selected_sites_df["capacity"] = pd.to_numeric(selected_sites_df["capacity"])
    selected_sites_df["selected"] = (
        pd.to_numeric(selected_sites_df["selected"]) > 0.5
    ).astype(int)

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
        .sort_values(["covered", "population"], ascending=[False, False])
    )
    zone_solution_df["population"] = pd.to_numeric(zone_solution_df["population"])
    zone_solution_df["covered"] = (
        pd.to_numeric(zone_solution_df["covered"]) > 0.5
    ).astype(int)

    assignment_df = (
        model.select(
            CoveragePair.site_id.alias("assigned_site_id"),
            TowerSite.name.alias("assigned_site"),
            CoveragePair.zone_id.alias("zone_id"),
            assigned.alias("assigned"),
        )
        .where(
            CoveragePair.z_assigned(assigned),
            CoveragePair.site(TowerSite),
            assigned > 0.5,
        )
        .to_df()
        .sort_values(["assigned_site_id", "zone_id"])
    )
    assignment_df["assigned"] = (
        pd.to_numeric(assignment_df["assigned"]) > 0.5
    ).astype(int)

    zone_solution_df = zone_solution_df.merge(
        assignment_df[["zone_id", "assigned_site_id", "assigned_site"]],
        on="zone_id",
        how="left",
    )
    zone_solution_df["assigned_site_id"] = zone_solution_df["assigned_site_id"].fillna("")
    zone_solution_df["assigned_site"] = zone_solution_df["assigned_site"].fillna("")

    total_population = pd.to_numeric(zones_df["population"]).sum()
    covered_population = zone_solution_df.loc[
        zone_solution_df["covered"] > 0.5, "population"
    ].sum()
    uncovered_population = total_population - covered_population
    selected_cost = selected_sites_df["build_cost"].sum()

    tower_load_df = (
        zone_solution_df[
            zone_solution_df["covered"] > 0.5
        ]
        .groupby("assigned_site_id", as_index=False)["population"]
        .sum()
        .rename(columns={"population": "assigned_population"})
    )
    selected_sites_df = selected_sites_df.merge(
        tower_load_df,
        left_on="site_id",
        right_on="assigned_site_id",
        how="left",
    ).drop(columns=["assigned_site_id"])
    selected_sites_df["assigned_population"] = (
        selected_sites_df["assigned_population"].fillna(0).astype(int)
    )
    selected_sites_df["utilization"] = (
        selected_sites_df["assigned_population"] / selected_sites_df["capacity"]
    )

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

    print("\n=== Coverage Summary ===")
    print(f"Selected build cost: ${selected_cost:,.0f} of ${BUILD_BUDGET:,.0f}")
    print(f"Covered population: {covered_population:,.0f} of {total_population:,.0f}")
    print(f"Coverage rate: {covered_population / total_population:.2%}")
    print(f"Uncovered population: {uncovered_population:,.0f}")

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
