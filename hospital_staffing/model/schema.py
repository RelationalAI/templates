"""Semantic schema for the hospital staffing template: nurses, shifts, availability, and frontier points."""

from relationalai.semantics import Float, Integer, Model, String

model = Model("hospital_staffing")
Concept, Property, Relationship = model.Concept, model.Property, model.Relationship

Nurse = Concept("Nurse", identify_by={"id": Integer})
Nurse.name = Property(f"{Nurse} has {String:name}")
Nurse.skill_level = Property(f"{Nurse} has {Integer:skill_level}")
Nurse.hourly_cost = Property(f"{Nurse} has {Float:hourly_cost}")
Nurse.regular_hours = Property(f"{Nurse} has {Integer:regular_hours}")
Nurse.overtime_multiplier = Property(f"{Nurse} has {Float:overtime_multiplier}")
Nurse.x_overtime_hours = Property(f"{Nurse} has {Float:overtime_hours}")

Shift = Concept("Shift", identify_by={"id": Integer})
Shift.name = Property(f"{Shift} has {String:name}")
Shift.start_hour = Property(f"{Shift} has {Integer:start_hour}")
Shift.duration = Property(f"{Shift} has {Integer:duration}")
Shift.min_nurses = Property(f"{Shift} has {Integer:min_nurses}")
Shift.min_skill = Property(f"{Shift} has {Integer:min_skill}")
Shift.patient_demand = Property(f"{Shift} has {Integer:patient_demand}")
Shift.patients_per_nurse_hour = Property(f"{Shift} has {Float:patients_per_nurse_hour}")
Shift.x_patients_served = Property(f"{Shift} has {Float:patients_served}")
Shift.x_unmet_demand = Property(f"{Shift} has {Float:unmet_demand}")

Availability = Concept("Availability", identify_by={"nurse_id": Integer, "shift_id": Integer})
Availability.nurse = Property(f"{Availability} for {Nurse}")
Availability.shift = Property(f"{Availability} in {Shift}")
Availability.available = Property(f"{Availability} is {Integer:available}")

Assignment = Concept("Assignment", identify_by={"availability": Availability})
Assignment.x_assigned = Property(f"{Assignment} is {Float:assigned}")

# Epsilon-constraint points: SweepPoint i bounds total unmet demand by its eps_unmet,
# a rule over the two anchor solves' results (model/reasoning.py).
SweepPoint = Concept("SweepPoint", identify_by={"index": Integer})
SweepPoint.eps_unmet = Property(f"{SweepPoint} allows {Float:eps_unmet}")

# Published results, one FrontierPoint per solve: position 0 is the cheapest anchor,
# 1..N_INTERIOR the sweep, N_INTERIOR + 1 the best-service anchor.
FrontierPoint = Concept("FrontierPoint", identify_by={"position": Integer})
FrontierPoint.status = Property(f"{FrontierPoint} has {String:status}")
FrontierPoint.overtime_cost = Property(f"{FrontierPoint} has {Float:overtime_cost}")
FrontierPoint.unmet_demand = Property(f"{FrontierPoint} has {Float:unmet_demand}")
FrontierPoint.assigns = Relationship(f"{FrontierPoint} assigns {Nurse} to {Shift}")
