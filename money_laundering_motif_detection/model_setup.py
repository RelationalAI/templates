"""Shared model setup for the three money-laundering motif-detection runners.

This module owns the ontology and data load that all three motifs share --
accounts, transactions, beneficial-owner clusters, KYC tier, jurisdiction.
Each motif runner (`motif_butterfly.py`, `motif_smurf_army.py`,
`motif_kyc_burst.py`) imports `create_model()` from here and then adds its
own decision properties + constraints + solve.
"""

from pathlib import Path

import pandas as pd
from relationalai.semantics import Integer, Model, String

DATA_DIR = Path(__file__).parent / "data"

# Currency-transaction-report (CTR) threshold from FinCEN 31 CFR 1010.311.
# Layering schemes split deposits into amounts that stay under this line so
# no single transaction triggers a CTR filing.
AMOUNT_THRESHOLD_DOLLARS = 10_000


def create_model():
    """Build the shared semantic model: accounts and transactions.

    Returns
    -------
    model : Model
        The Semantics model container.
    Account : Concept
        Account concept with name, bo_id, kyc_tier, jurisdiction properties.
    Transaction : Concept
        Transaction concept with src, dst, amount_dollars, ts_minutes.
    """
    accounts_csv = pd.read_csv(DATA_DIR / "accounts.csv")
    tx_csv = pd.read_csv(DATA_DIR / "transactions.csv")

    model = Model("money_laundering_motif_detection")

    # Concept: bank account.
    Account = model.Concept("Account", identify_by={"id": Integer})
    Account.name = model.Property(f"{Account} has {String:name}")
    Account.bo_id = model.Property(f"{Account} owned by {Integer:bo_id}")
    Account.kyc_tier = model.Property(f"{Account} has {String:kyc_tier}")
    Account.jurisdiction = model.Property(f"{Account} from {String:jurisdiction}")
    model.define(Account.new(model.data(accounts_csv).to_schema()))

    # Concept: transaction (a directed edge in the graph).
    Transaction = model.Concept("Transaction", identify_by={"tx_id": Integer})
    Transaction.src = model.Property(f"{Transaction} from {Account:src}")
    Transaction.dst = model.Property(f"{Transaction} to {Account:dst}")
    Transaction.amount_dollars = model.Property(f"{Transaction} has {Integer:amount_dollars}")
    Transaction.ts_minutes = model.Property(f"{Transaction} occurs at {Integer:ts_minutes}")
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

    return model, Account, Transaction
