"""Semantic schema for the BOM reachability template: SKUs and bill-of-materials rows."""

from relationalai.semantics import Model, String

model = Model("bom_reachability")

# SKU concept
SKU = model.Concept("SKU", identify_by={"id": String})
SKU.name = model.Property(f"{SKU} has {String:name}")
SKU.type = model.Property(f"{SKU} has type {String:type}")
SKU.category = model.Property(f"{SKU} in {String:category}")

# BillOfMaterials concept
BillOfMaterials = model.Concept("BillOfMaterials", identify_by={"id": String})
BillOfMaterials.output_sku = model.Relationship(f"{BillOfMaterials} produces {SKU}")
BillOfMaterials.input_sku = model.Relationship(f"{BillOfMaterials} requires {SKU}")
