"""Compliance rules: late and at-risk shipments, single-sourced BOM inputs, and escalated demands."""

from relationalai.semantics.std import aggregates

from .schema import (
    BOM,
    SKU,
    Demand,
    Operation,
    Priority,
    Relationship,
    Shipment,
    ShipmentStatus,
    Supplier,
    model,
)

# --------------------------------------------------
# Rule 1: Shipment.is_late
# A shipment is late when delay_days > 0.
# --------------------------------------------------

Shipment.is_late = Relationship(f"{Shipment} is late")
model.where(Shipment.delay_days > 0).define(Shipment.is_late())

# --------------------------------------------------
# Rule 2: Shipment.is_at_risk
# An undelivered shipment is at risk when its supplier has
# a reliability score below 0.8.
# --------------------------------------------------

Shipment.is_at_risk = Relationship(f"{Shipment} is at risk")
SupplierRef = Supplier.ref()
model.where(
    Shipment.status != ShipmentStatus.DELIVERED,
    Shipment.supplier(SupplierRef),
    SupplierRef.reliability_score < 0.8,
).define(Shipment.is_at_risk())

# --------------------------------------------------
# Rule 3: BillOfMaterials.is_single_sourced
# A BOM input is single-sourced when only one Operation
# produces the required input SKU (aggregation-based rule).
# --------------------------------------------------

BOM.is_single_sourced = Relationship(f"{BOM} is single sourced")
SkuRef = SKU.ref()
route_count = (
    aggregates.count(Operation)
    .per(BOM)
    .where(
        BOM.input_sku(SkuRef),
        Operation.output_sku(SkuRef),
    )
)
model.where(route_count == 1).define(BOM.is_single_sourced())

# --------------------------------------------------
# Rule 4: Demand.is_escalated
# A demand order is escalated when its priority is HIGH or URGENT.
# Multiple define() calls on the same Relationship produce OR semantics.
# --------------------------------------------------

Demand.is_escalated = Relationship(f"{Demand} is escalated")
model.where(Demand.priority == Priority.HIGH).define(Demand.is_escalated())
model.where(Demand.priority == Priority.URGENT).define(Demand.is_escalated())
