"""Article demand: each article's demand, summed from the sales GNN's predictions, and the planning
articles that lack it."""

from relationalai.semantics import Float, Integer
from relationalai.semantics.std import aggregates as aggs

# Declares Transaction.predictions, the sales predictions the demand sums.
from . import sales_forecast  # noqa: F401
from .schema import OptArticle, ProdCapacity, Transaction, model

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

# Scale factor applied when aggregating normalized GNN predictions into
# optimizer demand. HM_MINI prices are [0, ~0.6]-normalized; multiplying
# makes per-article demand comparable to the inventory scale.
DEMAND_SCALE = 200.0

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

# Both problems bound an article only where its demand is known: without it the markdown MILP
# drops the article's sales bound and the planning LP its inventory balance, so their plans for
# it mean nothing. Every planning article without predicted demand, and every capacity row
# outside the markdown planning set, is published here for the report to check. The first
# refresh, before `train.py` registers a GNN version, has no demand at all.
PlanningGap = model.Relationship(f"planning article {Integer:article_id} cannot be planned")
known_demand = ArticleDemand.ref()
model.where(
    OptArticle,
    model.not_(known_demand.article_id == OptArticle.opt_article_id, known_demand.adjusted_demand),
).define(PlanningGap(OptArticle.opt_article_id))
planned_article = OptArticle.ref()
model.where(
    ProdCapacity,
    model.not_(
        planned_article.opt_article_id == ProdCapacity.pc_article_id,
        known_demand.article_id == ProdCapacity.pc_article_id,
        known_demand.adjusted_demand,
    ),
).define(PlanningGap(ProdCapacity.pc_article_id))
