"""Supplier Reliability (prescriptive optimization) template.

This script demonstrates a sourcing optimization model in RelationalAI that
balances cost and supplier reliability:

- Load sample CSVs describing suppliers, products, and supplier-product supply options.
- Model those entities as *concepts* with typed properties.
- Choose non-negative order quantities for each supply option.
- Enforce supplier capacity limits and product demand satisfaction.
- Minimize total cost, with disruption scenario analysis that optionally excludes
  a supplier using the loop + where= filter pattern.

Modeling approach:
- Each disruption scenario (baseline, exclude SupplierC, exclude SupplierB) is solved
  as a separate Problem instance with a where= filter on solve_for.
- Entity exclusion is handled cleanly via where= filter — no constraint injection needed.
- Results collected per iteration and compared post-loop.

Run:
    `python supplier_reliability.py`

Output:
    Prints the solver termination status and an order plan per scenario, then a
    scenario summary table with termination status and objective value.
"""

from pathlib import Path

from pandas import read_csv

from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("supplier_reliability")
Concept, Property = model.Concept, model.Property

# --------------------------------------------------
# Define semantic model & load data
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
# Model the decision problem
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

# --------------------------------------------------
# Solve each disruption scenario (loop + where= filter)
# --------------------------------------------------

excluded_suppliers = [None, "SupplierC", "SupplierB"]
scenario_results = []

for excluded in excluded_suppliers:
    label = "baseline" if excluded is None else f"without_{excluded}"
    print(f"\nRunning scenario: {label}")

    p = Problem(model, Float)

    # Variable: order quantity — where= filter excludes supplier's orders
    if excluded is not None:
        active_orders = SupplyOrder.supplier.name != excluded
        p.solve_for(SupplyOrder.x_quantity, name=["qty", SupplyOrder.supplier.name, SupplyOrder.product.name],
                    lower=0, where=[active_orders], populate=False)
    else:
        p.solve_for(SupplyOrder.x_quantity, name=["qty", SupplyOrder.supplier.name, SupplyOrder.product.name],
                    lower=0, populate=False)

    # Constraint: total orders from supplier cannot exceed supplier capacity
    capacity_limit = model.require(
        sum(SupplyOrder.x_quantity).where(SupplyOrder.supplier == Supplier).per(Supplier) <= Supplier.capacity
    )
    p.satisfy(capacity_limit)

    # Constraint: demand satisfaction for each product
    meet_demand = model.require(
        sum(SupplyOrder.x_quantity).where(SupplyOrder.product == Product).per(Product) >= Product.demand
    )
    p.satisfy(meet_demand)

    # Objective: minimize cost
    direct_cost = sum(SupplyOrder.x_quantity * SupplyOrder.cost_per_unit)
    p.minimize(direct_cost)

    p.display()
    p.solve("highs", time_limit_sec=60)
    si = p.solve_info()
    si.display()

    scenario_results.append(
        {
            "scenario": label,
            "status": str(si.termination_status),
            "objective": si.objective_value,
        }
    )
    if si.termination_status != "OPTIMAL":
        print(f"  Status: {si.termination_status} — skipping results")
        continue
    print(f"  Status: {si.termination_status}, Objective: {si.objective_value}")

    # Print order plan from solver results
    var_df = p.variable_values().to_df()
    qty_df = var_df[var_df["name"].str.startswith("qty") & (var_df["value"] > 0.001)]
    print(f"\n  Orders:")
    print(qty_df.to_string(index=False))

# Summary
print("\n" + "=" * 50)
print("Scenario Analysis Summary")
print("=" * 50)
for result in scenario_results:
    obj = result["objective"]
    obj_str = f"{obj:.2f}" if obj is not None else "N/A"
    print(f"  {result['scenario']}: {result['status']}, obj={obj_str}")
