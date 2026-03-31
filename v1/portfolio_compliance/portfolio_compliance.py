"""Portfolio Compliance (logic reasoning) template.

This script demonstrates derived business rules in RelationalAI:

- Load sample CSVs describing users, accounts, stocks, holdings, and transactions.
- Define three rules as derived Relationships (boolean flags) on existing concepts.
- Query and display which entities match each rule.

Rules defined:
  1. Holding.is_overconcentrated -- single holding value exceeds 10% of account balance
  2. Account.has_sector_concentration -- total holdings in one sector exceed 30% of account balance
  3. User.is_high_risk_trader -- risk_score > 0.8 AND more than 5 flagged transactions

No optimization solver is used. Rules are pure logic derivations.

    Run:
        `python portfolio_compliance.py`

    Output:
        Prints which entities match each compliance rule.
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Boolean, Float, Integer, Model, String
from relationalai.semantics.std import aggregates

model = Model("portfolio_compliance")
Concept, Property, Relationship = model.Concept, model.Property, model.Relationship

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"

# User concept: account holders with risk profiles.
User = Concept("User", identify_by={"id": Integer})
User.name = Property(f"{User} has {String:name}")
User.risk_score = Property(f"{User} has {Float:risk_score}")
model.define(User.new(model.data(read_csv(DATA_DIR / "users.csv")).to_schema()))

# Account concept: investment accounts owned by users.
Account = Concept("Account", identify_by={"id": Integer})
Account.account_type = Property(f"{Account} has {String:account_type}")
Account.balance = Property(f"{Account} has {Float:balance}")
Account.owner = Relationship(f"{Account} owned by {User}")

acct_data = model.data(read_csv(DATA_DIR / "accounts.csv"))
model.define(
    a := Account.new(
        id=acct_data.id,
        owner=User.filter_by(id=acct_data.user_id),
    ),
    a.account_type(acct_data.account_type),
    a.balance(acct_data.balance),
)

# Stock concept: equities with sector and return attributes.
Stock = Concept("Stock", identify_by={"id": Integer})
Stock.ticker = Property(f"{Stock} has {String:ticker}")
Stock.sector = Property(f"{Stock} has {String:sector}")
Stock.expected_return = Property(f"{Stock} has {Float:expected_return}")
model.define(Stock.new(model.data(read_csv(DATA_DIR / "stocks.csv")).to_schema()))

# Holding concept: stock positions within accounts.
Holding = Concept("Holding", identify_by={"id": Integer})
Holding.quantity = Property(f"{Holding} has {Float:quantity}")
Holding.purchase_price = Property(f"{Holding} has {Float:purchase_price}")
Holding.account = Relationship(f"{Holding} in {Account}")
Holding.stock = Relationship(f"{Holding} of {Stock}")

holding_data = model.data(read_csv(DATA_DIR / "holdings.csv"))
model.define(
    h := Holding.new(
        id=holding_data.id,
        account=Account.filter_by(id=holding_data.account_id),
        stock=Stock.filter_by(id=holding_data.stock_id),
    ),
    h.quantity(holding_data.quantity),
    h.purchase_price(holding_data.purchase_price),
)

# Transaction concept: financial transactions linked to users.
Transaction = Concept("Transaction", identify_by={"id": Integer})
Transaction.amount = Property(f"{Transaction} has {Float:amount}")
Transaction.category = Property(f"{Transaction} has {String:category}")
Transaction.is_flagged = Property(f"{Transaction} has {Boolean:is_flagged}")
Transaction.user = Relationship(f"{Transaction} belongs to {User}")

txn_data = model.data(read_csv(DATA_DIR / "transactions.csv"))
model.define(
    t := Transaction.new(
        id=txn_data.id,
        user=User.filter_by(id=txn_data.user_id),
    ),
    t.amount(txn_data.amount),
    t.category(txn_data.category),
    t.is_flagged(txn_data.is_flagged),
)

# --------------------------------------------------
# Rule 1: Holding.is_overconcentrated
# A single holding's value (quantity * purchase_price) exceeds
# 10% of the account balance.
# --------------------------------------------------

Holding.is_overconcentrated = Relationship(f"{Holding} is overconcentrated")
acct_ref = Account.ref()
model.where(
    Holding.account(acct_ref),
    Holding.quantity * Holding.purchase_price > acct_ref.balance * 0.10,
).define(Holding.is_overconcentrated())

# --------------------------------------------------
# Rule 2: Account.has_sector_concentration
# Total holdings in a single sector exceed 30% of the account
# balance. Uses aggregation with .per(account, sector) to group
# holding values by account and sector before comparing to the
# threshold.
# --------------------------------------------------

Account.has_sector_concentration = Relationship(f"{Account} has sector concentration")
h_ref = Holding.ref()
s_ref = Stock.ref()
a_ref = Account.ref()

sector_total = (
    aggregates.sum(h_ref.quantity * h_ref.purchase_price)
    .per(a_ref, s_ref.sector)
    .where(
        h_ref.account(a_ref),
        h_ref.stock(s_ref),
    )
)

model.where(
    sector_total > a_ref.balance * 0.30,
).define(Account.has_sector_concentration(a_ref))

# --------------------------------------------------
# Rule 3: User.is_high_risk_trader
# A user has risk_score > 0.8 AND more than 5 flagged
# transactions. Combines a property threshold with an
# aggregation count.
# --------------------------------------------------

User.is_high_risk_trader = Relationship(f"{User} is high risk trader")
txn_ref = Transaction.ref()

flagged_count = (
    aggregates.count(txn_ref)
    .per(User)
    .where(
        txn_ref.user(User),
        txn_ref.is_flagged == True,
    )
)

model.where(
    User.risk_score > 0.8,
    flagged_count > 5,
).define(User.is_high_risk_trader())

# --------------------------------------------------
# Query results
# --------------------------------------------------

print("=== Rule 1: Overconcentrated Holdings (value > 10% of account balance) ===\n")
model.select(
    Holding.id.alias("holding_id"),
    Holding.stock.ticker.alias("ticker"),
    Holding.stock.sector.alias("sector"),
    Holding.quantity.alias("quantity"),
    Holding.purchase_price.alias("purchase_price"),
    Holding.account.balance.alias("account_balance"),
).where(Holding.is_overconcentrated()).inspect()

print("\n=== Rule 2: Sector Concentration (sector > 30% of account balance) ===\n")
model.select(
    Account.id.alias("account_id"),
    Account.owner.name.alias("owner"),
    Account.account_type.alias("account_type"),
    Account.balance.alias("balance"),
).where(Account.has_sector_concentration()).inspect()

print("\n=== Rule 3: High-Risk Traders (risk_score > 0.8 AND >5 flagged txns) ===\n")
model.select(
    User.id.alias("user_id"),
    User.name.alias("name"),
    User.risk_score.alias("risk_score"),
).where(User.is_high_risk_trader()).inspect()
