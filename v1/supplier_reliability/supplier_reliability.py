# supplier reliability problem:
# select suppliers to meet demand balancing cost and reliability

from pathlib import Path

from pandas import read_csv

from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("supplier_reliability")
Concept, Property = model.Concept, model.Property

# --------------------------------------------------
# Define ontology & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Concept: suppliers with reliability scores and capacity
Supplier = Concept("Supplier", identify_by={"id": Integer})
Supplier.name = Property(f"{Supplier} has {String:name}")
Supplier.reliability = Property(f"{Supplier} has {Float:reliability}")
Supplier.capacity = Property(f"{Supplier} has {Integer:capacity}")
supplier_csv = read_csv(data_dir / "suppliers.csv")
model.define(Supplier.new(model.data(supplier_csv).to_schema()))

# Concept: products with demand requirements
Product = Concept("Product", identify_by={"id": Integer})
Product.name = Property(f"{Product} has {String:name}")
Product.demand = Property(f"{Product} has {Integer:demand}")
product_csv = read_csv(data_dir / "products.csv")
model.define(Product.new(model.data(product_csv).to_schema()))

# Relationship: supply options linking suppliers to products
SupplyOption = Concept("SupplyOption", identify_by={"id": Integer})
SupplyOption.supplier = Property(f"{SupplyOption} from {Supplier}", short_name="supplier")
SupplyOption.product = Property(f"{SupplyOption} for {Product}", short_name="product")
SupplyOption.cost_per_unit = Property(f"{SupplyOption} has {Float:cost_per_unit}")

options_csv = read_csv(data_dir / "supply_options.csv")
options_data = model.data(options_csv)
model.define(
    so := SupplyOption.new(id=options_data.id, supplier=Supplier, product=Product,
                           cost_per_unit=options_data.cost_per_unit)
).where(Supplier.id == options_data.supplier_id, Product.id == options_data.product_id)

# --------------------------------------------------
# Model the problem
# --------------------------------------------------

# Decision concept: orders placed via each supply option
SupplyOrder = Concept("SupplyOrder")
SupplyOrder.option = Property(f"{SupplyOrder} uses {SupplyOption}", short_name="option")
SupplyOrder.x_quantity = Property(f"{SupplyOrder} has {Float:quantity}")
model.define(SupplyOrder.new(option=SupplyOption))

# Derived relationships for direct access (avoids multi-hop traversals)
SupplyOrder.supplier = Property(f"{SupplyOrder} has {Supplier}", short_name="supplier")
model.define(SupplyOrder.supplier(Supplier)).where(SupplyOrder.option(SupplyOption), SupplyOption.supplier(Supplier))

SupplyOrder.product = Property(f"{SupplyOrder} has {Product}", short_name="product")
model.define(SupplyOrder.product(Product)).where(SupplyOrder.option(SupplyOption), SupplyOption.product(Product))

SupplyOrder.cost_per_unit = Property(f"{SupplyOrder} has {Float:cost_per_unit}")
model.define(SupplyOrder.cost_per_unit(SupplyOption.cost_per_unit)).where(SupplyOrder.option(SupplyOption))

# Scenarios (what-if analysis)
SCENARIO_PARAM = "excluded_supplier"
SCENARIO_VALUES = [None, "SupplierC", "SupplierB"]
SCENARIO_CONCEPT = "Supplier"  # Entity type for exclusion scenarios

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

scenario_results = []

for excluded_supplier in SCENARIO_VALUES:
    print(f"\nRunning scenario: {SCENARIO_PARAM} = {excluded_supplier}")

    # Create fresh Problem for each scenario
    s = Problem(model, Float)

    # Variable: order quantity
    s.solve_for(SupplyOrder.x_quantity, name=["qty", SupplyOrder.supplier.name, SupplyOrder.product.name], lower=0, populate=False)

    # Constraint: total orders from supplier cannot exceed supplier capacity
    capacity_limit = model.require(sum(SupplyOrder.x_quantity).where(SupplyOrder.supplier == Supplier).per(Supplier) <= Supplier.capacity)
    s.satisfy(capacity_limit)

    # Constraint: demand satisfaction for each product
    meet_demand = model.require(sum(SupplyOrder.x_quantity).where(SupplyOrder.product == Product).per(Product) >= Product.demand)
    s.satisfy(meet_demand)

    # Constraint: exclude supplier if specified
    if excluded_supplier is not None:
        exclude = model.require(SupplyOrder.x_quantity == 0).where(SupplyOrder.supplier.name == excluded_supplier)
        s.satisfy(exclude)

    # Objective: minimize cost (no reliability penalty for simplicity)
    direct_cost = sum(SupplyOrder.x_quantity * SupplyOrder.cost_per_unit)
    s.minimize(direct_cost)

    s.display()
    s.solve("highs", time_limit_sec=60, _server_side_import=False)
    s.display_solve_info()

    scenario_results.append({
        "scenario": excluded_supplier,
        "status": str(s.termination_status),
        "objective": s.objective_value,
    })
    print(f"  Status: {s.termination_status}, Objective: {s.objective_value}")

    # Print order plan from solver results
    var_df = s.variable_values().to_df()
    qty_df = var_df[var_df["name"].str.startswith("qty") & (var_df["value"] > 0.001)]
    print(f"\n  Orders:")
    print(qty_df.to_string(index=False))

# Summary
print("\n" + "=" * 50)
print("Scenario Analysis Summary")
print("=" * 50)
for result in scenario_results:
    print(f"  {result['scenario']}: {result['status']}, obj={result['objective']}")
