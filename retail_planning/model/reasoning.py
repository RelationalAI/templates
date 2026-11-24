"""Retail planning reasoning: sales GNN, demand aggregation, markdown MILP, and demand/inventory planning LP."""

from relationalai.semantics import Float, Integer, String, count, std, sum
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.predictive import GNN, PropertyTransformer
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.std import aggregates as aggs

from .schema import (
    Article,
    Customer,
    Discount,
    OptArticle,
    ProdCapacity,
    Test,
    Train,
    Transaction,
    Val,
    Week,
    model,
)
from .source import NUM_WEEKS

# Optimizer tuning knobs -- edit without retraining the GNN.
UNMET_PENALTY = 50.0

# Scale factor applied when aggregating normalized GNN predictions into
# optimizer demand. HM_MINI prices are [0, ~0.6]-normalized; multiplying
# makes per-article demand comparable to the inventory scale.
DEMAND_SCALE = 200.0

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

# --------------------------------------------------
# Phase 3: Bridge -- aggregate per-transaction predictions to per-article demand
# --------------------------------------------------
# Sum predicted_value across all test-period transactions for each article,
# scaled by DEMAND_SCALE so the number is comparable to inventory units. The
# demand is a property of ArticleDemand, a concept of its own: the GNN reads the
# Article table, so an Article property derived from the predictions would make
# the predictions depend on themselves, and an OptArticle property keyed by the
# transactions' article ids would add an OptArticle row for every article.
ArticleDemand = model.Concept("ArticleDemand", identify_by={"article_id": Integer})
ArticleDemand.adjusted_demand = model.Property(
    f"{ArticleDemand} has {Float:adjusted_demand}")
model.define(ArticleDemand.new(article_id=Transaction.t_article_id)).where(
    Transaction.predictions,
)
model.define(
    ArticleDemand.adjusted_demand(
        aggs.sum(Transaction, Transaction.predictions.predicted_value)
        .where(Transaction.t_article_id == ArticleDemand.article_id)
        .per(ArticleDemand) * DEMAND_SCALE
    )
)

# --------------------------------------------------
# Phase 4: Markdown optimization (MILP, maximize revenue)
# --------------------------------------------------
num_weeks = model.Relationship(f"{Integer}")
model.define(num_weeks(count(Week)))

Week_ref = Week.ref()
Discount_ref = Discount.ref()
selection_ref = Float.ref()
sales_ref = Float.ref()
cumulative_ref = Float.ref()

problem = Problem(model, Float, name="retail_markdown")

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
    ArticleDemand.article_id == OptArticle.opt_article_id,
).require(
    sales_ref <= ArticleDemand.adjusted_demand
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
    OptArticle, Week_ref, Discount_ref,
    OptArticle.initial_price * (1 - Discount_ref.discount_pct / 100) * sales_ref,
).where(OptArticle.x_sales(Week_ref, Discount_ref, sales_ref))

salvage = sum(
    OptArticle, Week_ref,
    OptArticle.initial_price * OptArticle.salvage_rate
    * (OptArticle.initial_inventory - cumulative_ref),
).where(
    OptArticle.x_cuml_sales(Week_ref, cumulative_ref),
    Week_ref.num == num_weeks,
)

problem.maximize(revenue + salvage)

# Each refresh of the deployed model runs this solve.
problem.configure("highs", time_limit_sec=120)

# The solve's status and objective, which the deployed model publishes for the queries.
MarkdownStatus = model.Relationship(f"retail markdown status is {String:status}")
MarkdownRevenue = model.Relationship(f"retail markdown revenue is {Float:revenue}")
model.define(MarkdownStatus(problem.termination_status()), MarkdownRevenue(problem.objective_value()))

# The selected discount for each article-week.
OptArticle.markdown = model.Relationship(f"{OptArticle} in {Week} is marked down by {Discount}")
model.where(
    OptArticle.x_select(Week_ref, Discount_ref, selection_ref),
    selection_ref > 0.5,
).define(OptArticle.markdown(Week_ref, Discount_ref))

# --------------------------------------------------
# Phase 5: Demand/Inventory Planning (LP, minimize cost)
# --------------------------------------------------
dp_week_ref = Week.ref()
production_ref = Float.ref()
inventory_ref = Float.ref()

