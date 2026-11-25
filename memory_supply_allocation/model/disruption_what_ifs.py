"""Disruption what-ifs: baseline capacity per product and month, the capacity a supplier going offline or an
input shortage removes, each supplier's and input's affected cells, and the widest impact of each."""

from relationalai.semantics import Float, Integer, String, count, sum
from relationalai.semantics.std import aggregates

# Declares SupplierCapabilityForecast's rows, the forecast the baseline capacity reads.
from . import capability_forecast  # noqa: F401
from .schema import (
    Input,
    InputUsage,
    Product,
    Supplier,
    SupplierCapabilityForecast,
    SupplierOfflineImpact,
    SupplierProductCapacity,
    model,
)

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

# What-if thresholds: a supplier's offline impact counts (product, period)
# cells losing more than 10% of capacity; an input shortage (30% availability)
# counts cells losing more than 5%.
OFFLINE_DROP_THRESHOLD = 0.10
SHORTAGE_AVAILABILITY = 0.30
SHORTAGE_DROP_THRESHOLD = 0.05

Property = model.Property
SPC = SupplierProductCapacity

# --------------------------------------------------
# Stage 4: what-if analyses
# --------------------------------------------------

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

# Both what-ifs measure drops relative to baseline capacity, so they skip cells
# with zero baseline capacity, where the relative drop is undefined.

# What-if 1: a supplier going offline removes its share of each cell's capacity.
OfflineDrop = model.Relationship(
    f"{Supplier} offline cuts product {Integer:product_id} in period {Integer:period_id} by {Float:drop_pct}"
)
model.where(
    Supplier.id == SPC.supplier_id,
    SupplierCapabilityForecast.supplier_id == SPC.supplier_id,
    SupplierCapabilityForecast.period_id == SPC.period_id,
    BaselineCapacity(SPC.product_id, SPC.period_id, baseline),
    baseline > 0,
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

# The products behind those cells, by product id, comma-separated; empty when the supplier loses
# no cell above the threshold.
SupplierOfflineImpact.affected_products = Property(
    f"{SupplierOfflineImpact} has affected products {String:affected_products}"
)
model.define(
    SupplierOfflineImpact.affected_products(
        aggregates.string_join(Product.name, sep=", ", index=Product.id)
        .per(SupplierOfflineImpact)
        .where(
            Supplier.id == SupplierOfflineImpact.supplier_id,
            *significant_offline,
            Product.id == offline_product,
        )
        | ""
    )
)

# The supplier whose offline impact reaches the most cells, the lowest id among ties; none when no
# supplier loses a cell above the threshold.
SupplierOfflineImpact.has_widest_impact = model.Relationship(
    f"{SupplierOfflineImpact} has the widest offline impact"
)
model.where(
    SupplierOfflineImpact.n_affected_cells > 0,
    aggregates.rank(
        -SupplierOfflineImpact.n_affected_cells, SupplierOfflineImpact.supplier_id
    )
    == 1,
).define(SupplierOfflineImpact.has_widest_impact())

# What-if 2: an input at 30% availability scales each exposed product's
# capacity by 1 - intensity * (1 - availability) in every period.
ShortageDrop = model.Relationship(
    f"{Input} shortage cuts product {Integer:product_id} in period {Integer:period_id} by {Float:drop_pct}"
)
model.where(
    InputUsage.input_id == Input.id,
    BaselineCapacity(InputUsage.product_id, offline_period, baseline),
    baseline > 0,
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

# The mean drop over the cells above the threshold, per input and exposed product.
ShortageAverageDrop = model.Relationship(
    f"{Input} shortage cuts product {Integer:product_id} by {Float:avg_drop_pct} on average"
)
_cut_period, _cut_drop = Integer.ref(), Float.ref()
model.where(
    ShortageDrop(Input, shortage_product, shortage_period, shortage_drop),
    shortage_drop > SHORTAGE_DROP_THRESHOLD,
).define(
    ShortageAverageDrop(
        Input,
        shortage_product,
        aggregates.avg(_cut_period, _cut_drop)
        .per(Input, shortage_product)
        .where(
            ShortageDrop(Input, shortage_product, _cut_period, _cut_drop),
            _cut_drop > SHORTAGE_DROP_THRESHOLD,
        ),
    )
)

# The input whose shortage reaches the most cells, the lowest id among ties; none when no input
# loses a cell above the threshold.
Input.has_widest_shortage_impact = model.Relationship(
    f"{Input} has the widest shortage impact"
)
model.where(
    Input.shortage_impact_cells > 0,
    aggregates.rank(-Input.shortage_impact_cells, Input.id) == 1,
).define(Input.has_widest_shortage_impact())
