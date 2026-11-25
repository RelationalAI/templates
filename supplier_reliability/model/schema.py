"""Semantic schema for the supplier reliability template: suppliers, products, supply options, and orders."""

from relationalai.semantics import Float, Integer, Model, String

model = Model("supplier_reliability")
Concept, Property = model.Concept, model.Property

# Concept: suppliers with capacity and a reliability score. (reliability is carried as
# data only -- it is NOT priced into the cost objective and does NOT drive the hard-coded
# disruption scenarios in `model/disruption_scenarios.py`; it is here for you to extend, see "Customize".)
Supplier = Concept("Supplier", identify_by={"id": Integer})
Supplier.name = Property(f"{Supplier} has {String:name}")
Supplier.reliability = Property(f"{Supplier} has {Float:reliability}")
Supplier.capacity = Property(f"{Supplier} has {Integer:capacity}")

# Concept: products with demand requirements
Product = Concept("Product", identify_by={"id": Integer})
Product.name = Property(f"{Product} has {String:name}")
Product.demand = Property(f"{Product} has {Integer:demand}")

# Concept: supply options (reified supplier-product links) with a per-unit cost
SupplyOption = Concept("SupplyOption", identify_by={"id": Integer})
SupplyOption.supplier = Property(f"{SupplyOption} from {Supplier}", short_name="supplier")
SupplyOption.product = Property(f"{SupplyOption} for {Product}", short_name="product")
SupplyOption.cost_per_unit = Property(f"{SupplyOption} has {Float:cost_per_unit}")

# Decision concept: orders placed via each supply option
SupplyOrder = Concept("SupplyOrder")
SupplyOrder.option = Property(f"{SupplyOrder} uses {SupplyOption}", short_name="option")

# Derived relationships for direct access (avoids multi-hop traversals); `model/sourcing_plan.py`
# defines them.
SupplyOrder.supplier = Property(f"{SupplyOrder} has {Supplier}", short_name="supplier")
SupplyOrder.product = Property(f"{SupplyOrder} has {Product}", short_name="product")
SupplyOrder.cost_per_unit = Property(f"{SupplyOrder} has {Float:cost_per_unit}")
