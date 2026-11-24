"""Reasoning for the energy grid template: forecast, topology, corridors, compliance, and investment."""

from relationalai.semantics import Float, Hash, Integer, String, not_, sum, where
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std.math import maximum

from .schema import (
    DataCenterRequest,
    DCSubstation,
    DemandForecast,
    Generator,
    GeneratorSubstation,
    InvestmentLevel,
    InvestmentPortfolio,
    Substation,
    SubstationUpgrade,
    TransmissionLine,
    model,
)

AMORTIZATION_YEARS = 20  # upgrade cost spread over 20 years
CRITICAL_THRESHOLD = 3  # top-N substations by combined centrality rank are "structurally critical"
MAX_CORRIDOR_HOPS = 6

# --------------------------------------------------
# Stage 1: Forecast -- Substation Load
# --------------------------------------------------
# Enrich each Substation with a predicted_load property consumed by downstream
# stages: the maximum DemandForecast per substation.
Substation.predicted_load = model.Property(f"{Substation} has {Float:predicted_load}")
model.define(
    Substation.predicted_load(
        aggs.max(DemandForecast.predicted_load_mw)
        .where(DemandForecast.substation(Substation))
        .per(Substation)
    )
)

# Growth of the predicted peak over the current load (floored at 0.1 MW, so an idle
# substation still gets a growth figure), and the first forecast month whose
# predicted load exceeds the substation's capacity.
Substation.growth_rate = model.Property(f"{Substation} has load growth {Float:growth_rate}")
model.define(
    Substation.growth_rate(
        (Substation.predicted_load - Substation.current_load_mw)
        / maximum(Substation.current_load_mw, 0.1)
    )
)
Substation.breach_period = model.Property(
    f"{Substation} first exceeds capacity at {Integer:breach_period} months"
)
model.define(
    Substation.breach_period(
        aggs.min(DemandForecast.forecast_period)
        .where(
            DemandForecast.substation(Substation),
            DemandForecast.predicted_load_mw > Substation.max_capacity_mw,
        )
        .per(Substation)
    )
)

# --------------------------------------------------
# Stage 2: Graph -- Grid Topology & Structural Vulnerability
# --------------------------------------------------

grid_graph = Graph(
    model,
    name="grid_graph",
    directed=False,
    weighted=False,
    node_concept=Substation,
    aggregator="sum",
)

# Edges: active transmission lines between substations.
line_ref = TransmissionLine.ref()
model.define(grid_graph.Edge.new(src=line_ref.from_substation, dst=line_ref.to_substation)).where(
    line_ref.is_active == True
)

# a) Weakly Connected Components
wcc = grid_graph.weakly_connected_component()
Substation.component = model.Property(f"{Substation} in component {String:component}")
wcc_node, wcc_comp = Substation.ref(), Substation.ref()
model.define(wcc_node.component(wcc_comp.id)).where(wcc(wcc_node, wcc_comp))

# b) Community Detection (Louvain)
community = grid_graph.louvain()
comm_label = Integer.ref("comm")

# c) Centrality Analysis (betweenness, degree, eigenvector)
betweenness = grid_graph.betweenness_centrality()
btwn_score = Float.ref("btwn")

degree = grid_graph.degree_centrality()
deg_score = Float.ref("deg")

eigenvector = grid_graph.eigenvector_centrality()
eig_score = Float.ref("eig")

# Store graph results directly on Substation.
Substation.grid_community = model.Property(
    f"{Substation} in grid community {Integer:grid_community}"
)
Substation.betweenness = model.Property(f"{Substation} has {Float:betweenness}")
Substation.degree_centrality = model.Property(f"{Substation} has {Float:degree_centrality}")
Substation.eigenvector_centrality = model.Property(
    f"{Substation} has {Float:eigenvector_centrality}"
)

sub_ref = Substation.ref()
model.define(sub_ref.grid_community(comm_label)).where(community(sub_ref, comm_label))
model.define(sub_ref.betweenness(btwn_score)).where(betweenness(sub_ref, btwn_score))
model.define(sub_ref.degree_centrality(deg_score)).where(degree(sub_ref, deg_score))
model.define(sub_ref.eigenvector_centrality(eig_score)).where(eigenvector(sub_ref, eig_score))

