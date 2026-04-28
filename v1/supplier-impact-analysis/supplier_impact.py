"""Supplier Impact Analysis (graph analysis) template.

Answers:
  "Which suppliers do high-value customers depend upon?"
  -> Upstream reachability on directed BusinessGraph

  "If WaferTech Taiwan goes offline, which customers/products are impacted?"
  -> Downstream reachability from target supplier + SKU join for product impact

Data: supply chain (businesses + shipments).
Graph: directed, unweighted. Business nodes, ships_to edges
  (derived from Shipment data: supplier_business -> customer_business).
Derived concepts: is_high_value_customer, ships_to, receives_shipment.

Run:
    `python supplier_impact.py`

Output:
    Prints upstream supplier dependencies for high-value customers and the
    downstream blast-radius (customers and SKUs) of a target supplier outage.
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Float, Integer, Model, String, define, distinct, where
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.std import aggregates as aggs

model = Model("supplier_impact")

# --------------------------------------------------
# Load data & define semantic model
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Business concept
Business = model.Concept("Business", identify_by={"id": String})
Business.name = model.Property(f"{Business} named {String:name}")
Business.type = model.Property(f"{Business} has type {String:type}")
Business.value_tier = model.Property(f"{Business} has value tier {String:value_tier}")
Business.reliability_score = model.Property(f"{Business} has reliability {Float:reliability_score}")

biz_df = read_csv(data_dir / "businesses.csv")

# Load core columns (no NaN) first, then optional columns separately
biz_core = model.data(biz_df[["ID", "NAME", "TYPE"]])
model.define(Business.new(id=biz_core["ID"]))
where(Business.id == biz_core["ID"]).define(
    Business.name(biz_core["NAME"]),
    Business.type(biz_core["TYPE"]),
)

# Load optional columns (may have NaN) — filter to non-null rows
vt_df = biz_df[biz_df["VALUE_TIER"].notna()][["ID", "VALUE_TIER"]]
if len(vt_df) > 0:
    vt_data = model.data(vt_df)
    where(Business.id == vt_data["ID"]).define(Business.value_tier(vt_data["VALUE_TIER"]))

rs_df = biz_df[biz_df["RELIABILITY_SCORE"].notna()][["ID", "RELIABILITY_SCORE"]]
if len(rs_df) > 0:
    rs_data = model.data(rs_df)
    where(Business.id == rs_data["ID"]).define(Business.reliability_score(rs_data["RELIABILITY_SCORE"]))

# Shipment concept (with relationships to Business, not just string IDs)
Shipment = model.Concept("Shipment", identify_by={"id": String})
Shipment.quantity = model.Property(f"{Shipment} has {Integer:quantity}")
Shipment.sku_id = model.Property(f"{Shipment} has sku {String:sku_id}")
Shipment.supplier = model.Relationship(f"{Shipment} from {Business}", short_name="supplier")
Shipment.customer = model.Relationship(f"{Shipment} to {Business}", short_name="customer")

ship_data = model.data(read_csv(data_dir / "shipments.csv"))
model.define(Shipment.new(id=ship_data["ID"]))
where(Shipment.id == ship_data["ID"]).define(
    Shipment.quantity(ship_data["QUANTITY"]),
    Shipment.sku_id(ship_data["SKU_ID"]),
    Shipment.supplier(Business.filter_by(id=ship_data["SUPPLIER_BUSINESS_ID"])),
    Shipment.customer(Business.filter_by(id=ship_data["CUSTOMER_BUSINESS_ID"])),
)

# --------------------------------------------------
# Derived relationships
# --------------------------------------------------

# ships_to: supplier -> customer (derived from Shipment data)
Business.ships_to = model.Relationship(f"{Business:supplier} ships to {Business:customer}")

b_from, b_to = Business.ref(), Business.ref()
model.define(Business.ships_to(b_from, b_to)).where(
    Shipment.supplier(b_from),
    Shipment.customer(b_to),
)

# receives_shipment: customer -> shipment (for product impact)
Business.receives_shipment = model.Relationship(f"{Business} receives {Shipment}")
model.define(Business.receives_shipment(Business, Shipment)).where(
    Shipment.customer(Business),
)

# is_high_value_customer: BUYER + HIGH value_tier
Business.is_high_value_customer = model.Relationship(f"{Business} is a high-value customer")
model.define(Business.is_high_value_customer(Business)).where(
    Business.type == "BUYER",
    Business.value_tier == "HIGH",
)

# --------------------------------------------------
# Build graph: directed, unweighted BusinessGraph
# --------------------------------------------------

graph = Graph(
    model,
    directed=True,
    weighted=False,
    node_concept=Business,
)

model.define(graph.Edge.new(
    src=Business.ref(),
    dst=Business.ships_to(Business.ref()),
))

print("=== Supply Network Graph ===")
graph.num_nodes().inspect()
graph.num_edges().inspect()

# --------------------------------------------------
# Upstream: Which suppliers do high-value customers depend upon?
# --------------------------------------------------

target_customer = model.Relationship(f"Target Customer: {Business}")
define(target_customer(Business)).where(Business.is_high_value_customer(Business))

reachable_to = graph.reachable(to=target_customer)

supplier = graph.Node.ref()
q5_df = (
    where(
        reachable_to(supplier, target_customer),
        supplier.type == "SUPPLIER",
    )
    .select(
        target_customer.name.alias("customer_name"),
        target_customer.value_tier.alias("value_tier"),
        supplier.name.alias("supplier_name"),
        supplier.reliability_score.alias("supplier_reliability"),
        supplier.type.alias("supplier_type"),
    )
    .to_df()
)

print("\n=== Supplier Dependencies of High-Value Customers ===")

if q5_df.empty:
    print("No dependencies found.")
else:
    for customer in sorted(q5_df["customer_name"].unique()):
        cust_df = q5_df[q5_df["customer_name"] == customer]
        print(f"\n  {customer} ({cust_df['value_tier'].iloc[0]}):")
        print(f"  Depends on {len(cust_df)} supplier(s):")
        for _, row in cust_df.sort_values("supplier_name").iterrows():
            rel = row["supplier_reliability"]
            rel_str = f"{rel:.0%}" if not str(rel) == "nan" else "N/A"
            print(f"    - {row['supplier_name']} (reliability: {rel_str})")

    # Supplier risk view
    print("\n--- Supplier Risk Analysis ---")
    supplier_summary = (
        q5_df.groupby(["supplier_name", "supplier_reliability"])["customer_name"]
        .apply(lambda x: sorted(set(x)))
        .reset_index()
    )
    for _, row in supplier_summary.iterrows():
        rel = row["supplier_reliability"]
        rel_str = f"{rel:.0%}" if not str(rel) == "nan" else "N/A"
        print(f"  {row['supplier_name']} (reliability: {rel_str}):")
        print(f"    High-value customers at risk: {', '.join(row['customer_name'])}")

# --------------------------------------------------
# Downstream: If WaferTech Taiwan goes offline, who is impacted?
# --------------------------------------------------

TARGET_SUPPLIER = "WaferTech Taiwan"

target_supplier = model.Relationship(f"Target Supplier: {Business}")
define(target_supplier(Business)).where(Business.name == TARGET_SUPPLIER)

reachable_from = graph.reachable(from_=target_supplier)

customer = graph.Node.ref()

# Downstream customers with SKU details
q6_with_skus = (
    where(
        reachable_from(target_supplier, customer),
        customer.receives_shipment.sku_id,
    )
    .select(distinct(
        customer.name.alias("customer_name"),
        customer.type.alias("customer_type"),
        customer.value_tier.alias("customer_value_tier"),
        customer.receives_shipment.sku_id.alias("product_at_risk"),
        aggs.sum(customer.receives_shipment.quantity).per(customer, customer.receives_shipment.sku_id).alias("quantity_at_risk"),
    ))
    .to_df()
)

# Downstream customers only
q6_customers = (
    where(reachable_from(target_supplier, customer))
    .select(distinct(
        customer.name.alias("customer_name"),
        customer.type.alias("customer_type"),
    ))
    .to_df()
)

print(f"\n=== Impact if '{TARGET_SUPPLIER}' Goes Offline ===")

# Exclude the target itself
q6_customers = q6_customers[q6_customers["customer_name"] != TARGET_SUPPLIER]
q6_with_skus = q6_with_skus[q6_with_skus["customer_name"] != TARGET_SUPPLIER]

if q6_customers.empty:
    print(f"No downstream impact found for {TARGET_SUPPLIER}.")
else:
    print(f"\nTotal affected entities: {len(q6_customers)}")

    for btype in ["COMPONENT_MANUFACTURER", "MANUFACTURER", "WAREHOUSE", "BUYER"]:
        subset = q6_customers[q6_customers["customer_type"] == btype]
        if len(subset) > 0:
            print(f"\n  Affected {btype}s ({len(subset)}):")
            for _, row in subset.iterrows():
                print(f"    - {row['customer_name']}")

    # Product impact for end customers
    if not q6_with_skus.empty:
        buyers = q6_with_skus[q6_with_skus["customer_type"] == "BUYER"]
        if not buyers.empty:
            print("\n--- Products at Risk (End Customers) ---")
            for customer_name in sorted(buyers["customer_name"].unique()):
                cust_df = buyers[buyers["customer_name"] == customer_name]
                tier = cust_df["customer_value_tier"].iloc[0]
                tier_str = f", {tier}" if str(tier) != "nan" else ""
                print(f"\n  {customer_name} (BUYER{tier_str}):")
                for _, row in cust_df.iterrows():
                    qty = float(row["quantity_at_risk"])
                    print(f"    - {row['product_at_risk']}: {qty:,.0f} units at risk")

# --------------------------------------------------
# Betweenness centrality: structural bottlenecks
# --------------------------------------------------

betweenness = graph.betweenness_centrality()

node = graph.Node.ref("n")
score = Float.ref("s")
btw_df = (
    where(betweenness(node, score))
    .select(
        node.id.alias("business_id"),
        node.name.alias("business_name"),
        node.type.alias("type"),
        score.alias("betweenness"),
    )
    .to_df()
    .sort_values("betweenness", ascending=False)
    .reset_index(drop=True)
)

print("\n=== Betweenness Centrality (structural bottlenecks) ===")
print(btw_df.to_string(index=False))

bottlenecks = btw_df[btw_df["betweenness"] > 0]
if len(bottlenecks) > 0:
    top = bottlenecks.iloc[0]
    print(f"\nMost critical node: {top['business_name']} ({top['type']}, betweenness={top['betweenness']:.4f})")
