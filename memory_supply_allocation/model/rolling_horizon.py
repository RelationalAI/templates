"""Rolling-horizon allocation: the capability each iteration sees, its effective capacity per product
and month, one margin-maximising LP per iteration, and each plan's diff and per-customer allocation and demand."""

from relationalai.semantics import Float, Integer, String, not_, sum
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.std import aggregates

# Declare the forecast rows the effective capacity reads (capability_forecast) and the customer
# yield caps and floors the LPs read (customer_dependencies).
from . import (
    capability_forecast,  # noqa: F401
    customer_dependencies,  # noqa: F401
)
from .schema import (
    CapabilityOverride,
    Customer,
    Demand,
    EffectiveCapacity,
    InputMultiplier,
    Iteration,
    Product,
    SupplierCapabilityForecast,
    SupplierProductCapacity,
    model,
)
from .source import iter_specs

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

SOLVE_TIME_LIMIT_SEC = 60

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
# Every demanded cell in the horizon also gets a row, at zero capacity when no
# capability covers it (before the GNN is trained, or a gap in the forecast), so
# the capacity constraint below never leaves a demanded cell unbounded.
model.where(Demand.period_id >= Iteration.horizon_start).define(
    EffectiveCapacity.new(
        iter_id=Iteration.iter_id, product_id=Demand.product_id, period_id=Demand.period_id
    )
)
model.where(
    InputMultiplier.iter_id == EffectiveCapacity.iter_id,
    InputMultiplier.product_id == EffectiveCapacity.product_id,
).define(
    EffectiveCapacity.effective_capacity_usd(
        (
            sum(SPC, SPC.nominal_capacity_usd * capability)
            .per(EffectiveCapacity)
            .where(
                Iteration.iter_id == EffectiveCapacity.iter_id,
                SPC.product_id == EffectiveCapacity.product_id,
                SPC.period_id == EffectiveCapacity.period_id,
                Capability(Iteration, SPC.supplier_id, SPC.period_id, capability),
            )
            | 0.0
        )
        * InputMultiplier.mult
    )
)

# The number of effective-capacity cells each iteration loads.
EffectiveCapacityCells = model.Relationship(
    f"in iteration {Integer:iter_id} there are {Integer:n_cells} effective-capacity cells"
)
model.define(
    EffectiveCapacityCells(
        Iteration.iter_id,
        aggregates.count(EffectiveCapacity)
        .per(Iteration)
        .where(EffectiveCapacity.iter_id == Iteration.iter_id)
        | 0,
    )
)

# One Problem per iteration, each over its own horizon. Each Problem's status,
# total margin, and allocations are published under the Problem's name; the plan
# diff against the prior iteration and each customer's allocated and demanded
# totals are also published per iteration number.
allocations = []
PlanDiff = model.Relationship(
    f"in iteration {Integer:iter_id} {Customer} shifts {Float:delta_usd} against the prior plan"
)
CustomerService = model.Relationship(
    f"in iteration {Integer:iter_id} {Customer} is allocated {Float:alloc_usd} of {Float:demand_usd} demand"
)
_alloc_usd, _prior_usd, _demand_alloc_usd = Float.ref(), Float.ref(), Float.ref()
_cell, _demand_cell = Demand.ref(), Demand.ref()

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

    # The plan diff against the prior iteration's plan: the change in each customer's allocation
    # over the cells both plans cover, once the prior solve is OPTIMAL.
    if allocations:
        _, prior_status, _, prior_allocated = allocations[-1]
        model.where(
            Customer,
            prior_status("OPTIMAL"),
            delta_usd := sum(_cell, _alloc_usd - _prior_usd)
            .per(Customer)
            .where(
                allocated(_alloc_usd, _cell),
                prior_allocated(_prior_usd, _cell),
                _cell.customer_id == Customer.id,
            ),
        ).define(PlanDiff(iter_id, Customer, delta_usd))

    # Each customer's allocation and demand over the cells this iteration allocates; the report
    # divides them for the service level.
    model.where(
        Customer,
        alloc_usd := sum(_cell, _alloc_usd)
        .per(Customer)
        .where(allocated(_alloc_usd, _cell), _cell.customer_id == Customer.id),
        demand_usd := sum(_demand_cell, _demand_cell.demand_usd)
        .per(Customer)
        .where(allocated(_demand_alloc_usd, _demand_cell), _demand_cell.customer_id == Customer.id),
    ).define(CustomerService(iter_id, Customer, alloc_usd, demand_usd))

    allocations.append((spec, status, margin, allocated))
