"""Subscriber Retention (Snowflake source variant) -- predict per-subscriber
churn risk with a GNN.

Identical ontology, splits, PropertyTransformer, and GNN config as the
shipped `subscriber_retention.py`. The only difference: source data loads
from DEMO_TELCO.RAW Snowflake tables (not bundled CSVs). DEMO_TELCO.RAW
column names match the bundled CSV headers exactly, so the rest of the
pipeline is unchanged.

Run:
    python subscriber_retention_sf.py
"""

import os

import numpy as np
import pandas as pd
import snowflake.connector
from cryptography.hazmat.primitives import serialization

from relationalai.semantics import Any, Float, Integer, Model, String, count, select
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.predictive import GNN, PropertyTransformer

SEED = 42
STREAM_LOGS = False

TRAIN_FRAC = 0.70
VAL_FRAC = 0.15

TOP_N_PER_SEGMENT = 5

EXP_DATABASE = "TELCO_ENRICHMENT"
EXP_SCHEMA = "EXPERIMENTS"

SOURCE_DATABASE = "DEMO_TELCO"
SOURCE_SCHEMA = "RAW"


def _read_sf_table(table: str) -> pd.DataFrame:
    pk_path = os.path.expanduser(
        "~/.snowflake/rai_private_key_new.p8"
    )
    with open(pk_path, "rb") as f:
        pk = serialization.load_pem_private_key(f.read(), password=None)
    pkb = pk.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    with snowflake.connector.connect(
        account="jqb21724",
        user="cameron.afzal@relational.ai",
        private_key=pkb,
        warehouse="DEMOWAREHOUSE",
        role="ACCOUNTADMIN",
        database=SOURCE_DATABASE,
        schema=SOURCE_SCHEMA,
    ) as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM {SOURCE_DATABASE}.{SOURCE_SCHEMA}.{table}")
        return cur.fetch_pandas_all()


model = Model("subscriber_retention_sf_v1")
Concept, Relationship = model.Concept, model.Relationship

sub_df = _read_sf_table("SUBSCRIBERS")
plan_df = _read_sf_table("PLANS_CONTRACTS")
calls_df = _read_sf_table("CALL_DETAIL_RECORDS")

for col in ("SIGNUP_DATE",):
    if col in sub_df.columns:
        sub_df[col] = pd.to_datetime(sub_df[col])
for col in ("CONTRACT_START_DATE", "CONTRACT_END_DATE"):
    if col in plan_df.columns:
        plan_df[col] = pd.to_datetime(plan_df[col])
if "CALL_START_TIME" in calls_df.columns:
    calls_df["CALL_START_TIME"] = pd.to_datetime(calls_df["CALL_START_TIME"])

sub_df = sub_df.drop(columns=["FIRST_NAME", "LAST_NAME", "EMAIL", "PHONE"])

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

Subscriber = Concept("Subscriber", identify_by={"sub_id": String})
model.define(Subscriber.new(model.data(features_df).to_schema()))

Call = Concept("Call")
model.define(Call.new(model.data(calls_df).to_schema()))

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

pt = PropertyTransformer(
    drop=[
        Subscriber.sub_id,
        Subscriber.postal_code,
        Subscriber.churn_risk_score,
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
        Subscriber.pagerank,
    ],
    integer=[
        Subscriber.nps_score,
        Subscriber.data_limit_gb,
        Subscriber.term_months,
        Subscriber.outgoing_calls,
        Subscriber.incoming_calls,
    ],
    datetime=[Subscriber.signup_date],
)

rng = np.random.default_rng(SEED)
shuffled = features_df.sample(frac=1.0, random_state=SEED).reset_index(drop=True)

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
print("Predictive: subscriber churn-risk regression GNN (SF source)")
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
print("Run complete.")
print("=" * 60)
