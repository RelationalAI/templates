"""Customer dependencies: each customer's yield and floor from the dependency relation, the
customer-to-customer dependency edge, and the single-point-of-failure flag."""

from relationalai.semantics import Float, Integer
from relationalai.semantics.std import aggregates

from .schema import Customer, Dependency, model

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
