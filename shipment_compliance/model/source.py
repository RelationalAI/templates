"""Load the sample suppliers, SKUs, shipments, operations, BOMs, and demands into the model."""

from pathlib import Path

from pandas import read_csv

from .schema import (
    BOM,
    SKU,
    Demand,
    Operation,
    Priority,
    Shipment,
    ShipmentStatus,
    Supplier,
    model,
)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

model.define(Supplier.new(model.data(read_csv(DATA_DIR / "suppliers.csv")).to_schema()))

model.define(SKU.new(model.data(read_csv(DATA_DIR / "skus.csv")).to_schema()))

shipment_data = model.data(read_csv(DATA_DIR / "shipments.csv"))
model.define(
    s := Shipment.new(
        id=shipment_data.id,
        sku=SKU.lookup(id=shipment_data.sku_id),
        supplier=Supplier.lookup(id=shipment_data.supplier_id),
    ),
    s.status(ShipmentStatus.lookup(shipment_data.status)),
    s.delay_days(shipment_data.delay_days),
)

op_data = model.data(read_csv(DATA_DIR / "operations.csv"))
model.define(
    op := Operation.new(
        id=op_data.id,
        input_sku=SKU.lookup(id=op_data.input_sku_id),
        output_sku=SKU.lookup(id=op_data.output_sku_id),
    ),
    op.type(op_data.type),
    op.cost_per_unit(op_data.cost_per_unit),
    op.capacity_per_day(op_data.capacity_per_day),
)

bom_data = model.data(read_csv(DATA_DIR / "bill_of_materials.csv"))
model.define(
    b := BOM.new(
        id=bom_data.id,
        input_sku=SKU.lookup(id=bom_data.input_sku_id),
    ),
    b.site_id(bom_data.site_id),
    b.input_quantity(bom_data.input_quantity),
)

demand_data = model.data(read_csv(DATA_DIR / "demands.csv"))
model.define(
    d := Demand.new(
        id=demand_data.id,
        sku=SKU.lookup(id=demand_data.sku_id),
    ),
    d.quantity(demand_data.quantity),
    d.priority(Priority.lookup(demand_data.priority)),
)
