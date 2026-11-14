"""Sparse index replication: decision problem and solver settings.

Declares, at module level, everything the deployment needs beyond the source
facts in `model/source.py`:

- Choose exactly 20 names and their portfolio weights.
- Minimize full-history tracking residuals versus the benchmark.
- Enforce long-only weights, max position size, sector neutrality, and
  per-name ADV participation limits.

The optimization is a mixed-integer linear problem that minimizes absolute
tracking residuals. Each refresh of the deployed model runs the solve.
`queries/replication_report.py` prints the report from the deployed model.
"""

from relationalai.semantics import Float, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

from .schema import ReturnMonth, Sector, Stock, model
from .source import stocks_csv

# --------------------------------------------------
# Configure replication policy
# --------------------------------------------------

N_REPLICATION_NAMES = 20
MAX_WEIGHT = 0.10
SECTOR_ACTIVE_BAND = 0.04
PORTFOLIO_VALUE = 10_000_000
MAX_ADV_PARTICIPATION = 0.05
MONTHS_PER_YEAR = 12

# Basic feasibility checks before building and solving the optimization model.
eligible_stock_count = stocks_csv["ticker"].nunique()
if eligible_stock_count < N_REPLICATION_NAMES:
    raise ValueError(
        f"N_REPLICATION_NAMES={N_REPLICATION_NAMES} requires at least that many "
        f"eligible stocks, but only {eligible_stock_count} are available."
    )
if N_REPLICATION_NAMES * MAX_WEIGHT < 1.0:
    raise ValueError(
        f"N_REPLICATION_NAMES * MAX_WEIGHT must be at least 1.0 for full "
        f"investment, got {N_REPLICATION_NAMES * MAX_WEIGHT:.2f}."
    )

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

Stock.x_selected = model.Property(f"{Stock} selected if {Float:selected}")
Stock.x_weight = model.Property(f"{Stock} has replication weight {Float:weight}")
ReturnMonth.x_pos_error = model.Property(
    f"{ReturnMonth} has positive tracking residual {Float:pos_error}"
)
ReturnMonth.x_neg_error = model.Property(
    f"{ReturnMonth} has negative tracking residual {Float:neg_error}"
)

selected = Float.ref("selected")
weight = Float.ref("weight")
pos_error = Float.ref("pos_error")
neg_error = Float.ref("neg_error")
index_return = Float.ref("index_return")
stock_return = Float.ref("stock_return")

problem = Problem(model, Float)

problem.solve_for(
    Stock.x_selected(selected),
    type="bin",
    name=["selected", Stock.ticker],
)
problem.solve_for(
    Stock.x_weight(weight),
    type="cont",
    lower=0,
    upper=MAX_WEIGHT,
    name=["weight", Stock.ticker],
)
problem.solve_for(
    ReturnMonth.x_pos_error(pos_error),
    type="cont",
    lower=0,
    name=["pos_error", ReturnMonth.date],
)
problem.solve_for(
    ReturnMonth.x_neg_error(neg_error),
    type="cont",
    lower=0,
    name=["neg_error", ReturnMonth.date],
)

# Select exactly N names and invest all capital.
problem.satisfy(
    model.where(Stock.x_selected(selected)).require(
        sum(Stock, selected) == N_REPLICATION_NAMES
    )
)
# Full-investment constraint: portfolio weights must sum to 100%.
problem.satisfy(model.where(Stock.x_weight(weight)).require(sum(Stock, weight) == 1.0))

# A stock can carry weight only when selected.
problem.satisfy(
    model.where(
        Stock.x_weight(weight),
        Stock.x_selected(selected),
    ).require(weight <= MAX_WEIGHT * selected)
)

# Keep sector exposures close to benchmark sector weights.
problem.satisfy(
    model.where(
        Stock.x_weight(weight),
        Stock.sector_ref(Sector),
    ).require(
        sum(Stock, weight).per(Sector) <= Sector.benchmark_weight + SECTOR_ACTIVE_BAND
    )
)
problem.satisfy(
    model.where(
        Stock.x_weight(weight),
        Stock.sector_ref(Sector),
    ).require(
        sum(Stock, weight).per(Sector) >= Sector.benchmark_weight - SECTOR_ACTIVE_BAND
    )
)

# Limit per-name buy and sell dollars as a fraction of average dollar volume.
problem.satisfy(
    model.where(
        Stock.x_weight(weight),
    ).require(
        PORTFOLIO_VALUE * (weight - Stock.previous_weight)
        <= MAX_ADV_PARTICIPATION * Stock.avg_dollar_volume
    )
)
problem.satisfy(
    model.where(
        Stock.x_weight(weight),
    ).require(
        PORTFOLIO_VALUE * (Stock.previous_weight - weight)
        <= MAX_ADV_PARTICIPATION * Stock.avg_dollar_volume
    )
)

# Monthly benchmark residual:
# index_return[t] - sum_i weight[i] * stock_return[i,t] = pos_error[t] - neg_error[t]
problem.satisfy(
    model.where(
        ReturnMonth.index_return(index_return),
        ReturnMonth.x_pos_error(pos_error),
        ReturnMonth.x_neg_error(neg_error),
        Stock.x_weight(weight),
        Stock.monthly_return(ReturnMonth, stock_return),
    ).require(
        index_return - sum(Stock, stock_return * weight).per(ReturnMonth)
        == pos_error - neg_error
    )
)

# Minimize total absolute tracking residual.
problem.minimize(
    sum(ReturnMonth, pos_error + neg_error).where(
        ReturnMonth.x_pos_error(pos_error),
        ReturnMonth.x_neg_error(neg_error),
    )
)

# --------------------------------------------------
# Solve
# --------------------------------------------------

# Each refresh of the deployed model runs this solve.
problem.configure("highs", time_limit_sec=240)

# The solve's status and objective, published through the model's own relationships.
SolveStatus = model.Relationship(f"financial index replication solve status is {String:status}")
TotalResidual = model.Relationship(
    f"financial index replication total absolute residual is {Float:residual}"
)
model.define(SolveStatus(problem.termination_status()), TotalResidual(problem.objective_value()))
