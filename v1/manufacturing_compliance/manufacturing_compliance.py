"""Manufacturing Compliance (logic reasoning) template.

This script demonstrates derived business rules in RelationalAI for
manufacturing machine maintenance and parts inventory management.

- Load sample CSVs describing machines, parts inventory, technicians,
  and qualifications.
- Define four rules as derived Relationships (boolean flags).
- Query and display which entities match each rule.

Rules defined:
  1. Machine.is_overdue_maintenance -- remaining_useful_life < maintenance_duration_hours
  2. PartsInventory.needs_reorder -- stock_level <= min_order_qty
  3. Machine.is_high_risk -- failure_probability > 0.3 AND criticality == "HIGH"
  4. Qualification.is_expiring -- days_remaining < 30

No optimization solver is used. Rules are pure logic derivations.

Run:
    `python manufacturing_compliance.py`
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Float, Integer, Model, String

model = Model("manufacturing_compliance")
Concept, Property, Relationship = model.Concept, model.Property, model.Relationship

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Concept: machines
Machine = Concept("Machine", identify_by={"id": String})
Machine.name = Property(f"{Machine} has {String:name}")
Machine.machine_type = Property(f"{Machine} has type {String:machine_type}")
Machine.facility = Property(f"{Machine} at {String:facility}")
Machine.remaining_useful_life = Property(
    f"{Machine} has remaining useful life {Float:remaining_useful_life}"
)
Machine.maintenance_duration_hours = Property(
    f"{Machine} requires {Float:maintenance_duration_hours} hours"
)
Machine.failure_probability = Property(
    f"{Machine} has failure probability {Float:failure_probability}"
)
Machine.criticality = Property(f"{Machine} has criticality {String:criticality}")

machine_data = model.data(read_csv(data_dir / "machines.csv"))
model.define(
    m := Machine.new(id=machine_data.id),
    m.name(machine_data.name),
    m.machine_type(machine_data.machine_type),
    m.facility(machine_data.facility),
    m.remaining_useful_life(machine_data.remaining_useful_life),
    m.maintenance_duration_hours(machine_data.maintenance_duration_hours),
    m.failure_probability(machine_data.failure_probability),
    m.criticality(machine_data.criticality),
)

# Concept: parts inventory
PartsInventory = Concept("PartsInventory", identify_by={"id": String})
PartsInventory.facility = Property(f"{PartsInventory} at {String:facility}")
PartsInventory.part_name = Property(f"{PartsInventory} has {String:part_name}")
PartsInventory.stock_level = Property(
    f"{PartsInventory} has {Integer:stock_level} units in stock"
)
PartsInventory.min_order_qty = Property(
    f"{PartsInventory} minimum order {Integer:min_order_qty} units"
)

parts_data = model.data(read_csv(data_dir / "parts_inventory.csv"))
model.define(
    p := PartsInventory.new(id=parts_data.id),
    p.facility(parts_data.facility),
    p.part_name(parts_data.part_name),
    p.stock_level(parts_data.stock_level),
    p.min_order_qty(parts_data.min_order_qty),
)

# Concept: technicians
Technician = Concept("Technician", identify_by={"id": String})
Technician.name = Property(f"{Technician} has {String:name}")
Technician.skill_level = Property(f"{Technician} has skill level {String:skill_level}")

tech_data = model.data(read_csv(data_dir / "technicians.csv"))
model.define(
    t := Technician.new(id=tech_data.id),
    t.name(tech_data.name),
    t.skill_level(tech_data.skill_level),
)

# Concept: qualifications (technician-to-machine-type certifications)
Qualification = Concept(
    "Qualification", identify_by={"id": String}
)
Qualification.technician = Relationship(f"{Qualification} for {Technician}")
Qualification.machine_type = Property(
    f"{Qualification} covers {String:machine_type}"
)
Qualification.days_remaining = Property(
    f"{Qualification} has {Integer:days_remaining} days remaining"
)

qual_data = model.data(read_csv(data_dir / "qualifications.csv"))
model.define(
    q := Qualification.new(id=qual_data.id),
    q.technician(Technician.filter_by(id=qual_data.technician_id)),
    q.machine_type(qual_data.machine_type),
    q.days_remaining(qual_data.days_remaining),
)

# --------------------------------------------------
# Rule 1: Machine.is_overdue_maintenance
# A machine is overdue for maintenance when its remaining useful life
# is less than the time required to perform maintenance.
# --------------------------------------------------

Machine.is_overdue_maintenance = Relationship(f"{Machine} is overdue maintenance")
model.where(
    Machine.remaining_useful_life < Machine.maintenance_duration_hours,
).define(Machine.is_overdue_maintenance())

# --------------------------------------------------
# Rule 2: PartsInventory.needs_reorder
# Parts inventory needs reorder when stock has dropped to or below
# the minimum order quantity.
# --------------------------------------------------

PartsInventory.needs_reorder = Relationship(f"{PartsInventory} needs reorder")
model.where(
    PartsInventory.stock_level <= PartsInventory.min_order_qty,
).define(PartsInventory.needs_reorder())

# --------------------------------------------------
# Rule 3: Machine.is_high_risk
# A machine is high risk when it has both a failure probability
# above 0.3 AND a criticality of HIGH.
# --------------------------------------------------

Machine.is_high_risk = Relationship(f"{Machine} is high risk")
model.where(
    Machine.failure_probability > 0.3,
    Machine.criticality == "HIGH",
).define(Machine.is_high_risk())

# --------------------------------------------------
# Rule 4: Qualification.is_expiring
# A qualification is expiring when fewer than 30 days remain
# before certification expires.
# --------------------------------------------------

Qualification.is_expiring = Relationship(f"{Qualification} is expiring")
model.where(
    Qualification.days_remaining < 30,
).define(Qualification.is_expiring())

# --------------------------------------------------
# Query results
# --------------------------------------------------

print("=== Rule 1: Overdue Maintenance (remaining_useful_life < maintenance_duration_hours) ===\n")
model.select(
    Machine.id.alias("machine_id"),
    Machine.name.alias("machine_name"),
    Machine.facility.alias("facility"),
    Machine.remaining_useful_life.alias("remaining_useful_life"),
    Machine.maintenance_duration_hours.alias("maintenance_duration_hours"),
).where(Machine.is_overdue_maintenance()).inspect()

print("\n=== Rule 2: Parts Needing Reorder (stock_level <= min_order_qty) ===\n")
model.select(
    PartsInventory.id.alias("part_id"),
    PartsInventory.part_name.alias("part_name"),
    PartsInventory.facility.alias("facility"),
    PartsInventory.stock_level.alias("stock_level"),
    PartsInventory.min_order_qty.alias("min_order_qty"),
).where(PartsInventory.needs_reorder()).inspect()

print("\n=== Rule 3: High-Risk Machines (failure_probability > 0.3 AND criticality == HIGH) ===\n")
model.select(
    Machine.id.alias("machine_id"),
    Machine.name.alias("machine_name"),
    Machine.facility.alias("facility"),
    Machine.failure_probability.alias("failure_probability"),
    Machine.criticality.alias("criticality"),
).where(Machine.is_high_risk()).inspect()

print("\n=== Rule 4: Expiring Qualifications (days_remaining < 30) ===\n")
TechRef = Technician.ref()
model.select(
    Qualification.id.alias("qualification_id"),
    TechRef.name.alias("technician_name"),
    Qualification.machine_type.alias("machine_type"),
    Qualification.days_remaining.alias("days_remaining"),
).where(
    Qualification.is_expiring(),
    Qualification.technician(TechRef),
).inspect()
