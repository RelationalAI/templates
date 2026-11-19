"""Memory-supply model: concepts for supply, demand, dependencies and the forecast."""

from relationalai.semantics import Float, Integer, Model, String

model = Model("memory_supply_allocation")
Concept, Property = model.Concept, model.Property

# Customer concept: chip buyers (hyperscalers, OEMs, equipment makers).
Customer = Concept("Customer", identify_by={"id": Integer})
Customer.name = Property(f"{Customer} has {String:name}")
Customer.industry = Property(f"{Customer} has {String:industry}")
Customer.base_service_floor_pct = Property(f"{Customer} has {Float:base_service_floor_pct}")

# Product concept: memory SKUs.
Product = Concept("Product", identify_by={"id": Integer})
Product.name = Property(f"{Product} has {String:name}")
Product.family = Property(f"{Product} has {String:family}")
Product.unit_price_usd_per_gb = Property(f"{Product} has {Float:unit_price_usd_per_gb}")
Product.margin_pct = Property(f"{Product} has {Float:margin_pct}")

# Period concept: monthly buckets across the 36-month horizon.
Period = Concept("Period", identify_by={"id": Integer})
Period.month_num = Property(f"{Period} has {Integer:month_num}")
Period.label = Property(f"{Period} has {String:label}")

# Demand junction concept: one row per (customer, product, period).
Demand = Concept(
    "Demand",
    identify_by={
        "customer_id": Integer,
        "product_id": Integer,
        "period_id": Integer,
    },
)
Demand.demand_usd = Property(f"{Demand} has {Float:demand_usd}")

# Supplier concept: foundries / fabs producing memory SKUs, with the static
# features the GNN reads.
Supplier = Concept("Supplier", identify_by={"id": Integer})
Supplier.name = Property(f"{Supplier} has {String:name}")
Supplier.type = Property(f"{Supplier} has {String:type}")
Supplier.equipment_age_months = Property(f"{Supplier} has {Integer:equipment_age_months}")
Supplier.geopolitical_exposure_score = Property(
    f"{Supplier} has {Float:geopolitical_exposure_score}"
)
Supplier.region = Property(f"{Supplier} has {String:region}")
Supplier.process_node_nm = Property(f"{Supplier} has {Integer:process_node_nm}")
Supplier.workforce_size_k = Property(f"{Supplier} has {Integer:workforce_size_k}")

# SupplierProductCapacity: nominal monthly USD capacity per (supplier, product, period).
SupplierProductCapacity = Concept(
    "SupplierProductCapacity",
    identify_by={
        "supplier_id": Integer,
        "product_id": Integer,
        "period_id": Integer,
    },
)
SupplierProductCapacity.nominal_capacity_usd = Property(
    f"{SupplierProductCapacity} has {Float:nominal_capacity_usd}"
)

# Input concept: raw materials / consumables (helium, neon, palladium).
Input = Concept("Input", identify_by={"id": Integer})
Input.name = Property(f"{Input} has {String:name}")
Input.description = Property(f"{Input} has {String:description}")

# InputUsage: per (product, input) intensity (0 = no exposure, 1 = full exposure).
InputUsage = Concept("InputUsage", identify_by={"product_id": Integer, "input_id": Integer})
InputUsage.intensity = Property(f"{InputUsage} has {Float:intensity}")

# Dependency: downstream customer signals willingness to yield to upstream.
Dependency = Concept(
    "Dependency",
    identify_by={"downstream_id": Integer, "upstream_id": Integer},
)
Dependency.declared_yield_pct = Property(f"{Dependency} has {Float:declared_yield_pct}")
Dependency.elevated_floor_pct = Property(f"{Dependency} has {Float:elevated_floor_pct}")

# SupplierObservation: GNN source concept. One row per (supplier, period).
# Historical rows (-23..0) carry capability_pct as the regression label;
# future rows (1..36) are the prediction targets (no label). Each observation
# has its own id: a deployed GNN reads node concepts identified by one field.
SupplierObservation = Concept("SupplierObservation", identify_by={"id": Integer})
SupplierObservation.supplier_id = Property(f"{SupplierObservation} has {Integer:supplier_id}")
SupplierObservation.period_id = Property(f"{SupplierObservation} has {Integer:period_id}")
SupplierObservation.capability_pct = Property(f"{SupplierObservation} has {Float:capability_pct}")

# Task tables and the regression task relationships.
TrainTable = Concept("TrainTable")
ValTable = Concept("ValTable")
TestTable = Concept("TestTable")
Train = model.Relationship(f"{SupplierObservation} has {Float:value}")
Val = model.Relationship(f"{SupplierObservation} has {Float:value}")
Test = model.Relationship(f"{SupplierObservation}")

# Forecast capability per (supplier, month), from the GNN or the bundled CSV.
SupplierCapabilityForecast = Concept(
    "SupplierCapabilityForecast",
    identify_by={"supplier_id": Integer, "period_id": Integer},
)
SupplierCapabilityForecast.capability_pct = Property(
    f"{SupplierCapabilityForecast} has {Float:capability_pct}"
)

# Rolling-horizon iteration: one re-plan, with the disruptions revealed by its start.
Iteration = Concept("Iteration", identify_by={"iter_id": Integer})
Iteration.horizon_start = Property(f"{Iteration} has {Integer:horizon_start}")
Iteration.label = Property(f"{Iteration} has {String:label}")

# Capability per (iteration, supplier, month) after that iteration's revealed
# supplier disruptions, and the input-availability multiplier per (iteration, product).
CapabilityOverride = Concept(
    "CapabilityOverride",
    identify_by={"iter_id": Integer, "supplier_id": Integer, "period_id": Integer},
)
CapabilityOverride.capability_pct = Property(f"{CapabilityOverride} has {Float:capability_pct}")
InputMultiplier = Concept(
    "InputMultiplier", identify_by={"iter_id": Integer, "product_id": Integer}
)
InputMultiplier.mult = Property(f"{InputMultiplier} has {Float:mult}")

# Effective capacity per (iteration, product, period) inside that iteration's horizon.
EffectiveCapacity = Concept(
    "EffectiveCapacity",
    identify_by={
        "iter_id": Integer,
        "product_id": Integer,
        "period_id": Integer,
    },
)
EffectiveCapacity.effective_capacity_usd = Property(
    f"{EffectiveCapacity} has {Float:effective_capacity_usd}"
)

# Supplier-offline what-if per supplier: (product, period) cells losing more than
# the threshold share of capacity, and the largest such drop. Kept off Supplier:
# the GNN reads Supplier, and these figures derive from the GNN's forecast.
SupplierOfflineImpact = Concept("SupplierOfflineImpact", identify_by={"supplier_id": Integer})
SupplierOfflineImpact.n_affected_cells = Property(
    f"{SupplierOfflineImpact} has {Integer:n_affected_cells}"
)
SupplierOfflineImpact.max_cap_drop_pct = Property(
    f"{SupplierOfflineImpact} has {Float:max_cap_drop_pct}"
)

# Decision variable property.
Demand.x_alloc = Property(f"{Demand} has {Float:x_alloc}")
