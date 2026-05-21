"""Retail Planning -- local CSV-only runner for the predict-then-optimize template.

Runs the full predict-then-optimize pipeline on a small bundled subset of the
H&M dataset (HM_MINI, ~10K customers / 5K articles / 9.6K transactions).
Everything loads from CSVs in `data/hm_mini/` via `model.data()` -- no
Snowflake data loading, no GPU required (CPU GNN training on this slice is
tractable).

Differences from the full `retail_planning.py`:
- Trains only the sales-regression GNN (transaction-level price prediction).
  Churn and purchase GNNs are omitted for simplicity; in the aggregation
  step we use sales predictions alone and skip the churn-discount and
  purchase-propensity adjustments.
- Predicts per-transaction price, then aggregates to per-article sum to get
  article-level demand for the optimizers. The full template aggregates
  article-level targets before training.

Run:
    python retail_planning_local.py
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Any, Float, Integer, Model, String, count, select, std, sum
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.predictive import GNN, PropertyTransformer
from relationalai.semantics.reasoners.prescriptive import Problem

# Optimizer tuning knobs -- edit without retraining the GNN.
UNMET_PENALTY = 50.0

# Scale factor applied when aggregating normalized GNN predictions into
# optimizer demand. HM_MINI prices are [0, ~0.6]-normalized; multiplying
# makes per-article demand comparable to the inventory scale.
DEMAND_SCALE = 200.0

DATA_DIR = Path(__file__).parent / "data"
HM_DIR = DATA_DIR / "hm_mini"

model = Model("retail_planning_local")
Concept, Relationship = model.Concept, model.Relationship

# --------------------------------------------------
# Phase 1: Core entity concepts + graph
# --------------------------------------------------
Customer = Concept("Customer", identify_by={"c_customer_id": Integer})
Article = Concept("Article", identify_by={"a_article_id": Integer})
Transaction = Concept("Transaction", identify_by={"transaction_id": Integer})

customers_df = read_csv(HM_DIR / "customers.csv")
articles_df = read_csv(HM_DIR / "articles.csv")
transactions_df = read_csv(HM_DIR / "transactions.csv")

model.define(Customer.new(model.data(customers_df).to_schema()))
model.define(Article.new(model.data(articles_df).to_schema()))
model.define(Transaction.new(model.data(transactions_df).to_schema()))

gnn_graph = Graph(model, directed=True, weighted=False)
Edge = gnn_graph.Edge
model.define(Edge.new(src=Transaction, dst=Customer)).where(
    Transaction.t_customer_id == Customer.c_customer_id)
model.define(Edge.new(src=Transaction, dst=Article)).where(
    Transaction.t_article_id == Article.a_article_id)

# PropertyTransformer -- lean set following the rai-predictive-modeling skill.
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
        Customer.postal_code,  # high-cardinality hash, not informative
    ],
    datetime=[Transaction.t_dat],
    time_col=[Transaction.t_dat],
)

# --------------------------------------------------
# Phase 2: Sales regression task (transaction-level)
# --------------------------------------------------
TrainTable = Concept("TrainTable")
ValTable = Concept("ValTable")
TestTable = Concept("TestTable")

train_df = read_csv(HM_DIR / "train_sales.csv")
val_df = read_csv(HM_DIR / "val_sales.csv")
test_df = read_csv(HM_DIR / "test_sales.csv")

model.define(TrainTable.new(model.data(train_df).to_schema()))
model.define(ValTable.new(model.data(val_df).to_schema()))
model.define(TestTable.new(model.data(test_df).to_schema()))

Train = Relationship(f"{Transaction} at {Any:timestamp} has {Any:value}")
model.define(
    Train(Transaction, TrainTable.timestamp, TrainTable.value)
).where(Transaction.transaction_id == TrainTable.transaction_id)

Val = Relationship(f"{Transaction} at {Any:timestamp} has {Any:value}")
model.define(
    Val(Transaction, ValTable.timestamp, ValTable.value)
).where(Transaction.transaction_id == ValTable.transaction_id)

Test = Relationship(f"{Transaction} at {Any:timestamp}")
model.define(
    Test(Transaction, TestTable.timestamp)
).where(Transaction.transaction_id == TestTable.transaction_id)

# Target profile -- helps interpret val-RMSE vs predict-the-mean baseline.
_target_df = select(TrainTable.value.alias("value")).to_df()
if len(_target_df):
    _s = _target_df["value"]
    print("\n=== Sales target profile (train split) ===")
    print(f"  n={len(_s)}  min={_s.min():.4g}  max={_s.max():.4g}  "
          f"mean={_s.mean():.4g}  stddev={_s.std():.4g}")
    print(f"  Baseline RMSE (predict-the-mean) ~= stddev = {_s.std():.4g}")

# --------------------------------------------------
# Phase 3: Train GNN (CPU) + predict on test
# --------------------------------------------------
print("\n" + "=" * 60)
print("PREDICTIVE: Sales regression GNN (CPU, HM_MINI)")
print("=" * 60)

gnn = GNN(
    exp_database="HM_MINI", exp_schema="EXPERIMENTS",
    graph=gnn_graph, property_transformer=pt,
    train=Train, validation=Val,
    task_type="regression", eval_metric="rmse",
    has_time_column=True, stream_logs=False, seed=42,
    device="cpu", n_epochs=20, lr=0.005,
)
gnn.fit()
Transaction.predictions = gnn.predictions(domain=Test)

# --------------------------------------------------
# Phase 4: Bridge -- aggregate per-transaction predictions to per-article demand
# --------------------------------------------------
# Sum predicted_value across all test-period transactions for each article,
# scaled by DEMAND_SCALE so the number is comparable to inventory units.
Article.predicted_demand = model.Property(
    f"{Article} has {Float:predicted_demand}")
model.define(Article.predicted_demand(
    sum(Transaction.predictions.predicted_value).per(Article) * DEMAND_SCALE
)).where(
    Transaction.predictions,
    Transaction.t_article_id == Article.a_article_id,
)

# --------------------------------------------------
# Phase 5: OptArticle (optimizer scope) with pricing/inventory
# --------------------------------------------------
inv_csv = read_csv(HM_DIR / "articles_inventory.csv", dtype={"article_id": int})

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

model.define(OptArticle.article(Article)).where(
    OptArticle.opt_article_id == Article.a_article_id)

OptArticle.adjusted_demand = model.Property(
    f"{OptArticle} has {Float:adjusted_demand}")
model.define(OptArticle.adjusted_demand(Article.predicted_demand)).where(
    OptArticle.article(Article), Article.predicted_demand)

print("\n=== Adjusted Demand per Article (from sales GNN, aggregated) ===")
model.select(
    OptArticle.opt_article_id.alias("article_id"),
    OptArticle.name,
    OptArticle.adjusted_demand,
).inspect()

# --------------------------------------------------
# Phase 6: Markdown optimization (MILP, maximize revenue)
# --------------------------------------------------
print("\n" + "=" * 60)
print("PRESCRIPTIVE A: Markdown Optimization")
print("=" * 60)

Discount = Concept("Discount", identify_by={"level": Integer})
Discount.discount_pct = model.Property(f"{Discount} has {Float:discount_pct}")
Discount.demand_lift = model.Property(f"{Discount} has {Float:demand_lift}")
discount_csv = read_csv(DATA_DIR / "discounts.csv")
model.define(Discount.new(model.data(discount_csv).to_schema()))

Week = Concept("Week", identify_by={"num": Integer})
Week.demand_multiplier = model.Property(f"{Week} has {Float:demand_multiplier}")
week_csv = read_csv(DATA_DIR / "weeks.csv")
model.define(Week.new(model.data(week_csv).to_schema()))

num_weeks = model.Relationship(f"{Integer}")
model.define(num_weeks(count(Week)))

Week_ref = Week.ref()
Discount_ref = Discount.ref()
selection_ref = Float.ref()
sales_ref = Float.ref()
cumulative_ref = Float.ref()

problem = Problem(model, Float)

OptArticle.x_select = model.Property(
    f"{OptArticle} in {Week} has {Discount} if {Float:x}")
problem.solve_for(
    OptArticle.x_select(Week_ref, Discount_ref, selection_ref),
    type="bin",
    name=["select", OptArticle.opt_article_id, Week_ref.num, Discount_ref.discount_pct],
)

OptArticle.x_sales = model.Property(
    f"{OptArticle} in {Week} at {Discount} has {Float:y}")
problem.solve_for(
    OptArticle.x_sales(Week_ref, Discount_ref, sales_ref),
    type="cont", lower=0,
    name=["sales", OptArticle.opt_article_id, Week_ref.num, Discount_ref.discount_pct],
)

OptArticle.x_cuml_sales = model.Property(
    f"{OptArticle} up to {Week} has {Float:z}")
problem.solve_for(
    OptArticle.x_cuml_sales(Week_ref, cumulative_ref),
    type="cont", lower=0,
    name=["cuml", OptArticle.opt_article_id, Week_ref.num],
)

problem.satisfy(model.where(
    OptArticle.x_select(Week_ref, Discount_ref, selection_ref)
).require(
    sum(Discount_ref, selection_ref).per(OptArticle, Week_ref) == 1
))

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

problem.satisfy(model.where(
    OptArticle.x_select(Week_ref, Discount_ref, selection_ref),
    OptArticle.x_sales(Week_ref, Discount_ref, sales_ref),
).require(
    sales_ref <= OptArticle.adjusted_demand
    * Discount_ref.demand_lift * Week_ref.demand_multiplier * selection_ref
))

problem.satisfy(model.where(
    Week_ref.num == 1,
    OptArticle.x_cuml_sales(Week_ref, cumulative_ref),
    OptArticle.x_sales(Week_ref, Discount_ref, sales_ref),
).require(
    cumulative_ref == sum(Discount_ref, sales_ref).per(OptArticle, Week_ref)
))

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

problem.satisfy(model.where(
    OptArticle.x_cuml_sales(Week_ref, cumulative_ref)
).require(
    cumulative_ref <= OptArticle.initial_inventory
))

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

problem.solve("highs", time_limit_sec=120)
si = problem.solve_info()

print(f"\nMarkdown Status: {si.termination_status}")
if si.objective_value is not None:
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

# --------------------------------------------------
# Phase 7: Demand/Inventory Planning (LP, minimize cost)
# --------------------------------------------------
print("\n" + "=" * 60)
print("PRESCRIPTIVE B: Demand / Inventory Planning")
print("=" * 60)

prod_csv = read_csv(HM_DIR / "production_capacity.csv", dtype={"article_id": int})

ProdCapacity = Concept("ProdCapacity", identify_by={"pc_article_id": Integer})
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

ProdCapacity.opt_article = model.Relationship(
    f"{ProdCapacity} has {OptArticle:opt_article}")
model.define(ProdCapacity.opt_article(OptArticle)).where(
    ProdCapacity.pc_article_id == OptArticle.opt_article_id)

num_plan_weeks = len(week_csv)

dp_week_ref = Week.ref()
production_ref = Float.ref()
inventory_ref = Float.ref()

dp = Problem(model, Float)

ProdCapacity.x_production = model.Property(
    f"{ProdCapacity} in week {Week} produces {Float:production}")
dp.solve_for(
    ProdCapacity.x_production(dp_week_ref, production_ref),
    type="cont", lower=0,
    upper=ProdCapacity.max_production_per_week,
    name=["prod", ProdCapacity.pc_article_id, dp_week_ref.num],
    where=[dp_week_ref.num == std.common.range(1, num_plan_weeks + 1)],
)

inv_week_ref = Integer.ref()
ProdCapacity.x_inventory = model.Property(
    f"{ProdCapacity} at end of week {Integer} has inventory {Float:inventory}")
dp.solve_for(
    ProdCapacity.x_inventory(inv_week_ref, inventory_ref),
    type="cont", lower=0,
    name=["inv", ProdCapacity.pc_article_id, inv_week_ref],
    where=[inv_week_ref == std.common.range(0, num_plan_weeks + 1)],
)

unmet_ref = Float.ref()
ProdCapacity.x_unmet = model.Property(
    f"{ProdCapacity} in week {Week} has unmet {Float:demand}")
dp.solve_for(
    ProdCapacity.x_unmet(dp_week_ref, unmet_ref),
    type="cont", lower=0,
    name=["unmet", ProdCapacity.pc_article_id, dp_week_ref.num],
    where=[dp_week_ref.num == std.common.range(1, num_plan_weeks + 1)],
)

inv_init_ref = Float.ref()
dp.satisfy(model.where(
    ProdCapacity.x_inventory(0, inv_init_ref),
).require(inv_init_ref == ProdCapacity.pc_initial_inventory))

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

dp.solve("highs", time_limit_sec=120)
si_dp = dp.solve_info()

print(f"\nDemand Planning Status: {si_dp.termination_status}")
if si_dp.objective_value is not None:
    print(f"Total cost (production + holding + unmet penalty): ${si_dp.objective_value:.2f}")

print("\n" + "=" * 60)
print("Local run complete. Full pipeline (all 3 GNNs): retail_planning.py")
print("=" * 60)
