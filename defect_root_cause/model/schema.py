"""Semantic schema for the defect root-cause template: the product structure, genealogy, units, and candidate factors."""

from relationalai.semantics import Integer, Model, String

model = Model("defect_root_cause")

# SKU concept: a node in the product structure -- a finished good,
# sub-assembly, component, or raw material.
SKU = model.Concept("SKU", identify_by={"id": String})
SKU.name = model.Property(f"{SKU} has {String:name}")
SKU.tier = model.Property(f"{SKU} has {String:tier}")

# BillOfMaterials concept: one output SKU requires one input SKU (the
# type-level product structure that the lot genealogy instantiates).
BillOfMaterials = model.Concept("BillOfMaterials", identify_by={"id": String})
BillOfMaterials.output_sku = model.Property(f"{BillOfMaterials} produces {SKU:output_sku}")
BillOfMaterials.input_sku = model.Property(f"{BillOfMaterials} requires {SKU:input_sku}")

# Supplier concept: who sourced a lot.
Supplier = model.Concept("Supplier", identify_by={"id": String})
Supplier.name = model.Property(f"{Supplier} has {String:name}")

# Machine concept: a piece of process equipment (placement, reflow, assembly,
# test). calibration_age_days corroborates a machine-as-cause finding.
Machine = model.Concept("Machine", identify_by={"id": String})
Machine.name = model.Property(f"{Machine} has {String:name}")
Machine.machine_type = model.Property(f"{Machine} has {String:machine_type}")
Machine.calibration_age_days = model.Property(f"{Machine} has {Integer:calibration_age_days}")

# Lot concept: a specific received or produced batch of a SKU. Lot.consumes is
# the genealogy edge -- a built lot consumes its input lots (parent -> child).
Lot = model.Concept("Lot", identify_by={"id": String})
Lot.sku = model.Property(f"{Lot} is of {SKU:sku}")
Lot.supplier = model.Property(f"{Lot} supplied by {Supplier:supplier}")
Lot.received_date = model.Property(f"{Lot} received on {String:received_date}")
Lot.consumes = model.Relationship(f"{Lot} consumes {Lot:child}")

# Unit concept: a serialized finished unit and its final-test outcome.
Unit = model.Concept("Unit", identify_by={"id": String})
Unit.sku = model.Property(f"{Unit} is a {SKU:sku}")
Unit.build_date = model.Property(f"{Unit} built on {String:build_date}")
Unit.build_week = model.Property(f"{Unit} built in week {Integer:build_week}")
Unit.defective = model.Property(f"{Unit} has defective flag {Integer:defective}")
Unit.defect_type = model.Property(f"{Unit} has {String:defect_type}")
Unit.shift = model.Property(f"{Unit} ran on shift {String:shift}")
Unit.consumes_lot = model.Relationship(f"{Unit} consumes {Lot}")
Unit.ran_on = model.Relationship(f"{Unit} ran on {Machine}")
# is_defective: the symptom set the diagnosis must explain.
Unit.is_defective = model.Relationship(f"{Unit} is defective")

# Factor concept: a candidate root cause -- a lot, a machine, or a shift. The
# per-kind pointer properties let the touch incidence be derived in-engine.
Factor = model.Concept("Factor", identify_by={"id": String})
Factor.kind = model.Property(f"{Factor} has {String:kind}")
Factor.label = model.Property(f"{Factor} has {String:label}")
Factor.lot = model.Property(f"{Factor} points to {Lot:lot}")
Factor.machine = model.Property(f"{Factor} points to {Machine:machine}")
Factor.shift_name = model.Property(f"{Factor} points to shift {String:shift_name}")
