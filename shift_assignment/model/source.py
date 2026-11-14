"""Load the sample workers, shifts, availability, and scenarios into the shift assignment model."""

from pathlib import Path

from pandas import read_csv

from .schema import Scenario, Shift, Worker, model

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

worker_csv = read_csv(DATA_DIR / "workers.csv")
model.define(Worker.new(model.data(worker_csv).to_schema()))

shift_csv = read_csv(DATA_DIR / "shifts.csv")
model.define(Shift.new(model.data(shift_csv).to_schema()))

availability_csv = read_csv(DATA_DIR / "availability.csv")
availability_data = model.data(availability_csv)
model.define(Worker.available_for(Shift)).where(
    Worker.id(availability_data.worker_id),
    Shift.id(availability_data.shift_id)
)

scenario_data = model.data(
    [("coverage_1", 1), ("coverage_2", 2), ("coverage_3", 3)],
    columns=["name", "min_coverage"],
)
model.define(Scenario.new(scenario_data.to_schema()))