# Composite critical rank from all three centrality metrics.
Substation.betweenness_rank = model.Property(f"{Substation} has {Integer:betweenness_rank}")
Substation.degree_rank = model.Property(f"{Substation} has {Integer:degree_rank}")
Substation.eigenvector_rank = model.Property(f"{Substation} has {Integer:eigenvector_rank}")
Substation.combined_rank = model.Property(f"{Substation} has {Integer:combined_rank}")
Substation.critical_rank = model.Property(f"{Substation} has {Integer:critical_rank}")

model.define(
    Substation.betweenness_rank(aggs.rank(aggs.desc(Substation.betweenness, Substation.id)))
)
model.define(
    Substation.degree_rank(aggs.rank(aggs.desc(Substation.degree_centrality, Substation.id)))
)
model.define(
    Substation.eigenvector_rank(
        aggs.rank(aggs.desc(Substation.eigenvector_centrality, Substation.id))
    )
)
model.define(
    Substation.combined_rank(
        Substation.betweenness_rank + Substation.degree_rank + Substation.eigenvector_rank
    )
)
model.define(Substation.critical_rank(aggs.rank(Substation.combined_rank, Substation.id)))

Substation.is_structurally_critical = model.Relationship(f"{Substation} is structurally critical")
model.where(Substation.critical_rank <= CRITICAL_THRESHOLD).define(
    Substation.is_structurally_critical()
)

# --------------------------------------------------
# Stage 3: Paths -- Transmission Corridors & Contingency
#   PREVIEW capability; requires relationalai>=1.15.
# --------------------------------------------------
# Composes on Stage 2's Substation.betweenness. Where Stage 2 scores a *node*,
# paths scores the *corridor* feeding each data center: enumerate generator-sub ->
# DC-sub transmission routes, rank each by total betweenness summed along its hops
# (most fragile = greatest through-traffic exposure), then re-enumerate with the
# highest-betweenness substation offline to see which DC substations reroute.

# Bidirectional Substation<->Substation grid edge from active transmission lines.
Substation.connects_to = model.Relationship(
    f"{Substation} connects to {Substation}", short_name="connects_to"
)
tl_fwd = TransmissionLine.ref()
s_from, s_to = Substation.ref(), Substation.ref()
model.where(
    tl_fwd.from_substation(s_from),
    tl_fwd.to_substation(s_to),
    tl_fwd.is_active == True,
).define(s_from.connects_to(s_to))
tl_rev = TransmissionLine.ref()
s_a, s_b = Substation.ref(), Substation.ref()
model.where(
    tl_rev.from_substation(s_a),
    tl_rev.to_substation(s_b),
    tl_rev.is_active == True,
).define(s_b.connects_to(s_a))

# Typed endpoints: substations hosting a generator (source) and a DC request (sink).
gen_ref, gen_sub = Generator.ref(), Substation.ref()
model.where(gen_ref.substation(gen_sub)).define(GeneratorSubstation(gen_sub))
dc_ref, dc_sub = DataCenterRequest.ref(), Substation.ref()
model.where(dc_ref.substation(dc_sub)).define(DCSubstation(dc_sub))

# Enumerate generator-sub -> DC-sub corridors (finite repeat; the grid is meshed/cyclic).
corridor_src, corridor_dst = GeneratorSubstation.ref(), DCSubstation.ref()
corridor = (
    model.path(
        corridor_src, Substation.connects_to.repeat(1, MAX_CORRIDOR_HOPS), corridor_dst
    )
    .all()
    .paths()
)

# Each corridor's substations in hop order, which the deployed model publishes for the queries.
CorridorStep = model.Relationship(
    f"corridor {Hash:corridor} has {Substation:substation} at hop {Integer:hop}"
)
model.where(corridor).define(
    CorridorStep(corridor, Substation(corridor.nodes), corridor.nodes["index"])
)

