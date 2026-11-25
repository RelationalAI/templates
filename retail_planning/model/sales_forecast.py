"""Sales forecast: the transaction graph and the sales-regression GNN."""

from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.predictive import GNN, PropertyTransformer

from .schema import Article, Customer, Test, Train, Transaction, Val, model

# --------------------------------------------------
# Phase 1: Graph
# --------------------------------------------------
gnn_graph = Graph(model, name="transaction_graph", directed=True, weighted=False)
Edge = gnn_graph.Edge
model.define(Edge.new(src=Transaction, dst=Customer)).where(
    Transaction.t_customer_id == Customer.c_customer_id)
model.define(Edge.new(src=Transaction, dst=Article)).where(
    Transaction.t_article_id == Article.a_article_id)

# PropertyTransformer: every column the model loads is typed. Transaction.price is the sales
# label (the Train and Val values equal it), so it is not a feature.
pt = PropertyTransformer(
    category=[
        Customer.fn, Customer.active, Customer.club_member_status,
        Customer.fashion_news_frequency,
        Article.product_group_name, Article.colour_group_name,
        Article.index_group_name, Article.garment_group_name,
        Transaction.sales_channel_id,
    ],
    text=[Article.prod_name],
    continuous=[Customer.age],
    drop=[
        Customer.c_customer_id, Article.a_article_id,
        Transaction.transaction_id,
        Transaction.t_customer_id, Transaction.t_article_id,
        Transaction.price,
    ],
    datetime=[Transaction.t_dat],
    time_col=[Transaction.t_dat],
)

# --------------------------------------------------
# Phase 2: Sales regression GNN (transaction-level)
# --------------------------------------------------
# `name` ties this GNN to the registered model and version that
# `reasoners.predictive.gnns.sales_regression` names in raiconfig.yaml:
# train.py registers the trained run there, and every refresh scores the
# test split with it.
gnn = GNN(
    name="sales_regression",
    graph=gnn_graph, property_transformer=pt,
    train=Train, validation=Val,
    task_type="regression", eval_metric="rmse",
    has_time_column=True, stream_logs=False, seed=42,
    n_epochs=20, lr=0.005, patience=10,
)
Transaction.predictions = gnn.predictions(domain=Test)
