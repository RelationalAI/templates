"""Load the sample nurses, shifts, and availability into the hospital staffing model."""

from pathlib import Path

from pandas import read_csv

from .schema import Assignment, Availability, Nurse, Shift, model

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

nurse_csv = read_csv(DATA_DIR / "nurses.csv")
model.define(Nurse.new(model.data(nurse_csv).to_schema()))

shift_csv = read_csv(DATA_DIR / "shifts.csv")
model.define(Shift.new(model.data(shift_csv).to_schema()))

avail_csv = read_csv(DATA_DIR / "availability.csv")
avail_data = model.data(avail_csv)
model.define(
    a := Availability.new(nurse_id=avail_data.nurse_id, shift_id=avail_data.shift_id),
    a.available(avail_data.available),
)
model.define(Availability.nurse(Nurse)).where(Availability.nurse_id == Nurse.id)
model.define(Availability.shift(Shift)).where(Availability.shift_id == Shift.id)

model.define(Assignment.new(availability=Availability))
