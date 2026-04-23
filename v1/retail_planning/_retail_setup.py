"""Shared setup for the retail_planning split workflow.

Defines the model, concepts, data loading, graph, derived features, and
PropertyTransformer used by both `retail_train.py` and `retail_optimize.py`.

When the training and optimization phases run in separate sessions, each must
reconstruct the same model/graph/PT so the registry-loaded GNN sees the same
feature schema it was trained on. Keeping this shared avoids drift.

Not used by `retail_planning.py` (self-contained all-in-one).
"""

from pathlib import Path

from relationalai.semantics import Integer, Model, count
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.predictive import PropertyTransformer

# --------------------------------------------------
# Configuration
# --------------------------------------------------
DATABASE = "HM_PYREL"
SCHEMA = "HM_SCHEMA"
TASK_CHURN_SCHEMA = "TASK_CHURN"
TASK_SALES_SCHEMA = "TASK_SALES"
TASK_PURCHASE_SCHEMA = "TASK_PURCHASE"

# Snowflake location for GNN experiment artifacts. The RAI native app
# must have USAGE on the database and ALL on this schema:
#   GRANT USAGE ON DATABASE <db> TO APPLICATION RELATIONALAI;
#   GRANT ALL ON SCHEMA <db>.<schema> TO APPLICATION RELATIONALAI;
GNN_EXP_DATABASE = "HM_PYREL"
GNN_EXP_SCHEMA = "MODEL_DATA"

# Snowflake location for the GNN model registry. The 3 trained GNNs land here
# as named versions; retail_optimize.py loads them from the same location.
MODEL_REGISTRY_DATABASE = "HM_PYREL"
MODEL_REGISTRY_SCHEMA = "MODEL_REGISTRY"

# Registered model names (shared between train + optimize).
SALES_MODEL_NAME = "retail_sales_gnn"
CHURN_MODEL_NAME = "retail_churn_gnn"
PURCHASE_MODEL_NAME = "retail_purchase_gnn"
MODEL_VERSION = "v1"

# GNN determinism and log-stream behavior.
SEED = 42
STREAM_LOGS = False  # True for TTY; False avoids spinner flood in non-TTY logs

# Observability: print the engine-side data config after each fit().
VERBOSE_DATASET = False

DATA_DIR = Path(__file__).parent / "data"


def report(gnn, label):
    """After gnn.fit(), dump the engine-side data config (and optionally a
    schema PNG) to help diagnose feature-type or edge misconfig."""
    if not VERBOSE_DATASET:
        return
    print(f"\n--- {label}: engine-side data config ---")
    try:
        gnn.dataset.print_data_config()
    except Exception as e:
        print(f"  print_data_config unavailable: {e}")
    try:
        viz = gnn.visualize_dataset(show_dtypes=True)
        viz.write_png(f"{label}_schema.png")
        print(f"  wrote {label}_schema.png")
    except Exception as e:
        print(f"  visualize_dataset unavailable (install pydot?): {e}")


# --------------------------------------------------
# Shared Model, Concepts, Graph, Derived Features, PT
# --------------------------------------------------
model = Model("retail_planning")
Concept, Table, Relationship = model.Concept, model.Table, model.Relationship

Customer = Concept("Customer", identify_by={"customer_id": Integer})
Article = Concept("Article", identify_by={"article_id": Integer})
Transaction = Concept("Transaction")

model.define(Customer.new(Table(f"{DATABASE}.{SCHEMA}.CUSTOMERS").to_schema()))
model.define(Article.new(Table(f"{DATABASE}.{SCHEMA}.ARTICLES").to_schema()))
model.define(Transaction.new(Table(f"{DATABASE}.{SCHEMA}.TRANSACTIONS").to_schema()))

graph = Graph(model, directed=True, weighted=False)
Edge = graph.Edge
model.define(Edge.new(src=Transaction, dst=Customer)).where(
    Transaction.customer_id == Customer.customer_id)
model.define(Edge.new(src=Transaction, dst=Article)).where(
    Transaction.article_id == Article.article_id)

# Graph-derived features: Article popularity + Customer activity (transaction degrees).
Article.popularity_count = model.Property(
    f"{Article} has {Integer:popularity_count}")
model.define(Article.popularity_count(count(Transaction).per(Article))).where(
    Transaction.article_id == Article.article_id)

Customer.activity_count = model.Property(
    f"{Customer} has {Integer:activity_count}")
model.define(Customer.activity_count(count(Transaction).per(Customer))).where(
    Transaction.customer_id == Customer.customer_id)

# Shared PropertyTransformer — must match exactly between train and load phases.
pt = PropertyTransformer(
    category=[
        Article.product_code,
        Customer.fn, Customer.active, Customer.postal_code,
        Customer.club_member_status, Customer.fashion_news_frequency,
    ],
    text=[Article.prod_name],
    drop=[
        Article.article_id, Customer.customer_id,
        Transaction.customer_id, Transaction.article_id,
        Article.graphical_appearance_name, Article.colour_group_code,
    ],
    continuous=[Customer.age, Transaction.price],
    integer=[Article.popularity_count, Customer.activity_count],
    datetime=[Transaction.t_dat],
    time_col=[Transaction.t_dat],
)
