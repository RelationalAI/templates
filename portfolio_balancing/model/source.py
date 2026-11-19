"""Load the sample portfolio and market data and the budget-by-regime scenarios into the portfolio model."""

from pathlib import Path

from pandas import read_csv

from .schema import (
    Account,
    Holding,
    Regime,
    Scenario,
    Sector,
    Stock,
    Transaction,
    User,
    model,
)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# --------------------------------------------------
# Market data: stocks, covariance, sectors
# --------------------------------------------------

returns_csv = read_csv(DATA_DIR / "returns.csv")
covar_csv = read_csv(DATA_DIR / "covar.csv")

model.define(Stock.new(model.data(returns_csv).to_schema()))

paired_stock = Stock.ref()
covar_data = model.data(covar_csv)
model.where(
    Stock.index(covar_data.i),
    paired_stock.index(covar_data.j),
).define(Stock.covar(Stock, paired_stock, covar_data.covar))

model.define(Sector.new(sector_name=Stock.sector))
model.define(Stock.sector_ref(Sector)).where(Stock.sector == Sector.sector_name)

# --------------------------------------------------
# Portfolio data: users, accounts, holdings, transactions
# --------------------------------------------------

user_data = model.data(read_csv(DATA_DIR / "users.csv"))
model.define(
    user := User.new(user_id=user_data["id"]),
    user.user_name(user_data["name"]),
    user.risk_score(user_data["risk_score"]),
)

account_data = model.data(read_csv(DATA_DIR / "accounts.csv"))
model.define(
    account := Account.new(account_id=account_data["id"]),
    account.user_id(account_data["user_id"]),
    account.account_type(account_data["account_type"]),
    account.balance(account_data["balance"]),
)
model.define(Account.user(User)).where(Account.user_id == User.user_id)

holding_data = model.data(read_csv(DATA_DIR / "holdings.csv"))
model.define(
    holding := Holding.new(holding_id=holding_data["id"]),
    holding.account_id(holding_data["account_id"]),
    holding.stock_id(holding_data["stock_id"]),
    holding.quantity(holding_data["quantity"]),
    holding.purchase_price(holding_data["purchase_price"]),
)
model.define(Holding.account(Account)).where(Holding.account_id == Account.account_id)
model.define(Holding.stock(Stock)).where(Holding.stock_id == Stock.index)

transactions = read_csv(DATA_DIR / "transactions.csv")
transactions["is_flagged_int"] = (
    transactions["is_flagged"].astype(str).str.lower().map({"true": 1.0, "false": 0.0})
)
transaction_data = model.data(transactions)
model.define(
    transaction := Transaction.new(transaction_id=transaction_data["id"]),
    transaction.user_id(transaction_data["user_id"]),
    transaction.amount(transaction_data["amount"]),
    transaction.category(transaction_data["category"]),
    transaction.is_flagged_val(transaction_data["is_flagged_int"]),
)
model.define(Transaction.user(User)).where(Transaction.user_id == User.user_id)

# --------------------------------------------------
# Scenarios: budget x market regime
# --------------------------------------------------

# Two Regime instances ("base", "crisis") feed regime-conditioned covariance.
model.define(Regime.new(regime_name="base"))
model.define(Regime.new(regime_name="crisis"))

SCENARIOS = [
    ("base_500", 500, "base"),
    ("base_1000", 1000, "base"),
    ("base_2000", 2000, "base"),
    ("crisis_500", 500, "crisis"),
    ("crisis_1000", 1000, "crisis"),
    ("crisis_2000", 2000, "crisis"),
]
scenario_data = model.data(SCENARIOS, columns=["name", "budget", "regime"])
model.define(
    s := Scenario.new(name=scenario_data["name"]),
    s.budget(scenario_data["budget"]),
)
# Link Scenario to Regime by matching the regime name from the data.
scenario_link_ref = Scenario.ref()
regime_link_ref = Regime.ref()
model.where(
    scenario_link_ref.name == scenario_data["name"],
    regime_link_ref.regime_name == scenario_data["regime"],
).define(scenario_link_ref.regime(regime_link_ref))
