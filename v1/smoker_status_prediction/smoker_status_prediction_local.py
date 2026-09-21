"""Smoker Status Prediction -- local CSV-only template.

Predicts whether a person is a smoker (binary classification) using their
demographic and medical attributes plus a network of social connections.
The connections come from a `RELATED` edge list -- pairs of people who are
linked, where linked pairs are more likely to share smoking status. The GNN
learns from both per-person features and the network structure, leveraging
relational signal that flat tabular models miss.

This local script loads everything from the bundled CSVs in `data/` via
`model.data()` -- no Snowflake source-data loading. Defaults to
`device="cuda"`; switch to `"cpu"` at the top of the script if your RAI
engine is CPU-only.

Pipeline:
  1. Load People, Related (edge list), and Train / Validation / Test
     splits from the bundled CSVs.
  2. Build a self-referential People <-> People graph from the Related
     edge list so the GNN propagates signal between connected individuals.
  3. Configure feature preprocessing: continuous medical / demographic
     attributes plus a binary `dental caries` category; drop the `Id` PK.
  4. Train a binary-classification GNN to predict smoking status, with
     ROC-AUC on the held-out validation split.
  5. Generate per-person predictions on the held-out Test cohort.

Run:
    python smoker_status_prediction_local.py

Output:
    Data summary, GNN training metrics (ROC-AUC on validation), test-set
    ROC-AUC, predicted class distribution, and a sample of per-person
    predictions (Id, predicted label, probability).
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Any, Integer, Model, select
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.predictive import GNN, PropertyTransformer

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------
# Snowflake location for GNN experiment artifacts. The RelationalAI native
# app must have USAGE on the database and CREATE EXPERIMENT / CREATE MODEL
# on this schema:
#   GRANT USAGE ON DATABASE <db> TO APPLICATION RELATIONALAI;
#   GRANT USAGE ON SCHEMA <db>.<schema> TO APPLICATION RELATIONALAI;
#   GRANT CREATE EXPERIMENT ON SCHEMA <db>.<schema> TO APPLICATION RELATIONALAI;
#   GRANT CREATE MODEL ON SCHEMA <db>.<schema> TO APPLICATION RELATIONALAI;
GNN_EXP_DATABASE = "SMOKER_STATUS_PREDICTION"
GNN_EXP_SCHEMA = "EXPERIMENTS"

SEED = 42
STREAM_LOGS = False

DATA_DIR = Path(__file__).parent / "data"

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------
model = Model("smoker_status_prediction_local")
Concept, Relationship = model.Concept, model.Relationship

# Domain concepts
People = Concept("People", identify_by={"Id": Integer})
Related = Concept("Related")  # edge list between two People

# Task split concepts (no PK)
TrainTable = Concept("TrainTable")
ValidationTable = Concept("ValidationTable")
TestTable = Concept("TestTable")

# Load CSVs and bind them to the concepts above.
people_df = read_csv(DATA_DIR / "people.csv")
related_df = read_csv(DATA_DIR / "related.csv")
train_df = read_csv(DATA_DIR / "train.csv")
val_df = read_csv(DATA_DIR / "validation.csv")
test_df = read_csv(DATA_DIR / "test.csv")

model.define(People.new(model.data(people_df).to_schema()))
model.define(Related.new(model.data(related_df).to_schema()))
model.define(TrainTable.new(model.data(train_df).to_schema()))
model.define(ValidationTable.new(model.data(val_df).to_schema()))
model.define(TestTable.new(model.data(test_df).to_schema()))

# --------------------------------------------------
# Build the GNN graph
# --------------------------------------------------
# Self-referential edge: People -> People via the Related edge list.
# Each row of `Related` connects two People (person1 -> person2). Use a
# self-referential Edge to express it: same concept on both ends, so the
# destination is `People.ref()`.
gnn_graph = Graph(model, directed=True, weighted=False)
Edge = gnn_graph.Edge

PeopleRef = People.ref()
model.define(Edge.new(src=People, dst=PeopleRef)).where(
    People.Id == Related.person1,
    PeopleRef.Id == Related.person2,
)

# --------------------------------------------------
# Train / Val / Test split
# --------------------------------------------------
Train = Relationship(f"{People} has {Any:smoking}")
model.define(Train(People, TrainTable.smoking)).where(
    People.Id == TrainTable.Id
)

Validation = Relationship(f"{People} has {Any:smoking}")
model.define(Validation(People, ValidationTable.smoking)).where(
    People.Id == ValidationTable.Id
)

# Test has no label -- predictions will be generated for it after training.
Test = Relationship(f"{People}")
model.define(Test(People)).where(
    People.Id == TestTable.Id
)

# --------------------------------------------------
# PropertyTransformer -- declare feature types
# --------------------------------------------------
# Continuous medical and demographic features. Several columns use special
# characters (spaces, parentheses) that aren't valid Python identifiers, so
# we reference them via getattr().
pt = PropertyTransformer(
    continuous=[
        People.age,
        getattr(People, "height(cm)"),
        getattr(People, "weight(kg)"),
        People.systolic,
        People.relaxation,
        getattr(People, "fasting blood sugar"),
        People.Cholesterol,
        People.triglyceride,
        People.HDL,
        People.LDL,
        People.hemoglobin,
        getattr(People, "Urine protein"),
        getattr(People, "serum creatinine"),
        People.AST,
        People.ALT,
        People.Gtp,
    ],
    category=[getattr(People, "dental caries")],
    drop=[People.Id],
)

# --------------------------------------------------
# Train the GNN
# --------------------------------------------------
print("\n" + "=" * 60)
print("PREDICTIVE: Smoker status binary classification")
print("=" * 60)

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
    device="cuda",  # change to "cpu" if your RAI engine is CPU-only
    n_epochs=5,
    lr=0.005,
    train_batch_size=256,
    seed=SEED,
    stream_logs=STREAM_LOGS,
)
gnn.fit()

People.predictions = gnn.predictions(domain=Test)

# --------------------------------------------------
# Reporting -- inspect predictions
# --------------------------------------------------
# Pull per-person predictions joined to the held-out actual labels in a
# single query, so we can score the GNN on the test cohort.
predictions_df = (
    select(
        People.Id.alias("Id"),
        People.predictions.predicted_labels.alias("predicted_label"),
        People.predictions.probs.alias("prob"),
        TestTable.smoking.alias("actual_smoking"),
    )
    .where(
        People.predictions,
        People.Id == TestTable.Id,
    )
    .to_df()
)

if predictions_df.empty:
    print("(no test-set predictions returned)")
else:
    predictions_df["predicted_label"] = predictions_df["predicted_label"].astype(int)
    predictions_df["actual_smoking"] = predictions_df["actual_smoking"].astype(int)
    predictions_df["prob"] = predictions_df["prob"].astype(float)

    print("\n=== Smoker predictions (sample) ===")
    print(
        predictions_df[["Id", "predicted_label", "prob", "actual_smoking"]]
        .head(10)
        .to_string(index=False)
    )

    # Test-set metrics. Rank-based ROC-AUC keeps the script sklearn-free:
    # AUC = (sum_of_ranks_of_positives - n_pos*(n_pos+1)/2) / (n_pos * n_neg).
    n_test = len(predictions_df)
    accuracy = float(
        (predictions_df["predicted_label"] == predictions_df["actual_smoking"]).mean()
    )
    ranks = predictions_df["prob"].rank(method="average")
    pos_mask = predictions_df["actual_smoking"] == 1
    n_pos = int(pos_mask.sum())
    n_neg = int((~pos_mask).sum())
    test_auc = (
        float((ranks[pos_mask].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))
        if n_pos > 0 and n_neg > 0
        else float("nan")
    )
    actual_dist = (
        predictions_df["actual_smoking"].value_counts(normalize=True).sort_index().to_dict()
    )
    predicted_dist = (
        predictions_df["predicted_label"].value_counts(normalize=True).sort_index().to_dict()
    )

    print(f"\n=== Test-set metrics (n={n_test}) ===")
    print(f"  Test-set ROC-AUC:   {test_auc:.4f}")
    print(f"  Test-set accuracy:  {accuracy:.4f}")
    print(
        f"  Actual class dist:    "
        f"{{0: {actual_dist.get(0, 0):.4f}, 1: {actual_dist.get(1, 0):.4f}}}"
    )
    print(
        f"  Predicted class dist: "
        f"{{0: {predicted_dist.get(0, 0):.4f}, 1: {predicted_dist.get(1, 0):.4f}}}"
    )

print("\n" + "=" * 60)
print("Local run complete.")
print("=" * 60)

# --------------------------------------------------
# (Optional) Bonus: register and load the trained model
# --------------------------------------------------
# Uncomment the block below to save the trained model to the Snowflake Model
# Registry, then load it in a fresh GNN instance and predict without
# retraining. The native app must have CREATE MODEL on the registry schema.
#
# MODEL_DATABASE = GNN_EXP_DATABASE
# MODEL_SCHEMA = "MODEL_REGISTRY"
#
# # Register the model just trained.
# gnn.register_model(
#     model_database=MODEL_DATABASE,
#     model_schema=MODEL_SCHEMA,
#     model_name="smoker_status_predictor",
#     version_name="v1",
#     comment="Initial smoker classification baseline",
# )
#
# # Load it back. All structural arguments (graph, property_transformer,
# # source_concept, task_type) must match what was used at training time.
# loaded_gnn = GNN(
#     exp_database=GNN_EXP_DATABASE,
#     exp_schema=GNN_EXP_SCHEMA,
#     graph=gnn_graph,
#     property_transformer=pt,
#     source_concept=People,
#     task_type="binary_classification",
#     model_database=MODEL_DATABASE,
#     model_schema=MODEL_SCHEMA,
#     model_name="smoker_status_predictor",
#     version_name="v1",
# )
# loaded_gnn.load()
# People.loaded_predictions = loaded_gnn.predictions(domain=Test)
