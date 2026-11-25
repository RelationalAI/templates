"""Advisory signals: how many advisories the model keeps, and how much of the equipment the advised
models cover."""

from relationalai.semantics import Integer, String, distinct
from relationalai.semantics.std import aggregates as aggs

from .schema import ModelAdvisory, NetworkEquipment, model

# How many advisories the model keeps, and on how many distinct MODELs.
AdvisoryCount = model.Relationship(f"the model keeps {Integer:advisories} advisories on {Integer:models} distinct models")
model.define(AdvisoryCount(aggs.count(ModelAdvisory) | 0, aggs.count(distinct(ModelAdvisory.model)) | 0))

# The equipment items on each advised MODEL.
AdvisedModelEquipment = model.Relationship(
    f"advised model {String:eqp_model} sits on {Integer:equipment_items} equipment items"
)
_advised_model = String.ref()
model.where(ModelAdvisory.model == _advised_model).define(
    AdvisedModelEquipment(
        _advised_model,
        aggs.count(NetworkEquipment).per(_advised_model).where(NetworkEquipment.eqp_model == _advised_model) | 0,
    )
)

# The equipment items that sit on any advised MODEL.
AdvisedEquipmentCount = model.Relationship(f"{Integer:equipment_items} equipment items sit on an advised model")
model.define(
    AdvisedEquipmentCount(
        aggs.count(NetworkEquipment).where(NetworkEquipment.eqp_model == ModelAdvisory.model) | 0
    )
)
