"""Retail Planning -- predict-then-optimize template.

This script demonstrates a multi-reasoner pipeline on a retail dataset
(H&M via RelBench) in RelationalAI:

- Train three GNN models (item-sales regression, user-churn classification,
  user-item purchase link prediction) using the predictive reasoner.
- Aggregate predictions into churn-adjusted demand per article.
- Solve a markdown optimization (MILP) to choose discount schedules that
  maximize revenue while clearing inventory.
- Solve a demand/inventory planning (LP) to decide production quantities that
  minimize total cost given predicted demand.

The key idea: GNN-predicted sales, churn risk, and purchase propensity replace
static demand parameters in both optimization problems, creating a
predict-then-optimize pipeline.

Run:
    `python retail_planning.py`

Output:
    GNN evaluation metrics, optimal discount schedules, production plans,
    and cost/revenue summaries.
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Any, Float, Integer, Model, String, count, select, std, sum
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.predictive import GNN, PropertyTransformer
from relationalai.semantics.reasoners.prescriptive import Problem

# --------------------------------------------------
# Configuration
# --------------------------------------------------
# Snowflake location for H&M data. Adjust to match your environment.
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

# GNN determinism and log-stream behavior.
SEED = 42
STREAM_LOGS = False  # True for TTY; False avoids spinner flood in non-TTY logs

# Observability: print the engine-side data config after each fit(). Useful for
# spotting PropertyTransformer or edge misconfig early. Set True if debugging.
VERBOSE_DATASET = False


def _report(gnn, label):
    """After gnn.fit(), dump the engine-side data config (and optionally a
    schema PNG) to help diagnose feature-type or edge misconfig."""
    if not VERBOSE_DATASET:
        return
    print(f"\n--- {label}: engine-side data config ---")
    try:
        gnn.dataset.print_data_config()
    except Exception as e:  # best-effort debug, never block training
        print(f"  print_data_config unavailable: {e}")
    try:
        viz = gnn.visualize_dataset(show_dtypes=True)
        viz.write_png(f"{label}_schema.png")
        print(f"  wrote {label}_schema.png")
    except Exception as e:
        print(f"  visualize_dataset unavailable (install pydot?): {e}")

# Churn-adjustment weight: how much churn risk reduces demand (0 = ignore, 1 = full)
CHURN_DISCOUNT_WEIGHT = 0.3

# Purchase-propensity weight: how much predicted purchase demand uplifts demand
PURCHASE_PROPENSITY_WEIGHT = 0.1

# Unmet-demand penalty for demand planning
UNMET_PENALTY = 50.0

DATA_DIR = Path(__file__).parent / "data"

# --------------------------------------------------
# Phase 1: Shared Model & Data
# --------------------------------------------------

model = Model("retail_planning")
Concept, Table, Relationship = model.Concept, model.Table, model.Relationship

# Core entity concepts (shared across all GNN tasks)
Customer = Concept("Customer", identify_by={"customer_id": Integer})
Article = Concept("Article", identify_by={"article_id": Integer})
Transaction = Concept("Transaction")

# Populate from Snowflake
customers_table = Table(f"{DATABASE}.{SCHEMA}.CUSTOMERS")
model.define(Customer.new(customers_table.to_schema()))

articles_table = Table(f"{DATABASE}.{SCHEMA}.ARTICLES")
model.define(Article.new(articles_table.to_schema()))

transactions_table = Table(f"{DATABASE}.{SCHEMA}.TRANSACTIONS")
model.define(Transaction.new(transactions_table.to_schema()))

# Shared knowledge graph -- all three GNN tasks use the same Customer-Transaction-Article
# graph structure. Only the PropertyTransformer and task relationships differ.
graph = Graph(model, directed=True, weighted=False)
Edge = graph.Edge
model.define(Edge.new(src=Transaction, dst=Customer)).where(
    Transaction.customer_id == Customer.customer_id)
model.define(Edge.new(src=Transaction, dst=Article)).where(
    Transaction.article_id == Article.article_id)

# Graph-derived features — the pattern from rai-graph-analysis for feeding
# computed graph metrics into GNN features. Article popularity = incoming
# transaction degree; Customer activity = outgoing transaction degree. These
# give the GNN explicit signal beyond raw graph structure.
Article.popularity_count = model.Property(
    f"{Article} has {Integer:popularity_count}")
model.define(Article.popularity_count(count(Transaction).per(Article))).where(
    Transaction.article_id == Article.article_id)

Customer.activity_count = model.Property(
    f"{Customer} has {Integer:activity_count}")
model.define(Customer.activity_count(count(Transaction).per(Customer))).where(
    Transaction.customer_id == Customer.customer_id)

# Shared property transformer — same feature configuration for all three GNN tasks.
# Graph structure already encodes PKs/FKs; drop them so they don't pollute features.
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

# --------------------------------------------------
# Phase 2: Predictive — Item Sales (regression)
# --------------------------------------------------
# Predict total sales (sum of transaction prices) per article for the next
# 7-day window. Output feeds the prescriptive optimizers as demand forecasts.

# Task table concepts
SalesTrainTable = Concept("SalesTrainTable")
SalesValTable = Concept("SalesValTable")
SalesTestTable = Concept("SalesTestTable")

model.define(SalesTrainTable.new(
    Table(f"{DATABASE}.{TASK_SALES_SCHEMA}.TRAIN").to_schema()))
model.define(SalesValTable.new(
    Table(f"{DATABASE}.{TASK_SALES_SCHEMA}.VAL").to_schema()))
model.define(SalesTestTable.new(
    Table(f"{DATABASE}.{TASK_SALES_SCHEMA}.TEST").to_schema()))

# Task relationships (newer Graph/Relationship API)
SalesTrain = Relationship(f"{Article} at {Any:timestamp} has {Any:sales}")
model.define(
    SalesTrain(Article, SalesTrainTable.timestamp, SalesTrainTable.sales)
).where(Article.article_id == SalesTrainTable.article_id)

SalesVal = Relationship(f"{Article} at {Any:timestamp} has {Any:sales}")
model.define(
    SalesVal(Article, SalesValTable.timestamp, SalesValTable.sales)
).where(Article.article_id == SalesValTable.article_id)

SalesTest = Relationship(f"{Article} at {Any:timestamp}")
model.define(
    SalesTest(Article, SalesTestTable.timestamp)
).where(Article.article_id == SalesTestTable.article_id)

# Profile the sales target distribution on the train split. Val-RMSE below
# this stddev means the GNN is learning signal; at or above means the model
# has collapsed to the mean. See rai-predictive-training evaluation-debugging.
_sales_target_df = select(SalesTrainTable.sales.alias("sales")).to_df()
if len(_sales_target_df):
    _s = _sales_target_df["sales"]
    print("\n=== Sales target profile (train split) ===")
    print(f"  n={len(_s)}  min={_s.min():.4g}  max={_s.max():.4g}  "
          f"mean={_s.mean():.4g}  stddev={_s.std():.4g}")
    print(f"  Baseline RMSE (predict-the-mean) ~= stddev = {_s.std():.4g}")

# Train and predict
sales_gnn = GNN(
    exp_database=GNN_EXP_DATABASE, exp_schema=GNN_EXP_SCHEMA,
    graph=graph, property_transformer=pt,
    train=SalesTrain, validation=SalesVal,
    task_type="regression", eval_metric="rmse",
    has_time_column=True, stream_logs=STREAM_LOGS, seed=SEED,
    device="cuda", n_epochs=20, train_batch_size=256, lr=0.005, head_layers=2,
    temporal_strategy="last", max_iters=500,
)
sales_gnn.fit()
_report(sales_gnn, "sales_gnn")
Article.sales_predictions = sales_gnn.predictions(domain=SalesTest)

# Sanity check: warn if predictions are NaN or negative
_sales_df = select(
    Article.article_id, Article.sales_predictions.predicted_value,
).where(Article.sales_predictions).to_df()
if _sales_df["predicted_value"].isna().any() or (_sales_df["predicted_value"] < 0).any():
    print("WARNING: Sales predictions contain NaN or negative values")

print("=== Item Sales Predictions (sample) ===")
select(
    Article.article_id,
    Article.sales_predictions.predicted_value,
).where(Article.sales_predictions).inspect()

# --------------------------------------------------
# Phase 3: Predictive — User Churn (binary classification)
# --------------------------------------------------
# Predict whether a customer will churn (no transactions) in the next 7 days.
# Output is aggregated per article to create a churn-adjusted demand factor.

ChurnTrainTable = Concept("ChurnTrainTable")
ChurnValTable = Concept("ChurnValTable")
ChurnTestTable = Concept("ChurnTestTable")

model.define(ChurnTrainTable.new(
    Table(f"{DATABASE}.{TASK_CHURN_SCHEMA}.TRAIN").to_schema()))
model.define(ChurnValTable.new(
    Table(f"{DATABASE}.{TASK_CHURN_SCHEMA}.VAL").to_schema()))
model.define(ChurnTestTable.new(
    Table(f"{DATABASE}.{TASK_CHURN_SCHEMA}.TEST").to_schema()))

# Task relationships
ChurnTrain = Relationship(f"{Customer} at {Any:timestamp} has {Any:churn}")
model.define(
    ChurnTrain(Customer, ChurnTrainTable.timestamp, ChurnTrainTable.churn)
).where(Customer.customer_id == ChurnTrainTable.customer_id)

ChurnVal = Relationship(f"{Customer} at {Any:timestamp} has {Any:churn}")
model.define(
    ChurnVal(Customer, ChurnValTable.timestamp, ChurnValTable.churn)
).where(Customer.customer_id == ChurnValTable.customer_id)

ChurnTest = Relationship(f"{Customer} at {Any:timestamp}")
model.define(
    ChurnTest(Customer, ChurnTestTable.timestamp)
).where(Customer.customer_id == ChurnTestTable.customer_id)

# Train and predict
churn_gnn = GNN(
    exp_database=GNN_EXP_DATABASE, exp_schema=GNN_EXP_SCHEMA,
    graph=graph, property_transformer=pt,
    train=ChurnTrain, validation=ChurnVal,
    task_type="binary_classification", eval_metric="roc_auc",
    has_time_column=True, stream_logs=STREAM_LOGS, seed=SEED,
    device="cuda", n_epochs=5, train_batch_size=256, lr=0.005, head_layers=2,
    temporal_strategy="last", max_iters=500,
)
churn_gnn.fit()
_report(churn_gnn, "churn_gnn")
Customer.churn_predictions = churn_gnn.predictions(domain=ChurnTest)

# Sanity check: warn if churn probabilities are outside [0, 1]
_churn_df = select(
    Customer.customer_id, Customer.churn_predictions.probs,
).where(Customer.churn_predictions).to_df()
if _churn_df["probs"].isna().any() or (_churn_df["probs"] < 0).any() or (_churn_df["probs"] > 1).any():
    print("WARNING: Churn predictions contain NaN or out-of-range probabilities")

print("\n=== User Churn Predictions (sample) ===")
select(
    Customer.customer_id,
    Customer.churn_predictions.predicted_labels,
    Customer.churn_predictions.probs,
).where(Customer.churn_predictions).inspect()

# --------------------------------------------------
# Phase 4: Predictive — User-Item Purchase (link prediction)
# --------------------------------------------------
# Predict which articles each customer will purchase in the next 7 days.
# Aggregated per article in Phase 5 as a demand uplift signal.

PurchaseTrainTable = Concept("PurchaseTrainTable")
PurchaseValTable = Concept("PurchaseValTable")
PurchaseTestTable = Concept("PurchaseTestTable")

model.define(PurchaseTrainTable.new(
    Table(f"{DATABASE}.{TASK_PURCHASE_SCHEMA}.TRAIN").to_schema()))
model.define(PurchaseValTable.new(
    Table(f"{DATABASE}.{TASK_PURCHASE_SCHEMA}.VAL").to_schema()))
model.define(PurchaseTestTable.new(
    Table(f"{DATABASE}.{TASK_PURCHASE_SCHEMA}.TEST").to_schema()))

# Task relationships (link prediction uses source → target pattern)
PurchaseTrain = Relationship(f"{Customer} at {Any:timestamp} has {Article}")
model.define(
    PurchaseTrain(Customer, PurchaseTrainTable.timestamp, Article)
).where(
    Customer.customer_id == PurchaseTrainTable.customer_id,
    Article.article_id == PurchaseTrainTable.article_id,
)

PurchaseVal = Relationship(f"{Customer} at {Any:timestamp} has {Article}")
model.define(
    PurchaseVal(Customer, PurchaseValTable.timestamp, Article)
).where(
    Customer.customer_id == PurchaseValTable.customer_id,
    Article.article_id == PurchaseValTable.article_id,
)

PurchaseTest = Relationship(f"{Customer} at {Any:timestamp}")
model.define(
    PurchaseTest(Customer, PurchaseTestTable.timestamp)
).where(Customer.customer_id == PurchaseTestTable.customer_id)
# Train and predict
purchase_gnn = GNN(
    exp_database=GNN_EXP_DATABASE, exp_schema=GNN_EXP_SCHEMA,
    graph=graph, property_transformer=pt,
    train=PurchaseTrain, validation=PurchaseVal,
    task_type="repeated_link_prediction", eval_metric="link_prediction_map@12",
    has_time_column=True, stream_logs=STREAM_LOGS, seed=SEED,
    device="cuda", n_epochs=5, train_batch_size=16, lr=0.0001,
    temporal_strategy="last", max_iters=500,
)
purchase_gnn.fit()
_report(purchase_gnn, "purchase_gnn")
Customer.purchase_predictions = purchase_gnn.predictions(domain=PurchaseTest)

# Sanity check: warn if purchase scores are NaN
_purchase_df = select(
    Customer.customer_id, Customer.purchase_predictions.scores,
).where(Customer.purchase_predictions).to_df()
if _purchase_df["scores"].isna().any():
    print("WARNING: Purchase predictions contain NaN scores")

print("\n=== User-Item Purchase Predictions (sample) ===")
select(
    Customer.customer_id,
    Customer.purchase_predictions.predicted_article,
    Customer.purchase_predictions.rank,
    Customer.purchase_predictions.scores,
).where(Customer.purchase_predictions).inspect()

# --------------------------------------------------
# Phase 5: Bridge — Aggregate Predictions for Prescriptive Use
# --------------------------------------------------
# Combine all three GNN outputs into an adjusted demand estimate per article.
# This is the key linkage: GNN output -> optimizer input.
#
# For each article in the optimizer's subset:
#   adjusted_demand = predicted_sales
#                     * (1 - CHURN_DISCOUNT_WEIGHT * avg_buyer_churn)
#                     * (1 + PURCHASE_PROPENSITY_WEIGHT * avg_purchase_score)
#
# Articles whose recent buyers have high churn risk get reduced demand estimates,
# while articles with high purchase propensity get an uplift.

# Load article subset for optimization (fabricated pricing/inventory data)
inv_csv = read_csv(DATA_DIR / "articles_inventory.csv", dtype={"article_id": int})

# Concept: articles in the optimizer's scope, with pricing and inventory
OptArticle = Concept("OptArticle", identify_by={"opt_article_id": Integer})
OptArticle.name = model.Property(f"{OptArticle} has {String:name}")
OptArticle.initial_price = model.Property(f"{OptArticle} has {Float:initial_price}")
OptArticle.cost = model.Property(f"{OptArticle} has {Float:cost}")
OptArticle.initial_inventory = model.Property(
    f"{OptArticle} has {Integer:initial_inventory}")
OptArticle.salvage_rate = model.Property(f"{OptArticle} has {Float:salvage_rate}")

inv_data = model.data(inv_csv)
model.define(
    oa := OptArticle.new(opt_article_id=inv_data.article_id),
    oa.name(inv_data.name),
    oa.initial_price(inv_data.initial_price),
    oa.cost(inv_data.cost),
    oa.initial_inventory(inv_data.initial_inventory),
    oa.salvage_rate(inv_data.salvage_rate),
)

# Link OptArticle to the Article concept (for joining with GNN predictions)
model.define(OptArticle.article(Article)).where(
    OptArticle.opt_article_id == Article.article_id)

# Derive predicted demand per OptArticle from item-sales GNN
OptArticle.predicted_sales = model.Property(
    f"{OptArticle} has {Float:predicted_sales}")
model.define(OptArticle.predicted_sales(
    Article.sales_predictions.predicted_value
)).where(OptArticle.article(Article), Article.sales_predictions)

# Derive average churn probability of each article's recent buyers.
# Buyers are customers who purchased the article (via Transaction).
OptArticle.avg_buyer_churn = model.Property(
    f"{OptArticle} has {Float:avg_buyer_churn}")
model.define(OptArticle.avg_buyer_churn(
    sum(Customer.churn_predictions.probs).per(OptArticle)
    / count(Customer).per(OptArticle)
)).where(
    OptArticle.article(Article),
    Transaction.article_id == Article.article_id,
    Transaction.customer_id == Customer.customer_id,
    Customer.churn_predictions,
)

# Purchase propensity: average prediction score across customers predicted to buy
OptArticle.avg_purchase_score = model.Property(
    f"{OptArticle} has {Float:avg_purchase_score}")
model.define(OptArticle.avg_purchase_score(
    sum(Customer.purchase_predictions.scores).per(OptArticle)
    / count(Customer).per(OptArticle)
)).where(
    OptArticle.article(Article),
    Customer.purchase_predictions.predicted_article == Article,
)

# Adjusted demand: combine all three GNN signals
OptArticle.adjusted_demand = model.Property(
    f"{OptArticle} has {Float:adjusted_demand}")
model.define(OptArticle.adjusted_demand(
    OptArticle.predicted_sales
    * (1 - CHURN_DISCOUNT_WEIGHT * OptArticle.avg_buyer_churn)
    * (1 + PURCHASE_PROPENSITY_WEIGHT * OptArticle.avg_purchase_score)
))

print("\n=== Adjusted Demand per Article ===")
model.select(
    OptArticle.opt_article_id.alias("article_id"),
    OptArticle.name,
    OptArticle.predicted_sales,
    OptArticle.avg_buyer_churn,
    OptArticle.avg_purchase_score,
    OptArticle.adjusted_demand,
).inspect()

# --------------------------------------------------
# Phase 6: Prescriptive A — Markdown Optimization (maximize revenue)
# --------------------------------------------------
# Given GNN-predicted demand, choose a weekly discount schedule per article to
# maximize total revenue (sales + salvage) while clearing inventory.
# Adapted from the retail_markdown template.

print("\n" + "=" * 60)
print("PRESCRIPTIVE A: Markdown Optimization")
print("=" * 60)

# Discount concept: markdown tiers with demand response.
Discount = Concept("Discount", identify_by={"level": Integer})
Discount.discount_pct = model.Property(f"{Discount} has {Float:discount_pct}")
Discount.demand_lift = model.Property(f"{Discount} has {Float:demand_lift}")
discount_csv = read_csv(DATA_DIR / "discounts.csv")
model.define(Discount.new(model.data(discount_csv).to_schema()))

# Week concept: planning periods with seasonal demand multipliers.
Week = Concept("Week", identify_by={"num": Integer})
Week.demand_multiplier = model.Property(f"{Week} has {Float:demand_multiplier}")
week_csv = read_csv(DATA_DIR / "weeks.csv")
model.define(Week.new(model.data(week_csv).to_schema()))

num_weeks = model.Relationship(f"{Integer}")
model.define(num_weeks(count(Week)))

# Decision variable references
Week_ref = Week.ref()
Discount_ref = Discount.ref()
selection_ref = Float.ref()
sales_ref = Float.ref()
cumulative_ref = Float.ref()

problem = Problem(model, Float)

# Variable: select[article, week, discount] — binary: is this discount active?
OptArticle.x_select = model.Property(
    f"{OptArticle} in {Week} has {Discount} if {Float:x}")
problem.solve_for(
    OptArticle.x_select(Week_ref, Discount_ref, selection_ref),
    type="bin",
    name=["select", OptArticle.opt_article_id, Week_ref.num, Discount_ref.discount_pct],
)

# Variable: sales[article, week, discount] — continuous: units sold
OptArticle.x_sales = model.Property(
    f"{OptArticle} in {Week} at {Discount} has {Float:y}")
problem.solve_for(
    OptArticle.x_sales(Week_ref, Discount_ref, sales_ref),
    type="cont", lower=0,
    name=["sales", OptArticle.opt_article_id, Week_ref.num, Discount_ref.discount_pct],
)

# Variable: cumulative sales[article, week] — continuous: total sold through week
OptArticle.x_cuml_sales = model.Property(
    f"{OptArticle} up to {Week} has {Float:z}")
problem.solve_for(
    OptArticle.x_cuml_sales(Week_ref, cumulative_ref),
    type="cont", lower=0,
    name=["cuml", OptArticle.opt_article_id, Week_ref.num],
)

# Constraint: exactly one discount level per article-week
problem.satisfy(model.where(
    OptArticle.x_select(Week_ref, Discount_ref, selection_ref)
).require(
    sum(Discount_ref, selection_ref).per(OptArticle, Week_ref) == 1
))

# Constraint: price ladder — discounts can only increase week-over-week
Discount_inner = Discount.ref()
Week_inner = Week.ref()
selection_inner = Float.ref()
problem.satisfy(model.where(
    OptArticle.x_select(Week_ref, Discount_ref, selection_ref),
    OptArticle.x_select(Week_inner, Discount_inner, selection_inner),
    Week_inner.num == Week_ref.num + 1,
    Discount_inner.level < Discount_ref.level,
).require(
    selection_ref + selection_inner <= 1
))

# Constraint: sales bounded by adjusted demand * lift * weekly multiplier * selection
# Key difference from retail_markdown: base demand is GNN-predicted, not static CSV
problem.satisfy(model.where(
    OptArticle.x_select(Week_ref, Discount_ref, selection_ref),
    OptArticle.x_sales(Week_ref, Discount_ref, sales_ref),
).require(
    sales_ref <= OptArticle.adjusted_demand
    * Discount_ref.demand_lift * Week_ref.demand_multiplier * selection_ref
))

# Constraint: cumulative sales — first week
problem.satisfy(model.where(
    Week_ref.num == 1,
    OptArticle.x_cuml_sales(Week_ref, cumulative_ref),
    OptArticle.x_sales(Week_ref, Discount_ref, sales_ref),
).require(
    cumulative_ref == sum(Discount_ref, sales_ref).per(OptArticle, Week_ref)
))

# Constraint: cumulative sales — subsequent weeks
Week_prev = Week.ref()
cumulative_prev = Float.ref()
problem.satisfy(model.where(
    Week_ref.num > 1,
    Week_prev.num == Week_ref.num - 1,
    OptArticle.x_cuml_sales(Week_ref, cumulative_ref),
    OptArticle.x_cuml_sales(Week_prev, cumulative_prev),
    OptArticle.x_sales(Week_ref, Discount_ref, sales_ref),
).require(
    cumulative_ref == cumulative_prev
    + sum(Discount_ref, sales_ref).per(OptArticle, Week_ref)
))

# Constraint: cumulative sales cannot exceed initial inventory
problem.satisfy(model.where(
    OptArticle.x_cuml_sales(Week_ref, cumulative_ref)
).require(
    cumulative_ref <= OptArticle.initial_inventory
))

# Objective: maximize revenue from sales + salvage value of remaining inventory
revenue = sum(
    OptArticle.initial_price * (1 - Discount_ref.discount_pct / 100) * sales_ref
).where(OptArticle.x_sales(Week_ref, Discount_ref, sales_ref))

salvage = sum(
    OptArticle.initial_price * OptArticle.salvage_rate
    * (OptArticle.initial_inventory - cumulative_ref)
).where(
    OptArticle.x_cuml_sales(Week_ref, cumulative_ref),
    Week_ref.num == num_weeks,
)

problem.maximize(revenue + salvage)

# Solve
problem.display()
problem.solve("highs", time_limit_sec=120)
model.require(problem.termination_status() == "OPTIMAL")
si = problem.solve_info()
si.display()

print(f"\nMarkdown Status: {si.termination_status}")
print(f"Total revenue (sales + salvage): ${si.objective_value:.2f}")

print("\n=== Markdown: Selected Discounts by Article-Week ===")
model.select(
    OptArticle.name.alias("article"),
    Week_ref.num.alias("week"),
    Discount_ref.discount_pct.alias("discount_pct"),
).where(
    OptArticle.x_select(Week_ref, Discount_ref, selection_ref),
    selection_ref > 0.5,
).inspect()

print("\n=== Markdown: Sales by Article-Week ===")
model.select(
    OptArticle.name.alias("article"),
    Week_ref.num.alias("week"),
    Discount_ref.discount_pct.alias("discount_pct"),
    sales_ref.alias("units_sold"),
).where(
    OptArticle.x_sales(Week_ref, Discount_ref, sales_ref),
    sales_ref > 0.01,
).inspect()

print("\n=== Markdown: Cumulative Sales by Article-Week ===")
model.select(
    OptArticle.name.alias("article"),
    Week_ref.num.alias("week"),
    cumulative_ref.alias("cumulative_sold"),
).where(OptArticle.x_cuml_sales(Week_ref, cumulative_ref)).inspect()

# --------------------------------------------------
# Phase 7: Prescriptive B — Demand/Inventory Planning (minimize cost)
# --------------------------------------------------
# Given GNN-predicted demand, decide how much to produce per article per week
# to minimize total cost (production + holding + unmet demand penalty).
# Adapted from the demand_planning_temporal template.

print("\n" + "=" * 60)
print("PRESCRIPTIVE B: Demand / Inventory Planning")
print("=" * 60)

# ProdCapacity concept: per-article production parameters for demand planning.
prod_csv = read_csv(DATA_DIR / "production_capacity.csv", dtype={"article_id": int})

ProdCapacity = Concept(
    "ProdCapacity", identify_by={"pc_article_id": Integer})
ProdCapacity.max_production_per_week = model.Property(
    f"{ProdCapacity} has {Integer:max_production_per_week}")
ProdCapacity.production_cost = model.Property(
    f"{ProdCapacity} has {Float:production_cost}")
ProdCapacity.holding_cost_per_week = model.Property(
    f"{ProdCapacity} has {Float:holding_cost_per_week}")
ProdCapacity.pc_initial_inventory = model.Property(
    f"{ProdCapacity} has {Float:pc_initial_inventory}")

prod_data = model.data(prod_csv)
model.define(
    pc := ProdCapacity.new(pc_article_id=prod_data.article_id),
    pc.max_production_per_week(prod_data.max_production_per_week),
    pc.production_cost(prod_data.production_cost),
    pc.holding_cost_per_week(prod_data.holding_cost_per_week),
    pc.pc_initial_inventory(prod_data.initial_inventory),
)

# Link ProdCapacity to OptArticle (for joining with adjusted demand)
model.define(ProdCapacity.opt_article(OptArticle)).where(
    ProdCapacity.pc_article_id == OptArticle.opt_article_id)

# Planning uses the same Week concept from Phase 6
num_plan_weeks = len(week_csv)

# Decision variable references
dp_week_ref = Week.ref()
production_ref = Float.ref()
inventory_ref = Float.ref()

dp = Problem(model, Float)

# Variable: production[article, week] — units to produce
ProdCapacity.x_production = model.Property(
    f"{ProdCapacity} in week {Week} produces {Float:production}")
dp.solve_for(
    ProdCapacity.x_production(dp_week_ref, production_ref),
    type="cont", lower=0,
    upper=ProdCapacity.max_production_per_week,
    name=["prod", ProdCapacity.pc_article_id, dp_week_ref.num],
    where=[dp_week_ref.num == std.common.range(1, num_plan_weeks + 1)],
)

# Variable: inventory[article, week] — stock at end of week (week 0 = initial)
inv_week_ref = Integer.ref()
ProdCapacity.x_inventory = model.Property(
    f"{ProdCapacity} at end of week {Integer} has inventory {Float:inventory}")
dp.solve_for(
    ProdCapacity.x_inventory(inv_week_ref, inventory_ref),
    type="cont", lower=0,
    name=["inv", ProdCapacity.pc_article_id, inv_week_ref],
    where=[inv_week_ref == std.common.range(0, num_plan_weeks + 1)],
)

# Variable: unmet demand[article, week] — shortfall
unmet_ref = Float.ref()
ProdCapacity.x_unmet = model.Property(
    f"{ProdCapacity} in week {Week} has unmet {Float:demand}")
dp.solve_for(
    ProdCapacity.x_unmet(dp_week_ref, unmet_ref),
    type="cont", lower=0,
    name=["unmet", ProdCapacity.pc_article_id, dp_week_ref.num],
    where=[dp_week_ref.num == std.common.range(1, num_plan_weeks + 1)],
)

# Constraint: initial inventory (week 0)
inv_init_ref = Float.ref()
dp.satisfy(model.where(
    ProdCapacity.x_inventory(0, inv_init_ref),
).require(inv_init_ref == ProdCapacity.pc_initial_inventory))

# Constraint: flow conservation — inv[t] = inv[t-1] + production[t] - demand[t] + unmet[t]
# Demand per article per week = adjusted_demand * weekly_multiplier (spread across weeks)
inv_curr = Float.ref()
inv_prev = Float.ref()
flow_prod_ref = Float.ref()
flow_unmet_ref = Float.ref()
flow_week_ref = Week.ref()

dp.satisfy(model.where(
    ProdCapacity.x_inventory(flow_week_ref.num, inv_curr),
    ProdCapacity.x_inventory(flow_week_ref.num - 1, inv_prev),
    ProdCapacity.x_production(flow_week_ref, flow_prod_ref),
    ProdCapacity.x_unmet(flow_week_ref, flow_unmet_ref),
    ProdCapacity.opt_article(OptArticle),
).require(
    inv_curr == inv_prev + flow_prod_ref
    - OptArticle.adjusted_demand * flow_week_ref.demand_multiplier
    + flow_unmet_ref
))

# Objective: minimize production cost + holding cost + unmet demand penalty
prod_cost_total = sum(
    ProdCapacity.production_cost * production_ref
).where(ProdCapacity.x_production(dp_week_ref, production_ref))

hold_cost_total = sum(
    ProdCapacity.holding_cost_per_week * inventory_ref
).where(
    ProdCapacity.x_inventory(inv_week_ref, inventory_ref),
    inv_week_ref >= 1,
)

unmet_cost_total = sum(
    UNMET_PENALTY * unmet_ref
).where(ProdCapacity.x_unmet(dp_week_ref, unmet_ref))

dp.minimize(prod_cost_total + hold_cost_total + unmet_cost_total)

# Solve
dp.display()
dp.solve("highs", time_limit_sec=120)
si_dp = dp.solve_info()
si_dp.display()

print(f"\nDemand Planning Status: {si_dp.termination_status}")
if si_dp.objective_value is not None:
    print(f"Total cost (production + holding + unmet penalty): ${si_dp.objective_value:.2f}")

# --------------------------------------------------
# Phase 8: Results Display
# --------------------------------------------------

week_ref = Week.ref()
int_ref = Integer.ref()
value_ref = Float.ref()

print("\n=== Demand Planning: Production Plan (non-zero) ===")
prod_rows = (
    model.select(
        ProdCapacity.pc_article_id.alias("article_id"),
        week_ref.num.alias("week"),
        value_ref.alias("production"),
    )
    .where(
        ProdCapacity.x_production(week_ref, value_ref),
        value_ref > 0.01,
    )
    .to_df()
)
if not prod_rows.empty:
    print(prod_rows.to_string(index=False))
else:
    print("  No production needed.")

print("\n=== Demand Planning: Inventory Levels ===")
inv_rows = (
    model.select(
        ProdCapacity.pc_article_id.alias("article_id"),
        int_ref.alias("week"),
        value_ref.alias("inventory"),
    )
    .where(ProdCapacity.x_inventory(int_ref, value_ref))
    .to_df()
)
if not inv_rows.empty:
    print(inv_rows.to_string(index=False))

print("\n=== Demand Planning: Unmet Demand ===")
unmet_rows = (
    model.select(
        ProdCapacity.pc_article_id.alias("article_id"),
        week_ref.num.alias("week"),
        value_ref.alias("unmet"),
    )
    .where(
        ProdCapacity.x_unmet(week_ref, value_ref),
        value_ref > 0.01,
    )
    .to_df()
)
if unmet_rows.empty:
    print("  All demand fulfilled!")
else:
    print(unmet_rows.to_string(index=False))

print("\n" + "=" * 60)
print("Pipeline Complete")
print("=" * 60)
print("Predictive: 3 GNN models trained (item-sales, user-churn, user-item-purchase)")
print("Prescriptive A (Markdown): discount schedule optimized for revenue")
print("Prescriptive B (Demand Planning): production plan optimized for cost")
