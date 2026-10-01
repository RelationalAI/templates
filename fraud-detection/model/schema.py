"""Stable semantic schema shared by the fraud-detection runners."""

from relationalai.semantics import Any, DateTime, Float, Integer, Model, String

model = Model("fraud_detection")

Account = model.Concept("Account", identify_by={"account_id": String})
Account.account_type_prefix = model.Property(
    f"{Account} has type prefix {String:account_type_prefix}"
)

Transaction = model.Concept("Transaction", identify_by={"transaction_id": Integer})
Transaction.step = model.Property(f"{Transaction} has step {Integer:step}")
Transaction.step_ts = model.Property(
    f"{Transaction} has timestamp {DateTime:step_ts}"
)
Transaction.trans_type = model.Property(
    f"{Transaction} has type {String:trans_type}"
)
Transaction.amount = model.Property(f"{Transaction} has amount {Float:amount}")
Transaction.name_orig = model.Property(
    f"{Transaction} has origin account {String:name_orig}"
)
Transaction.old_balance_orig = model.Property(
    f"{Transaction} has old origin balance {Float:old_balance_orig}"
)
Transaction.new_balance_orig = model.Property(
    f"{Transaction} has new origin balance {Float:new_balance_orig}"
)
Transaction.name_dest = model.Property(
    f"{Transaction} has destination account {String:name_dest}"
)
Transaction.old_balance_dest = model.Property(
    f"{Transaction} has old destination balance {Float:old_balance_dest}"
)
Transaction.new_balance_dest = model.Property(
    f"{Transaction} has new destination balance {Float:new_balance_dest}"
)
Transaction.is_flagged_fraud = model.Property(
    f"{Transaction} has heuristic fraud flag {Integer:is_flagged_fraud}"
)
Transaction.audit_cost = model.Property(
    f"{Transaction} has audit cost {Float:audit_cost}"
)

Transaction.sender = model.Relationship(f"{Transaction} was sent by {Account}")
Transaction.receiver = model.Relationship(f"{Transaction} was received by {Account}")

TrainTable = model.Concept("TrainTable")
ValTable = model.Concept("ValTable")
TestTable = model.Concept("TestTable")

Train = model.Relationship(f"{Transaction} at {Any:step_ts} has {Any:label}")
Val = model.Relationship(f"{Transaction} at {Any:step_ts} has {Any:label}")
Test = model.Relationship(f"{Transaction} at {Any:step_ts}")
