"""Dependency rules, the supplier-capability GNN, the rolling-horizon LPs, and the what-ifs."""

import pandas as pd
from relationalai.semantics import Float, Integer, String, count, not_, sum
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.predictive import GNN, PropertyTransformer
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.std import aggregates
from relationalai.semantics.std import math as rmath
from relationalai.semantics.std.path import PathTraversal

from .schema import (
    CapabilityOverride,
    Customer,
    Demand,
    Dependency,
    EffectiveCapacity,
    Input,
    InputMultiplier,
    InputUsage,
    Iteration,
    Product,
    Supplier,
    SupplierCapabilityForecast,
    SupplierObservation,
    SupplierOfflineImpact,
    SupplierProductCapacity,
    Test,
    Train,
    Val,
    model,
)
from .source import DATA_DIR, iter_specs

SOLVE_TIME_LIMIT_SEC = 60

# Stage 2 (Predictive) configuration.
# Default behavior is an actual GNN regression run on Supplier capability;
# set USE_PRECOMPUTED_FORECAST=True to skip training and load the bundled
# forecast CSV directly (useful for fast iteration / offline reproducibility).
USE_PRECOMPUTED_FORECAST = False
GNN_N_EPOCHS = 30
GNN_LR = 0.005
GNN_SEED = 42

# What-if thresholds: a supplier's offline impact counts (product, period)
# cells losing more than 10% of capacity; an input shortage (30% availability)
# counts cells losing more than 5%.
OFFLINE_DROP_THRESHOLD = 0.10
SHORTAGE_AVAILABILITY = 0.30
SHORTAGE_DROP_THRESHOLD = 0.05

# --------------------------------------------------
# Stage 1: Rules -- derive customer yield/floor properties + graph edges
# --------------------------------------------------

Property = model.Property

# Per-customer max declared yield across outgoing dependencies (0.0 if none).
Customer.max_declared_yield_pct = Property(f"{Customer} has {Float:max_declared_yield_pct}")
max_yield_expr = (
    aggregates.max(Dependency.declared_yield_pct)
    .per(Customer)
    .where(Dependency.downstream_id == Customer.id)
    | 0.0
)
model.define(Customer.max_declared_yield_pct(max_yield_expr))

# Per-customer elevated floor across incoming dependencies (0.0 if none).
Customer.elevated_floor_pct = Property(f"{Customer} has {Float:elevated_floor_pct}")
elevated_expr = (
    aggregates.max(Dependency.elevated_floor_pct)
    .per(Customer)
    .where(Dependency.upstream_id == Customer.id)
    | 0.0
)
model.define(Customer.elevated_floor_pct(elevated_expr))

# Customer-to-customer dependency relationship for Stage 4 path traversal.
Customer.depends_on = model.Relationship(f"{Customer:downstream} depends on {Customer:upstream}")
_c_down = Customer.ref("c_down")
_c_up = Customer.ref("c_up")
model.where(
    Dependency.downstream_id == _c_down.id,
    Dependency.upstream_id == _c_up.id,
).define(Customer.depends_on(_c_down, _c_up))

# Count of incoming dependencies (how many downstream signals protect this customer).
Customer.n_incoming_dependencies = Property(f"{Customer} has {Integer:n_incoming_dependencies}")
incoming_count_expr = (
    aggregates.count(Dependency).per(Customer).where(Dependency.upstream_id == Customer.id) | 0
)
model.define(Customer.n_incoming_dependencies(incoming_count_expr))

# Boolean: this customer's effective floor exceeds its base.
Customer.has_elevated_floor = model.Relationship(f"{Customer} has elevated floor")
model.where(
    Customer.elevated_floor_pct > Customer.base_service_floor_pct,
).define(Customer.has_elevated_floor())

# Boolean: single point of failure in the dependency graph (1 protecting edge).
Customer.is_dependency_spof = model.Relationship(
    f"{Customer} is dependency single point of failure"
)
model.where(
    Customer.n_incoming_dependencies == 1,
    Customer.elevated_floor_pct > Customer.base_service_floor_pct,
).define(Customer.is_dependency_spof())

