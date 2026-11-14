"""Cell tower coverage (prescriptive optimization) template: the model.

This package demonstrates maximum coverage planning in RelationalAI:

- Load sample demand zones, candidate tower sites, and tower-zone coverage pairs.
- Choose tower sites to build under a fixed capital budget and tower-count limit.
- Assign each covered demand zone to one selected tower that can serve it.
- Enforce tower capacity limits on assigned population.
- Maximize total covered population.
- Report selected sites, assigned demand zones, tower utilization, and uncovered
  population.

The optimization is modeled as a mixed-integer linear problem.

Run:
    `rai models deploy --path model` deploys this model to the schema in
    raiconfig.yaml and waits for its first refresh, which runs the solve.
    `python -m queries.coverage_report` then prints the report from the deployed model.
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

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

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
        sum(TowerSite, selected) <= MAX_NEW_TOWERS
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
        sum(CoveragePair, assigned).per(DemandZone) == covered
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
        sum(CoveragePair, DemandZone.population * assigned).per(TowerSite)
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

# Each refresh of the deployed model runs this solve.
problem.configure("highs", time_limit_sec=60)

# The solve's status and objective, published through the model's own relationships.
SolveStatus = model.Relationship(f"cell tower coverage solve status is {String:status}")
CoveredPopulation = model.Relationship(
    f"cell tower coverage covered population is {Float:covered_population}"
)
model.define(SolveStatus(problem.termination_status()), CoveredPopulation(problem.objective_value()))
