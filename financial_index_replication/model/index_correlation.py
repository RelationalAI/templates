"""Index correlation: each stock's correlation with the index's returns and its rank by that
correlation, which picks the stocks of the equal-weight baseline."""

from relationalai.semantics import Float, Integer
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std import math

from .schema import ReturnMonth, Stock, model

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

# The baseline holds this many of the stocks most correlated with the index.
BASELINE_NAMES = 20

# --------------------------------------------------
# Correlation with the index
# --------------------------------------------------

# The absolute Pearson correlation of a stock's monthly returns with the index's,
# over the months in which the stock has a return: the covariance less the
# product of the means, over the square root of the product of the variances.
Stock.abs_index_correlation = model.Property(
    f"{Stock} has absolute index correlation {Float:abs_index_correlation}"
)
_return = Float.ref()
_priced = Stock.monthly_return(ReturnMonth, _return)
_mean_return = aggs.avg(ReturnMonth, _return).per(Stock).where(_priced)
_mean_index = aggs.avg(ReturnMonth, ReturnMonth.index_return).per(Stock).where(_priced)
_mean_product = aggs.avg(ReturnMonth, _return * ReturnMonth.index_return).per(Stock).where(_priced)
_var_return = aggs.variance(ReturnMonth, _return).per(Stock).where(_priced)
_var_index = aggs.variance(ReturnMonth, ReturnMonth.index_return).per(Stock).where(_priced)
model.define(
    Stock.abs_index_correlation(
        math.abs((_mean_product - _mean_return * _mean_index) / math.sqrt(_var_return * _var_index))
    )
)

# The stocks ranked from the most to the least correlated, ties broken by ticker.
# The correlation is negated so both keys sort ascending: rank sorts all its keys in one direction.
Stock.correlation_rank = model.Property(f"{Stock} has correlation rank {Integer:correlation_rank}")
model.define(Stock.correlation_rank(aggs.rank(-Stock.abs_index_correlation, Stock.ticker)))
