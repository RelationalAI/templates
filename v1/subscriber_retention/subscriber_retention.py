"""Subscriber Retention (predictive GNN) template.

This script demonstrates a node-classification GNN pipeline in RelationalAI:

- Build a directed call-pattern graph over telco subscribers from
  DEMO_TELCO.RAW Snowflake tables.
- Configure a PropertyTransformer over subscriber demographics, plan
  attributes, and (optional) precomputed graph-metric features.
- Train a binary-classification GNN to predict next-quarter churn.
- Generate per-subscriber churn probability, attach to the Subscriber
  concept, and report the highest-risk subscribers per region.

Pattern:
- Mirrors retail_planning_local.py — a single CPU-tractable runner against
  the Snowflake-resident dataset (no bundled data; the Snowflake tables ARE
  the sample).
- Uses the rai-predictive-modeling and rai-predictive-training skills'
  canonical patterns: graph-node Concept (Subscriber), edge-intermediary
  Concept (Call), task table Concepts (Train / Val / Test).

Run:
    `python subscriber_retention.py`

Output:
    Prints data shape summary, GNN training metrics (ROC-AUC), and a table
    of top-N at-risk subscribers per region with their predicted churn
    probability.
"""

# TODO: Verify the import surface once we start writing code. Per
# rai-predictive-modeling: stdlib -> third-party -> relationalai.
import pandas as pd  # noqa: F401  -- TODO remove if not needed
from relationalai.semantics import Any, Integer, Model, String, define, select  # noqa: F401
from relationalai.semantics.reasoners.graph import Graph  # noqa: F401
from relationalai.semantics.reasoners.predictive import GNN, PropertyTransformer  # noqa: F401

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

# TODO: Determine actual Snowflake FQNs for source and task tables once
# we inspect DEMO_TELCO.RAW. Likely:
# - Source: DEMO_TELCO.RAW.SUBSCRIBERS, DEMO_TELCO.RAW.CALL_RECORDS,
#   DEMO_TELCO.RAW.PLANS
# - Task tables: pre-split TRAIN_SUBSCRIBERS / VAL_SUBSCRIBERS /
#   TEST_SUBSCRIBERS keyed by subscriber_id with churn label
# - Experiment artifacts: pick a writable schema (typically
#   DEMO_TELCO.EXPERIMENTS or a per-user schema)
SUBSCRIBER_TABLE = "DEMO_TELCO.RAW.SUBSCRIBERS"
CALL_TABLE = "DEMO_TELCO.RAW.CALL_RECORDS"
TRAIN_TABLE = "DEMO_TELCO.RAW.TRAIN_SUBSCRIBERS"  # TODO confirm
VAL_TABLE = "DEMO_TELCO.RAW.VAL_SUBSCRIBERS"  # TODO confirm
TEST_TABLE = "DEMO_TELCO.RAW.TEST_SUBSCRIBERS"  # TODO confirm
EXP_DATABASE = "DEMO_TELCO"
EXP_SCHEMA = "EXPERIMENTS"  # TODO confirm writable

# GNN hyperparameters — start conservative; tune via rai-predictive-training.
TASK_TYPE = "binary_classification"
EVAL_METRIC = "roc_auc"
N_EPOCHS = 5
LR = 0.005
DEVICE = "cuda"  # TODO match raiconfig.yaml predictive engine sizing

# Reporting parameters.
TOP_N_AT_RISK = 10

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

model = Model("subscriber_retention")

# TODO: Declare concepts per rai-predictive-modeling § "Define and Populate
# Concepts":
#   Subscriber (graph-node, identify_by={"subscriber_id": ...}) — load from
#     Subscriber Snowflake table; carries demographics + plan features.
#   Call (edge-intermediary, no identify_by) — used in Edge.new(src, dst)
#     to express the directed call graph.
#   TrainSubscriber, ValSubscriber, TestSubscriber (task tables, no
#     identify_by) — each carries (subscriber_id, churn_label[, ts]).
# Use Concept.new(Table("...").to_schema()) to populate.

# TODO: Build the directed call graph
#   gnn_graph = Graph(model, directed=True, weighted=False)
#   define(gnn_graph.Edge.new(src=Subscriber, dst=SubscriberRef)).where(
#       Call.caller_id == Subscriber.subscriber_id,
#       Call.callee_id == SubscriberRef.subscriber_id,
#   )

# TODO: (Optional) Compute graph-metric features and bind as Subscriber
# properties — per rai-predictive-modeling § "Graph metrics as features":
#   algo_graph = Graph(model, directed=True, weighted=False)
#   define(algo_graph.Edge.new(...))  # same edges
#   Subscriber.pagerank = model.Property(f"{Subscriber} has {Float:pagerank}")
#   model.define(Subscriber.pagerank(algo_graph.pagerank()))
# These derived features can then be added to the PropertyTransformer below.

# TODO: Define task Relationships per rai-predictive-modeling § "Task
# Relationships". For binary classification with no time column:
#   Train = model.Relationship(f"{Subscriber} has {Any:churn_label}")
#   Val = model.Relationship(f"{Subscriber} has {Any:churn_label}")
#   Test = model.Relationship(f"{Subscriber}")
# Populate from task tables matching subscriber_id.

# --------------------------------------------------
# Configure features (PropertyTransformer)
# --------------------------------------------------

# TODO: pt = PropertyTransformer(
#     category=[Subscriber.region, Subscriber.plan_type, Subscriber.contract_status],
#     continuous=[Subscriber.tenure_months, Subscriber.monthly_charges,
#                 Subscriber.pagerank],  # PageRank as a continuous feature
#     drop=[Subscriber.subscriber_id],   # PKs/FKs add noise; graph carries identity
# )
# Per rai-predictive-modeling § "Feature Selection Strategy": drop PKs/FKs,
# start lean on text fields.

# --------------------------------------------------
# Train predictive model
# --------------------------------------------------

# TODO: gnn = GNN(
#     exp_database=EXP_DATABASE, exp_schema=EXP_SCHEMA,
#     graph=gnn_graph, property_transformer=pt,
#     train=Train, validation=Val,
#     task_type=TASK_TYPE, eval_metric=EVAL_METRIC,
#     device=DEVICE, n_epochs=N_EPOCHS, lr=LR,
# )
# gnn.fit()

# --------------------------------------------------
# Generate predictions
# --------------------------------------------------

# TODO: Pattern 1 (recommended): bind predictions to a concept attribute
#   Subscriber.predictions = gnn.predictions(domain=Test)
# Then query .probs / .predicted_labels.

# --------------------------------------------------
# Validate / inspect
# --------------------------------------------------

# TODO: Print data shape summary (count of subscribers, calls, train/val/test
# split sizes), training metrics (final ROC-AUC on val), and the top-N
# at-risk subscribers per region:
#   model.select(
#       Subscriber.region.alias("region"),
#       Subscriber.subscriber_id.alias("subscriber_id"),
#       Subscriber.predictions.probs.alias("churn_prob"),
#   ).where(...).inspect()

# TODO: Add `inspect.schema(model)` summary at the end so the user sees
# what got registered (per rai-build-starter-ontology § Step 7e).
