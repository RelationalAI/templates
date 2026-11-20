"""Bundled CSVs for the people, their connections, and the train / validation / test splits."""

from pathlib import Path

from pandas import read_csv

from .schema import (
    People,
    Related,
    Test,
    TestTable,
    Train,
    TrainTable,
    Validation,
    ValidationTable,
    model,
)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# Identifier-safe column names (RAI-55920); before removing, check that a deploy accepts the raw headers.
people_df = read_csv(DATA_DIR / "people.csv")
people_df.columns = [
    c if c == "Id" else c.replace("(", "_").replace(")", "").replace(" ", "_").lower()
    for c in people_df.columns
]

# Frames of at most 9,746 rows (RAI-52357); before removing, check that a deploy accepts people.csv as one frame.
PEOPLE_ROWS_PER_FRAME = 9_746
for start in range(0, len(people_df), PEOPLE_ROWS_PER_FRAME):
    frame = people_df.iloc[start : start + PEOPLE_ROWS_PER_FRAME]
    model.define(People.new(model.data(frame).to_schema()))
model.define(Related.new(model.data(read_csv(DATA_DIR / "related.csv")).to_schema()))

model.define(TrainTable.new(model.data(read_csv(DATA_DIR / "train.csv")).to_schema()))
model.define(ValidationTable.new(model.data(read_csv(DATA_DIR / "validation.csv")).to_schema()))
model.define(TestTable.new(model.data(read_csv(DATA_DIR / "test.csv")).to_schema()))

# --------------------------------------------------
# Train / Val / Test split
# --------------------------------------------------
model.define(Train(People, TrainTable.smoking)).where(People.Id == TrainTable.Id)
model.define(Validation(People, ValidationTable.smoking)).where(People.Id == ValidationTable.Id)
model.define(Test(People)).where(People.Id == TestTable.Id)
