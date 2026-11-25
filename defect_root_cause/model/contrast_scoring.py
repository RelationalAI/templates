"""Contrast scoring: the plant-wide failure rate, each candidate factor's defect counts, rate, and
lift over that baseline, the suspects screened for the diagnosis, and the naive ranking by raw
defect count."""

from relationalai.semantics import Float, Integer
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std import floats

# Declares Factor.touches, the incidence the counts range over.
from . import genealogy  # noqa: F401
from .schema import Factor, Unit, model

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

# Stage 2 contrast-scoring thresholds. A factor is a suspect only if defects
# among the units it touches run materially above the plant-wide baseline
# (LIFT) and it touches enough units to trust the rate (SUPPORT) and enough
# defects to matter (MIN_DEFECTS).
LIFT_THRESHOLD = 1.5
MIN_SUPPORT = 30
MIN_DEFECTS = 5

# --------------------------------------------------
# Stage 2 -- Rules: contrast scoring of candidate factors
# --------------------------------------------------

# Plant-wide failure rate: defective units over the distinct units in the model.
PlantBaseline = model.Concept("PlantBaseline", identify_by={"id": Integer})
PlantBaseline.n_units = model.Property(f"{PlantBaseline} has {Integer:n_units}")
PlantBaseline.n_defective = model.Property(f"{PlantBaseline} has {Integer:n_defective}")
PlantBaseline.failure_rate = model.Property(f"{PlantBaseline} has {Float:failure_rate}")
model.define(PlantBaseline.new(id=1))
model.define(PlantBaseline.n_units(aggs.count(Unit).per(PlantBaseline)))
model.define(
    PlantBaseline.n_defective(aggs.count(Unit).per(PlantBaseline).where(Unit.is_defective()))
)
model.define(
    PlantBaseline.failure_rate(
        floats.float(PlantBaseline.n_defective) / floats.float(PlantBaseline.n_units)
    )
)

# Per-factor incidence: how many units it touches, and how many of those failed.
Factor.touched_count = model.Property(f"{Factor} touches {Integer:touched_count}")
Factor.defect_count = model.Property(f"{Factor} has {Integer:defect_count}")
Factor.defect_rate = model.Property(f"{Factor} has {Float:defect_rate}")
Factor.lift = model.Property(f"{Factor} has {Float:lift}")
# is_suspect: defects are concentrated enough among the units this factor
# touches to warrant optimization -- the contrast screen before the MILP.
Factor.is_suspect = model.Relationship(f"{Factor} is suspect")

model.define(Factor.touched_count(aggs.count(Unit).per(Factor).where(Factor.touches(Unit))))
model.define(Factor.defect_count(aggs.count(Unit).per(Factor).where(Factor.touches(Unit), Unit.is_defective())))
# defect_rate and lift each derive directly from the two counts (kept one
# level deep so the chain stays robust alongside the genealogy graph).
model.where(Factor.defect_count > 0).define(
    Factor.defect_rate(floats.float(Factor.defect_count) / floats.float(Factor.touched_count))
)
model.where(Factor.defect_count > 0).define(
    Factor.lift(
        (floats.float(Factor.defect_count) / floats.float(Factor.touched_count))
        / PlantBaseline.failure_rate
    )
)
# A factor is a suspect only when defect lift, support, and defect count all
# clear threshold -- screening out high-coverage, low-lift trunk factors.
model.where(
    Factor.lift >= LIFT_THRESHOLD,
    Factor.touched_count >= MIN_SUPPORT,
    Factor.defect_count >= MIN_DEFECTS
).define(Factor.is_suspect(Factor))

# The naive view: factors ranked by the raw count of defective units they
# touch, most first, ties broken by factor id. High-volume factors top it
# because they touch almost everything -- the bias contrast scoring corrects.
# The count is negated so both keys sort ascending, a form every backend ranks.
Factor.raw_defect_rank = model.Property(f"{Factor} has {Integer:raw_defect_rank}")
model.define(Factor.raw_defect_rank(
    aggs.rank(-Factor.defect_count, Factor.id)
))
