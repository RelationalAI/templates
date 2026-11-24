"""The people graph, the feature types, the smoker-status GNN, and the predictions it publishes."""

from relationalai.semantics import Float, Integer
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.predictive import GNN, PropertyTransformer

from .schema import People, Related, Test, Train, Validation, model

SEED = 42
STREAM_LOGS = False

# --------------------------------------------------
# Build the GNN graph
# --------------------------------------------------
# Self-referential edge: People -> People via the Related edge list.
# Each row of `Related` connects two People (person1 -> person2). Use a
# self-referential Edge to express it: same concept on both ends, so the
# destination is `People.ref()`.
gnn_graph = Graph(model, name="people_graph", directed=True, weighted=False)
Edge = gnn_graph.Edge

PeopleRef = People.ref()
model.define(Edge.new(src=People, dst=PeopleRef)).where(
    People.Id == Related.person1,
    PeopleRef.Id == Related.person2,
)

# --------------------------------------------------
# PropertyTransformer -- declare feature types
# --------------------------------------------------
# Continuous medical and demographic features, plus the binary dental-caries
# indicator as a category.
pt = PropertyTransformer(
    continuous=[
        People.age,
        People.height_cm,
        People.weight_kg,
        People.systolic,
        People.relaxation,
        People.fasting_blood_sugar,
        People.cholesterol,
        People.triglyceride,
        People.hdl,
        People.ldl,
        People.hemoglobin,
        People.urine_protein,
        People.serum_creatinine,
        People.ast,
        People.alt,
        People.gtp,
    ],
    category=[People.dental_caries],
    drop=[People.Id],
)

# --------------------------------------------------
# The GNN and its predictions
# --------------------------------------------------
# `name` ties this GNN to the registered model and version that
# `reasoners.predictive.gnns.smoker_status` names in raiconfig.yaml:
# train.py registers the trained run there, and every refresh scores the
# test cohort with it.

gnn = GNN(
    name="smoker_status",
    graph=gnn_graph,
    property_transformer=pt,
    train=Train,
    validation=Validation,
    task_type="binary_classification",
    eval_metric="roc_auc",
    has_time_column=False,
    n_epochs=5,
    lr=0.005,
    train_batch_size=256,
    seed=SEED,
    stream_logs=STREAM_LOGS,
)
People.predictions = gnn.predictions(domain=Test)

# --------------------------------------------------
# Published predictions
# --------------------------------------------------
# A deployed query reads only what the model publishes, so the predictions
# are copied onto a concept of their own. The GNN reads People, so a People
# property derived from its predictions would feed back into them.
SmokerPrediction = model.Concept("SmokerPrediction", identify_by={"person_id": Integer})
SmokerPrediction.probability = model.Property(f"{SmokerPrediction} has {Float:probability}")
SmokerPrediction.predicted_label = model.Property(
    f"{SmokerPrediction} has {Integer:predicted_label}"
)
model.define(
    prediction := SmokerPrediction.new(person_id=People.Id),
    prediction.probability(People.predictions.probs),
    prediction.predicted_label(People.predictions.predicted_labels),
).where(People.predictions)
