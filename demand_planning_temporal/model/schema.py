"""Semantic schema for the demand planning template: sites, SKUs, orders, capacity, and weekly demand."""

from relationalai.semantics import Float, Integer, Model, String

model = Model("demand_planning")
Concept, Property = model.Concept, model.Property

# Concept: warehouse/distribution center sites
Site = Concept("Site", identify_by={"id": Integer})
Site.name = Property(f"{Site} has {String:name}")
Site.site_type = Property(f"{Site} has {String:site_type}")
Site.capacity_per_week = Property(f"{Site} has {Integer:capacity_per_week}")

# Concept: products (SKUs)
SKU = Concept("SKU", identify_by={"id": Integer})
SKU.name = Property(f"{SKU} has {String:name}")
SKU.unit_cost = Property(f"{SKU} has {Float:unit_cost}")
SKU.holding_cost_per_week = Property(f"{SKU} has {Float:holding_cost_per_week}")

# Concept: demand orders (EVENT TABLE - has date column, needs filtering)
# Raw data spans Oct 2025 - Mar 2026. Each planning horizon scopes the orders to its window.
DemandOrder = Concept("DemandOrder", identify_by={"id": Integer})
DemandOrder.quantity = Property(f"{DemandOrder} has {Integer:quantity}")
DemandOrder.due_date = Property(f"{DemandOrder} has {String:due_date}")
DemandOrder.site_id = Property(f"{DemandOrder} ships from site {Integer:site_id}")
DemandOrder.sku_id = Property(f"{DemandOrder} is for SKU {Integer:sku_id}")
DemandOrder.week_num = Property(f"{DemandOrder} falls in week {Integer:week_num}")

# The orders inside each planning horizon, keyed by the horizon's planning_end date.
OrderInPlan = model.Relationship(f"{DemandOrder} is in the plan ending {String:planning_end}")

# Concept: production capacity per site x SKU (REFERENCE TABLE - no filtering needed)
ProdCapacity = Concept(
    "ProdCapacity", identify_by={"site_id": Integer, "sku_id": Integer}
)
ProdCapacity.max_production_per_week = Property(
    f"{ProdCapacity} has {Integer:max_production_per_week}"
)
ProdCapacity.production_cost = Property(f"{ProdCapacity} has {Float:production_cost}")
ProdCapacity.initial_inventory = Property(
    f"{ProdCapacity} has {Float:initial_inventory}"
)
ProdCapacity.holding_cost_per_week = Property(
    f"{ProdCapacity} has {Float:holding_cost_per_week}"
)

# Concept: starting inventory per site x SKU (REFERENCE TABLE - no filtering needed)
InitialInventory = Concept(
    "InitialInventory", identify_by={"site_id": Integer, "sku_id": Integer}
)
InitialInventory.quantity = Property(f"{InitialInventory} has {Integer:quantity}")

# Concept: demand per site x SKU x week in each planning horizon (0 for weeks with no orders)
WeeklyDemand = Concept(
    "WeeklyDemand",
    identify_by={
        "wk_planning_end": String,
        "wk_site_id": Integer,
        "wk_sku_id": Integer,
        "wk_week_num": Integer,
    },
)
WeeklyDemand.wk_quantity = Property(f"{WeeklyDemand} has {Float:wk_quantity}")
