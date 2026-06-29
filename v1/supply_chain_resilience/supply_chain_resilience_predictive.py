"""Predictive stage -- GNN supplier delay-risk forecast for supply_chain_resilience.

Dual-mode, selected by the TRAIN_GNN env var:

  - TRAIN_GNN=false (default): skip training. The downstream Rules stage consumes the
    bundled data/delay_prediction.csv, which was itself produced by a real GNN run (this
    script with TRAIN_GNN=true). Fast, no GPU, no Snowflake experiment schema needed.

  - TRAIN_GNN=true: train a GNN from scratch on the bundled multi-year corpus
    (data/shipment_corpus.csv + the temporal splits) and the shipment relatedness graph
    (data/shipment_edges.csv), then (re)write data/delay_prediction.csv.

Everything loads from local CSV via model.data() -- only the GNN experiment artifacts are
Snowflake-resident. The graph is homogeneous (Shipment nodes): each shipment links to
others sharing its supplier and to shipments of its UPSTREAM suppliers, so risk
propagates through the chain. A shipper with high own reliability is still flagged risky
when its upstream supplier is unreliable (B004 <- B003) -- the GNN learns that from the
graph + labels even though the denormalized supplier_reliability feature looks benign.

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

TRAIN_GNN = os.getenv("TRAIN_GNN", "false").lower() == "true"
GNN_EXP_DATABASE = os.getenv("GNN_EXP_DATABASE", "SUPPLY_CHAIN")
GNN_EXP_SCHEMA = os.getenv("GNN_EXP_SCHEMA", "EXPERIMENTS")
GNN_DEVICE = os.getenv("GNN_DEVICE", "cuda")  # "cpu" if your RAI engine is CPU-only
SEED = 42
DATA_DIR = Path(__file__).parent / "data"
PRED_CSV = DATA_DIR / "delay_prediction.csv"
FORECAST_QUARTERS = ["Q1-2025", "Q2-2025", "Q3-2025", "Q4-2025"]

if not TRAIN_GNN:
    print(
        f"[predictive] TRAIN_GNN unset -> using the bundled GNN predictions at "
        f"{PRED_CSV.name}. Set TRAIN_GNN=true to retrain the model from scratch."
    )
    raise SystemExit(0)

print("=" * 60)
print("PREDICTIVE: training supplier delay-risk GNN from scratch")
print("=" * 60)

model = Model("supply_chain_resilience_predictive")
Concept, Relationship = model.Concept, model.Relationship

# Homogeneous node type (Shipment) + an explicit relatedness edge list -- the proven
# CSV-backed GNN shape. Secondary entities (supplier/sku/site) enter as denormalized
# features and via the edge structure, not as separate node tables.
Shipment = Concept("CorpusShipment", identify_by={"id": String})
Related = Concept("Related")  # shipment-to-shipment edge list (src, dst)
TrainTable = Concept("TrainTable")
ValTable = Concept("ValTable")
TestTable = Concept("TestTable")

model.define(Shipment.new(model.data(read_csv(DATA_DIR / "shipment_corpus.csv")).to_schema()))
model.define(Related.new(model.data(read_csv(DATA_DIR / "shipment_edges.csv")).to_schema()))
model.define(TrainTable.new(model.data(read_csv(DATA_DIR / "shipment_train.csv")).to_schema()))
model.define(ValTable.new(model.data(read_csv(DATA_DIR / "shipment_val.csv")).to_schema()))
model.define(TestTable.new(model.data(read_csv(DATA_DIR / "shipment_test.csv")).to_schema()))

# --------------------------------------------------
# Task split (Test is unlabelled)
# --------------------------------------------------
Train = Relationship(f"{Shipment} has {Any:is_late}")
model.define(Train(Shipment, TrainTable.is_late)).where(Shipment.id == TrainTable.shipment_id)
Validation = Relationship(f"{Shipment} has {Any:is_late}")
model.define(Validation(Shipment, ValTable.is_late)).where(Shipment.id == ValTable.shipment_id)
Test = Relationship(f"{Shipment}")
model.define(Test(Shipment)).where(Shipment.id == TestTable.shipment_id)

# --------------------------------------------------
# Self-referential Shipment <-> Shipment graph from the relatedness edge list
# --------------------------------------------------
gnn_graph = Graph(model, directed=True, weighted=False)
Edge = gnn_graph.Edge
ShipmentRef = Shipment.ref()
model.define(Edge.new(src=Shipment, dst=ShipmentRef)).where(
    Shipment.id == Related.src,
    ShipmentRef.id == Related.dst,
)

# --------------------------------------------------
# Features -- per-shipment observables (label-derived columns dropped)
# --------------------------------------------------
pt = PropertyTransformer(
    continuous=[Shipment.quantity, Shipment.supplier_reliability],
    category=[Shipment.ship_month, Shipment.ship_quarter],
    drop=[
        Shipment.id, Shipment.supplier_business_id, Shipment.customer_business_id,
        Shipment.sku_id, Shipment.origin_site_id, Shipment.destination_site_id,
        Shipment.operation_id, Shipment.order_date, Shipment.ship_date,
        Shipment.expected_delivery_date, Shipment.actual_delivery_date,
        Shipment.status, Shipment.delay_days, Shipment.fiscal_quarter,
        Shipment.fiscal_year, Shipment.is_late,
    ],
)

# --------------------------------------------------
# Train + predict
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
    seed=SEED,
    n_epochs=50,
)
gnn.fit()
Shipment.predictions = gnn.predictions(domain=Test)

# --------------------------------------------------
# Aggregate per-shipment probabilities to a per-supplier delay risk
# --------------------------------------------------
preds_df = (
    select(
        Shipment.supplier_business_id.alias("supplier"),
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
