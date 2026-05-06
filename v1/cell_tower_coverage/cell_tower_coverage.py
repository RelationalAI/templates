"""Cell tower coverage (prescriptive optimization) template.

This script demonstrates maximum coverage planning in RelationalAI:

- Load sample demand zones, candidate tower sites, and tower-zone coverage pairs.
- Choose tower sites to build under a fixed capital budget and tower-count limit.
- Assign each covered demand zone to one selected tower that can serve it.
- Enforce tower capacity limits on assigned population.
- Maximize total covered population.
- Report selected sites, assigned demand zones, tower utilization, and uncovered
  population.

The optimization is modeled as a mixed-integer linear problem.

Run:
    python cell_tower_coverage.py

Output:
    Prints the selected tower sites, assigned demand zones, tower utilization,
    coverage summary, and writes data/coverage_solution.csv for downstream
    mapping or reporting.
"""

from pathlib import Path

import pandas as pd
from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

# --------------------------------------------------
# Configure coverage policy
# --------------------------------------------------

BUILD_BUDGET = 650_000
MAX_NEW_TOWERS = 3

DATA_DIR = Path(__file__).parent / "data"

# --------------------------------------------------
# Define semantic model and load data
# --------------------------------------------------

# Load candidate sites, demand zones, and feasible coverage pairs.
tower_sites_csv = pd.read_csv(DATA_DIR / "tower_sites.csv")
demand_zones_csv = pd.read_csv(DATA_DIR / "demand_zones.csv")
coverage_pairs_csv = pd.read_csv(DATA_DIR / "coverage_pairs.csv")

# Basic feasibility checks before building and solving the optimization model.
if tower_sites_csv.empty:
    raise ValueError("tower_sites.csv must contain at least one candidate tower site.")
if demand_zones_csv.empty:
    raise ValueError("demand_zones.csv must contain at least one demand zone.")
if coverage_pairs_csv.empty:
    raise ValueError("coverage_pairs.csv must contain at least one coverage pair.")
if MAX_NEW_TOWERS <= 0:
    raise ValueError("MAX_NEW_TOWERS must be positive.")
if BUILD_BUDGET <= 0:
    raise ValueError("BUILD_BUDGET must be positive.")

missing_site_ids = set(coverage_pairs_csv["site_id"]) - set(tower_sites_csv["site_id"])
if missing_site_ids:
    raise ValueError(f"coverage_pairs.csv references unknown site IDs: {sorted(missing_site_ids)}")

missing_zone_ids = set(coverage_pairs_csv["zone_id"]) - set(demand_zones_csv["zone_id"])
if missing_zone_ids:
    raise ValueError(f"coverage_pairs.csv references unknown zone IDs: {sorted(missing_zone_ids)}")

unreachable_zone_ids = set(demand_zones_csv["zone_id"]) - set(coverage_pairs_csv["zone_id"])
if unreachable_zone_ids:
    raise ValueError(
        "Every demand zone should have at least one feasible covering site. "
        f"Unreachable zones: {sorted(unreachable_zone_ids)}"
    )

model = Model("cell_tower_coverage")

# TowerSite concept: candidate infrastructure locations with build cost.
TowerSite = model.Concept("TowerSite", identify_by={"site_id": String})
TowerSite.name = model.Property(f"{TowerSite} has name {String:name}")
TowerSite.site_type = model.Property(f"{TowerSite} has type {String:site_type}")
TowerSite.region = model.Property(f"{TowerSite} in region {String:region}")
TowerSite.build_cost = model.Property(f"{TowerSite} has build cost {Float:build_cost}")
TowerSite.capacity = model.Property(f"{TowerSite} has capacity {Integer:capacity}")
model.define(TowerSite.new(model.data(tower_sites_csv).to_schema()))

# DemandZone concept: population areas that may be covered by selected towers.
DemandZone = model.Concept("DemandZone", identify_by={"zone_id": String})
DemandZone.name = model.Property(f"{DemandZone} has name {String:name}")
DemandZone.region = model.Property(f"{DemandZone} in region {String:region}")
DemandZone.population = model.Property(f"{DemandZone} has population {Integer:population}")
model.define(DemandZone.new(model.data(demand_zones_csv).to_schema()))

