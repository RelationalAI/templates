"""Sales forecast: the transaction graph, the sales-regression GNN, and the profile of its training
target."""

from relationalai.semantics import Float, Integer, String
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.predictive import GNN, PropertyTransformer
from relationalai.semantics.std import aggregates as aggs

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

# The train split's sales target: how many transactions it labels and the minimum, maximum, mean
# and sample standard deviation of their sales. The standard deviation is also the RMSE of
# predicting the mean.
TrainTargetProfile = model.Relationship(
    f"the train split has {Integer:n} sales labels from {Float:minimum} to {Float:maximum} "
    f"with mean {Float:mean} and sample standard deviation {Float:stddev}"
)
_train_timestamp, _train_sales = String.ref(), Float.ref()
_labeled = Train(Transaction, _train_timestamp, _train_sales)
model.define(TrainTargetProfile(
    aggs.count(Transaction).where(_labeled),
    aggs.min(_train_sales).where(_labeled),
    aggs.max(_train_sales).where(_labeled),
    aggs.avg(Transaction, _train_sales).where(_labeled),
    aggs.stddev_samp(Transaction, _train_sales).where(_labeled),
))
