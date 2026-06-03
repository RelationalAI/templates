"""Supplier Reliability (prescriptive optimization) template.

This script demonstrates a sourcing optimization model in RelationalAI that
minimizes total sourcing cost subject to supplier capacity and product demand, then
reads back the *marginals* a planner asks next (and stress-tests supplier reliability
with disruption scenarios):

- Load sample CSVs describing suppliers, products, and supplier-product supply options.
- Model those entities as *concepts* with typed properties.
- Choose non-negative order quantities for each supply option.
- Enforce supplier capacity limits and product demand satisfaction.
- Minimize total cost.

A plain solve answers "what is the cheapest sourcing plan?". Requesting
``solve(sensitivity=True)`` on the baseline ALSO answers the marginal questions --
in one solve, with the answers read straight off the variable / constraint objects
(the same attribute style as ``.name`` or ``.lower``):

- **Shadow price** of a supplier's capacity (``cap.shadow_price``): how much total
  cost moves per unit of capacity. A capacity with room to spare prices at zero; a
  nonzero price marks a binding bottleneck -- so this ranks which supplier to expand
  first. (One way only: slack => zero price, nonzero price => binding.)
- **Shadow price** of a product's demand (``meet.shadow_price``): the marginal cost
  to serve one more unit of that product.
- **Reduced cost** of a supply lane (``qty_var.reduced_cost``) and its **basis
  status** (``qty_var.basis_status``): which lanes are priced out versus in use.

Each constraint carries an entity back-pointer to what it grounds over
(``cap.supplier`` / ``meet.product``), just like a variable points back to its lane
(``qty_var.supplyorder``), so a marginal joins to that entity's own data by ENTITY
KEY (``cap.supplier.capacity``) -- never by parsing the constraint name string.

Modeling approach:
- Phase A: one baseline Problem solved with ``sensitivity=True``; the marginals are
  read off the captured variable / constraint handles. (These reads live on the
  baseline Problem, OUTSIDE the scenario loop -- a handle captured in the loop would
  carry the last exclusion scenario's marginals instead.)
- Phase B: disruption scenarios (exclude SupplierC, exclude SupplierB), each a
  separate Problem with a where= filter -- a FINITE structural change the local
  marginals contextualize but do not by themselves predict.

Run:
    `python supplier_reliability.py`

Output:
    Prints the baseline plan with its capacity / demand shadow prices, lane reduced
    costs and basis status, then an order plan per disruption scenario and a summary
    table with termination status and objective value.
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Float, Integer, Model, String, std, sum
from relationalai.semantics.reasoners.prescriptive import Problem

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

model = Model("supplier_reliability")
Concept, Property = model.Concept, model.Property

# Concept: suppliers with capacity and a reliability score. (reliability is carried as
# data only -- it is NOT priced into the cost objective and does NOT drive the hard-coded
# Phase B exclusions below; it is here for you to extend, see "Customize".)
Supplier = Concept("Supplier", identify_by={"id": Integer})
Supplier.name = Property(f"{Supplier} has {String:name}")
Supplier.reliability = Property(f"{Supplier} has {Float:reliability}")
Supplier.capacity = Property(f"{Supplier} has {Integer:capacity}")
supplier_csv = read_csv(DATA_DIR / "suppliers.csv")
model.define(Supplier.new(model.data(supplier_csv).to_schema()))

# Concept: products with demand requirements
Product = Concept("Product", identify_by={"id": Integer})
Product.name = Property(f"{Product} has {String:name}")
Product.demand = Property(f"{Product} has {Integer:demand}")
product_csv = read_csv(DATA_DIR / "products.csv")
model.define(Product.new(model.data(product_csv).to_schema()))

# Concept: supply options (reified supplier-product links) with a per-unit cost
SupplyOption = Concept("SupplyOption", identify_by={"id": Integer})
SupplyOption.supplier = Property(f"{SupplyOption} from {Supplier}", short_name="supplier")
SupplyOption.product = Property(f"{SupplyOption} for {Product}", short_name="product")
SupplyOption.cost_per_unit = Property(f"{SupplyOption} has {Float:cost_per_unit}")

options_csv = read_csv(DATA_DIR / "supply_options.csv")
options_data = model.data(options_csv)
model.define(
    SupplyOption.new(
        id=options_data.id,
        supplier=Supplier,
        product=Product,
        cost_per_unit=options_data.cost_per_unit,
    )
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
# Phase A — baseline solve with sensitivity analysis
# --------------------------------------------------
# The marginal reads MUST live on this single baseline Problem, built OUTSIDE the
# scenario loop below: the loop rebuilds a fresh Problem each iteration, so a handle
# captured in the loop would carry the LAST exclusion scenario's marginals.

baseline = Problem(model, Float)

# Variable: order quantity per supply lane (continuous, non-negative).
qty_var = baseline.solve_for(
    SupplyOrder.x_quantity,
    name=["qty", SupplyOrder.supplier.name, SupplyOrder.product.name],
    lower=0,
    populate=False,
)

# Constraints, captured as handles and named per entity so each instance's marginal
# reads back through the constraint's ENTITY KEY (cap.supplier / meet.product), never
# by parsing the constraint name string.
cap = baseline.satisfy(
    model.require(
        sum(SupplyOrder.x_quantity)
        .where(SupplyOrder.supplier == Supplier)
        .per(Supplier)
        <= Supplier.capacity
    ),
    name=["cap", Supplier.name],
)
meet = baseline.satisfy(
    model.require(
        sum(SupplyOrder.x_quantity).where(SupplyOrder.product == Product).per(Product)
        >= Product.demand
    ),
    name=["demand", Product.name],
)

# Objective: minimize total sourcing cost.
baseline.minimize(sum(SupplyOrder.x_quantity * SupplyOrder.cost_per_unit))

baseline.display()
baseline.solve("highs", time_limit_sec=60, sensitivity=True)
si = baseline.solve_info()
si.display()

assert si.termination_status == "OPTIMAL"
assert si.sensitivity is True
# Optimum: SupplierC (cheapest for every product) fills its 600 capacity; the
# remaining 150 units of demand go to SupplierB at +2/unit -> 4550 + 300 = 4850.
assert si.objective_value is not None and abs(si.objective_value - 4850) < 0.01

baseline_objective = si.objective_value
print(
    f"\nBaseline status: {si.termination_status}, objective: {baseline_objective:.2f}"
)

# --- The baseline sourcing plan -------------------------------------------------
# Read the solved amounts via values(0, ref) on the variable (no populate), filtered
# to the lanes actually used in the query.
amt = Float.ref()
orders_df = (
    model.select(
        qty_var.supplyorder.supplier.name.alias("supplier"),
        qty_var.supplyorder.product.name.alias("product"),
        amt.alias("quantity"),
    )
    .where(qty_var.values(0, amt), amt > 1e-6)
    .to_df()
    .sort_values(["supplier", "product"], ignore_index=True)
)
print("\nBaseline orders:")
print(orders_df.to_string(index=False))

# --- Reduced costs: which lanes are priced out? ---------------------------------
# Each marginal reads straight off the variable; the variable's back-pointer
# (qty_var.supplyorder) joins it to the lane's supplier / product by ENTITY KEY.
lane_rc_df = (
    model.select(
        qty_var.supplyorder.supplier.name.alias("supplier"),
        qty_var.supplyorder.product.name.alias("product"),
        qty_var.reduced_cost.alias("reduced_cost"),
        qty_var.basis_status.alias("basis_status"),
    )
    .to_df()
    .sort_values(["supplier", "product"], ignore_index=True)
)
print("\nLane reduced costs and basis status:")
print(lane_rc_df.to_string(index=False))
# A lane in use is BASIC with ~0 reduced cost; a priced-out lane is NONBASIC_AT_LOWER
# with a positive reduced cost (how far its cost must fall before using it pays off).
#
# Complementary slackness, the ALWAYS-TRUE directions only. (1) SupplierA's and
# SupplierD's lanes are genuinely priced out -- state it relationally, joined to the
# supplier by key:
model.where(qty_var.supplyorder.supplier.name == "SupplierA").require(
    qty_var.reduced_cost > 1e-6
)
model.where(qty_var.supplyorder.supplier.name == "SupplierD").require(
    qty_var.reduced_cost > 1e-6
)
# (these requires are validated when the next query below runs)
# (2) Every lane actually in use prices at ~0. Read each lane's reduced cost and solved
# amount together (values(k, ref) is the solution accessor) and check in Python:
rc_amt = Float.ref()
cs_df = (
    model.select(
        qty_var.supplyorder.supplier.name.alias("supplier"),
        qty_var.reduced_cost.alias("reduced_cost"),
        rc_amt.alias("quantity"),
    )
    .where(qty_var.values(0, rc_amt))
    .to_df()
)
assert (cs_df.loc[cs_df["quantity"] > 1e-6, "reduced_cost"].abs() < 1e-4).all()
# NOT the converse "every unused lane has rc > 0": SupplierB's lanes are each exactly
# +2 over SupplierC, so the optimum has alternate optima and some unused B lanes price
# at ~0. The strict converse holds only under a unique optimum.

# --- Shadow prices: the marginal value of capacity and demand -------------------
# A constraint carries an entity back-pointer too (cap.supplier / meet.product), so a
# shadow price joins to that entity's own data by KEY -- no name parsing, no pandas.
cap_sp_df = (
    model.select(
        cap.supplier.name.alias("supplier"),
        cap.supplier.capacity.alias("capacity"),
        cap.shadow_price.alias("shadow_price"),
    )
    .to_df()
    .sort_values("supplier", ignore_index=True)
)
print("\nSupplier capacity shadow prices (d cost / d capacity):")
print(cap_sp_df.to_string(index=False))
# Minimize + a <= capacity constraint => shadow_price <= 0: loosening a binding
# capacity lowers cost. SupplierC is the only binding capacity (cheapest source, fills
# up), so it carries the marginal value; the others have room to spare and price at 0.
model.where(cap.supplier.name == "SupplierC").require(cap.shadow_price < -1e-6)
model.where(cap.supplier.name != "SupplierC").require(
    std.math.abs(cap.shadow_price) < 1e-6
)

demand_sp_df = (
    model.select(
        meet.product.name.alias("product"),
        meet.product.demand.alias("demand"),
        meet.shadow_price.alias("shadow_price"),
    )
    .to_df()
    .sort_values("product", ignore_index=True)
)
print("\nProduct demand shadow prices (d cost / d demand):")
print(demand_sp_df.to_string(index=False))
# Minimize + a >= demand constraint => shadow_price >= 0: the marginal cost to serve
# one more unit of that product. Every product's demand binds here, and each demand
# shadow price is strictly positive because the marginal serving cost of each is > 0.
model.where(meet.product.name == "Widget").require(meet.shadow_price > 1e-6)
model.where(meet.product.name == "Gadget").require(meet.shadow_price > 1e-6)
model.where(meet.product.name == "Component").require(meet.shadow_price > 1e-6)

# --- Acting on it: which supplier capacity is the bottleneck? -------------------
# The largest-magnitude capacity shadow price is the capacity whose marginal unit
# moves the bill the most -- the supplier to expand (or protect) first. This read is
# also the query that validates the demand requires stated just above: a
# model.require() stays pending until the next query forces its evaluation.
bottleneck_df = model.select(
    cap.supplier.name.alias("supplier"), cap.shadow_price.alias("shadow_price")
).to_df()
bottleneck = max(
    zip(bottleneck_df["supplier"], bottleneck_df["shadow_price"]),
    key=lambda sp: abs(sp[1]),
)
print(
    f"\nMost cost-sensitive capacity: {bottleneck[0]} (d cost / d capacity = {bottleneck[1]:+.2f})"
)

# --------------------------------------------------
# Phase B — disruption scenarios (separate re-solves)
# --------------------------------------------------
# Each scenario is its own Problem with a where= filter excluding one supplier -- a
# FINITE structural change (a supplier fully removed). A shadow price is a marginal at
# the current optimum, not an exclusion-impact ranking, so these re-solves are
# CONSISTENT WITH Phase A (SupplierC, the most valuable capacity, hurts most when
# excluded) without being predicted by the duals alone.

# Known optima for the disruption scenarios (the LP objective is unique even under the
# alternate optima above), asserted in the loop so a Phase B regression fails loudly.
EXPECTED_SCENARIO_OBJECTIVE = {"without_SupplierC": 6750.0, "without_SupplierB": 5150.0}

scenario_results = [
    {
        "scenario": "baseline",
        "status": str(si.termination_status),
        "objective": baseline_objective,
    }
]

for excluded in ["SupplierC", "SupplierB"]:
    label = f"without_{excluded}"
    print(f"\nRunning scenario: {label}")

    problem = Problem(model, Float)

    # Exclude one supplier via where=; populate=False leaves SupplyOrder.x_quantity
    # untouched so the baseline's persistent integrity constraints stay valid.
    qty_scn = problem.solve_for(
        SupplyOrder.x_quantity,
        name=["qty", SupplyOrder.supplier.name, SupplyOrder.product.name],
        lower=0,
        where=[SupplyOrder.supplier.name != excluded],
        populate=False,
    )

    problem.satisfy(
        model.require(
            sum(SupplyOrder.x_quantity)
            .where(SupplyOrder.supplier == Supplier)
            .per(Supplier)
            <= Supplier.capacity
        )
    )
    problem.satisfy(
        model.require(
            sum(SupplyOrder.x_quantity)
            .where(SupplyOrder.product == Product)
            .per(Product)
            >= Product.demand
        )
    )
    problem.minimize(sum(SupplyOrder.x_quantity * SupplyOrder.cost_per_unit))

    problem.solve("highs", time_limit_sec=60)
    si_scn = problem.solve_info()
    si_scn.display()

    scenario_results.append(
        {
            "scenario": label,
            "status": str(si_scn.termination_status),
            "objective": si_scn.objective_value,
        }
    )
    if si_scn.termination_status != "OPTIMAL":
        print(f"  Status: {si_scn.termination_status} — skipping results")
        continue
    print(f"  Status: {si_scn.termination_status}, Objective: {si_scn.objective_value}")
    assert abs(si_scn.objective_value - EXPECTED_SCENARIO_OBJECTIVE[label]) < 0.01

    value_ref = Float.ref()
    qty_df = (
        model.select(
            qty_scn.supplyorder.supplier.name.alias("supplier"),
            qty_scn.supplyorder.product.name.alias("product"),
            value_ref.alias("quantity"),
        )
        .where(qty_scn.values(0, value_ref), value_ref > 1e-6)
        .to_df()
        .sort_values(["supplier", "product"], ignore_index=True)
    )
    print("\n  Orders:")
    print(qty_df.to_string(index=False))

# Summary
print("\n" + "=" * 50)
print("Scenario Analysis Summary")
print("=" * 50)
for result in scenario_results:
    obj = result["objective"]
    obj_str = f"{obj:.2f}" if obj is not None else "N/A"
    print(f"  {result['scenario']}: {result['status']}, obj={obj_str}")