# CoveragePair concept: feasible tower-zone service relationships.
CoveragePair = model.Concept(
    "CoveragePair",
    identify_by={"site_id": String, "zone_id": String},
)
CoveragePair.distance_km = model.Property(
    f"{CoveragePair} has distance km {Float:distance_km}"
)
CoveragePair.signal_score = model.Property(
    f"{CoveragePair} has signal score {Float:signal_score}"
)
CoveragePair.site = model.Relationship(f"{CoveragePair} uses {TowerSite}")
CoveragePair.zone = model.Relationship(f"{CoveragePair} covers {DemandZone}")
model.define(CoveragePair.new(model.data(coverage_pairs_csv).to_schema()))
model.define(CoveragePair.site(TowerSite)).where(
    CoveragePair.site_id == TowerSite.site_id
)
model.define(CoveragePair.zone(DemandZone)).where(
    CoveragePair.zone_id == DemandZone.zone_id
)

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

TowerSite.x_selected = model.Property(f"{TowerSite} selected if {Float:selected}")
DemandZone.y_covered = model.Property(f"{DemandZone} covered if {Float:covered}")
CoveragePair.z_assigned = model.Property(f"{CoveragePair} assigned if {Float:assigned}")

selected = Float.ref("selected")
covered = Float.ref("covered")
assigned = Float.ref("assigned")

problem = Problem(model, Float)

problem.solve_for(
    TowerSite.x_selected(selected),
    type="bin",
    name=["selected", TowerSite.site_id],
)
problem.solve_for(
    DemandZone.y_covered(covered),
    type="bin",
    name=["covered", DemandZone.zone_id],
)
problem.solve_for(
    CoveragePair.z_assigned(assigned),
    type="bin",
    name=["assigned", CoveragePair.site_id, CoveragePair.zone_id],
)

# Select only as many towers as the plan allows.
problem.satisfy(
    model.where(TowerSite.x_selected(selected)).require(
        sum(selected) <= MAX_NEW_TOWERS
    )
)

# Stay within the capital budget.
problem.satisfy(
    model.where(TowerSite.x_selected(selected)).require(
        sum(TowerSite.build_cost * selected) <= BUILD_BUDGET
    )
)

# A demand zone can count as covered only when it is assigned to exactly one
# selected tower that can serve it. Assignment variables exist only on feasible
# coverage pairs, so the coverage-pair table defines the allowed service links.
problem.satisfy(
    model.where(
        DemandZone.y_covered(covered),
        CoveragePair.zone(DemandZone),
        CoveragePair.z_assigned(assigned),
    ).require(
        sum(assigned).per(DemandZone) == covered
    )
)

# A zone can only be assigned to a tower that is selected.
problem.satisfy(
    model.where(
        CoveragePair.site(TowerSite),
        CoveragePair.z_assigned(assigned),
        TowerSite.x_selected(selected),
    ).require(
        assigned <= selected
    )
)

# Each selected tower can serve assigned demand up to its population capacity.
problem.satisfy(
    model.where(
        CoveragePair.site(TowerSite),
        CoveragePair.zone(DemandZone),
        CoveragePair.z_assigned(assigned),
        TowerSite.x_selected(selected),
    ).require(
        sum(DemandZone.population * assigned).per(TowerSite)
        <= TowerSite.capacity * selected
    )
)

# Maximize covered population.
problem.maximize(
    sum(DemandZone.population * covered).where(DemandZone.y_covered(covered))
)

# --------------------------------------------------
# Solve
# --------------------------------------------------

print("=" * 70)
print("CELL TOWER COVERAGE")
print("=" * 70)
print(f"Candidate tower sites: {len(tower_sites_csv)}")
print(f"Demand zones: {len(demand_zones_csv)}")
print(f"Coverage pairs: {len(coverage_pairs_csv)}")
print(f"Build budget: ${BUILD_BUDGET:,.0f}")
print(f"Max new towers: {MAX_NEW_TOWERS}")

# Uncomment to print the formulated problem for debugging.
# problem.display()
problem.solve("highs", time_limit_sec=60)
si = problem.solve_info()
si.display()
assert si.termination_status == "OPTIMAL" or si.termination_status == "TIME_LIMIT", "Solver did not find an optimal solution."

print(f"\nStatus: {si.termination_status}")
print(f"Objective: covered population = {si.objective_value:,.0f}")

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

total_population = demand_zones_csv["population"].sum()
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
