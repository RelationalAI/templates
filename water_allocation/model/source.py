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

# The model drops a connection whose endpoint id matches no source or user, divides by
# max_flow in the loss term, and states each user's demand over that user's connections,
# so a user with demand and no connection would silently get no demand constraint.
unknown = ~conn_csv["source_id"].isin(source_csv["id"]) | ~conn_csv["user_id"].isin(user_csv["id"])
if unknown.any():
    raise ValueError(f"connections.csv rows {conn_csv.index[unknown].tolist()} name an unknown source or user.")
bad_flow = ~conn_csv["max_flow"].between(0, float("inf"), inclusive="neither")
if bad_flow.any():
    raise ValueError(f"connections.csv rows {conn_csv.index[bad_flow].tolist()} need a positive, finite max_flow.")
unconnected = user_csv[(user_csv["demand"] > 0) & ~user_csv["id"].isin(conn_csv["user_id"])]
if len(unconnected):
    raise ValueError(f"Users {unconnected['id'].tolist()} have demand but no connection.")

conn_data = model.data(conn_csv)
model.define(
    Connection.new(source=Source, user=User, max_flow=conn_data.max_flow, loss_rate=conn_data.loss_rate)
).where(Source.id == conn_data.source_id, User.id == conn_data.user_id)
