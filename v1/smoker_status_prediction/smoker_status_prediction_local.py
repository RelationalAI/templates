"""Smoker Status Prediction -- local CSV-only runner.

Predicts whether a person is a smoker (binary classification) using their
demographic and medical attributes plus a network of social connections.
The connections come from a `RELATED` edge list -- pairs of people who are
linked, where linked pairs are more likely to share smoking status. The GNN
learns from both per-person features and the network structure, leveraging
relational signal that flat tabular models miss.

This local runner loads everything from the bundled CSVs in `data/` via
`model.data()` -- no Snowflake data loading, no GPU required (CPU GNN
training on this slice is tractable).

Run:
    python smoker_status_prediction_local.py
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Any, Integer, Model, select
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.predictive import GNN, PropertyTransformer

DATA_DIR = Path(__file__).parent / "data"

# --------------------------------------------------
# Phase 1: Model & concepts
# --------------------------------------------------
model = Model("smoker_status_prediction_local")
Concept, Relationship = model.Concept, model.Relationship

# Domain concepts
People = Concept("People", identify_by={"Id": Integer})
Related = Concept("Related")  # edge bridge between two People

# Task split concepts (no PK)
TrainTable = Concept("TrainTable")
ValidationTable = Concept("ValidationTable")
TestTable = Concept("TestTable")

# --------------------------------------------------
# Phase 2: Load CSVs
# --------------------------------------------------
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
# Phase 3: Build the graph
# --------------------------------------------------
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
# Phase 4: Task relationships (no time component)
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
# Phase 5: Configure feature preprocessing
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
# Phase 6: Train + predict
# --------------------------------------------------
print("\n" + "=" * 60)
print("PREDICTIVE: Smoker status binary classification (CPU)")
print("=" * 60)

gnn = GNN(
    exp_database="SMOKER_STATUS_PREDICTION",
    exp_schema="EXPERIMENTS",
    graph=gnn_graph,
    property_transformer=pt,
    train=Train,
    validation=Validation,
    task_type="binary_classification",
    eval_metric="roc_auc",
    has_time_column=False,
    device="cpu",
    n_epochs=5,
    lr=0.005,
    train_batch_size=256,
    seed=42,
)
gnn.fit()

People.predictions = gnn.predictions(domain=Test)

# --------------------------------------------------
# Phase 7: Inspect predictions
# --------------------------------------------------
print("\n=== Smoker predictions (sample) ===")
select(
    People.Id,
    People.predictions.predicted_labels,
    People.predictions.probs,
).where(People.predictions).inspect()

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
# # Register the model just trained.
# gnn.register_model(
#     model_database="SMOKER_STATUS_PREDICTION",
#     model_schema="MODEL_REGISTRY",
#     model_name="smoker_status_predictor",
#     version_name="v1",
#     comment="Initial smoker classification baseline",
# )
#
# # Load it back. All structural arguments (graph, property_transformer,
# # source_concept, task_type) must match what was used at training time.
# loaded_gnn = GNN(
#     exp_database="SMOKER_STATUS_PREDICTION",
#     exp_schema="EXPERIMENTS",
#     graph=gnn_graph,
#     property_transformer=pt,
#     source_concept=People,
#     task_type="binary_classification",
#     model_database="SMOKER_STATUS_PREDICTION",
#     model_schema="MODEL_REGISTRY",
#     model_name="smoker_status_predictor",
#     version_name="v1",
# )
# loaded_gnn.load()
# People.loaded_predictions = loaded_gnn.predictions(domain=Test)
