"""Coverage summary: the size of the inputs, the policy limits and plan totals, each tower's load and
utilization, the tower serving each covered zone, and the coverage rate and uncovered population."""

from relationalai.semantics import Float, Integer, String, count, sum
from relationalai.semantics.std import floats

from .schema import CoveragePair, DemandZone, TowerSite, model

# Declares the solution values the totals and loads read, and the covered population.
from .site_selection import CoveredPopulation, assigned, selected
from .source import BUILD_BUDGET, MAX_NEW_TOWERS

# The number of candidate sites, demand zones, and coverage pairs loaded.
CandidateSiteCount = model.Relationship(f"cell tower coverage has {Integer:sites} candidate sites")
DemandZoneCount = model.Relationship(f"cell tower coverage has {Integer:zones} demand zones")
CoveragePairCount = model.Relationship(f"cell tower coverage has {Integer:pairs} coverage pairs")
model.define(
    CandidateSiteCount(count(TowerSite)),
    DemandZoneCount(count(DemandZone)),
    CoveragePairCount(count(CoveragePair)),
)

# Policy limits and plan totals, which the deployed model publishes for the report.
BuildBudget = model.Relationship(f"cell tower coverage build budget is {Float:budget}")
MaxNewTowers = model.Relationship(f"cell tower coverage tower cap is {Integer:max_towers}")
TotalPopulation = model.Relationship(f"cell tower coverage total population is {Integer:population}")
SelectedBuildCost = model.Relationship(f"cell tower coverage selected build cost is {Float:cost}")
model.define(
    BuildBudget(float(BUILD_BUDGET)),
    MaxNewTowers(MAX_NEW_TOWERS),
    TotalPopulation(sum(DemandZone, DemandZone.population)),
    SelectedBuildCost(
        sum(TowerSite, TowerSite.build_cost).where(TowerSite.x_selected(selected), selected > 0.5)
    ),
)

# The share of the population the plan covers (zero when there is no population) and the
# population it leaves uncovered.
CoverageRate = model.Relationship(f"cell tower coverage rate is {Float:coverage_rate}")
UncoveredPopulation = model.Relationship(
    f"cell tower coverage uncovered population is {Float:uncovered_population}"
)
_population, _covered = Integer.ref(), Float.ref()
model.where(TotalPopulation(_population), CoveredPopulation(_covered), _population > 0).define(
    CoverageRate(_covered / floats.float(_population))
)
model.where(TotalPopulation(0)).define(CoverageRate(0.0))
model.where(TotalPopulation(_population), CoveredPopulation(_covered)).define(
    UncoveredPopulation(floats.float(_population) - _covered)
)

# Each tower's load: the population of the zones assigned to it (zero for a tower with none) and
# that load as a share of its capacity (zero for a tower without capacity). The values live on
# TowerLoad, not TowerSite: a property computed from the solution on a concept the solve reads
# leaves the solution empty after the first refresh.
TowerLoad = model.Concept("TowerLoad", identify_by={"site_id": String})
TowerLoad.assigned_population = model.Property(
    f"{TowerLoad} serves assigned population {Integer:assigned_population}"
)
TowerLoad.utilization = model.Property(f"{TowerLoad} has utilization {Float:utilization}")
model.define(TowerLoad.new(site_id=TowerSite.site_id))
model.define(
    TowerLoad.assigned_population(
        sum(CoveragePair, DemandZone.population)
        .per(TowerLoad)
        .where(
            CoveragePair.site_id == TowerLoad.site_id,
            CoveragePair.zone(DemandZone),
            CoveragePair.z_assigned(assigned),
            assigned > 0.5,
        )
        | 0
    )
)
model.where(TowerSite.site_id == TowerLoad.site_id, TowerSite.capacity > 0).define(
    TowerLoad.utilization(
        floats.float(TowerLoad.assigned_population) / floats.float(TowerSite.capacity)
    )
)
model.where(TowerSite.site_id == TowerLoad.site_id, TowerSite.capacity <= 0).define(
    TowerLoad.utilization(0.0)
)

# The tower each covered zone is assigned to.
ZoneAssignment = model.Relationship(
    f"cell tower coverage assigns zone {String:zone_id} to site {String:site_id} "
    f"named {String:site_name}"
)
model.where(CoveragePair.z_assigned(assigned), assigned > 0.5, CoveragePair.site(TowerSite)).define(
    ZoneAssignment(CoveragePair.zone_id, CoveragePair.site_id, TowerSite.name)
)
