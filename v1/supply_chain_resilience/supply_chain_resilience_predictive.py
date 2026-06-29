"""Predictive stage -- GNN supplier delay-risk forecast for supply_chain_resilience.

Dual-mode, selected by the TRAIN_GNN env var:

  - TRAIN_GNN=false (default): skip training. The downstream Rules stage consumes the
    bundled data/delay_prediction.csv, which was itself produced by a real GNN run (this
    script with TRAIN_GNN=true). Fast, no GPU, no Snowflake experiment schema needed.

  - TRAIN_GNN=true: train a GNN from scratch on the bundled multi-year corpus
    (data/shipment_corpus.csv + the temporal splits shipment_{train,val,test}.csv),
    generate per-supplier delay-risk predictions, and (re)write data/delay_prediction.csv.

Why a GNN: delay risk propagates through the supply graph -- a shipper with high own
reliability is still risky when its upstream supplier is unreliable (e.g. B004 <- B003).
A per-supplier or flat tabular model can't see that; message-passing over
Shipment -> Supplier -> upstream-Supplier edges recovers it. Features and graph load from
the local CSVs via model.data(); only the GNN experiment artifacts are Snowflake-resident.

Run (train from scratch):  TRAIN_GNN=true python supply_chain_resilience_predictive.py
Run (use bundled output):  python supply_chain_resilience_predictive.py
"""
import os
from datetime import datetime, timezone
from pathlib import Path

from pandas import DataFrame, read_csv
from relationalai.semantics import Any, Model, String, select
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.predictive import GNN, PropertyTransformer

# --------------------------------------------------
# Configuration
# --------------------------------------------------
TRAIN_GNN = os.getenv("TRAIN_GNN", "false").lower() == "true"
# Snowflake location for GNN experiment artifacts (the native app needs USAGE +
# CREATE EXPERIMENT / CREATE MODEL here). Features themselves load from local CSV.
GNN_EXP_DATABASE = os.getenv("GNN_EXP_DATABASE", "SUPPLY_CHAIN")
GNN_EXP_SCHEMA = os.getenv("GNN_EXP_SCHEMA", "EXPERIMENTS")
GNN_DEVICE = os.getenv("GNN_DEVICE", "cuda")  # "cpu" if your RAI engine is CPU-only
SEED = 42
DATA_DIR = Path(__file__).parent / "data"
PRED_CSV = DATA_DIR / "delay_prediction.csv"
# Quarters the bundled prediction table covers (the Rules stage reads Q1-2025).
FORECAST_QUARTERS = ["Q1-2025", "Q2-2025", "Q3-2025", "Q4-2025"]

if not TRAIN_GNN:
    print(
        f"[predictive] TRAIN_GNN unset -> using the bundled GNN predictions at "
        f"{PRED_CSV.name}. Set TRAIN_GNN=true to retrain the model from scratch."
    )
    raise SystemExit(0)

# --------------------------------------------------
# Define semantic model & load data (local CSV)
# --------------------------------------------------
print("=" * 60)
print("PREDICTIVE: training supplier delay-risk GNN from scratch")
print("=" * 60)

model = Model("supply_chain_resilience_predictive")
Concept, Relationship = model.Concept, model.Relationship

Shipment = Concept("CorpusShipment", identify_by={"ID": String})
Business = Concept("Business", identify_by={"ID": String})
Operation = Concept("Operation", identify_by={"ID": String})
TrainTable = Concept("TrainTable")
ValTable = Concept("ValTable")
TestTable = Concept("TestTable")

corpus_df = read_csv(DATA_DIR / "shipment_corpus.csv")
biz_df = read_csv(DATA_DIR / "business.csv")
ops_df = read_csv(DATA_DIR / "operation.csv")
train_df = read_csv(DATA_DIR / "shipment_train.csv")
val_df = read_csv(DATA_DIR / "shipment_val.csv")
test_df = read_csv(DATA_DIR / "shipment_test.csv")

model.define(Shipment.new(model.data(corpus_df).to_schema()))
model.define(Business.new(model.data(biz_df).to_schema()))
model.define(Operation.new(model.data(ops_df).to_schema()))
model.define(TrainTable.new(model.data(train_df).to_schema()))
model.define(ValTable.new(model.data(val_df).to_schema()))
model.define(TestTable.new(model.data(test_df).to_schema()))

# --------------------------------------------------
# Build the GNN graph -- this is where the graph earns its keep
# --------------------------------------------------
# Shipment -> its Supplier, and Supplier -> upstream Supplier (a SHIP operation
# SOURCE_SITE->OUTPUT_SITE means the business at SOURCE feeds the business at OUTPUT).
# Message-passing then carries upstream reliability down to each shipment.
gnn_graph = Graph(model, directed=True, weighted=False)
Edge = gnn_graph.Edge

model.define(Edge.new(src=Shipment, dst=Business)).where(
    Shipment.SUPPLIER_BUSINESS_ID == Business.ID
)

