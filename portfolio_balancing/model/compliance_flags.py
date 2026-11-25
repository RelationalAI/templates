"""Portfolio compliance rules: each holding's value and share of its account balance, the overconcentrated
holdings, each account's exposure to each sector and the concentrated sector positions, and the high-risk
traders."""

from relationalai.semantics import Float, sum

from .schema import Account, Holding, Sector, Stock, Transaction, User, model

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

POSITION_LIMIT = 0.15  # max fraction per stock in Stage 1 compliance rules
SECTOR_LIMIT = 0.30  # max fraction of budget per sector (both stages)

# --------------------------------------------------
# Stage 1: Rules -- compliance flags
# --------------------------------------------------

# Derived holding value = quantity * purchase_price.
model.define(Holding.value(Holding.quantity * Holding.purchase_price))

# Rule 1: Overconcentrated holdings -- position value > POSITION_LIMIT of balance.
Holding.share_of_balance = model.Property(f"{Holding} has {Float:share_of_balance}")
AccountR1 = Account.ref()
model.where(Holding.account(AccountR1)).define(
    Holding.share_of_balance(Holding.value / AccountR1.balance)
)
model.where(
    Holding.account(AccountR1),
    Holding.value > POSITION_LIMIT * AccountR1.balance,
).define(Holding.is_overconcentrated())

# Rule 2: Sector concentration -- total sector exposure > SECTOR_LIMIT of balance.
# An account has one exposure to each sector it holds.
SectorExposure = model.Concept(
    "SectorExposure", identify_by={"account": Account, "sector": Sector}
)
SectorExposure.exposure = model.Property(f"{SectorExposure} has {Float:sector_exposure}")
SectorExposure.share_of_balance = model.Property(
    f"{SectorExposure} has {Float:sector_share_of_balance}"
)
SectorExposure.is_concentrated = model.Relationship(f"{SectorExposure} is concentrated")

HoldingSC = Holding.ref()
StockSC = Stock.ref()
AccountSC = Account.ref()
SectorSC = Sector.ref()

model.where(
    Holding.account(AccountSC),
    Holding.stock(StockSC),
    StockSC.sector_ref(SectorSC),
).define(SectorExposure.new(account=AccountSC, sector=SectorSC))

model.define(
    SectorExposure.exposure(
        sum(HoldingSC, HoldingSC.value)
        .per(SectorExposure)
        .where(
            HoldingSC.account(SectorExposure.account),
            HoldingSC.stock(StockSC),
            StockSC.sector_ref(SectorExposure.sector),
        )
    )
)
model.define(
    SectorExposure.share_of_balance(SectorExposure.exposure / SectorExposure.account.balance)
)
model.where(
    SectorExposure.exposure > SECTOR_LIMIT * SectorExposure.account.balance
).define(SectorExposure.is_concentrated())

# A holding is in a concentrated sector position when its account's exposure to the
# holding's sector is concentrated.
model.where(
    Holding.account(AccountSC),
    Holding.stock(StockSC),
    StockSC.sector_ref(SectorSC),
    SectorExposure.account == AccountSC,
    SectorExposure.sector == SectorSC,
    SectorExposure.is_concentrated(),
).define(Holding.is_sector_concentrated())

# Rule 3: High-risk traders -- risk_score > 0.8 AND >5 flagged transactions.
TransactionHR = Transaction.ref()
flagged_count = (
    sum(TransactionHR.is_flagged_val)
    .where(
        TransactionHR.user(User),
    )
    .per(User)
)

model.where(
    User.risk_score > 0.8,
    flagged_count > 5,
).define(User.is_high_risk_trader())
