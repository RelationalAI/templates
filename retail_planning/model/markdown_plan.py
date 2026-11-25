"""Markdown plan: the markdown MILP that picks a discount for each article and week to maximize
revenue plus salvage, its solve status and revenue, and the selected discounts."""

from relationalai.semantics import Float, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

from .article_demand import ArticleDemand
from .planning_horizon import num_weeks
from .schema import Discount, OptArticle, Week, model

# --------------------------------------------------
# Phase 4: Markdown optimization (MILP, maximize revenue)
# --------------------------------------------------

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
