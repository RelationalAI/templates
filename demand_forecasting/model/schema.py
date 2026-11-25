"""Demand-forecasting model: concepts and the regression task relationships."""

from relationalai.semantics import DateTime, Integer, Model, String

model = Model("demand_forecasting")
Concept, Relationship = model.Concept, model.Relationship

# Store concept: physical retail store with city, state, type, cluster.
Store = Concept("Store", identify_by={"store_id": Integer})

# Item concept: SKU with family, class, perishability.
Item = Concept("Item", identify_by={"item_id": Integer})

# ItemFamily concept: derived from the unique Item.family values; gives the
# GNN a hierarchical edge structure (Item -> Family) that lets signal
# propagate across items within a family.
ItemFamily = Concept("ItemFamily", identify_by={"family": String})

# Sale concept: one row per (store, item, date) with unit_sales target and
# onpromotion flag. The GNN target is Sale.unit_sales.
Sale = Concept("Sale", identify_by={"sale_id": Integer})

# Regression task relationships: the Sales in each temporal split. Each carries
# the timestamp (Sale.date) since the GNN is trained with has_time_column=True.
Train = Relationship(f"{Sale} at {DateTime:timestamp} has {Integer:value}")
Val = Relationship(f"{Sale} at {DateTime:timestamp} has {Integer:value}")
Test = Relationship(f"{Sale} at {DateTime:timestamp}")