# Each DC substation's fragility load is the highest corridor score among the simple
# corridors ending at it, where a corridor's score sums Stage 2's betweenness over its
# nodes. The grid is cyclic, so .all().paths() also yields walks that revisit a node;
# not_(where(i < j, p.nodes(i) == p.nodes(j))) drops them in the same where() as the sum,
# so on every corridor that remains the position sum equals the distinct-substation sum.
i, j = Integer.ref(), Integer.ref()
Substation.fragility_load = model.Property(f"{Substation} has {Float:fragility_load}")
model.where(
    corridor,
    not_(where(i < j, corridor.nodes(i) == corridor.nodes(j))),  # simple corridors only
    total := aggs.sum(Substation(corridor.nodes).betweenness).per(corridor),
    frag := aggs.max(total).per(corridor_dst),
).define(corridor_dst.fragility_load(frag))

# --------------------------------------------------
# Stage 4: Rules -- Interconnection Queue Compliance
# --------------------------------------------------
# Accretive chain: each rule consumes ontology enrichments from earlier stages.
# Rule 1 reads Substation.predicted_load (Stage 1).
# Rule 2 reads Substation.is_structurally_critical (Stage 2).
# Rule 3 reads Generator.emissions_rate (base data) to derive low-carbon capacity.
# All flags are written back as Relationships — queryable and consumable downstream.

# Rule 1: Capacity check -- consumes predicted_load from Stage 1
DataCenterRequest.fails_capacity = model.Relationship(f"{DataCenterRequest} fails capacity check")
SubRef_rule = Substation.ref()
effective_load_rule = SubRef_rule.predicted_load | SubRef_rule.current_load_mw
model.where(
    DataCenterRequest.substation(SubRef_rule),
    DataCenterRequest.requested_mw + effective_load_rule > SubRef_rule.max_capacity_mw,
).define(DataCenterRequest.fails_capacity())

# Rule 2: Structural risk -- uses centrality-based criticality from Stage 2
DataCenterRequest.fails_structural = model.Relationship(f"{DataCenterRequest} fails structural risk check")
SubRef_sr = Substation.ref()
model.where(
    DataCenterRequest.substation(SubRef_sr),
    SubRef_sr.is_structurally_critical(),
).define(DataCenterRequest.fails_structural())

# Rule 3: Low-carbon mandate -- check if DC's low-carbon requirement can be met
# Low-carbon = zero-emission generation (renewable + nuclear), keyed on emissions_rate == 0.
# The requirement is a fraction of the substation's generation (0.60 means 60%).
Substation.low_carbon_gen_mw = model.Property(f"{Substation} has {Float:low_carbon_gen_mw}")
Substation.total_gen_mw = model.Property(f"{Substation} has {Float:total_gen_mw}")
model.define(
    Substation.low_carbon_gen_mw(
        aggs.sum(Generator.capacity_mw)
        .where(Generator.substation(Substation), Generator.emissions_rate == 0.0)
        .per(Substation)
    )
)
model.define(
    Substation.total_gen_mw(
        aggs.sum(Generator.capacity_mw)
        .where(Generator.substation(Substation))
        .per(Substation)
    )
)

DataCenterRequest.fails_low_carbon = model.Relationship(f"{DataCenterRequest} fails low-carbon mandate")
SubRef_lc = Substation.ref()
model.where(
    DataCenterRequest.substation(SubRef_lc),
    (SubRef_lc.low_carbon_gen_mw | 0.0)
    < DataCenterRequest.low_carbon_requirement_pct * SubRef_lc.total_gen_mw,
).define(DataCenterRequest.fails_low_carbon())
# A substation without generating capacity cannot meet any positive requirement.
model.where(
    DataCenterRequest.substation(SubRef_lc),
    DataCenterRequest.low_carbon_requirement_pct > 0,
    not_(SubRef_lc.total_gen_mw > 0),
).define(DataCenterRequest.fails_low_carbon())

# Composite: compliant if none of the checks fail
DataCenterRequest.is_compliant = model.Relationship(f"{DataCenterRequest} is compliant")
model.where(
    model.not_(DataCenterRequest.fails_capacity()),
    model.not_(DataCenterRequest.fails_structural()),
    model.not_(DataCenterRequest.fails_low_carbon()),
).define(DataCenterRequest.is_compliant())

# --------------------------------------------------
# Stage 5: Optimize -- Joint DC Approval + Grid Upgrade
#   Accretive chain: the capacity constraint uses predicted_load from Stage 1
#   (via the | fallback pattern), matching the rules engine. All solve results
#   (x_approve, x_upgrade per InvestmentLevel) are written to the ontology —
#   queryable via model.select(), not parsed from solver output.
#   One solve across 5 InvestmentLevel scenarios produces the Pareto frontier.
# --------------------------------------------------