# --------------------------------------------------
# Stage 2: Predictive -- supplier capability forecast
# --------------------------------------------------
#
# Default: a node-regression GNN on Supplier predicts capability_pct per
# (supplier, period) from static features + historical observations; train.py
# trains and registers it, and every refresh predicts with the registered
# version. Either path populates the same SupplierCapabilityForecast concept;
# downstream stages don't care which ran.

if USE_PRECOMPUTED_FORECAST:
    gnn = None
    forecast_df = pd.read_csv(DATA_DIR / "supplier_capability_forecast.csv")
    model.define(SupplierCapabilityForecast.new(model.data(forecast_df).to_schema()))
else:
    # GNN graph: each observation links to its supplier; suppliers in the same
    # region link to each other so feature signal flows between similar fabs.
    gnn_graph = Graph(model, directed=True, weighted=False)
    GEdge = gnn_graph.Edge
    model.define(GEdge.new(src=SupplierObservation, dst=Supplier)).where(
        SupplierObservation.supplier_id == Supplier.id
    )
    SupRef = Supplier.ref()
    model.define(GEdge.new(src=Supplier, dst=SupRef)).where(
        Supplier.region == SupRef.region,
        Supplier.id < SupRef.id,
    )

    pt = PropertyTransformer(
        drop=[
            Supplier.id,
            Supplier.name,
            Supplier.type,
            SupplierObservation.id,
            SupplierObservation.supplier_id,
            SupplierObservation.period_id,
            SupplierObservation.capability_pct,  # target — don't leak
        ],
        category=[Supplier.region],
        continuous=[Supplier.geopolitical_exposure_score],
        integer=[
            Supplier.equipment_age_months,
            Supplier.process_node_nm,
            Supplier.workforce_size_k,
        ],
    )

    # `name` ties this GNN to the registered model and version that
    # `reasoners.predictive.gnns.supplier_capability` names in raiconfig.yaml.
    gnn = GNN(
        name="supplier_capability",
        graph=gnn_graph,
        property_transformer=pt,
        train=Train,
        validation=Val,
        task_type="regression",
        eval_metric="rmse",
        has_time_column=False,
        stream_logs=False,
        seed=GNN_SEED,
        n_epochs=GNN_N_EPOCHS,
        lr=GNN_LR,
    )
    SupplierObservation.predictions = gnn.predictions(domain=Test)

    # Forecast = predicted capability, clipped to [0.85, 1.0].
    predicted = Float.ref()
    model.where(
        SupplierObservation.predictions.predicted_value(predicted),
    ).define(
        SupplierCapabilityForecast.new(
            supplier_id=SupplierObservation.supplier_id,
            period_id=SupplierObservation.period_id,
            capability_pct=rmath.round(rmath.clip(predicted, 0.85, 1.0), 4),
        )
    )

# --------------------------------------------------
# Stage 3: Prescriptive -- monthly rolling-horizon LP
# --------------------------------------------------
#
# Effective capacity per (iteration, product, period) inside the iteration's
# horizon = sum over suppliers of nominal capacity x capability (the forecast,
# or the iteration's revealed override), times the iteration's input multiplier.
# The LP at iteration K references only its own rows.

Capability = model.Relationship(
    f"in {Iteration} supplier {Integer:supplier_id} in period {Integer:period_id} has capability {Float:capability_pct}"
)
model.where(
    Iteration,
    not_(
        CapabilityOverride.iter_id == Iteration.iter_id,
        CapabilityOverride.supplier_id == SupplierCapabilityForecast.supplier_id,
        CapabilityOverride.period_id == SupplierCapabilityForecast.period_id,
    ),
).define(
    Capability(
        Iteration,
        SupplierCapabilityForecast.supplier_id,
        SupplierCapabilityForecast.period_id,
        SupplierCapabilityForecast.capability_pct,
    )
)
model.where(
    CapabilityOverride.iter_id == Iteration.iter_id,
    CapabilityOverride.supplier_id == SupplierCapabilityForecast.supplier_id,
    CapabilityOverride.period_id == SupplierCapabilityForecast.period_id,
).define(
    Capability(
        Iteration,
        CapabilityOverride.supplier_id,
        CapabilityOverride.period_id,
        CapabilityOverride.capability_pct,
    )
)

