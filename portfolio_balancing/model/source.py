"""Load bundled portfolio and market data into the shared model."""

from pathlib import Path

from pandas import read_csv

from .schema import Account, Holding, Sector, Stock, Transaction, User, model

DATA_DIR = Path(__file__).parent.parent / "data"


def load_market_data():
    """Load stock returns, covariance, and sector relationships."""
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
    model.define(Stock.sector_ref(Sector)).where(
        Stock.sector == Sector.sector_name
    )

    return returns_csv, covar_csv


def load_portfolio_data():
    """Load users, accounts, holdings, transactions, and their relationships."""
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
    model.define(Holding.account(Account)).where(
        Holding.account_id == Account.account_id
    )
    model.define(Holding.stock(Stock)).where(Holding.stock_id == Stock.index)

    transactions = read_csv(DATA_DIR / "transactions.csv")
    transactions["is_flagged_int"] = (
        transactions["is_flagged"]
        .astype(str)
        .str.lower()
        .map({"true": 1.0, "false": 0.0})
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


returns_csv, covar_csv = load_market_data()
load_portfolio_data()

__all__ = [
    "DATA_DIR",
    "covar_csv",
    "load_market_data",
    "load_portfolio_data",
    "returns_csv",
]
