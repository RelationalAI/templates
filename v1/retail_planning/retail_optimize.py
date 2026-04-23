"""Retail Planning -- optimize phase.

Loads three trained GNNs from the Snowflake model registry, aggregates their
predictions into adjusted demand, and solves the markdown MILP + demand
planning LP.

Prerequisite: run `retail_train.py` first to train and register the models.

For an all-in-one single-script alternative, see `retail_planning.py`.

Run:
    python retail_optimize.py
"""

from pandas import read_csv
from relationalai.semantics import Any, Float, Integer, String, count, select, std, sum
from relationalai.semantics.reasoners.predictive import GNN
from relationalai.semantics.reasoners.prescriptive import Problem

from _retail_setup import (
    Article,
    CHURN_MODEL_NAME,
    Concept,
    Customer,
    DATA_DIR,
    DATABASE,
    GNN_EXP_DATABASE,
    GNN_EXP_SCHEMA,
    MODEL_REGISTRY_DATABASE,
    MODEL_REGISTRY_SCHEMA,
    MODEL_VERSION,
    PURCHASE_MODEL_NAME,
    Relationship,
    SALES_MODEL_NAME,
    Table,
    TASK_CHURN_SCHEMA,
    TASK_PURCHASE_SCHEMA,
    TASK_SALES_SCHEMA,
    Transaction,
    graph,
    model,
    pt,
)

# Optimizer tuning knobs — edit without retraining GNNs.
CHURN_DISCOUNT_WEIGHT = 0.3
PURCHASE_PROPENSITY_WEIGHT = 0.1
UNMET_PENALTY = 50.0

# --------------------------------------------------
# Test splits and predictions -- load each registered GNN and run inference
# --------------------------------------------------
SalesTestTable = Concept("SalesTestTable")
ChurnTestTable = Concept("ChurnTestTable")
PurchaseTestTable = Concept("PurchaseTestTable")

model.define(SalesTestTable.new(
    Table(f"{DATABASE}.{TASK_SALES_SCHEMA}.TEST").to_schema()))
model.define(ChurnTestTable.new(
    Table(f"{DATABASE}.{TASK_CHURN_SCHEMA}.TEST").to_schema()))
model.define(PurchaseTestTable.new(
    Table(f"{DATABASE}.{TASK_PURCHASE_SCHEMA}.TEST").to_schema()))

SalesTest = Relationship(f"{Article} at {Any:timestamp}")
model.define(SalesTest(Article, SalesTestTable.timestamp)).where(
    Article.article_id == SalesTestTable.article_id)

ChurnTest = Relationship(f"{Customer} at {Any:timestamp}")
model.define(ChurnTest(Customer, ChurnTestTable.timestamp)).where(
    Customer.customer_id == ChurnTestTable.customer_id)

PurchaseTest = Relationship(f"{Customer} at {Any:timestamp}")
model.define(PurchaseTest(Customer, PurchaseTestTable.timestamp)).where(
    Customer.customer_id == PurchaseTestTable.customer_id)

# Load sales regression GNN from registry.
sales_gnn = GNN(
    exp_database=GNN_EXP_DATABASE, exp_schema=GNN_EXP_SCHEMA,
    graph=graph, property_transformer=pt,
    source_concept=Article,
    task_type="regression",
    has_time_column=True,
    model_database=MODEL_REGISTRY_DATABASE, model_schema=MODEL_REGISTRY_SCHEMA,
    model_name=SALES_MODEL_NAME, version_name=MODEL_VERSION,
)
sales_gnn.load()
Article.sales_predictions = sales_gnn.predictions(domain=SalesTest)

# Load churn classification GNN from registry.
churn_gnn = GNN(
    exp_database=GNN_EXP_DATABASE, exp_schema=GNN_EXP_SCHEMA,
    graph=graph, property_transformer=pt,
    source_concept=Customer,
    task_type="binary_classification",
    has_time_column=True,
    model_database=MODEL_REGISTRY_DATABASE, model_schema=MODEL_REGISTRY_SCHEMA,
    model_name=CHURN_MODEL_NAME, version_name=MODEL_VERSION,
)
churn_gnn.load()
Customer.churn_predictions = churn_gnn.predictions(domain=ChurnTest)

# Load purchase link prediction GNN from registry.
purchase_gnn = GNN(
    exp_database=GNN_EXP_DATABASE, exp_schema=GNN_EXP_SCHEMA,
    graph=graph, property_transformer=pt,
    source_concept=Customer,
    target_concept=Article,
    task_type="repeated_link_prediction",
    has_time_column=True,
    model_database=MODEL_REGISTRY_DATABASE, model_schema=MODEL_REGISTRY_SCHEMA,
    model_name=PURCHASE_MODEL_NAME, version_name=MODEL_VERSION,
)
purchase_gnn.load()
Customer.purchase_predictions = purchase_gnn.predictions(domain=PurchaseTest)

# --------------------------------------------------
# Bridge: aggregate predictions into per-article adjusted demand
# --------------------------------------------------
inv_csv = read_csv(DATA_DIR / "articles_inventory.csv", dtype={"article_id": int})

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
    OptArticle.opt_article_id == Article.article_id)

OptArticle.predicted_sales = model.Property(
    f"{OptArticle} has {Float:predicted_sales}")
model.define(OptArticle.predicted_sales(
    Article.sales_predictions.predicted_value
)).where(OptArticle.article(Article), Article.sales_predictions)

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

OptArticle.avg_purchase_score = model.Property(
    f"{OptArticle} has {Float:avg_purchase_score}")
model.define(OptArticle.avg_purchase_score(
    sum(Customer.purchase_predictions.scores).per(OptArticle)
    / count(Customer).per(OptArticle)
)).where(
    OptArticle.article(Article),
    Customer.purchase_predictions.predicted_article == Article,
)

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
# Prescriptive A: Markdown optimization (maximize revenue)
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
# Prescriptive B: Demand/Inventory Planning (minimize cost)
# --------------------------------------------------
print("\n" + "=" * 60)
print("PRESCRIPTIVE B: Demand / Inventory Planning")
print("=" * 60)

prod_csv = read_csv(DATA_DIR / "production_capacity.csv", dtype={"article_id": int})

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

dp.display()
dp.solve("highs", time_limit_sec=120)
si_dp = dp.solve_info()
si_dp.display()

print(f"\nDemand Planning Status: {si_dp.termination_status}")
if si_dp.objective_value is not None:
    print(f"Total cost (production + holding + unmet penalty): ${si_dp.objective_value:.2f}")

# --------------------------------------------------
# Results
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
print("Optimization complete (GNN models loaded from registry).")
print("=" * 60)