SrcBiz, DstBiz = Business.ref(), Business.ref()
op = Operation.ref()
model.define(Edge.new(src=SrcBiz, dst=DstBiz)).where(
    op.SOURCE_SITE_ID == SrcBiz.SITE_ID,
    op.OUTPUT_SITE_ID == DstBiz.SITE_ID,
)

# --------------------------------------------------
# Train / Val / Test split (labels keyed in by shipment id)
# --------------------------------------------------
Train = Relationship(f"{Shipment} has {Any:is_late}")
model.define(Train(Shipment, TrainTable.IS_LATE)).where(Shipment.ID == TrainTable.SHIPMENT_ID)

Validation = Relationship(f"{Shipment} has {Any:is_late}")
model.define(Validation(Shipment, ValTable.IS_LATE)).where(Shipment.ID == ValTable.SHIPMENT_ID)

Test = Relationship(f"{Shipment}")
model.define(Test(Shipment)).where(Shipment.ID == TestTable.SHIPMENT_ID)

# --------------------------------------------------
# Features -- per-shipment observables only (no label-derived columns)
# --------------------------------------------------
# Seasonality (month/quarter) is signal; quantity is a minor covariate. Everything
# label-derived (STATUS / DELAY_DAYS / ACTUAL_DELIVERY_DATE / IS_LATE) and every
# identifier/date is dropped to prevent leakage. Supplier/upstream risk arrives via
# the graph, not as a shipment feature.
pt = PropertyTransformer(
    continuous=[Shipment.QUANTITY],
    category=[Shipment.SHIP_MONTH, Shipment.SHIP_QUARTER],
    drop=[
        Shipment.ID, Shipment.SUPPLIER_BUSINESS_ID, Shipment.CUSTOMER_BUSINESS_ID,
        Shipment.SKU_ID, Shipment.ORIGIN_SITE_ID, Shipment.DESTINATION_SITE_ID,
        Shipment.OPERATION_ID, Shipment.ORDER_DATE, Shipment.SHIP_DATE,
        Shipment.EXPECTED_DELIVERY_DATE, Shipment.ACTUAL_DELIVERY_DATE,
        Shipment.STATUS, Shipment.DELAY_DAYS, Shipment.FISCAL_QUARTER,
        Shipment.FISCAL_YEAR, Shipment.IS_LATE,
    ],
)

# --------------------------------------------------
# Train the GNN  (n_epochs high enough to avoid early-stopping into the base rate)
# --------------------------------------------------
gnn = GNN(
    exp_database=GNN_EXP_DATABASE,
    exp_schema=GNN_EXP_SCHEMA,
    graph=gnn_graph,
    property_transformer=pt,
    train=Train,
    validation=Validation,
    task_type="binary_classification",
    eval_metric="roc_auc",
    has_time_column=False,
    device=GNN_DEVICE,
    n_epochs=30,
    lr=0.005,
    train_batch_size=256,
    seed=SEED,
    stream_logs=False,
)
gnn.fit()
Shipment.predictions = gnn.predictions(domain=Test)

# --------------------------------------------------
# Aggregate per-shipment probabilities to a per-supplier delay risk
# --------------------------------------------------
preds_df = (
    select(
        Shipment.SUPPLIER_BUSINESS_ID.alias("supplier"),
        Shipment.predictions.probs.alias("prob"),
    )
    .where(Shipment.predictions)
    .to_df()
)
preds_df["prob"] = preds_df["prob"].astype(float)
per_supplier = preds_df.groupby("supplier")["prob"].mean().sort_values(ascending=False)

print("\n=== per-supplier predicted delay risk (top) ===")
print(per_supplier.head(8).round(3).to_string())

# --------------------------------------------------
# (Re)write data/delay_prediction.csv from the GNN output
# --------------------------------------------------
def _tier(p):
    return "HIGH" if p >= 0.30 else ("MEDIUM" if p >= 0.12 else "LOW")

now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
rows = []
for supplier, prob in per_supplier.items():
    prob = round(float(prob), 3)
    for q in FORECAST_QUARTERS:
        rows.append({
            "ID": f"PRED_{supplier}_{q.replace('-', '_')}",
            "SUPPLIER_BUSINESS_ID": supplier,
            "FISCAL_QUARTER": q,
            "PREDICTED_DELAY_PROB": prob,
            "PREDICTED_AVG_DELAY_DAYS": round(prob * 10.0, 1),
            "CONFIDENCE": 0.85,
            "RISK_TIER": _tier(prob),
            "MODEL_VERSION": "gnn_v3.0",
            "CREATED_AT": now,
        })
DataFrame(rows).to_csv(PRED_CSV, index=False)
print(f"\n[predictive] wrote {len(rows)} rows to {PRED_CSV.name} "
      f"({per_supplier.size} suppliers x {len(FORECAST_QUARTERS)} quarters, model gnn_v3.0)")
print("=" * 60)
