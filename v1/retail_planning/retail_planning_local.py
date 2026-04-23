"""Retail Planning -- local CSV-only runner.

Runs only the prescriptive phases (markdown + demand planning) using
pre-computed predictions from `data/predictions_sample.csv`. Useful for:

- Quickly demoing the optimizer logic without Snowflake / GPU / H&M data
- Regression-testing the prescriptive models after changes

The full predict-then-optimize pipeline (with real GNN training on H&M) is
`retail_planning.py`. This local runner substitutes `predictions_sample.csv`
for the GNN outputs so the optimizers have inputs; numbers are illustrative.

Run:
    python retail_planning_local.py
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Float, Integer, String, count, select, std, sum
from relationalai.semantics import Model
from relationalai.semantics.reasoners.prescriptive import Problem

CHURN_DISCOUNT_WEIGHT = 0.3
PURCHASE_PROPENSITY_WEIGHT = 0.1
UNMET_PENALTY = 50.0

DATA_DIR = Path(__file__).parent / "data"

model = Model("retail_planning_local")
Concept = model.Concept

# --------------------------------------------------
# OptArticle -- pricing, inventory, and stubbed GNN predictions
# --------------------------------------------------
inv_csv = read_csv(DATA_DIR / "articles_inventory.csv", dtype={"article_id": int})
pred_csv = read_csv(DATA_DIR / "predictions_sample.csv", dtype={"article_id": int})
combined = inv_csv.merge(pred_csv, on="article_id", how="inner")

OptArticle = Concept("OptArticle", identify_by={"opt_article_id": Integer})
OptArticle.name = model.Property(f"{OptArticle} has {String:name}")
OptArticle.initial_price = model.Property(f"{OptArticle} has {Float:initial_price}")
OptArticle.cost = model.Property(f"{OptArticle} has {Float:cost}")
OptArticle.initial_inventory = model.Property(
    f"{OptArticle} has {Integer:initial_inventory}")
OptArticle.salvage_rate = model.Property(f"{OptArticle} has {Float:salvage_rate}")
OptArticle.predicted_sales = model.Property(
    f"{OptArticle} has {Float:predicted_sales}")
OptArticle.avg_buyer_churn = model.Property(
    f"{OptArticle} has {Float:avg_buyer_churn}")
OptArticle.avg_purchase_score = model.Property(
    f"{OptArticle} has {Float:avg_purchase_score}")
OptArticle.adjusted_demand = model.Property(
    f"{OptArticle} has {Float:adjusted_demand}")

d = model.data(combined)
model.define(
    oa := OptArticle.new(opt_article_id=d.article_id),
    oa.name(d.name),
    oa.initial_price(d.initial_price),
    oa.cost(d.cost),
    oa.initial_inventory(d.initial_inventory),
    oa.salvage_rate(d.salvage_rate),
    oa.predicted_sales(d.predicted_sales),
    oa.avg_buyer_churn(d.avg_buyer_churn),
    oa.avg_purchase_score(d.avg_purchase_score),
)

model.define(OptArticle.adjusted_demand(
    OptArticle.predicted_sales
    * (1 - CHURN_DISCOUNT_WEIGHT * OptArticle.avg_buyer_churn)
    * (1 + PURCHASE_PROPENSITY_WEIGHT * OptArticle.avg_purchase_score)
))

print("\n=== Adjusted Demand per Article (from predictions_sample.csv) ===")
model.select(
    OptArticle.opt_article_id.alias("article_id"),
    OptArticle.name,
    OptArticle.predicted_sales,
    OptArticle.avg_buyer_churn,
    OptArticle.avg_purchase_score,
    OptArticle.adjusted_demand,
).inspect()

# --------------------------------------------------
# Prescriptive A: Markdown Optimization (maximize revenue)
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

# --------------------------------------------------
# Prescriptive B: Demand / Inventory Planning
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
print("Local CSV-only run complete. Full pipeline: retail_planning.py")
print("=" * 60)