dp = Problem(model, Float, name="retail_demand_planning")

ProdCapacity.x_production = model.Property(
    f"{ProdCapacity} in week {Week} produces {Float:production}")
dp.solve_for(
    ProdCapacity.x_production(dp_week_ref, production_ref),
    type="cont", lower=0,
    upper=ProdCapacity.max_production_per_week,
    name=["prod", ProdCapacity.pc_article_id, dp_week_ref.num],
    where=[dp_week_ref.num == std.common.range(1, NUM_WEEKS + 1)],
)

inv_week_ref = Integer.ref()
ProdCapacity.x_inventory = model.Property(
    f"{ProdCapacity} at end of week {Integer} has inventory {Float:inventory}")
dp.solve_for(
    ProdCapacity.x_inventory(inv_week_ref, inventory_ref),
    type="cont", lower=0,
    name=["inv", ProdCapacity.pc_article_id, inv_week_ref],
    where=[inv_week_ref == std.common.range(0, NUM_WEEKS + 1)],
)

unmet_ref = Float.ref()
ProdCapacity.x_unmet = model.Property(
    f"{ProdCapacity} in week {Week} has unmet {Float:demand}")
dp.solve_for(
    ProdCapacity.x_unmet(dp_week_ref, unmet_ref),
    type="cont", lower=0,
    name=["unmet", ProdCapacity.pc_article_id, dp_week_ref.num],
    where=[dp_week_ref.num == std.common.range(1, NUM_WEEKS + 1)],
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
    ArticleDemand.article_id == ProdCapacity.pc_article_id,
).require(
    inv_curr == inv_prev + flow_prod_ref
    - ArticleDemand.adjusted_demand * flow_week_ref.demand_multiplier
    + flow_unmet_ref
))

prod_cost_total = sum(
    ProdCapacity, dp_week_ref,
    ProdCapacity.production_cost * production_ref,
).where(ProdCapacity.x_production(dp_week_ref, production_ref))

hold_cost_total = sum(
    ProdCapacity, inv_week_ref,
    ProdCapacity.holding_cost_per_week * inventory_ref,
).where(
    ProdCapacity.x_inventory(inv_week_ref, inventory_ref),
    inv_week_ref >= 1,
)

unmet_cost_total = sum(
    ProdCapacity, dp_week_ref,
    UNMET_PENALTY * unmet_ref,
).where(ProdCapacity.x_unmet(dp_week_ref, unmet_ref))

dp.minimize(prod_cost_total + hold_cost_total + unmet_cost_total)

# Each refresh of the deployed model runs this solve.
dp.configure("highs", time_limit_sec=120)

# The solve's status and objective, which the deployed model publishes for the queries.
DemandPlanStatus = model.Relationship(f"retail demand planning status is {String:status}")
DemandPlanCost = model.Relationship(f"retail demand planning cost is {Float:cost}")
model.define(DemandPlanStatus(dp.termination_status()), DemandPlanCost(dp.objective_value()))

# The plan, which the deployed model publishes for the queries: production and unmet demand
# for each planning article and week, and inventory at the end of each week (week 0 is the
# opening stock).
ProdCapacity.planned_production = model.Relationship(
    f"{ProdCapacity} in week {Week} has planned production {Float:production}")
ProdCapacity.planned_inventory = model.Relationship(
    f"{ProdCapacity} at end of week {Integer:week} has planned inventory {Float:inventory}")
ProdCapacity.planned_unmet = model.Relationship(
    f"{ProdCapacity} in week {Week} has planned unmet demand {Float:unmet}")
plan_week, plan_end_week, plan_value = Week.ref(), Integer.ref(), Float.ref()
model.where(ProdCapacity.x_production(plan_week, plan_value)).define(
    ProdCapacity.planned_production(plan_week, plan_value))
model.where(ProdCapacity.x_inventory(plan_end_week, plan_value)).define(
    ProdCapacity.planned_inventory(plan_end_week, plan_value))
model.where(ProdCapacity.x_unmet(plan_week, plan_value)).define(
    ProdCapacity.planned_unmet(plan_week, plan_value))
