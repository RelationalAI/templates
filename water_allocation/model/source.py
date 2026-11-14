"""Load the sample sources, users, and connections into the water allocation model."""

from pathlib import Path

from pandas import read_csv

from .schema import Connection, Source, User, model

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

source_csv = read_csv(DATA_DIR / "sources.csv")
model.define(Source.new(model.data(source_csv).to_schema()))

user_csv = read_csv(DATA_DIR / "users.csv")
model.define(User.new(model.data(user_csv).to_schema()))

conn_csv = read_csv(DATA_DIR / "connections.csv")
conn_data = model.data(conn_csv)
model.define(
    Connection.new(source=Source, user=User, max_flow=conn_data.max_flow, loss_rate=conn_data.loss_rate)
).where(Source.id == conn_data.source_id, User.id == conn_data.user_id)
