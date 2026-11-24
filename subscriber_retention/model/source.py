"""Bundled telco CSVs and the stratified train / validation / test split."""

from pathlib import Path

import numpy as np
import pandas as pd

from .schema import (
    Call,
    Subscriber,
    Test,
    TestTable,
    Train,
    TrainTable,
    Val,
    ValTable,
    model,
)

SEED = 42
DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "telco_mini"

TRAIN_FRAC = 0.70
VAL_FRAC = 0.15
# TEST_FRAC = 0.15 (remainder)

# Load and denormalize source data into a single Subscriber feature table.
sub_df = pd.read_csv(DATA_DIR / "subscribers.csv", parse_dates=["SIGNUP_DATE"])
plan_df = pd.read_csv(
    DATA_DIR / "plans_contracts.csv",
    parse_dates=["CONTRACT_START_DATE", "CONTRACT_END_DATE"],
)
calls_df = pd.read_csv(
    DATA_DIR / "call_detail_records.csv", parse_dates=["CALL_START_TIME"]
)

# Drop unused identifier columns -- not useful as features. A source that already
# omits them loads unchanged.
sub_df = sub_df.drop(
    columns=["FIRST_NAME", "LAST_NAME", "EMAIL", "PHONE"], errors="ignore"
)

# Each subscriber has exactly one active contract; left-join plan attrs onto
# the subscriber row (1:1 denormalization).
plan_keep = plan_df[
    [
        "SUB_ID",
        "PLAN_TYPE",
        "MONTHLY_RATE_USD",
        "DATA_LIMIT_GB",
        "TERM_MONTHS",
        "AUTO_RENEW",
        "EARLY_TERMINATION_FEE_USD",
    ]
]
features_df = sub_df.merge(plan_keep, on="SUB_ID", how="left")

model.define(Subscriber.new(model.data(features_df).to_schema()))
model.define(Call.new(model.data(calls_df).to_schema()))

# --------------------------------------------------
# Train / Val / Test split
# --------------------------------------------------
# Build train/val/test splits in pandas. Stratified by segment so each split
# preserves the segment mix; CHURN_RISK_SCORE distribution carries through.
rng = np.random.default_rng(SEED)
shuffled = features_df.sample(frac=1.0, random_state=SEED).reset_index(drop=True)

# Stratify split by segment to keep distribution stable across splits.
train_idx, val_idx, test_idx = [], [], []
for seg, group in shuffled.groupby("SEGMENT", group_keys=False):
    n = len(group)
    n_train = int(n * TRAIN_FRAC)
    n_val = int(n * VAL_FRAC)
    idx = rng.permutation(group.index.values)
    train_idx.extend(idx[:n_train])
    val_idx.extend(idx[n_train : n_train + n_val])
    test_idx.extend(idx[n_train + n_val :])

train_df = shuffled.loc[train_idx, ["SUB_ID", "CHURN_RISK_SCORE"]].reset_index(drop=True)
val_df = shuffled.loc[val_idx, ["SUB_ID", "CHURN_RISK_SCORE"]].reset_index(drop=True)
test_df = shuffled.loc[test_idx, ["SUB_ID"]].reset_index(drop=True)

model.define(TrainTable.new(model.data(train_df).to_schema()))
model.define(ValTable.new(model.data(val_df).to_schema()))
model.define(TestTable.new(model.data(test_df).to_schema()))

model.define(Train(Subscriber, TrainTable.churn_risk_score)).where(
    Subscriber.sub_id == TrainTable.sub_id
)
model.define(Val(Subscriber, ValTable.churn_risk_score)).where(
    Subscriber.sub_id == ValTable.sub_id
)
model.define(Test(Subscriber)).where(Subscriber.sub_id == TestTable.sub_id)
