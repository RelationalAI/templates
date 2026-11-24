"""Retail planning (predict-then-optimize) template: the model.

Runs the predict-then-optimize pipeline on a small bundled subset of the H&M
dataset (HM_MINI, ~10K customers / 5K articles / 9.6K transactions). Everything
loads from the CSVs in `data/hm_mini/` via `model.data()`; no Snowflake source
tables and no GPU are required.

- Trains a sales-regression GNN (transaction-level price prediction) over the
  Customer-Transaction-Article graph. Churn and purchase GNNs are in the full
  `retail_planning.py`; here the aggregation step uses the sales predictions
  alone and skips the churn-discount and purchase-propensity adjustments.
- Aggregates the predicted per-transaction price to a per-article sum to get
  article-level demand for the optimizers.
- Solves a markdown optimization (MILP) that picks a discount per article and
  week to maximize revenue plus salvage, and a demand/inventory planning (LP)
  that minimizes production, holding, and unmet-demand cost.

`rai models deploy --path model` deploys this package, `python train.py` trains and
registers the GNN, and `python -m queries.retail_report` prints the results of a refresh.
"""

from .reasoning import (
    ArticleDemand,
    DemandPlanCost,
    DemandPlanStatus,
    MarkdownRevenue,
    MarkdownStatus,
    gnn,
)
from .schema import (
    Discount,
    OptArticle,
    ProdCapacity,
    Train,
    Transaction,
    Week,
    model,
)
from .source import DATA_DIR

__all__ = [
    "ArticleDemand",
    "DATA_DIR",
    "DemandPlanCost",
    "DemandPlanStatus",
    "Discount",
    "MarkdownRevenue",
    "MarkdownStatus",
    "OptArticle",
    "ProdCapacity",
    "Train",
    "Transaction",
    "Week",
    "gnn",
    "model",
]
