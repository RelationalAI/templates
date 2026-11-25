"""Load the sample accounts and transactions into the money-laundering motif model."""

from pathlib import Path

import pandas as pd

from .schema import Account, Transaction, model

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# Currency-transaction-report (CTR) threshold from FinCEN 31 CFR 1010.311.
# Layering schemes split deposits into amounts that stay under this line so
# no single transaction triggers a CTR filing.
AMOUNT_THRESHOLD_DOLLARS = 10_000

accounts_csv = pd.read_csv(DATA_DIR / "accounts.csv")
tx_csv = pd.read_csv(DATA_DIR / "transactions.csv")

model.define(Account.new(model.data(accounts_csv).to_schema()))

tx_data = model.data(tx_csv)
model.define(
    t := Transaction.new(tx_id=tx_data.tx_id),
    t.amount_dollars(tx_data.amount_dollars),
    t.ts_minutes(tx_data.ts_minutes),
)
model.define(Transaction.src(Account)).where(
    Transaction.tx_id(tx_data.tx_id),
    Account.id(tx_data.src_id),
)
model.define(Transaction.dst(Account)).where(
    Transaction.tx_id(tx_data.tx_id),
    Account.id(tx_data.dst_id),
)
