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

# Load the subscribers, their plan contracts, and the calls.
sub_df = pd.read_csv(DATA_DIR / "subscribers.csv", parse_dates=["SIGNUP_DATE"])
plan_df = pd.read_csv(
    DATA_DIR / "plans_contracts.csv",
    usecols=[
        "SUB_ID",
        "PLAN_TYPE",
        "MONTHLY_RATE_USD",
        "DATA_LIMIT_GB",
        "TERM_MONTHS",
        "AUTO_RENEW",
        "EARLY_TERMINATION_FEE_USD",
    ],
)
calls_df = pd.read_csv(
    DATA_DIR / "call_detail_records.csv", parse_dates=["CALL_START_TIME"]
)

# Drop unused identifier columns -- not useful as features. A source that already
# omits them loads unchanged.
sub_df = sub_df.drop(
    columns=["FIRST_NAME", "LAST_NAME", "EMAIL", "PHONE"], errors="ignore"
)

model.define(Subscriber.new(model.data(sub_df).to_schema()))
model.define(Call.new(model.data(calls_df).to_schema()))

# Each subscriber has exactly one active contract (1:1 denormalization): bind its plan
# attributes onto the subscriber. A subscriber without a contract has no plan attributes.
plan_data = model.data(plan_df)
model.where(Subscriber.sub_id == plan_data.SUB_ID).define(
    Subscriber.plan_type(plan_data.PLAN_TYPE),
    Subscriber.monthly_rate_usd(plan_data.MONTHLY_RATE_USD),
    Subscriber.data_limit_gb(plan_data.DATA_LIMIT_GB),
    Subscriber.term_months(plan_data.TERM_MONTHS),
    Subscriber.auto_renew(plan_data.AUTO_RENEW),
    Subscriber.early_termination_fee_usd(plan_data.EARLY_TERMINATION_FEE_USD),
)

# --------------------------------------------------
# Train / Val / Test split
# --------------------------------------------------
# Build train/val/test splits in pandas. Stratified by segment so each split
# preserves the segment mix; CHURN_RISK_SCORE distribution carries through. The shuffle and
# the per-segment permutation are seeded, and PyRel has no seeded random primitive.
rng = np.random.default_rng(SEED)
shuffled = sub_df.sample(frac=1.0, random_state=SEED).reset_index(drop=True)

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