SPC = SupplierProductCapacity
capability = Float.ref()
model.where(
    SPC.period_id >= Iteration.horizon_start,
    Capability(Iteration, SPC.supplier_id, SPC.period_id, capability),
).define(
    EffectiveCapacity.new(
        iter_id=Iteration.iter_id, product_id=SPC.product_id, period_id=SPC.period_id
    )
)
model.where(
    InputMultiplier.iter_id == EffectiveCapacity.iter_id,
    InputMultiplier.product_id == EffectiveCapacity.product_id,
).define(
    EffectiveCapacity.effective_capacity_usd(
        sum(SPC, SPC.nominal_capacity_usd * capability)
        .per(EffectiveCapacity)
        .where(
            Iteration.iter_id == EffectiveCapacity.iter_id,
            SPC.product_id == EffectiveCapacity.product_id,
            SPC.period_id == EffectiveCapacity.period_id,
            Capability(Iteration, SPC.supplier_id, SPC.period_id, capability),
        )
        * InputMultiplier.mult
    )
)

# One Problem per iteration, each over its own horizon. Each Problem's status,
# total margin, and allocations are published under the Problem's name.
allocations = []
for spec in iter_specs:
    iter_id = spec["iter_id"]
    horizon_start = spec["horizon_start"]
    name = f"memory_supply_allocation_iter_{iter_id}"

    problem = Problem(model, Float, name=name)
    # `populate=False` keeps the three Problems from writing the same
    # `Demand.x_alloc` property; each iteration's values are read through its own
    # `alloc.values(...)`, published below as that iteration's allocations.
    alloc = problem.solve_for(
        Demand.x_alloc,
        type="cont",
        lower=0.0,
        name=["alloc", Demand.customer_id, Demand.product_id, Demand.period_id],
        where=[Demand.period_id >= horizon_start],
        populate=False,
    )

    # Capacity constraint scoped to this iteration's effective-capacity rows.
    problem.satisfy(
        model.where(EffectiveCapacity.iter_id == iter_id).require(
            sum(Demand.x_alloc)
            .per(EffectiveCapacity)
            .where(
                Demand.product_id == EffectiveCapacity.product_id,
                Demand.period_id == EffectiveCapacity.period_id,
            )
            <= EffectiveCapacity.effective_capacity_usd
        ),
        name=[
            "cap",
            EffectiveCapacity.iter_id,
            EffectiveCapacity.product_id,
            EffectiveCapacity.period_id,
        ],
    )

    # Demand cap (yield-aware), base floor, elevated floor -- all scoped to horizon.
    problem.satisfy(
        model.where(
            Demand.customer_id == Customer.id,
            Demand.period_id >= horizon_start,
        ).require(Demand.x_alloc <= (1.0 - Customer.max_declared_yield_pct) * Demand.demand_usd),
        name=["dcap", Demand.customer_id, Demand.product_id, Demand.period_id],
    )
    problem.satisfy(
        model.where(
            Demand.customer_id == Customer.id,
            Demand.period_id >= horizon_start,
        ).require(Demand.x_alloc >= Customer.base_service_floor_pct * Demand.demand_usd),
        name=["bfloor", Demand.customer_id, Demand.product_id, Demand.period_id],
    )
    problem.satisfy(
        model.where(
            Demand.customer_id == Customer.id,
            Demand.period_id >= horizon_start,
        ).require(Demand.x_alloc >= Customer.elevated_floor_pct * Demand.demand_usd),
        name=["efloor", Demand.customer_id, Demand.product_id, Demand.period_id],
    )

    # Objective: margin-weighted allocation over the current horizon.
    problem.maximize(
        sum(Demand.x_alloc * Product.margin_pct).where(
            Demand.product_id == Product.id,
            Demand.period_id >= horizon_start,
        )
    )
    # Each refresh of the deployed model runs this solve.
    problem.configure("highs", time_limit_sec=SOLVE_TIME_LIMIT_SEC)

    # The solve's status and objective, which the deployed model publishes for the queries.
    status = model.Relationship(f"{name} solve status is {String:status}")
    margin = model.Relationship(f"{name} total margin is {Float:margin}")
    model.define(status(problem.termination_status()), margin(problem.objective_value()))

    # The iteration's allocation per demand row (USD), published for the queries.
    allocated = model.Relationship(f"{name} allocates {Float:alloc_usd} to {Demand}")
    alloc_value = Float.ref()
    model.where(alloc.values(0, alloc_value)).define(allocated(alloc_value, alloc.demand))
    allocations.append((spec, status, margin, allocated))

