"""Demand Forecasting (predictive GNN) template.

This script demonstrates a regression GNN pipeline in RelationalAI on
retail demand-forecasting data (Kaggle Favorita Grocery Sales Forecasting):

- Build a knowledge graph over Stores, Items, Item Families/Classes, and
  daily sales transactions.
- Configure a PropertyTransformer over store/item categorical attributes,
  promotional flags, and time features.
- Train a regression GNN to predict next-period unit sales per
  (store, item, date).
- Generate per-(store, item, date) demand predictions and aggregate to
  weekly forecasts.

Pattern:
- Mirrors retail_planning_local.py — bundled CPU-tractable subset under
  data/favorita_mini/ so the template runs end-to-end on a laptop. A
  separate runner (TODO: demand_forecasting_full.py) targets the full
  Snowflake-loaded dataset.
- Uses the rai-predictive-modeling and rai-predictive-training skills'
  canonical patterns for regression with a time column.

Run:
    `python demand_forecasting.py`

Output:
    Prints data shape summary, GNN training metrics (RMSE), and a table
    of forecasted demand per (store, item) for the next prediction window.
"""

# TODO: Verify the import surface once we start writing code. Per
# rai-predictive-modeling: stdlib -> third-party -> relationalai.
import pandas as pd  # noqa: F401  -- TODO remove if unused
from relationalai.semantics import (  # noqa: F401
    Any,
    Date,
    Float,
    Integer,
    Model,
    String,
    define,
    select,
)
from relationalai.semantics.reasoners.graph import Graph  # noqa: F401
from relationalai.semantics.reasoners.predictive import GNN, PropertyTransformer  # noqa: F401

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

# TODO: Either bundled local mini-set or Snowflake FQNs:
# Local pattern (preferred for first runner):
#   DATA_DIR = Path(__file__).parent / "data" / "favorita_mini"
#   - stores.csv (~50 stores; metadata: city, state, type, cluster)
#   - items.csv (~1000 items; metadata: family, class, perishable)
#   - sales_train.csv (~500K rows; date, store_id, item_id, unit_sales, onpromotion)
#   - sales_val.csv (~50K rows)
#   - sales_test.csv (~50K rows; no unit_sales target)
#
# Snowflake pattern (full-data runner):
#   STORE_TABLE = "FAVORITA.PUBLIC.STORES"
#   ITEM_TABLE = "FAVORITA.PUBLIC.ITEMS"
#   TRAIN_TABLE = "FAVORITA.TASKS.SALES_TRAIN"
#   VAL_TABLE = "FAVORITA.TASKS.SALES_VAL"
#   TEST_TABLE = "FAVORITA.TASKS.SALES_TEST"
#   EXP_DATABASE = "FAVORITA"
#   EXP_SCHEMA = "EXPERIMENTS"

# GNN hyperparameters — start conservative; tune via rai-predictive-training.
TASK_TYPE = "regression"
EVAL_METRIC = "rmse"
N_EPOCHS = 5
LR = 0.005
DEVICE = "cpu"  # local-runner default; switch to cuda for full-data runner

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

model = Model("demand_forecasting")

# TODO: Declare concepts per rai-predictive-modeling § "Define and Populate
# Concepts":
#   Store (graph-node, identify_by={"store_id": Integer})
#     properties: city, state, type, cluster
#   Item (graph-node, identify_by={"item_id": Integer})
#     properties: family, class, perishable
#   ItemFamily (graph-node, identify_by={"family": String}) — derived from Item
#     for hierarchical edge structure
#   SalesEvent (edge-intermediary, no identify_by) — connects Store/Item
#     and carries the time column (date)
#   TrainSales / ValSales / TestSales (task tables, no identify_by)
#     Each: (store_id, item_id, date, unit_sales[, onpromotion])

# TODO: Build the knowledge graph
#   gnn_graph = Graph(model, directed=True, weighted=False)
#   define(gnn_graph.Edge.new(src=Store, dst=Item)).where(
#       SalesEvent.store_id == Store.store_id,
#       SalesEvent.item_id == Item.item_id,
#   )
#   define(gnn_graph.Edge.new(src=Item, dst=ItemFamily)).where(
#       Item.family == ItemFamily.family,
#   )

# TODO: (Optional) Compute graph-metric features and bind as Item or Store
# properties — per rai-predictive-modeling § "Graph metrics as features".
# Store/Item PageRank gives a "centrality of demand" signal that can help
# the GNN cold-start on new items.

# TODO: Define task Relationships per rai-predictive-modeling § "Task
# Relationships". For regression with a time column:
#   Train = model.Relationship(f"{Store} at {Any:date} has {Any:unit_sales}")
#       — wait: task is on (Store, Item, date) jointly. Need a junction
#       concept (e.g., StoreItem) or use multi-key task table per skill.
#       TODO confirm pattern with rai-predictive-modeling skill.

# --------------------------------------------------
# Configure features (PropertyTransformer)
# --------------------------------------------------

# TODO: pt = PropertyTransformer(
#     category=[Store.city, Store.state, Store.type, Item.family,
#               Item.class_],  # 'class' is a Python keyword; rename
#     continuous=[Store.cluster, Item.pagerank],  # PageRank as feature
#     datetime=[SalesEvent.date],
#     time_col=[SalesEvent.date],
#     drop=[Store.store_id, Item.item_id],  # PKs add noise
# )
# Per rai-predictive-modeling: time_col fields must also be in datetime list.

# --------------------------------------------------
# Train predictive model
# --------------------------------------------------

# TODO: gnn = GNN(
#     exp_database=EXP_DATABASE, exp_schema=EXP_SCHEMA,
#     graph=gnn_graph, property_transformer=pt,
#     train=Train, validation=Val,
#     task_type=TASK_TYPE, eval_metric=EVAL_METRIC,
#     has_time_column=True,
#     device=DEVICE, n_epochs=N_EPOCHS, lr=LR,
# )
# gnn.fit()
#
# Note has_time_column=True has known failure modes per
# rai-predictive-training § Known Limitations — fall back to non-temporal
# Relationships (drop the 'at' clause) if the trainer rejects datetime.

# --------------------------------------------------
# Generate predictions
# --------------------------------------------------

# TODO: predictions = gnn.predictions(domain=Test)
# For regression: predictions.predicted_value gives unit_sales forecast.
# Aggregate predicted_value per (store, item) over the prediction window
# for a weekly demand forecast.

# --------------------------------------------------
# Validate / inspect
# --------------------------------------------------

# TODO: Print data shape summary, training RMSE on val, and a forecast
# table per (store, item) for the next prediction period:
#   model.select(
#       Store.store_id.alias("store_id"),
#       Item.item_id.alias("item_id"),
#       Item.family.alias("family"),
#       predictions.predicted_value.alias("forecast"),
#   ).where(...).inspect()

# TODO: Add `inspect.schema(model)` summary at the end
# (per rai-build-starter-ontology § Step 7e).
