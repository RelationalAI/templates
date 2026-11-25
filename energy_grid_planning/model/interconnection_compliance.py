"""Interconnection compliance: each data center request's capacity, structural-risk, and low-carbon checks,
whether it is compliant, and the compliance counts."""

from relationalai.semantics import Float, Integer, not_
from relationalai.semantics.std import aggregates as aggs

# Declare Substation.predicted_load and is_structurally_critical, the stage outputs the checks read.
from . import grid_topology, load_forecast  # noqa: F401
from .schema import DataCenterRequest, Generator, Substation, model

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

# How many requests there are, how many are compliant, and how many are flagged (not compliant).
ComplianceSummary = model.Concept("ComplianceSummary", identify_by={"id": Integer})
ComplianceSummary.n_requests = model.Property(f"{ComplianceSummary} has {Integer:n_requests} requests")
ComplianceSummary.n_compliant = model.Property(f"{ComplianceSummary} has {Integer:n_compliant} compliant requests")
ComplianceSummary.n_flagged = model.Property(f"{ComplianceSummary} has {Integer:n_flagged} flagged requests")
model.define(ComplianceSummary.new(id=1))
model.define(
    ComplianceSummary.n_requests(aggs.count(DataCenterRequest).per(ComplianceSummary)),
    ComplianceSummary.n_compliant(
        aggs.count(DataCenterRequest).per(ComplianceSummary).where(DataCenterRequest.is_compliant()) | 0
    ),
    ComplianceSummary.n_flagged(
        aggs.count(DataCenterRequest).per(ComplianceSummary).where(not_(DataCenterRequest.is_compliant())) | 0
    ),
)
