"""Subscriber Retention -- predict per-subscriber churn risk with a GNN.

Runs an end-to-end predictive pipeline on a small bundled telco dataset
(~1.2K subscribers, ~6K call-detail records). All data loads from CSVs via
`model.data()`; no Snowflake data loading, no GPU required.

Stages:
  1. Graph    -- PageRank on a directed Subscriber -> Subscriber call graph,
                 bound to `Subscriber.pagerank` and fed to the GNN as a
                 continuous node feature.
  2. Rules    -- derived `Subscriber.outgoing_calls` and `incoming_calls`
                 Properties capturing call-volume signal, fed as integer
                 features.
  3. Predictive -- GNN regression on `Subscriber.churn_risk_score` over
                   demographic + plan + call-graph features.
  4. Reporting -- top-N at-risk subscribers per segment for retention
                  targeting.

The CHURN_RISK_SCORE target is a continuous 0-1 risk score sourced from the
existing analyst-facing risk model in DEMO_TELCO.RAW.SUBSCRIBERS. Customers
adapting this template would replace it with their own labelled churn
ground-truth (binary outcome) -- the regression scaffold transfers directly
to a binary_classification task by switching `task_type` and the target
type. See README "Customize this template" for the swap.

Run:
    python subscriber_retention.py

Output:
    Subscriber-count summary, GNN training metrics (RMSE on validation),
    top-15 highest-predicted-risk subscribers per segment.
"""

from pathlib import Path

import numpy as np
import pandas as pd
from relationalai.semantics import Any, Float, Integer, Model, String, count, select
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.predictive import GNN, PropertyTransformer

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

SEED = 42
STREAM_LOGS = False
DATA_DIR = Path(__file__).parent / "data" / "telco_mini"

TRAIN_FRAC = 0.70
VAL_FRAC = 0.15
# TEST_FRAC = 0.15 (remainder)

TOP_N_PER_SEGMENT = 5

# RelationalAI's predictive reasoner writes GNN experiment artifacts to a
# Snowflake schema that the RELATIONALAI native app must have write access
# to. Set EXP_DATABASE to a database you own; the schema EXPERIMENTS will
# be created on first run. See README "Prerequisites" for the one-time
# setup DDL.
EXP_DATABASE = "TELCO_ENRICHMENT"
EXP_SCHEMA = "EXPERIMENTS"

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

model = Model("subscriber_retention_local")
Concept, Relationship = model.Concept, model.Relationship

# Load and denormalize source data into a single Subscriber feature table.
sub_df = pd.read_csv(DATA_DIR / "subscribers.csv", parse_dates=["SIGNUP_DATE"])
plan_df = pd.read_csv(
    DATA_DIR / "plans_contracts.csv",
    parse_dates=["CONTRACT_START_DATE", "CONTRACT_END_DATE"],
)
calls_df = pd.read_csv(
    DATA_DIR / "call_detail_records.csv", parse_dates=["CALL_START_TIME"]
)

# Drop PII columns before bundling into the feature table -- not useful as
# features, and we don't want them exposed in template-bundled CSVs.
sub_df = sub_df.drop(columns=["FIRST_NAME", "LAST_NAME", "EMAIL", "PHONE"])

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

# Subscriber concept: one row per subscriber with denormalized plan attrs.
Subscriber = Concept("Subscriber", identify_by={"sub_id": String})
model.define(Subscriber.new(model.data(features_df).to_schema()))

# Call concept: edge-intermediary for the Subscriber -> Subscriber call
# graph. No identify_by (the CDR_ID is irrelevant downstream); the edges are
# the only thing we need.
Call = Concept("Call")
model.define(Call.new(model.data(calls_df).to_schema()))

# --------------------------------------------------
# Stage 1: Graph -- PageRank on the call graph
# --------------------------------------------------
# Build a directed weighted Subscriber -> Subscriber graph with one edge per
# call. PageRank scores act as a "social influence" continuous feature.

call_graph = Graph(
    model,
    directed=True,
    weighted=False,
    node_concept=Subscriber,
    aggregator="sum",
)
caller = Subscriber.ref()
callee = Subscriber.ref()
call_ref = Call.ref()
model.define(call_graph.Edge.new(src=caller, dst=callee)).where(
    call_ref.caller_sub_id == caller.sub_id,
    call_ref.callee_sub_id == callee.sub_id,
)

pagerank_rel = call_graph.pagerank()
Subscriber.pagerank = model.Property(f"{Subscriber} has {Float:pagerank}")
sub_pr = Subscriber.ref()
score_pr = Float.ref()
model.define(sub_pr.pagerank(score_pr)).where(pagerank_rel(sub_pr, score_pr))

# --------------------------------------------------
# Stage 2: Rules -- call-volume features per subscriber
# --------------------------------------------------
# Outgoing-call count is a derivation rule (count aggregate per subscriber).
# Mirror pattern from fraud_detection_local: explicit Property bound via
# count(...).per(Subscriber).where(...).

Subscriber.outgoing_calls = model.Property(
    f"{Subscriber} has {Integer:outgoing_calls}"
)
model.define(
    Subscriber.outgoing_calls(count(Call).per(Subscriber))
).where(Call.caller_sub_id == Subscriber.sub_id)