# Decision variables indexed by InvestmentLevel
DataCenterRequest.x_approve = model.Property(
    f"{DataCenterRequest} in {InvestmentLevel} has {Float:x_approve}"
)
SubstationUpgrade.x_upgrade = model.Property(
    f"{SubstationUpgrade} in {InvestmentLevel} has {Float:x_upgrade}"
)

# Float refs for variable binding in constraints/objective
x_a = Float.ref("xa")
x_u = Float.ref("xu")

# Refs for aggregation joins
DCRef = DataCenterRequest.ref()
UpgRef = SubstationUpgrade.ref()

# Problem formulation
problem = Problem(model, Float, name="energy_grid_planning")

problem.solve_for(DataCenterRequest.x_approve(InvestmentLevel, x_a), type="bin",
            name=["approve", InvestmentLevel.name, DataCenterRequest.id])
problem.solve_for(SubstationUpgrade.x_upgrade(InvestmentLevel, x_u), type="bin",
            name=["upgrade", InvestmentLevel.name, SubstationUpgrade.id])

# C1: Substation capacity per investment level
# Uses predicted_load from Stage 1 (with current_load fallback) — the accretive chain.
x_a_c = Float.ref("xa_c")
x_u_c = Float.ref("xu_c")
effective_load = Substation.predicted_load | Substation.current_load_mw

# Each upgrade's capacity and each request's MW is weighted by its own variable.
# A substation with no upgrade options adds no capacity (`| 0.0`).
problem.satisfy(
    model.where(
        InvestmentLevel,
        DataCenterRequest.substation(Substation),
    ).require(
        Substation.max_capacity_mw
        - effective_load
        + (
            sum(UpgRef, x_u_c * UpgRef.capacity_increase_mw)
            .where(
                UpgRef.substation == Substation,
                UpgRef.x_upgrade(InvestmentLevel, x_u_c),
            )
            .per(Substation, InvestmentLevel)
            | 0.0
        )
        >= sum(DCRef, x_a_c * DCRef.requested_mw)
        .where(
            DCRef.substation == Substation,
            DCRef.x_approve(InvestmentLevel, x_a_c),
        )
        .per(Substation, InvestmentLevel)
    )
)

# C2: Budget per investment level
problem.satisfy(model.where(
    SubstationUpgrade.x_upgrade(InvestmentLevel, x_u),
).require(
    sum(x_u * SubstationUpgrade.cost_million).per(InvestmentLevel) <= InvestmentLevel.budget_cap
))

# Objective: maximize total DC revenue across all levels
problem.maximize(
    sum(InvestmentLevel, x_a * DataCenterRequest.annual_revenue_per_mw * DataCenterRequest.requested_mw).where(
        DataCenterRequest.x_approve(InvestmentLevel, x_a)
    )
)

# Each refresh of the deployed model runs this solve (one solve for all levels).
problem.configure("highs", time_limit_sec=120)

# The solve's status and objective, which the deployed model publishes for the queries.
SolveStatus = model.Relationship(f"energy grid solve status is {String:status}")
SolveObjective = model.Relationship(f"energy grid solve objective is {Float:objective}")
model.define(SolveStatus(problem.termination_status()), SolveObjective(problem.objective_value()))

