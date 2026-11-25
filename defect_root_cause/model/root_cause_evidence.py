"""Root-cause evidence: for each suspect factor, the defect type its failures concentrate in and
that type's share of its defective units with a recorded type."""

from relationalai.semantics import Float, Integer, String
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std import floats

# Declares the suspect screen.
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
# share of the factor's defective units that have a type.
Factor.signature_type = model.Property(f"{Factor} has signature defect type {String:type}")
Factor.signature_share = model.Property(f"{Factor} has signature share {Float:share}")
_n_units, _any_type, _n_typed = Integer.ref(), String.ref(), Integer.ref()
# Most units first (negated count), ties broken by defect type name.
model.where(
    Factor.defect_type_count(_type, _n_units),
    aggs.rank(-_n_units, _type).per(Factor) == 1,
).define(
    Factor.signature_type(_type),
    Factor.signature_share(floats.float(_n_units) / floats.float(
        aggs.sum(_any_type, _n_typed).per(Factor).where(
            Factor.defect_type_count(_any_type, _n_typed)
        )
    )),
)
