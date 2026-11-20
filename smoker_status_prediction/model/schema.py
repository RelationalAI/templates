"""Semantic schema for smoker status prediction: people, their connections, and the smoking-label task."""

from relationalai.semantics import Integer, Model

model = Model("smoker_status_prediction")
Concept, Relationship = model.Concept, model.Relationship

# Domain concepts
People = Concept("People", identify_by={"Id": Integer})
Related = Concept("Related")  # edge list between two People

# Task split concepts (no PK)
TrainTable = Concept("TrainTable")
ValidationTable = Concept("ValidationTable")
TestTable = Concept("TestTable")

# Train / Validation / Test split
# Test has no label -- predictions are generated for it after training.
Train = Relationship(f"{People} has {Integer:smoking}")
Validation = Relationship(f"{People} has {Integer:smoking}")
Test = Relationship(f"{People}")
