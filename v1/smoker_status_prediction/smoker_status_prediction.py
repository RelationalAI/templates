"""Smoker Status Prediction -- Snowflake reference pipeline.

Reference pattern for adapting the smoker classification pipeline against
Snowflake-hosted tables. See `smoker_status_prediction_local.py` for a
CSV-based script that you can execute without external setup.

Predicts whether a person is a smoker (binary classification) using their
demographic and medical attributes plus a network of social connections.

Setup:
    Upload the bundled CSVs to your Snowflake account. Quote column names
    when creating the tables so spaces and parentheses are preserved
    (e.g. `"height(cm)"`, `"fasting blood sugar"`). The expected schema is:

        <DATABASE>.<SCHEMA>.PEOPLE        (Id, age, "height(cm)", ...)
        <DATABASE>.<SCHEMA>.RELATED       (person1, person2)
        <DATABASE>.<TASK_SCHEMA>.TRAIN    (Id, smoking)
        <DATABASE>.<TASK_SCHEMA>.VALIDATION (Id, smoking)
        <DATABASE>.<TASK_SCHEMA>.TEST     (Id)

Run:
    python smoker_status_prediction.py
"""

from relationalai.semantics import Any, Integer, Model, select
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.predictive import GNN, PropertyTransformer

# --------------------------------------------------
# Configuration -- edit to match your Snowflake account
# --------------------------------------------------
# Snowflake location of the source data.
DATABASE = "SMOKER_STATUS_PREDICTION"
SCHEMA = "DATA"           # holds PEOPLE and RELATED
TASK_SCHEMA = "DATA"      # holds TRAIN, VALIDATION, TEST (can be the same)

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

# --------------------------------------------------
# Phase 1: Model & concepts
# --------------------------------------------------
model = Model("smoker_status_prediction")
Concept, Table, Relationship = model.Concept, model.Table, model.Relationship

# Domain concepts
People = Concept("People", identify_by={"Id": Integer})
Related = Concept("Related")  # edge bridge between two People

# Task split concepts (no PK)
TrainTable = Concept("TrainTable")
ValidationTable = Concept("ValidationTable")
TestTable = Concept("TestTable")

# --------------------------------------------------
# Phase 2: Load from Snowflake
# --------------------------------------------------
model.define(People.new(Table(f"{DATABASE}.{SCHEMA}.PEOPLE").to_schema()))
model.define(Related.new(Table(f"{DATABASE}.{SCHEMA}.RELATED").to_schema()))

model.define(TrainTable.new(Table(f"{DATABASE}.{TASK_SCHEMA}.TRAIN").to_schema()))
model.define(ValidationTable.new(Table(f"{DATABASE}.{TASK_SCHEMA}.VALIDATION").to_schema()))
model.define(TestTable.new(Table(f"{DATABASE}.{TASK_SCHEMA}.TEST").to_schema()))

# --------------------------------------------------
# Phase 3: Build the graph
# --------------------------------------------------
# Self-referential edge: People -> People via the Related bridge.
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
print("Pipeline complete.")
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
