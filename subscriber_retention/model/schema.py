"""Semantic schema for subscriber retention: subscribers, calls, and the churn-risk task."""

from relationalai.semantics import Float, Model, String

model = Model("subscriber_retention")
Concept, Relationship = model.Concept, model.Relationship

# Subscriber concept: one row per subscriber with denormalized plan attrs.
Subscriber = Concept("Subscriber", identify_by={"sub_id": String})

# Call concept: edge-intermediary for the Subscriber -> Subscriber call
# graph. No identify_by (the CDR_ID is irrelevant downstream); the edges are
# the only thing we need.
Call = Concept("Call")

# Task tables: one row per subscriber in each split.
TrainTable = Concept("TrainTable")
ValTable = Concept("ValTable")
TestTable = Concept("TestTable")

# Regression task relationships (no time column -- prediction is on
# subscriber state, not per-call events).
Train = Relationship(f"{Subscriber} has {Float:risk}")
Val = Relationship(f"{Subscriber} has {Float:risk}")
Test = Relationship(f"{Subscriber}")
