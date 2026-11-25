"""Semantic schema for the supply chain resilience template: sites, businesses, SKUs, operations, demand, shipments, and delay predictions."""

from relationalai.semantics import Float, Integer, Model, String

model = Model("supply_chain_resilience")

# Site concept: factories, distribution centers, offices, stores.
Site = model.Concept("Site", identify_by={"id": String})
Site.name = model.Property(f"{Site} has {String:name}")
Site.site_type = model.Property(f"{Site} has type {String:site_type}")
Site.region = model.Property(f"{Site} in {String:region}")
Site.country = model.Property(f"{Site} in {String:country}")

# Business concept: suppliers, manufacturers, warehouses, buyers.
Business = model.Concept("Business", identify_by={"id": String})
Business.name = model.Property(f"{Business} has {String:name}")
Business.business_type = model.Property(f"{Business} has type {String:business_type}")
Business.reliability_score = model.Property(
    f"{Business} has reliability {Float:reliability_score}"
)
Business.site = model.Relationship(f"{Business} operates at {Site}")

# SKU concept: stock keeping units (raw materials, components, finished goods).
SKU = model.Concept("SKU", identify_by={"id": String})
SKU.name = model.Property(f"{SKU} has {String:name}")
SKU.sku_type = model.Property(f"{SKU} has type {String:sku_type}")

# Operation concept: shipping and transfer routes between sites.
Operation = model.Concept("Operation", identify_by={"id": String})
Operation.op_type = model.Property(f"{Operation} has type {String:op_type}")
Operation.transit_time_days = model.Property(
    f"{Operation} takes {Integer:transit_time_days} days"
)
Operation.cost_per_unit = model.Property(
    f"{Operation} costs {Float:cost_per_unit} per unit"
)
Operation.capacity_per_day = model.Property(
    f"{Operation} has capacity {Integer:capacity_per_day} per day"
)
Operation.source_site = model.Relationship(f"{Operation} from {Site}")
Operation.output_site = model.Relationship(f"{Operation} to {Site}")
Operation.output_sku = model.Relationship(f"{Operation} produces {SKU}")

# Demand concept: customer orders for SKUs.
Demand = model.Concept("Demand", identify_by={"id": String})
Demand.quantity = model.Property(f"{Demand} for {Integer:quantity} units")
Demand.priority = model.Property(f"{Demand} has priority {String:priority}")
Demand.business = model.Relationship(f"{Demand} placed by {Business}")
Demand.sku = model.Relationship(f"{Demand} for {SKU}")

# Shipment concept: supplier-to-customer shipments. They give Stage 0 its directed
# Business graph and give the report its late-shipment statistics.
Shipment = model.Concept("Shipment", identify_by={"id": String})
Shipment.supplier = model.Relationship(f"{Shipment} from {Business}", short_name="supplier")
Shipment.customer = model.Relationship(f"{Shipment} to {Business}", short_name="customer")
Shipment.sku_id = model.Property(f"{Shipment} has sku {String:sku_id}")
Shipment.quantity = model.Property(f"{Shipment} has {Integer:quantity}")
Shipment.delay_days = model.Property(f"{Shipment} is delayed {Float:delay_days} days")

# DelayPrediction concept: ML-predicted delay probabilities per supplier.
DelayPrediction = model.Concept("DelayPrediction", identify_by={"id": String})
DelayPrediction.fiscal_quarter = model.Property(
    f"{DelayPrediction} for {String:fiscal_quarter}"
)
DelayPrediction.predicted_delay_prob = model.Property(
    f"{DelayPrediction} has {Float:predicted_delay_prob}"
)
DelayPrediction.risk_tier = model.Property(
    f"{DelayPrediction} has risk tier {String:risk_tier}"
)
DelayPrediction.supplier_business = model.Relationship(
    f"{DelayPrediction} predicts for {Business}"
)
