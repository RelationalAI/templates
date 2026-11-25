"""Memory Supply Allocation (predictive + rules + prescriptive + paths) template: the model.

Allocates constrained memory-chip supply across customers in a monthly rolling
horizon when supply is scarce and disruptions surface over time. Four reasoners
chained on one ontology:

- Stage 1 (Rules): derive `Customer.max_declared_yield_pct`,
  `Customer.elevated_floor_pct`, `Customer.depends_on` (graph edge), plus
  `Customer.is_dependency_spof`, from the dependency relation.
- Stage 2 (Predictive): a node-regression GNN predicts `capability_pct` per
  (supplier, month); the clipped prediction is `SupplierCapabilityForecast`.
  Set `USE_PRECOMPUTED_FORECAST = True` in `model/capability_forecast.py` to load the
  bundled forecast CSV instead.
- Stage 3 (Prescriptive): monthly margin-max LP over a 36-month horizon, run
  as a 3-step rolling horizon. A baseline solve at month 1, then disruption
  reveals at months 5 and 13 re-solve the remaining horizon. Effective capacity
  per (product, period) = sum over suppliers of nominal x predicted capability,
  scaled by input availability.
- Stage 4 (Graph / PATHS): enumerate variable-length dependency chains via
  `model.path(Customer.depends_on.repeat(1, 3)).all().paths()` for root cause
  on the customer-customer graph. Two what-if branches: (1) supplier goes
  offline, (2) raw-material input shortage. Each surfaces affected (product,
  period) cells without re-solving the LP.

Each stage lives in its own module, and each module imports the modules whose
declarations it reads: `customer_dependencies.py` (Stage 1), `capability_forecast.py`
(Stage 2), `rolling_horizon.py` (Stage 3), `dependency_chains.py` and
`disruption_what_ifs.py` (Stage 4).

`rai models deploy --path model` deploys this package to the schemas in
raiconfig.yaml, `python train.py` trains and registers the GNN, and
`python -m queries.allocation_report` prints the results of a refresh.
"""

from .capability_forecast import NumForecastRows, gnn
from .dependency_chains import (
    DependencyChain,
    DependencyChainStep,
    NumDependencyChains,
)
from .disruption_what_ifs import (
    OFFLINE_DROP_THRESHOLD,
    SHORTAGE_DROP_THRESHOLD,
    OfflineDrop,
    ShortageAverageDrop,
    ShortageDrop,
)
from .rolling_horizon import (
    CustomerService,
    EffectiveCapacityCells,
    PlanDiff,
    allocations,
)
from .schema import (
    Customer,
    Demand,
    EffectiveCapacity,
    Input,
    Product,
    Supplier,
    SupplierCapabilityForecast,
    SupplierOfflineImpact,
    model,
)
from .source import HORIZON_END_PERIOD

__all__ = [
    "HORIZON_END_PERIOD",
    "OFFLINE_DROP_THRESHOLD",
    "SHORTAGE_DROP_THRESHOLD",
    "Customer",
    "CustomerService",
    "Demand",
    "DependencyChain",
    "DependencyChainStep",
    "EffectiveCapacity",
    "EffectiveCapacityCells",
    "Input",
    "NumDependencyChains",
    "NumForecastRows",
    "OfflineDrop",
    "PlanDiff",
    "Product",
    "ShortageAverageDrop",
    "ShortageDrop",
    "Supplier",
    "SupplierCapabilityForecast",
    "SupplierOfflineImpact",
    "allocations",
    "gnn",
    "model",
]
