"""Data loaders and source-to-schema mappings for fraud detection."""

from pathlib import Path

import numpy as np
from pandas import read_csv

from .schema import (
    Account,
    Test,
    TestTable,
    Train,
    TrainTable,
    Transaction,
    Val,
    ValTable,
    model,
)

PAYSIM_DIR = Path(__file__).parents[1] / "data" / "paysim_mini"


def load_local_data(
    data_dir: Path = PAYSIM_DIR,
    *,
    large_amount_threshold: float,
    small_audit_cost_hours: float,
    large_audit_cost_hours: float,
) -> None:
    """Load bundled PaySim CSVs and map them to the shared schema."""
    accounts_df = read_csv(data_dir / "accounts.csv")
    transactions_df = read_csv(data_dir / "transactions.csv", parse_dates=["step_ts"])
    transactions_df["audit_cost"] = np.where(
        transactions_df["amount"] > large_amount_threshold,
        large_audit_cost_hours,
        small_audit_cost_hours,
    )
    train_df = read_csv(data_dir / "train.csv", parse_dates=["step_ts"])
    val_df = read_csv(data_dir / "val.csv", parse_dates=["step_ts"])
    test_df = read_csv(data_dir / "test.csv", parse_dates=["step_ts"])

    model.define(Account.new(model.data(accounts_df).to_schema()))
    model.define(Transaction.new(model.data(transactions_df).to_schema()))
    model.define(TrainTable.new(model.data(train_df).to_schema()))
    model.define(ValTable.new(model.data(val_df).to_schema()))
    model.define(TestTable.new(model.data(test_df).to_schema()))

    model.define(Transaction.sender(Transaction, Account)).where(
        Transaction.name_orig == Account.account_id
    )
    model.define(Transaction.receiver(Transaction, Account)).where(
        Transaction.name_dest == Account.account_id
    )
    model.define(Train(Transaction, TrainTable.step_ts, TrainTable.is_fraud)).where(
        Transaction.transaction_id == TrainTable.transaction_id
    )
    model.define(Val(Transaction, ValTable.step_ts, ValTable.is_fraud)).where(
        Transaction.transaction_id == ValTable.transaction_id
    )
    model.define(Test(Transaction, TestTable.step_ts)).where(
        Transaction.transaction_id == TestTable.transaction_id
    )


def load_snowflake_data(database: str, schema: str) -> None:
    """Load PaySim Snowflake tables and map them to the shared schema."""
    accounts = model.Table(f"{database}.{schema}.ACCOUNTS")
    transactions = model.Table(f"{database}.{schema}.TRANSACTIONS")
    train = model.Table(f"{database}.{schema}.TRAIN")
    validation = model.Table(f"{database}.{schema}.VAL")
    test = model.Table(f"{database}.{schema}.TEST")

    model.define(Account.new(accounts.to_schema()))
    model.define(Transaction.new(transactions.to_schema()))
    model.define(TrainTable.new(train.to_schema()))
    model.define(ValTable.new(validation.to_schema()))
    model.define(TestTable.new(test.to_schema()))

    model.define(Transaction.sender(Transaction, Account)).where(
        Transaction.name_orig == Account.account_id
    )
    model.define(Transaction.receiver(Transaction, Account)).where(
        Transaction.name_dest == Account.account_id
    )
    model.define(Train(Transaction, TrainTable.step_ts, TrainTable.is_fraud)).where(
        Transaction.transaction_id == TrainTable.transaction_id
    )
    model.define(Val(Transaction, ValTable.step_ts, ValTable.is_fraud)).where(
        Transaction.transaction_id == ValTable.transaction_id
    )
    model.define(Test(Transaction, TestTable.step_ts)).where(
        Transaction.transaction_id == TestTable.transaction_id
    )
