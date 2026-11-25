"""Semantic schema for subscriber retention: subscribers, calls, and the churn-risk task."""

from relationalai.semantics import Boolean, Float, Integer, Model, String

model = Model("subscriber_retention")
Concept, Property, Relationship = model.Concept, model.Property, model.Relationship

# Subscriber concept: one row per subscriber with denormalized plan attrs.
Subscriber = Concept("Subscriber", identify_by={"sub_id": String})
Subscriber.plan_type = Property(f"{Subscriber} has {String:plan_type}")
Subscriber.monthly_rate_usd = Property(f"{Subscriber} has {Float:monthly_rate_usd}")
Subscriber.data_limit_gb = Property(f"{Subscriber} has {Integer:data_limit_gb}")
Subscriber.term_months = Property(f"{Subscriber} has {Integer:term_months}")
Subscriber.auto_renew = Property(f"{Subscriber} has {Boolean:auto_renew}")
Subscriber.early_termination_fee_usd = Property(f"{Subscriber} has {Integer:early_termination_fee_usd}")

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
