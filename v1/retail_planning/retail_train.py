"""Retail Planning -- train phase.

Trains three GNN models (item-sales regression, user-churn classification,
user-item purchase link prediction) and registers each to the Snowflake model
registry. Pair with `retail_optimize.py` for the optimization phase.

Use this split when you want to train once and re-run optimization many times
with different parameters (`CHURN_DISCOUNT_WEIGHT`, `UNMET_PENALTY`, etc).

For an all-in-one single-script alternative, see `retail_planning.py`.

Run:
    python retail_train.py
"""

from relationalai.semantics import Any
from relationalai.semantics.reasoners.predictive import GNN

from _retail_setup import (
    Article,
    CHURN_MODEL_NAME,
    Concept,
    Customer,
    DATABASE,
    GNN_EXP_DATABASE,
    GNN_EXP_SCHEMA,
    MODEL_REGISTRY_DATABASE,
    MODEL_REGISTRY_SCHEMA,
    MODEL_VERSION,
    PURCHASE_MODEL_NAME,
    Relationship,
    SALES_MODEL_NAME,
    SEED,
    STREAM_LOGS,
    Table,
    TASK_CHURN_SCHEMA,
    TASK_PURCHASE_SCHEMA,
    TASK_SALES_SCHEMA,
    graph,
    model,
    pt,
    report,
)
from relationalai.semantics import select

# --------------------------------------------------
# Sales -- regression
# --------------------------------------------------
SalesTrainTable = Concept("SalesTrainTable")
SalesValTable = Concept("SalesValTable")

model.define(SalesTrainTable.new(
    Table(f"{DATABASE}.{TASK_SALES_SCHEMA}.TRAIN").to_schema()))
model.define(SalesValTable.new(
    Table(f"{DATABASE}.{TASK_SALES_SCHEMA}.VAL").to_schema()))

SalesTrain = Relationship(f"{Article} at {Any:timestamp} has {Any:sales}")
model.define(
    SalesTrain(Article, SalesTrainTable.timestamp, SalesTrainTable.sales)
).where(Article.article_id == SalesTrainTable.article_id)

SalesVal = Relationship(f"{Article} at {Any:timestamp} has {Any:sales}")
model.define(
    SalesVal(Article, SalesValTable.timestamp, SalesValTable.sales)
).where(Article.article_id == SalesValTable.article_id)

# Target profile — helps interpret val-RMSE vs the predict-the-mean baseline.
_s_df = select(SalesTrainTable.sales.alias("sales")).to_df()
if len(_s_df):
    _s = _s_df["sales"]
    print("\n=== Sales target profile (train split) ===")
    print(f"  n={len(_s)}  min={_s.min():.4g}  max={_s.max():.4g}  "
          f"mean={_s.mean():.4g}  stddev={_s.std():.4g}")
    print(f"  Baseline RMSE (predict-the-mean) ~= stddev = {_s.std():.4g}")

sales_gnn = GNN(
    exp_database=GNN_EXP_DATABASE, exp_schema=GNN_EXP_SCHEMA,
    graph=graph, property_transformer=pt,
    train=SalesTrain, validation=SalesVal,
    task_type="regression", eval_metric="rmse",
    has_time_column=True, stream_logs=STREAM_LOGS, seed=SEED,
    device="cuda", n_epochs=20, train_batch_size=256, lr=0.005, head_layers=2,
    temporal_strategy="last", max_iters=500,
)
sales_gnn.fit()
report(sales_gnn, "sales_gnn")
sales_gnn.register_model(
    model_database=MODEL_REGISTRY_DATABASE,
    model_schema=MODEL_REGISTRY_SCHEMA,
    model_name=SALES_MODEL_NAME,
    version_name=MODEL_VERSION,
    comment="Item-sales regression trained on H&M",
)
print(f"Registered: {SALES_MODEL_NAME} {MODEL_VERSION}")

# --------------------------------------------------
# Churn -- binary classification
# --------------------------------------------------
ChurnTrainTable = Concept("ChurnTrainTable")
ChurnValTable = Concept("ChurnValTable")

model.define(ChurnTrainTable.new(
    Table(f"{DATABASE}.{TASK_CHURN_SCHEMA}.TRAIN").to_schema()))
