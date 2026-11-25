"""Demand forecast: the GNN graph, the regression GNN, and the per-Sale predictions it declares."""

from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.predictive import GNN, PropertyTransformer

# Declare the loaded Sale, Store, and Item properties, and derive the Train, Val, and Test
# relationships the GNN trains and predicts over.
from . import source, temporal_split  # noqa: F401
from .schema import Item, ItemFamily, Sale, Store, Test, Train, Val, model

SEED = 42
STREAM_LOGS = False

# --------------------------------------------------
# Build the GNN graph
# --------------------------------------------------
# Heterogeneous: each Sale connects to its Store and its Item; each Item
# connects to its ItemFamily. The GNN aggregates over these neighborhoods
# while the time column (Sale.date) drives temporal causality.

gnn_graph = Graph(model, name="sales_graph", directed=True, weighted=False)
Edge = gnn_graph.Edge
model.define(Edge.new(src=Sale, dst=Store)).where(Sale.store_id == Store.store_id)
model.define(Edge.new(src=Sale, dst=Item)).where(Sale.item_id == Item.item_id)
model.define(Edge.new(src=Item, dst=ItemFamily)).where(Item.family == ItemFamily.family)

# --------------------------------------------------
# PropertyTransformer -- declare feature types
# --------------------------------------------------

pt = PropertyTransformer(
    drop=[
        # PKs and FKs add noise; the graph carries identity.
        Sale.sale_id,
        Sale.store_id,
        Sale.item_id,
        Store.store_id,
        Item.item_id,
        ItemFamily.family,
        # The GNN target is unit_sales — keeping it as a feature would leak.
        Sale.unit_sales,
    ],
    category=[
        Store.city,
        Store.state,
        Store.store_type,
        Item.family,
        Item.perishable,
        Sale.onpromotion,
    ],
    continuous=[Store.cluster],
    integer=[Item.item_class],
    datetime=[Sale.date],
    time_col=[Sale.date],
)

# --------------------------------------------------
# The GNN and its predictions
# --------------------------------------------------
# `name` ties this GNN to the registered model and version that
# `reasoners.predictive.gnns.demand_forecast` names in raiconfig.yaml:
# train.py registers the trained run there, and every refresh scores the
# test window with it.

gnn = GNN(
    name="demand_forecast",
    graph=gnn_graph,
    property_transformer=pt,
    train=Train,
    validation=Val,
    task_type="regression",
    eval_metric="rmse",
    has_time_column=True,
    stream_logs=STREAM_LOGS,
    seed=SEED,
    n_epochs=20,
    lr=0.005,
)
Sale.predictions = gnn.predictions(domain=Test)
