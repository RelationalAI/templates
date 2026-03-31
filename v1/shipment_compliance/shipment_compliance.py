"""Shipment Compliance (logic reasoning) template.

This script demonstrates derived business rules in RelationalAI:

- Load sample CSVs describing suppliers, SKUs, shipments, operations, BOMs, and demand.
- Define four rules as derived Relationships (boolean flags) on existing concepts.
- Query and display which entities match each rule.

Rules defined:
  1. Shipment.is_late -- shipment arrived after expected date (delay_days > 0)
  2. Shipment.is_at_risk -- undelivered shipment from an unreliable supplier
  3. BillOfMaterials.is_single_sourced -- only one operation produces the input SKU
  4. Demand.is_escalated -- demand priority is HIGH or URGENT

No optimization solver is used. Rules are pure logic derivations.

    Run:
        `python shipment_compliance.py`

    Output:
        Prints which entities match each compliance rule.
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Float, Integer, Model, String
from relationalai.semantics.std import aggregates

model = Model("shipment_compliance")
Concept, Property, Relationship = model.Concept, model.Property, model.Relationship

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"

# Supplier concept: companies that supply parts.
Supplier = Concept("Supplier", identify_by={"id": Integer})
Supplier.name = Property(f"{Supplier} has {String:name}")
Supplier.reliability_score = Property(f"{Supplier} has {Float:reliability_score}")
model.define(Supplier.new(model.data(read_csv(DATA_DIR / "suppliers.csv")).to_schema()))

# SKU concept: stock keeping units tracked in the supply chain.
SKU = Concept("SKU", identify_by={"id": Integer})
SKU.name = Property(f"{SKU} has {String:name}")
SKU.product_type = Property(f"{SKU} has {String:product_type}")
model.define(SKU.new(model.data(read_csv(DATA_DIR / "skus.csv")).to_schema()))

# Shipment concept: deliveries of SKUs from suppliers.
Shipment = Concept("Shipment", identify_by={"id": Integer})
Shipment.sku = Relationship(f"{Shipment} carries {SKU}")
Shipment.supplier = Relationship(f"{Shipment} from {Supplier}")
Shipment.status = Property(f"{Shipment} has {String:status}")
Shipment.delay_days = Property(f"{Shipment} has {Integer:delay_days}")

shipment_data = model.data(read_csv(DATA_DIR / "shipments.csv"))
model.define(
    s := Shipment.new(
        id=shipment_data.id,
        sku=SKU.filter_by(id=shipment_data.sku_id),
        supplier=Supplier.filter_by(id=shipment_data.supplier_id),
    ),
    s.status(shipment_data.status),
    s.delay_days(shipment_data.delay_days),
)

# Operation concept: production or shipping routes that transform SKUs.
Operation = Concept("Operation", identify_by={"id": Integer})
Operation.type = Property(f"{Operation} has {String:type}")
Operation.input_sku = Relationship(f"{Operation} consumes {SKU}", short_name="input_sku")
Operation.output_sku = Relationship(f"{Operation} produces {SKU}", short_name="output_sku")
Operation.cost_per_unit = Property(f"{Operation} has {Float:cost_per_unit}")
Operation.capacity_per_day = Property(f"{Operation} has {Integer:capacity_per_day}")

op_data = model.data(read_csv(DATA_DIR / "operations.csv"))
model.define(
    op := Operation.new(
        id=op_data.id,
        input_sku=SKU.filter_by(id=op_data.input_sku_id),
        output_sku=SKU.filter_by(id=op_data.output_sku_id),
    ),
    op.type(op_data.type),
    op.cost_per_unit(op_data.cost_per_unit),
    op.capacity_per_day(op_data.capacity_per_day),
)

# BillOfMaterials concept: input SKU requirements for production.
BOM = Concept("BillOfMaterials", identify_by={"id": Integer})
BOM.input_sku = Relationship(f"{BOM} requires {SKU}", short_name="input_sku")
BOM.site_id = Property(f"{BOM} has {Integer:site_id}")
BOM.input_quantity = Property(f"{BOM} has {Integer:input_quantity}")

bom_data = model.data(read_csv(DATA_DIR / "bill_of_materials.csv"))
model.define(
    b := BOM.new(
        id=bom_data.id,
        input_sku=SKU.filter_by(id=bom_data.input_sku_id),
    ),
    b.site_id(bom_data.site_id),
    b.input_quantity(bom_data.input_quantity),
)

# Demand concept: quantity requirements for specific SKUs.
Demand = Concept("Demand", identify_by={"id": Integer})
Demand.sku = Relationship(f"{Demand} for {SKU}")
Demand.quantity = Property(f"{Demand} has {Integer:quantity}")
Demand.priority = Property(f"{Demand} has {String:priority}")

demand_data = model.data(read_csv(DATA_DIR / "demands.csv"))
model.define(
    d := Demand.new(
        id=demand_data.id,
        sku=SKU.filter_by(id=demand_data.sku_id),
    ),
    d.quantity(demand_data.quantity),
    d.priority(demand_data.priority),
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
    Shipment.status != "DELIVERED",
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
model.where(Demand.priority == "HIGH").define(Demand.is_escalated())
model.where(Demand.priority == "URGENT").define(Demand.is_escalated())

# --------------------------------------------------
# Query results
# --------------------------------------------------

print("=== Rule 1: Late Shipments (delay_days > 0) ===\n")
model.select(
    Shipment.id.alias("shipment_id"),
    Shipment.sku.name.alias("sku"),
    Shipment.supplier.name.alias("supplier"),
    Shipment.delay_days.alias("delay_days"),
).where(Shipment.is_late()).inspect()

print("\n=== Rule 2: At-Risk Shipments (undelivered + unreliable supplier) ===\n")
model.select(
    Shipment.id.alias("shipment_id"),
    Shipment.sku.name.alias("sku"),
    Shipment.supplier.name.alias("supplier"),
    Shipment.status.alias("status"),
    Shipment.supplier.reliability_score.alias("reliability"),
).where(Shipment.is_at_risk()).inspect()

print("\n=== Rule 3: Single-Sourced BOM Inputs (only 1 operation route) ===\n")
model.select(
    BOM.id.alias("bom_id"),
    BOM.input_sku.name.alias("input_sku"),
    BOM.input_quantity.alias("qty"),
).where(BOM.is_single_sourced()).inspect()

print("\n=== Rule 4: Escalated Demands (HIGH or URGENT priority) ===\n")
model.select(
    Demand.id.alias("demand_id"),
    Demand.sku.name.alias("sku"),
    Demand.quantity.alias("quantity"),
    Demand.priority.alias("priority"),
).where(Demand.is_escalated()).inspect()