model.define(ChurnValTable.new(
    Table(f"{DATABASE}.{TASK_CHURN_SCHEMA}.VAL").to_schema()))

ChurnTrain = Relationship(f"{Customer} at {Any:timestamp} has {Any:churn}")
model.define(
    ChurnTrain(Customer, ChurnTrainTable.timestamp, ChurnTrainTable.churn)
).where(Customer.customer_id == ChurnTrainTable.customer_id)

ChurnVal = Relationship(f"{Customer} at {Any:timestamp} has {Any:churn}")
model.define(
    ChurnVal(Customer, ChurnValTable.timestamp, ChurnValTable.churn)
).where(Customer.customer_id == ChurnValTable.customer_id)

churn_gnn = GNN(
    exp_database=GNN_EXP_DATABASE, exp_schema=GNN_EXP_SCHEMA,
    graph=graph, property_transformer=pt,
    train=ChurnTrain, validation=ChurnVal,
    task_type="binary_classification", eval_metric="roc_auc",
    has_time_column=True, stream_logs=STREAM_LOGS, seed=SEED,
    device="cuda", n_epochs=5, train_batch_size=256, lr=0.005, head_layers=2,
    temporal_strategy="last", max_iters=500,
)
churn_gnn.fit()
report(churn_gnn, "churn_gnn")
churn_gnn.register_model(
    model_database=MODEL_REGISTRY_DATABASE,
    model_schema=MODEL_REGISTRY_SCHEMA,
    model_name=CHURN_MODEL_NAME,
    version_name=MODEL_VERSION,
    comment="Customer churn binary classifier trained on H&M",
)
print(f"Registered: {CHURN_MODEL_NAME} {MODEL_VERSION}")

# --------------------------------------------------
# Purchase -- link prediction
# --------------------------------------------------
PurchaseTrainTable = Concept("PurchaseTrainTable")
PurchaseValTable = Concept("PurchaseValTable")

model.define(PurchaseTrainTable.new(
    Table(f"{DATABASE}.{TASK_PURCHASE_SCHEMA}.TRAIN").to_schema()))
model.define(PurchaseValTable.new(
    Table(f"{DATABASE}.{TASK_PURCHASE_SCHEMA}.VAL").to_schema()))

PurchaseTrain = Relationship(f"{Customer} at {Any:timestamp} has {Article}")
model.define(
    PurchaseTrain(Customer, PurchaseTrainTable.timestamp, Article)
).where(
    Customer.customer_id == PurchaseTrainTable.customer_id,
    Article.article_id == PurchaseTrainTable.article_id,
)

PurchaseVal = Relationship(f"{Customer} at {Any:timestamp} has {Article}")
model.define(
    PurchaseVal(Customer, PurchaseValTable.timestamp, Article)
).where(
    Customer.customer_id == PurchaseValTable.customer_id,
    Article.article_id == PurchaseValTable.article_id,
)

purchase_gnn = GNN(
    exp_database=GNN_EXP_DATABASE, exp_schema=GNN_EXP_SCHEMA,
    graph=graph, property_transformer=pt,
    train=PurchaseTrain, validation=PurchaseVal,
    task_type="repeated_link_prediction", eval_metric="link_prediction_map@12",
    has_time_column=True, stream_logs=STREAM_LOGS, seed=SEED,
    device="cuda", n_epochs=5, train_batch_size=16, lr=0.0001,
    temporal_strategy="last", max_iters=500,
)
purchase_gnn.fit()
report(purchase_gnn, "purchase_gnn")
purchase_gnn.register_model(
    model_database=MODEL_REGISTRY_DATABASE,
    model_schema=MODEL_REGISTRY_SCHEMA,
    model_name=PURCHASE_MODEL_NAME,
    version_name=MODEL_VERSION,
    comment="Customer-Article repeated link prediction trained on H&M",
)
print(f"Registered: {PURCHASE_MODEL_NAME} {MODEL_VERSION}")

print("\n" + "=" * 60)
print("Training complete. Run retail_optimize.py to load these models")
print("and execute the markdown + demand planning optimizers.")
print("=" * 60)
