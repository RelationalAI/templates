"""Cell tower coverage decision problem: choose sites and assign demand zones to maximize covered population."""

from relationalai.semantics import Float, Integer, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

from .schema import CoveragePair, DemandZone, TowerSite, model
from .source import BUILD_BUDGET, MAX_NEW_TOWERS

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

TowerSite.x_selected = model.Property(f"{TowerSite} selected if {Float:selected}")
DemandZone.y_covered = model.Property(f"{DemandZone} covered if {Float:covered}")
CoveragePair.z_assigned = model.Property(f"{CoveragePair} assigned if {Float:assigned}")

selected = Float.ref("selected")
covered = Float.ref("covered")
assigned = Float.ref("assigned")

problem = Problem(model, Float, name="cell_tower_coverage")

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

# The solve's status and objective, which the deployed model publishes for the queries.
SolveStatus = model.Relationship(f"cell tower coverage solve status is {String:status}")
CoveredPopulation = model.Relationship(
    f"cell tower coverage covered population is {Float:covered_population}"
)
model.define(SolveStatus(problem.termination_status()), CoveredPopulation(problem.objective_value()))

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

# Population each tower serves through its assigned zones. It lives on TowerLoad, not TowerSite:
# a property computed from the solution on a concept the solve reads fails the deploy.
TowerLoad = model.Concept("TowerLoad", identify_by={"site_id": String})
TowerLoad.assigned_population = model.Property(
    f"{TowerLoad} serves assigned population {Integer:assigned_population}"
)
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
    )
)