Subscriber.incoming_calls = model.Property(
    f"{Subscriber} has {Integer:incoming_calls}"
)
model.define(
    Subscriber.incoming_calls(count(Call).per(Subscriber))
).where(Call.callee_sub_id == Subscriber.sub_id)

# --------------------------------------------------
# PropertyTransformer -- declare feature types
# --------------------------------------------------

pt = PropertyTransformer(
    drop=[
        Subscriber.sub_id,  # PK -- graph carries identity
        Subscriber.postal_code,  # high-cardinality int ID; noise as a feature
    ],
    category=[
        Subscriber.subscriber_type,
        Subscriber.segment,
        Subscriber.status,
        Subscriber.plan_type,
        Subscriber.auto_renew,
    ],
    continuous=[
        Subscriber.lifetime_value_usd,
        Subscriber.monthly_rate_usd,
        Subscriber.early_termination_fee_usd,
        Subscriber.pagerank,  # graph-reasoner feature (Stage 1)
    ],
    integer=[
        Subscriber.nps_score,
        Subscriber.data_limit_gb,
        Subscriber.term_months,
        Subscriber.outgoing_calls,  # rule-derived feature (Stage 2)
        Subscriber.incoming_calls,  # rule-derived feature (Stage 2)
    ],
    datetime=[Subscriber.signup_date],
)

# --------------------------------------------------
# Stage 3: Predictive -- GNN regression on CHURN_RISK_SCORE
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

print(f"Subscribers: {len(features_df)}  Calls: {len(calls_df)}")
print(
    f"Splits: train={len(train_df)}  val={len(val_df)}  test={len(test_df)}  (stratified by SEGMENT)"
)
print(
    f"CHURN_RISK_SCORE: min={features_df['CHURN_RISK_SCORE'].min():.2f}  "
    f"mean={features_df['CHURN_RISK_SCORE'].mean():.2f}  "
    f"max={features_df['CHURN_RISK_SCORE'].max():.2f}"
)

TrainTable = Concept("TrainTable")
ValTable = Concept("ValTable")
TestTable = Concept("TestTable")
model.define(TrainTable.new(model.data(train_df).to_schema()))
model.define(ValTable.new(model.data(val_df).to_schema()))
model.define(TestTable.new(model.data(test_df).to_schema()))

# Regression task relationships per the rai-predictive-modeling skill
# (no time column -- prediction is on subscriber state, not per-call events).
Train = Relationship(f"{Subscriber} has {Any:risk}")
model.define(Train(Subscriber, TrainTable.churn_risk_score)).where(
    Subscriber.sub_id == TrainTable.sub_id
)
Val = Relationship(f"{Subscriber} has {Any:risk}")
model.define(Val(Subscriber, ValTable.churn_risk_score)).where(
    Subscriber.sub_id == ValTable.sub_id
)
Test = Relationship(f"{Subscriber}")
model.define(Test(Subscriber)).where(Subscriber.sub_id == TestTable.sub_id)

print("\n" + "=" * 60)
print("Stage 3: Predictive -- subscriber churn-risk regression GNN (CPU)")
print("=" * 60)

gnn = GNN(
    exp_database=EXP_DATABASE,
    exp_schema=EXP_SCHEMA,
    graph=call_graph,
    property_transformer=pt,
    train=Train,
    validation=Val,
    task_type="regression",
    eval_metric="rmse",
    has_time_column=False,
    stream_logs=STREAM_LOGS,
    seed=SEED,
    device="cpu",
    n_epochs=20,
    lr=0.005,
)
gnn.fit()
Subscriber.predictions = gnn.predictions(domain=Test)

# --------------------------------------------------
# Stage 4: Reporting -- highest-predicted-risk subscribers per segment
# --------------------------------------------------

print("\n" + "=" * 60)
print(f"Top {TOP_N_PER_SEGMENT} highest-predicted-risk subscribers per segment")
print("=" * 60)

sub_ref = Subscriber.ref()
risk_ref = Float.ref()
results_df = (
    select(
        sub_ref.sub_id.alias("sub_id"),
        sub_ref.segment.alias("segment"),
        sub_ref.subscriber_type.alias("type"),
        sub_ref.lifetime_value_usd.alias("lifetime_value"),
        sub_ref.churn_risk_score.alias("actual_risk"),
        risk_ref.alias("predicted_risk"),
    )
    .where(
        sub_ref.predictions.predicted_value(risk_ref),
    )
    .to_df()
)

if results_df.empty:
    print("(no predictions returned)")
else:
    results_df["predicted_risk"] = results_df["predicted_risk"].astype(float)
    results_df["actual_risk"] = results_df["actual_risk"].astype(float)
    for seg, group in results_df.groupby("segment"):
        top = group.sort_values("predicted_risk", ascending=False).head(
            TOP_N_PER_SEGMENT
        )
        print(f"\n[{seg}]  ({len(group)} test subscribers)")
        print(top.to_string(index=False))

    rmse = float(
        ((results_df["predicted_risk"] - results_df["actual_risk"]) ** 2).mean() ** 0.5
    )
    print(f"\nTest-set RMSE: {rmse:.4f}")

print("\n" + "=" * 60)
print("Local run complete.")
print("=" * 60)