# --------------------------------------------------
# Stage 4: Graph (PATHS) -- dependency chains, then what-if analyses
# --------------------------------------------------
# Every 1-3 hop customer-customer dependency chain. The enumeration is declared
# here, in the model: a deployed model only has the path tables its own rules
# ask for. Each chain's customers are published with their step index.
chain = model.path(Customer.depends_on.repeat(1, 3)).all().paths()
DependencyChainStep = model.Relationship(
    f"{PathTraversal:chain} of {Integer:hops} hops visits {Customer} at step {Integer:step}"
)
model.where(chain).define(
    DependencyChainStep(chain, chain.length, Customer(chain.nodes), chain.nodes["index"])
)

# What-ifs (no re-solve) on the baseline forecast. Baseline capacity per
# (product, period): every supplier at its forecast capability, every input
# fully available.

BaselineCapacity = model.Relationship(
    f"product {Integer:product_id} in period {Integer:period_id} has baseline capacity {Float:usd}"
)
model.where(
    SupplierCapabilityForecast.supplier_id == SPC.supplier_id,
    SupplierCapabilityForecast.period_id == SPC.period_id,
).define(
    BaselineCapacity(
        SPC.product_id,
        SPC.period_id,
        sum(SPC, SPC.nominal_capacity_usd * SupplierCapabilityForecast.capability_pct).per(
            SPC.product_id, SPC.period_id
        ),
    )
)
baseline = Float.ref()

# What-if 1: a supplier going offline removes its share of each cell's capacity.
OfflineDrop = model.Relationship(
    f"{Supplier} offline cuts product {Integer:product_id} in period {Integer:period_id} by {Float:drop_pct}"
)
model.where(
    Supplier.id == SPC.supplier_id,
    SupplierCapabilityForecast.supplier_id == SPC.supplier_id,
    SupplierCapabilityForecast.period_id == SPC.period_id,
    BaselineCapacity(SPC.product_id, SPC.period_id, baseline),
).define(
    OfflineDrop(
        Supplier,
        SPC.product_id,
        SPC.period_id,
        SPC.nominal_capacity_usd * SupplierCapabilityForecast.capability_pct / baseline,
    )
)

# Persist what-if 1 output to the ontology so a downstream analyst can query
# supplier-offline risk.
offline_product, offline_period, offline_drop = Integer.ref(), Integer.ref(), Float.ref()
significant_offline = [
    OfflineDrop(Supplier, offline_product, offline_period, offline_drop),
    offline_drop > OFFLINE_DROP_THRESHOLD,
]
model.define(
    SupplierOfflineImpact.new(
        supplier_id=Supplier.id,
        n_affected_cells=count(offline_product, offline_period)
        .per(Supplier)
        .where(*significant_offline)
        | 0,
        max_cap_drop_pct=aggregates.max(offline_drop).per(Supplier).where(*significant_offline)
        | 0.0,
    )
)

# What-if 2: an input at 30% availability scales each exposed product's
# capacity by 1 - intensity * (1 - availability) in every period.
ShortageDrop = model.Relationship(
    f"{Input} shortage cuts product {Integer:product_id} in period {Integer:period_id} by {Float:drop_pct}"
)
model.where(
    InputUsage.input_id == Input.id,
    BaselineCapacity(InputUsage.product_id, offline_period, baseline),
).define(
    ShortageDrop(
        Input,
        InputUsage.product_id,
        offline_period,
        InputUsage.intensity * (1.0 - SHORTAGE_AVAILABILITY),
    )
)

# Persist what-if 2 output so the input-shortage risk ranking is queryable.
Input.shortage_impact_cells = Property(f"{Input} has {Integer:shortage_impact_cells}")
shortage_product, shortage_period, shortage_drop = Integer.ref(), Integer.ref(), Float.ref()
model.define(
    Input.shortage_impact_cells(
        count(shortage_product, shortage_period)
        .per(Input)
        .where(
            ShortageDrop(Input, shortage_product, shortage_period, shortage_drop),
            shortage_drop > SHORTAGE_DROP_THRESHOLD,
        )
        | 0
    )
)
