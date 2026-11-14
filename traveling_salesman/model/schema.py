"""Semantic schema for the traveling salesman template: directed edges and nodes."""

from relationalai.semantics import Float, Integer, Model

model = Model("tsp")

# Edge concept: directed edges with distances between nodes.
Edge = model.Concept("Edge", identify_by={"i": Integer, "j": Integer})
Edge.dist = model.Property(f"{Edge} has {Float:dist}")

# Node concept: derived from edge endpoints.
Node = model.Concept("Node", identify_by={"v": Integer})
