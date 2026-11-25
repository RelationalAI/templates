"""Investment frontier: each investment level's portfolio of approved requests and upgrades, the budget
range, the gains from each level to the next, the marginal value per added budget, and the knee point."""

from relationalai.semantics import Float, Integer
from relationalai.semantics.std import aggregates as aggs

# Declare the approval and upgrade variables each portfolio reads.
from . import investment_solve  # noqa: F401
from .schema import (
    DataCenterRequest,
    InvestmentLevel,
    InvestmentPortfolio,
    SubstationUpgrade,
    model,
)

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

AMORTIZATION_YEARS = 20  # upgrade cost spread over 20 years

# --------------------------------------------------
# Portfolio per InvestmentLevel, from the solved values
# --------------------------------------------------
# One InvestmentPortfolio row per scenario: approved requests, their MW and
# revenue, the selected upgrades' cost (in dollars, to match revenue), and the
# net value (revenue less the upgrade cost amortized over AMORTIZATION_YEARS).
x_ap, x_up = Float.ref(), Float.ref()
model.define(
    portfolio := InvestmentPortfolio.new(investment_level_name=InvestmentLevel.name),
    portfolio.investment_level(InvestmentLevel),
)
model.define(
    InvestmentPortfolio.dc_count(
        (
            aggs.count(DataCenterRequest)
            .where(
                InvestmentPortfolio.investment_level(InvestmentLevel),
                DataCenterRequest.x_approve(InvestmentLevel, x_ap),
                x_ap > 0.5,
            )
            .per(InvestmentPortfolio)
        )
        | 0
    )
)
model.define(
    InvestmentPortfolio.total_mw(
        (
            sum(DataCenterRequest, DataCenterRequest.requested_mw)
            .where(
                InvestmentPortfolio.investment_level(InvestmentLevel),
                DataCenterRequest.x_approve(InvestmentLevel, x_ap),
                x_ap > 0.5,
            )
            .per(InvestmentPortfolio)
        )
        | 0.0
    )
)
model.define(
    InvestmentPortfolio.annual_revenue(
        (
            sum(DataCenterRequest, DataCenterRequest.annual_revenue)
            .where(
                InvestmentPortfolio.investment_level(InvestmentLevel),
                DataCenterRequest.x_approve(InvestmentLevel, x_ap),
                x_ap > 0.5,
            )
            .per(InvestmentPortfolio)
        )
        | 0.0
    )
)
model.define(
    InvestmentPortfolio.upgrade_cost(
        (
            sum(SubstationUpgrade, SubstationUpgrade.cost_million * 1e6)
            .where(
                InvestmentPortfolio.investment_level(InvestmentLevel),
                SubstationUpgrade.x_upgrade(InvestmentLevel, x_up),
                x_up > 0.5,
            )
            .per(InvestmentPortfolio)
        )
        | 0.0
    )
)
model.define(
    InvestmentPortfolio.upgrade_count(
        (
            aggs.count(SubstationUpgrade)
            .where(
                InvestmentPortfolio.investment_level(InvestmentLevel),
                SubstationUpgrade.x_upgrade(InvestmentLevel, x_up),
                x_up > 0.5,
            )
            .per(InvestmentPortfolio)
        )
        | 0
    )
)
model.define(
    InvestmentPortfolio.upgrade_mw(
        (
            sum(SubstationUpgrade, SubstationUpgrade.capacity_increase_mw)
            .where(
                InvestmentPortfolio.investment_level(InvestmentLevel),
                SubstationUpgrade.x_upgrade(InvestmentLevel, x_up),
                x_up > 0.5,
            )
            .per(InvestmentPortfolio)
        )
        | 0.0
    )
)
model.define(
    InvestmentPortfolio.net_value(
        InvestmentPortfolio.annual_revenue - InvestmentPortfolio.upgrade_cost / AMORTIZATION_YEARS
    )
)

# The number of investment levels and their smallest and largest budgets.
InvestmentRange = model.Concept("InvestmentRange", identify_by={"id": Integer})
InvestmentRange.n_levels = model.Property(f"{InvestmentRange} has {Integer:n_levels} levels")
InvestmentRange.min_budget = model.Property(f"{InvestmentRange} has smallest budget {Float:min_budget}")
InvestmentRange.max_budget = model.Property(f"{InvestmentRange} has largest budget {Float:max_budget}")
model.define(InvestmentRange.new(id=1))
model.define(
    InvestmentRange.n_levels(aggs.count(InvestmentLevel).per(InvestmentRange)),
    InvestmentRange.min_budget(aggs.min(InvestmentLevel.budget_cap).per(InvestmentRange)),
    InvestmentRange.max_budget(aggs.max(InvestmentLevel.budget_cap).per(InvestmentRange)),
)

# Gains from each level to the next larger budget: net value, budget, megawatts approved, and requests
# approved. The largest level has no next step.
higher, step_from, step_to = InvestmentLevel.ref(), InvestmentLevel.ref(), InvestmentLevel.ref()
model.define(InvestmentLevel.next_level(step_to)).where(
    step_to.budget_cap
    == aggs.min(higher.budget_cap).where(higher.budget_cap > InvestmentLevel.budget_cap).per(InvestmentLevel)
)
InvestmentPortfolio.value_gain = model.Property(f"{InvestmentPortfolio} gains {Float:value_gain} net value")
InvestmentPortfolio.budget_gain = model.Property(f"{InvestmentPortfolio} gains {Float:budget_gain} budget")
InvestmentPortfolio.mw_gain = model.Property(f"{InvestmentPortfolio} gains {Float:mw_gain} approved MW")
InvestmentPortfolio.dc_gain = model.Property(f"{InvestmentPortfolio} gains {Integer:dc_gain} approved requests")
next_portfolio = InvestmentPortfolio.ref()
model.define(
    InvestmentPortfolio.value_gain(next_portfolio.net_value - InvestmentPortfolio.net_value),
    InvestmentPortfolio.budget_gain(step_to.budget_cap - step_from.budget_cap),
    InvestmentPortfolio.mw_gain(next_portfolio.total_mw - InvestmentPortfolio.total_mw),
    InvestmentPortfolio.dc_gain(next_portfolio.dc_count - InvestmentPortfolio.dc_count),
).where(
    InvestmentPortfolio.investment_level(step_from),
    step_from.next_level(step_to),
    next_portfolio.investment_level(step_to),
)

# Marginal value of each budget step: net value gained per added $M from a level
# to the next larger budget.
model.define(
    InvestmentPortfolio.marginal_per_m_to_next_level(InvestmentPortfolio.value_gain / InvestmentPortfolio.budget_gain)
)

# The knee is the level where the marginal value falls the most, from the step
# into it to the step out of it; on a tie, the smaller budget. A frontier whose
# marginal value never falls has no knee. The drop is negated so both rank keys sort ascending, a form
# every backend ranks.
prev_portfolio = InvestmentPortfolio.ref()
model.define(
    InvestmentPortfolio.marginal_drop(
        prev_portfolio.marginal_per_m_to_next_level - InvestmentPortfolio.marginal_per_m_to_next_level
    )
).where(
    prev_portfolio.investment_level(step_from),
    step_from.next_level(step_to),
    InvestmentPortfolio.investment_level(step_to),
)
model.define(InvestmentPortfolio.is_knee_point()).where(
    InvestmentPortfolio.investment_level(step_to),
    InvestmentPortfolio.marginal_drop > 0,
    aggs.rank(-InvestmentPortfolio.marginal_drop, step_to.budget_cap) == 1,
)
