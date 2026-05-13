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


# --------------------------------------------------
# Pre-solve invariants
#
# Catch the most common silent-failure modes before the solver runs:
# duplicate keys (would collapse rows) and dangling foreign keys (would
# silently drop transactions from joins, weakening every motif IC that
# walks Transaction.src/dst). Non-positive amounts would make the
# under-threshold IC vacuous and let zero-dollar edges pass as motif
# edges; self-loops would let an account count as both source and
# destination of the same transaction.
# --------------------------------------------------


def _assert_unique_keys(df, key, source):
    dupe_rows = df[df.duplicated(subset=[key], keep=False)]
    if not dupe_rows.empty:
        duplicates = sorted({int(v) for v in dupe_rows[key].tolist()})
        raise ValueError(
            f"{source} has duplicate {key}={duplicates}. Each {key} "
            f"must be unique; duplicates collapse rows on join."
        )


def _assert_no_dangling_fks(child_df, child_col, parent_df, parent_col, source, parent_source):
    parent_ids = set(parent_df[parent_col].unique().tolist())
    dangling = sorted(
        {int(v) for v in child_df[child_col].unique().tolist() if v not in parent_ids}
    )
    if dangling:
        raise ValueError(
            f"{source}.{child_col} references unknown {parent_col}={dangling} "
            f"that does not appear in {parent_source}.{parent_col}. Every "
            f"foreign key must resolve, or the transaction is silently "
            f"dropped from Transaction.src / Transaction.dst joins."
        )


def _assert_positive(df, cols, source):
    cols = cols if isinstance(cols, list) else [cols]
    for c in cols:
        bad = sorted({int(v) for v in df[c].tolist() if int(v) <= 0})
        if bad:
            raise ValueError(
                f"{source} has non-positive {c}={bad}. {c} must be > 0; "
                f"a zero or negative amount would make the under-threshold "
                f"IC vacuous and admit spurious motif edges."
            )


def _assert_non_negative(df, cols, source):
    cols = cols if isinstance(cols, list) else [cols]
    for c in cols:
        bad = sorted({int(v) for v in df[c].tolist() if int(v) < 0})
        if bad:
            raise ValueError(
                f"{source} has negative {c}={bad}. {c} must be >= 0; "
                f"a negative timestamp breaks the burst-window IC, which "
                f"compares (max ts - min ts) across the chosen subset."
            )


def _assert_no_self_loops(df, src_col, dst_col, source):
    self_rows = df[df[src_col] == df[dst_col]]
    if not self_rows.empty:
        bad = sorted({int(v) for v in self_rows[src_col].tolist()})
        raise ValueError(
            f"{source} has self-loop rows where {src_col} == {dst_col} = {bad}. "
            f"A transaction's src and dst must be distinct accounts; a "
            f"self-loop lets one account count as both source and "
            f"destination of the same edge in the motif ICs."
        )


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

    _assert_unique_keys(accounts_csv, "id", "accounts.csv")
    _assert_unique_keys(tx_csv, "tx_id", "transactions.csv")
    _assert_no_dangling_fks(
        tx_csv, "src_id", accounts_csv, "id", "transactions.csv", "accounts.csv"
    )
    _assert_no_dangling_fks(
        tx_csv, "dst_id", accounts_csv, "id", "transactions.csv", "accounts.csv"
    )
    _assert_positive(tx_csv, "amount_dollars", "transactions.csv")
    _assert_non_negative(tx_csv, "ts_minutes", "transactions.csv")
    _assert_no_self_loops(tx_csv, "src_id", "dst_id", "transactions.csv")

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
