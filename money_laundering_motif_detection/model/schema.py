"""Semantic schema for the money-laundering motif template: accounts and transactions."""

from relationalai.semantics import Integer, Model, String

model = Model("money_laundering_motif_detection")

# Concept: bank account.
Account = model.Concept("Account", identify_by={"id": Integer})
Account.name = model.Property(f"{Account} has {String:name}")
Account.bo_id = model.Property(f"{Account} owned by {Integer:bo_id}")
Account.kyc_tier = model.Property(f"{Account} has {String:kyc_tier}")
Account.jurisdiction = model.Property(f"{Account} from {String:jurisdiction}")

# Concept: transaction (a directed edge in the graph).
Transaction = model.Concept("Transaction", identify_by={"tx_id": Integer})
Transaction.src = model.Property(f"{Transaction} from {Account:src}")
Transaction.dst = model.Property(f"{Transaction} to {Account:dst}")
Transaction.amount_dollars = model.Property(f"{Transaction} has {Integer:amount_dollars}")
Transaction.ts_minutes = model.Property(f"{Transaction} occurs at {Integer:ts_minutes}")
