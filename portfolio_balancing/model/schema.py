"""Semantic schema for the portfolio template: stocks, accounts, holdings, scenarios, and frontier points."""

from relationalai.semantics import Float, Integer, Model, String

model = Model("portfolio")

Stock = model.Concept("Stock", identify_by={"index": Integer})
Stock.ticker = model.Property(f"{Stock} has ticker {String:stock_ticker}")
Stock.sector = model.Property(f"{Stock} has sector {String:stock_sector}")
Stock.returns = model.Property(f"{Stock} has {Float:returns}")
Stock.covar = model.Property(f"{Stock} and {Stock} have {Float:covar}")
Stock.variance = model.Property(f"{Stock} has {Float:stock_variance}")
Stock.volatility = model.Property(f"{Stock} has {Float:stock_volatility}")
Stock.correlation = model.Property(
    f"{Stock} and {Stock} have correlation {Float:stock_correlation}"
)
Stock.cluster = model.Property(f"{Stock} in cluster {Integer:cluster_id}")
Stock.sharpe = model.Property(f"{Stock} has Sharpe {Float:stock_sharpe}")
Stock.cluster_max_sharpe = model.Property(
    f"{Stock} has cluster max Sharpe {Float:cluster_max_sharpe}"
)
Stock.is_representative = model.Relationship(f"{Stock} is cluster representative")
Stock.is_non_representative = model.Relationship(
    f"{Stock} is not cluster representative"
)

Sector = model.Concept("Sector", identify_by={"sector_name": String})
Stock.sector_ref = model.Relationship(f"{Stock} in {Sector}")

User = model.Concept("User", identify_by={"user_id": Integer})
User.user_name = model.Property(f"{User} has name {String:user_name}")
User.risk_score = model.Property(f"{User} has risk score {Float:risk_score}")
User.is_high_risk_trader = model.Relationship(f"{User} is high risk trader")

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
Holding.value = model.Property(f"{Holding} has value {Float:holding_value}")
Holding.account = model.Relationship(f"{Holding} in {Account}")
Holding.stock = model.Relationship(f"{Holding} of {Stock}")
Holding.is_overconcentrated = model.Relationship(f"{Holding} is overconcentrated")
Holding.is_sector_concentrated = model.Relationship(
    f"{Holding} is in a concentrated sector position"
)

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

Regime = model.Concept("Regime", identify_by={"regime_name": String})

Scenario = model.Concept("Scenario", identify_by={"name": String})
Scenario.budget = model.Property(f"{Scenario} has {Float:budget}")
Scenario.regime = model.Property(f"{Scenario} in {Regime}")

Stock.regime_covar = model.Property(
    f"{Stock} and {Stock} in {Regime} have {Float:regime_covar}"
)
Stock.x_quantity = model.Property(f"{Stock} in {Scenario} has {Float:quantity}")

# One solve's published result for one Scenario: its expected return, its risk (variance),
# the shadow price of its return floor, and the stocks it allocates.
FrontierPoint = model.Concept(
    "FrontierPoint",
    identify_by={"scenario_label": String, "solve": String},
)
FrontierPoint.scenario = model.Property(f"{FrontierPoint} for {Scenario}")
FrontierPoint.return_value = model.Property(
    f"{FrontierPoint} has return {Float:fp_return}"
)
FrontierPoint.risk = model.Property(f"{FrontierPoint} has risk {Float:fp_risk}")
FrontierPoint.marginal_risk_per_return = model.Property(
    f"{FrontierPoint} has marginal {Float:fp_marginal}"
)
FrontierPoint.allocates = model.Relationship(
    f"{FrontierPoint} allocates {Stock} amount {Float:fp_amount}"
)

__all__ = [
    "Account",
    "FrontierPoint",
    "Holding",
    "Regime",
    "Scenario",
    "Sector",
    "Stock",
    "Transaction",
    "User",
    "model",
]
