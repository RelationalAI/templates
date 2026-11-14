"""Semantic schema for the cell tower coverage template: tower sites, demand zones, and coverage pairs."""

from relationalai.semantics import Float, Integer, Model, String

model = Model("cell_tower_coverage")

# TowerSite concept: candidate infrastructure locations with build cost.
TowerSite = model.Concept("TowerSite", identify_by={"site_id": String})
TowerSite.name = model.Property(f"{TowerSite} has name {String:name}")
TowerSite.site_type = model.Property(f"{TowerSite} has type {String:site_type}")
TowerSite.region = model.Property(f"{TowerSite} in region {String:region}")
TowerSite.build_cost = model.Property(f"{TowerSite} has build cost {Float:build_cost}")
TowerSite.capacity = model.Property(f"{TowerSite} has capacity {Integer:capacity}")

# DemandZone concept: population areas that may be covered by selected towers.
DemandZone = model.Concept("DemandZone", identify_by={"zone_id": String})
DemandZone.name = model.Property(f"{DemandZone} has name {String:name}")
DemandZone.region = model.Property(f"{DemandZone} in region {String:region}")
DemandZone.population = model.Property(f"{DemandZone} has population {Integer:population}")

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
