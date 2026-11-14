"""Load the sample distance matrix into the traveling salesman model."""

from pathlib import Path

from pandas import read_csv

from .schema import Edge, Node, model

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# Load edges from CSV.
edge_csv = read_csv(DATA_DIR / "edges.csv")
model.define(Edge.new(model.data(edge_csv).to_schema()))

# Nodes are derived from the edge endpoints.
model.define(Node.new(v=Edge.i))
