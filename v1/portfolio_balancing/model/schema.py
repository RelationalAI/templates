"""Stable concepts and relationships for the portfolio model."""

from relationalai.semantics import Float, Integer, Model, String

model = Model("portfolio")

Stock = model.Concept("Stock", identify_by={"index": Integer})
Stock.ticker = model.Property(f"{Stock} has ticker {String:stock_ticker}")
Stock.sector = model.Property(f"{Stock} has sector {String:stock_sector}")
Stock.returns = model.Property(f"{Stock} has {Float:returns}")
Stock.covar = model.Property(f"{Stock} and {Stock} have {Float:covar}")

Sector = model.Concept("Sector", identify_by={"sector_name": String})
Stock.sector_ref = model.Relationship(f"{Stock} in {Sector}")

User = model.Concept("User", identify_by={"user_id": Integer})
User.user_name = model.Property(f"{User} has name {String:user_name}")
User.risk_score = model.Property(f"{User} has risk score {Float:risk_score}")

Account = model.Concept("Account", identify_by={"account_id": Integer})
Account.user_id = model.Property(f"{Account} has user id {Integer:acct_user_id}")
Account.account_type = model.Property(f"{Account} has type {String:account_type}")
Account.balance = model.Property(f"{Account} has balance {Float:balance}")
Account.user = model.Relationship(f"{Account} belongs to {User}")

Holding = model.Concept("Holding", identify_by={"holding_id": Integer})
Holding.account_id = model.Property(
    f"{Holding} has account id {Integer:holding_account_id}"
)
Holding.stock_id = model.Property(f"{Holding} has stock id {Integer:holding_stock_id}")
Holding.quantity = model.Property(f"{Holding} has quantity {Float:holding_quantity}")
Holding.purchase_price = model.Property(
    f"{Holding} has purchase price {Float:purchase_price}"
)
Holding.account = model.Relationship(f"{Holding} in {Account}")
Holding.stock = model.Relationship(f"{Holding} of {Stock}")

Transaction = model.Concept("Transaction", identify_by={"transaction_id": Integer})
Transaction.user_id = model.Property(
    f"{Transaction} has user id {Integer:txn_user_id}"
)
Transaction.amount = model.Property(f"{Transaction} has amount {Float:txn_amount}")
Transaction.category = model.Property(
    f"{Transaction} has category {String:txn_category}"
)
Transaction.is_flagged_val = model.Property(
    f"{Transaction} flagged {Float:is_flagged_val}"
)
Transaction.user = model.Relationship(f"{Transaction} by {User}")

__all__ = [
    "Account",
    "Holding",
    "Sector",
    "Stock",
    "Transaction",
    "User",
    "model",
]
