"""Semantic schema for the shipment compliance template: supply chain entities and vocabularies."""

from relationalai.semantics import Float, Integer, Model, String

model = Model("shipment_compliance")
Concept, Property, Relationship = model.Concept, model.Property, model.Relationship

# Supplier concept: companies that supply parts.
Supplier = Concept("Supplier", identify_by={"id": Integer})
Supplier.name = Property(f"{Supplier} has {String:name}")
Supplier.reliability_score = Property(f"{Supplier} has {Float:reliability_score}")

# SKU concept: stock keeping units tracked in the supply chain.
SKU = Concept("SKU", identify_by={"id": Integer})
SKU.name = Property(f"{SKU} has {String:name}")
SKU.product_type = Property(f"{SKU} has {String:product_type}")


# Shipment-status vocabulary. CSV status strings map to members BY NAME via
# `ShipmentStatus.lookup(...)` in `model/source.py`; the wrapped values are arbitrary
# distinct integers (here in lifecycle order).
class ShipmentStatus(model.Enum):
    PENDING = 1
    IN_TRANSIT = 2
    DELIVERED = 3


# Shipment concept: deliveries of SKUs from suppliers.
Shipment = Concept("Shipment", identify_by={"id": Integer})
Shipment.sku = Relationship(f"{Shipment} carries {SKU}")
Shipment.supplier = Relationship(f"{Shipment} from {Supplier}")
Shipment.status = Property(f"{Shipment} has {ShipmentStatus:status}")
Shipment.delay_days = Property(f"{Shipment} has {Integer:delay_days}")

# Operation concept: production or shipping routes that transform SKUs.
Operation = Concept("Operation", identify_by={"id": Integer})
Operation.type = Property(f"{Operation} has {String:type}")
Operation.input_sku = Relationship(f"{Operation} consumes {SKU}", short_name="input_sku")
Operation.output_sku = Relationship(f"{Operation} produces {SKU}", short_name="output_sku")
Operation.cost_per_unit = Property(f"{Operation} has {Float:cost_per_unit}")
Operation.capacity_per_day = Property(f"{Operation} has {Integer:capacity_per_day}")

# BillOfMaterials concept: input SKU requirements for production.
BOM = Concept("BillOfMaterials", identify_by={"id": Integer})
BOM.input_sku = Relationship(f"{BOM} requires {SKU}", short_name="input_sku")
BOM.site_id = Property(f"{BOM} has {Integer:site_id}")
BOM.input_quantity = Property(f"{BOM} has {Integer:input_quantity}")


# Demand-priority vocabulary; the wrapped values are arbitrary distinct
# integers (here in ascending urgency order).
class Priority(model.Enum):
    LOW = 1
    STANDARD = 2
    HIGH = 3
    URGENT = 4


# Demand concept: quantity requirements for specific SKUs.
Demand = Concept("Demand", identify_by={"id": Integer})
Demand.sku = Relationship(f"{Demand} for {SKU}")
Demand.quantity = Property(f"{Demand} has {Integer:quantity}")
Demand.priority = Property(f"{Demand} has {Priority:priority}")
