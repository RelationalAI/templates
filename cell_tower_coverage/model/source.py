"""Load the sample tower sites, demand zones, and coverage pairs, and check the inputs."""

from pathlib import Path

import pandas as pd

from .schema import CoveragePair, DemandZone, TowerSite, model

# --------------------------------------------------
# Configure coverage policy
# --------------------------------------------------

BUILD_BUDGET = 650_000
MAX_NEW_TOWERS = 3

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# --------------------------------------------------
# Load data
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

model.define(TowerSite.new(model.data(tower_sites_csv).to_schema()))
model.define(DemandZone.new(model.data(demand_zones_csv).to_schema()))
model.define(CoveragePair.new(model.data(coverage_pairs_csv).to_schema()))
model.define(CoveragePair.site(TowerSite)).where(
    CoveragePair.site_id == TowerSite.site_id
)
model.define(CoveragePair.zone(DemandZone)).where(
    CoveragePair.zone_id == DemandZone.zone_id
)
