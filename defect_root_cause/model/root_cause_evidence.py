"""Root-cause evidence: for each suspect factor, the defect type its failures concentrate in and
that type's share, and the kind-specific evidence an engineer confirms: supplier and receipt date
for a lot, calibration age for a machine, the shift for a shift."""

from relationalai.semantics import Float, Integer, String
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std import floats, strings

# Declares the suspect screen and Factor.defect_count.
from . import contrast_scoring  # noqa: F401
from .schema import Factor, Unit, model

# Defect types of the defective units each suspect touches.
Factor.defect_type_count = model.Relationship(
    f"{Factor} has {String:defect_type} on {Integer:n_units} defective units"
)
_type = String.ref()
model.where(
    Factor.is_suspect(),
    Factor.touches(Unit),
    Unit.is_defective(),
    Unit.defect_type == _type,
).define(Factor.defect_type_count(_type, aggs.count(Unit).per(Factor, _type)))

# Defect signature: the most frequent type (ties broken by type name) and its
# share of the factor's defective units.
Factor.signature_type = model.Property(f"{Factor} has signature defect type {String:type}")
Factor.signature_share = model.Property(f"{Factor} has signature share {Float:share}")
_n_units = Integer.ref()
model.where(
    Factor.defect_type_count(_type, _n_units),
    aggs.rank(aggs.desc(_n_units), aggs.asc(_type)).per(Factor) == 1,
).define(
    Factor.signature_type(_type),
    Factor.signature_share(floats.float(_n_units) / floats.float(Factor.defect_count)),
)

# Kind-specific evidence, read through the factor's typed pointer to its lot,
# machine, or shift.
Factor.evidence = model.Property(f"{Factor} has evidence {String:evidence}")
model.where(Factor.is_suspect()).define(Factor.evidence(strings.concat(
    "supplier ", Factor.lot.supplier.name, ", received ", Factor.lot.received_date
)))
model.where(Factor.is_suspect()).define(Factor.evidence(strings.concat(
    strings.string(Factor.machine.calibration_age_days), " days since last calibration"
)))
model.where(Factor.is_suspect()).define(Factor.evidence(
    strings.concat(Factor.shift_name, " shift")
))