# --------------------------------------------------
# Portfolio per InvestmentLevel, from the solved values
# --------------------------------------------------
# One InvestmentPortfolio row per scenario: approved requests, their MW and
# revenue, the selected upgrades' cost (in dollars, to match revenue), and the
# net value (revenue less the upgrade cost amortized over AMORTIZATION_YEARS).
x_ap, x_up = Float.ref(), Float.ref()
model.define(
    portfolio := InvestmentPortfolio.new(investment_level_name=InvestmentLevel.name),
    portfolio.investment_level(InvestmentLevel),
)
model.define(
    InvestmentPortfolio.dc_count(
        (
            aggs.count(DataCenterRequest)
            .where(
                InvestmentPortfolio.investment_level(InvestmentLevel),
                DataCenterRequest.x_approve(InvestmentLevel, x_ap),
                x_ap > 0.5,
            )
            .per(InvestmentPortfolio)
        )
        | 0
    )
)
model.define(
    InvestmentPortfolio.total_mw(
        (
            sum(DataCenterRequest, DataCenterRequest.requested_mw)
            .where(
                InvestmentPortfolio.investment_level(InvestmentLevel),
                DataCenterRequest.x_approve(InvestmentLevel, x_ap),
                x_ap > 0.5,
            )
            .per(InvestmentPortfolio)
        )
        | 0.0
    )
)
model.define(
    InvestmentPortfolio.annual_revenue(
        (
            sum(DataCenterRequest, DataCenterRequest.requested_mw * DataCenterRequest.annual_revenue_per_mw)
            .where(
                InvestmentPortfolio.investment_level(InvestmentLevel),
                DataCenterRequest.x_approve(InvestmentLevel, x_ap),
                x_ap > 0.5,
            )
            .per(InvestmentPortfolio)
        )
        | 0.0
    )
)
model.define(
    InvestmentPortfolio.upgrade_cost(
        (
            sum(SubstationUpgrade, SubstationUpgrade.cost_million * 1e6)
            .where(
                InvestmentPortfolio.investment_level(InvestmentLevel),
                SubstationUpgrade.x_upgrade(InvestmentLevel, x_up),
                x_up > 0.5,
            )
            .per(InvestmentPortfolio)
        )
        | 0.0
    )
)
model.define(
    InvestmentPortfolio.upgrade_count(
        (
            aggs.count(SubstationUpgrade)
            .where(
                InvestmentPortfolio.investment_level(InvestmentLevel),
                SubstationUpgrade.x_upgrade(InvestmentLevel, x_up),
                x_up > 0.5,
            )
            .per(InvestmentPortfolio)
        )
        | 0
    )
)
model.define(
    InvestmentPortfolio.upgrade_mw(
        (
            sum(SubstationUpgrade, SubstationUpgrade.capacity_increase_mw)
            .where(
                InvestmentPortfolio.investment_level(InvestmentLevel),
                SubstationUpgrade.x_upgrade(InvestmentLevel, x_up),
                x_up > 0.5,
            )
            .per(InvestmentPortfolio)
        )
        | 0.0
    )
)
model.define(
    InvestmentPortfolio.net_value(
        InvestmentPortfolio.annual_revenue - InvestmentPortfolio.upgrade_cost / AMORTIZATION_YEARS
    )
)

# Marginal value of each budget step: net value gained per added $M from a level
# to the next larger budget. The largest level has no next step.
higher, step_from, step_to = InvestmentLevel.ref(), InvestmentLevel.ref(), InvestmentLevel.ref()
model.define(InvestmentLevel.next_level(step_to)).where(
    step_to.budget_cap
    == aggs.min(higher.budget_cap).where(higher.budget_cap > InvestmentLevel.budget_cap).per(InvestmentLevel)
)
next_portfolio = InvestmentPortfolio.ref()
model.define(
    InvestmentPortfolio.marginal_per_m_to_next_level(
        (next_portfolio.net_value - InvestmentPortfolio.net_value) / (step_to.budget_cap - step_from.budget_cap)
    )
).where(
    InvestmentPortfolio.investment_level(step_from),
    step_from.next_level(step_to),
    next_portfolio.investment_level(step_to),
)

# The knee is the level where the marginal value falls the most, from the step
# into it to the step out of it; on a tie, the smaller budget. A frontier whose
# marginal value never falls has no knee.
prev_portfolio = InvestmentPortfolio.ref()
model.define(
    InvestmentPortfolio.marginal_drop(
        prev_portfolio.marginal_per_m_to_next_level - InvestmentPortfolio.marginal_per_m_to_next_level
    )
).where(
    prev_portfolio.investment_level(step_from),
    step_from.next_level(step_to),
    InvestmentPortfolio.investment_level(step_to),
)
model.define(InvestmentPortfolio.is_knee_point()).where(
    InvestmentPortfolio.investment_level(step_to),
    InvestmentPortfolio.marginal_drop > 0,
    aggs.rank(aggs.desc(InvestmentPortfolio.marginal_drop), step_to.budget_cap) == 1,
)
