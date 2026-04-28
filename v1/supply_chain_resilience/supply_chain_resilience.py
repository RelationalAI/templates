"""Supply chain resilience (multi-reasoner) template.

This script demonstrates a chained multi-reasoner workflow in RelationalAI,
combining graph analysis, rules-based classification, and prescriptive
optimization for supply chain risk management:

- Stage 0 -- Blast-radius pre-analysis: build a directed Business graph from
  shipment data, run upstream reachability from high-priority demand customers
  to surface every supplier they transitively depend upon. This shows the
  exposure footprint before any optimization runs.
- Stage 1 -- Graph: build a site dependency graph from shipping operations,
  compute eigenvector centrality to identify critical warehouses and bridges
  between supply chain regions.
- Stage 2 -- Rules: classify suppliers by risk level (avoid/watch/reliable)
  using reliability scores and ML delay predictions. Flag late shipments
  and escalated demand orders.
- Stage 3 -- Prescriptive: solve a minimum-cost network flow that routes
  supply to meet demand. Graph centrality feeds a bottleneck penalty in the
  objective. Supplier risk flags feed hard constraints (no flow from "avoid"
  suppliers) and surcharges (extra cost for "watch" suppliers).
- Scenario analysis: re-solve with disruptions (critical site offline,
  supplier downgrade) to quantify resilience costs.

Run:
    `python supply_chain_resilience.py`

Output:
    Prints network analysis (clusters, centrality, bridges), supplier risk
    classifications, optimized flow plan with cost breakdown, and scenario
    comparison showing the cost of disruptions.
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Float, Integer, Model, String, sum, where
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.std import aggregates as aggs

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"
UNMET_PENALTY = 100.0  # penalty for unmet demand (kept moderate so routing costs are visible)
RISK_SURCHARGE = 5.0  # cost multiplier for "watch" supplier operations
CENTRALITY_WEIGHT = 2.0  # multiplier for bottleneck site penalty
DELAY_PROB_THRESHOLD = 0.15  # above this = high delay risk
RELIABILITY_THRESHOLD = 0.80  # below this = unreliable supplier
PREDICTION_QUARTER = "Q1-2025"  # which quarter's predictions to use

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

model = Model("supply_chain_resilience")

# Site concept: factories, distribution centers, offices, stores.
Site = model.Concept("Site", identify_by={"id": String})
Site.name = model.Property(f"{Site} has {String:name}")
Site.site_type = model.Property(f"{Site} has type {String:site_type}")
Site.region = model.Property(f"{Site} in {String:region}")
Site.country = model.Property(f"{Site} in {String:country}")

site_data = model.data(read_csv(DATA_DIR / "site.csv"))
model.define(
    s := Site.new(id=site_data["ID"]),
    s.name(site_data["NAME"]),
    s.site_type(site_data["SITE_TYPE"]),
    s.region(site_data["REGION"]),
    s.country(site_data["COUNTRY"]),
)

# Business concept: suppliers, manufacturers, warehouses, buyers.
Business = model.Concept("Business", identify_by={"id": String})
Business.name = model.Property(f"{Business} has {String:name}")
Business.business_type = model.Property(f"{Business} has type {String:business_type}")
Business.reliability_score = model.Property(
    f"{Business} has reliability {Float:reliability_score}"
)
Business.site = model.Relationship(f"{Business} operates at {Site}")

biz_csv = read_csv(DATA_DIR / "business.csv")

# Load businesses in two batches: with and without reliability score.
# Only pass needed columns to model.data() — extra columns with NaN
# values cause data loading issues.
biz_cols = ["ID", "NAME", "TYPE", "SITE_ID", "RELIABILITY_SCORE"]
biz_with_rel = biz_csv.dropna(subset=["RELIABILITY_SCORE"])[biz_cols]
biz_no_rel = biz_csv[biz_csv["RELIABILITY_SCORE"].isna()][biz_cols[:4]]

# Batch 1: businesses WITH reliability (suppliers, manufacturers).
d1 = model.data(biz_with_rel)
model.define(
    b1 := Business.new(id=d1["ID"], site=Site.filter_by(id=d1["SITE_ID"])),
    b1.name(d1["NAME"]),
    b1.business_type(d1["TYPE"]),
    b1.reliability_score(d1["RELIABILITY_SCORE"]),
)

# Batch 2: businesses WITHOUT reliability (buyers, warehouses).
if len(biz_no_rel) > 0:
    d2 = model.data(biz_no_rel)
    model.define(
        b2 := Business.new(id=d2["ID"], site=Site.filter_by(id=d2["SITE_ID"])),
        b2.name(d2["NAME"]),
        b2.business_type(d2["TYPE"]),
    )

# SKU concept: stock keeping units (raw materials, components, finished goods).
SKU = model.Concept("SKU", identify_by={"id": String})
SKU.name = model.Property(f"{SKU} has {String:name}")
SKU.sku_type = model.Property(f"{SKU} has type {String:sku_type}")

sku_data = model.data(read_csv(DATA_DIR / "sku.csv"))
model.define(
    sk := SKU.new(id=sku_data["ID"]),
    sk.name(sku_data["NAME"]),
    sk.sku_type(sku_data["TYPE"]),
)

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

op_data = model.data(read_csv(DATA_DIR / "operation.csv"))
model.define(
    o := Operation.new(id=op_data["ID"]),
    o.op_type(op_data["TYPE"]),
    o.transit_time_days(op_data["TRANSIT_TIME_DAYS"]),
    o.cost_per_unit(op_data["COST_PER_UNIT"]),
    o.capacity_per_day(op_data["CAPACITY_PER_DAY"]),
    o.source_site(Site.filter_by(id=op_data["SOURCE_SITE_ID"])),
    o.output_site(Site.filter_by(id=op_data["OUTPUT_SITE_ID"])),
    o.output_sku(SKU.filter_by(id=op_data["OUTPUT_SKU"])),
)

# Derived relationship: Operation's source business (via shared site).
Operation.source_business = model.Relationship(
    f"{Operation} sourced from {Business}"
)
model.define(Operation.source_business(Operation, Business)).where(
    Operation.source_site == Business.site
)

# Verify source_business derived relationship populates correctly.
sb_df = (
    model.select(Operation.id.alias("op"), Business.id.alias("biz"))
    .where(Operation.source_business(Operation, Business))
    .to_df()
)
print(f"Source-business links: {len(sb_df)}")
if len(sb_df) == 0:
    print("WARNING: source_business derived relationship is empty!")
else:
    print(f"  Sample: {sb_df.head(5).to_string(index=False)}")

# Demand concept: customer orders for SKUs.
Demand = model.Concept("Demand", identify_by={"id": String})
Demand.quantity = model.Property(f"{Demand} for {Integer:quantity} units")
Demand.priority = model.Property(f"{Demand} has priority {String:priority}")
Demand.business = model.Relationship(f"{Demand} placed by {Business}")
Demand.sku = model.Relationship(f"{Demand} for {SKU}")

dem_data = model.data(read_csv(DATA_DIR / "demand.csv"))
model.define(
    d := Demand.new(id=dem_data["ID"]),
    d.quantity(dem_data["QUANTITY"]),
    d.priority(dem_data["PRIORITY"]),
    d.business(Business.filter_by(id=dem_data["BUSINESS_ID"])),
    d.sku(SKU.filter_by(id=dem_data["SKU_ID"])),
)

# Shipment data: loaded BOTH as pandas DataFrame (for late-shipment stats)
# AND as a RAI Concept (so Stage 0 can run reachability on a directed
# Business graph derived from supplier->customer edges).
shipments_df = read_csv(DATA_DIR / "shipment.csv")

Shipment = model.Concept("Shipment", identify_by={"id": String})
Shipment.supplier = model.Relationship(f"{Shipment} from {Business}", short_name="supplier")
Shipment.customer = model.Relationship(f"{Shipment} to {Business}", short_name="customer")
Shipment.sku_id = model.Property(f"{Shipment} has sku {String:sku_id}")
Shipment.quantity = model.Property(f"{Shipment} has {Integer:quantity}")

ship_data = model.data(shipments_df[["ID", "SUPPLIER_BUSINESS_ID", "CUSTOMER_BUSINESS_ID", "SKU_ID", "QUANTITY"]])
model.define(
    sh := Shipment.new(id=ship_data["ID"]),
    sh.supplier(Business.filter_by(id=ship_data["SUPPLIER_BUSINESS_ID"])),
    sh.customer(Business.filter_by(id=ship_data["CUSTOMER_BUSINESS_ID"])),
    sh.sku_id(ship_data["SKU_ID"]),
    sh.quantity(ship_data["QUANTITY"]),
)

# Derived ships_to: supplier -> customer (collapses many shipments into edges).
Business.ships_to = model.Relationship(
    f"{Business:supplier} ships to {Business:customer}"
)
b_from, b_to = Business.ref(), Business.ref()
model.define(Business.ships_to(b_from, b_to)).where(
    Shipment.supplier(b_from),
    Shipment.customer(b_to),
)

# Flag businesses that hold at least one HIGH-priority demand — they are
# the customers whose blast-radius we care about most.
Business.is_high_priority_customer = model.Relationship(
    f"{Business} is a high-priority customer"
)
model.where(
    Demand.business(Business),
    Demand.priority == "HIGH",
).define(Business.is_high_priority_customer())

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

pred_data = model.data(read_csv(DATA_DIR / "delay_prediction.csv"))
model.define(
    dp := DelayPrediction.new(id=pred_data["ID"]),
    dp.fiscal_quarter(pred_data["FISCAL_QUARTER"]),
    dp.predicted_delay_prob(pred_data["PREDICTED_DELAY_PROB"]),
    dp.risk_tier(pred_data["RISK_TIER"]),
    dp.supplier_business(Business.filter_by(id=pred_data["SUPPLIER_BUSINESS_ID"])),
)

# --------------------------------------------------
# Stage 0: Blast-radius pre-analysis (directed Business graph)
# --------------------------------------------------
# Trace every supplier each high-priority customer transitively depends on.
# This surfaces the exposure footprint BEFORE the MILP runs, so the
# scenario analysis in Stage 3 can be read in context: "if supplier X is
# downgraded, the optimizer is rerouting around the demands listed here."

print("=" * 70)
print("STAGE 0: Blast-Radius Pre-Analysis (directed Business graph)")
print("=" * 70)

biz_graph = Graph(model, directed=True, weighted=False, node_concept=Business)
b_src, b_dst = Business.ref(), Business.ref()
model.where(Business.ships_to(b_src, b_dst)).define(
    biz_graph.Edge.new(src=b_src, dst=b_dst)
)

biz_graph.num_nodes().inspect()
biz_graph.num_edges().inspect()

# Upstream reachability: which suppliers do high-priority customers depend on?
target_customer = model.Relationship(f"target customer {Business}")
model.where(Business.is_high_priority_customer()).define(target_customer(Business))

reachable_to = biz_graph.reachable(to=target_customer)
supplier_node = biz_graph.Node.ref()
blast_df = (
    where(
        reachable_to(supplier_node, target_customer),
        supplier_node.business_type == "SUPPLIER",
    )
    .select(
        target_customer.name.alias("customer"),
        supplier_node.id.alias("supplier_id"),
        supplier_node.name.alias("supplier"),
        supplier_node.reliability_score.alias("supplier_reliability"),
    )
    .to_df()
)

print("\nUpstream supplier dependencies for high-priority customers:")
if blast_df.empty:
    print("  (no high-priority demands or no SUPPLIER-typed upstream)")
else:
    for cust in sorted(blast_df["customer"].unique()):
        cust_rows = blast_df[blast_df["customer"] == cust]
        print(f"\n  {cust} depends on {len(cust_rows)} supplier(s):")
        for _, row in cust_rows.sort_values("supplier").iterrows():
            rel = row["supplier_reliability"]
            rel_str = f"{rel:.0%}" if rel == rel else "N/A"  # NaN check
            print(f"    - {row['supplier']} (reliability: {rel_str})")

# --------------------------------------------------
# Stage 1: Graph -- network criticality
# --------------------------------------------------

print("\n" + "=" * 70)
print("STAGE 1: Graph -- Network Criticality")
print("=" * 70)

# Build undirected unweighted graph: Sites as nodes, SHIP operations as edges.
graph = Graph(model, directed=False, weighted=False, node_concept=Site, aggregator="sum")

s1, s2, op_ref = Site.ref(), Site.ref(), Operation.ref()
model.define(
    graph.Edge.new(src=s1, dst=s2)
).where(
    op_ref.source_site(s1),
    op_ref.output_site(s2),
    op_ref.op_type == "SHIP",
)

graph.num_nodes().inspect()
graph.num_edges().inspect()

# Weakly connected components.
wcc = graph.weakly_connected_component()
node_ref = graph.Node.ref("n")
comp_ref = graph.Node.ref("comp")

wcc_df = (
    where(wcc(node_ref, comp_ref))
    .select(
        node_ref.id.alias("site_id"),
        node_ref.name.alias("site_name"),
        node_ref.site_type.alias("site_type"),
        node_ref.region.alias("region"),
        comp_ref.id.alias("component_id"),
        aggs.count(node_ref).per(comp_ref).alias("cluster_size"),
    )
    .to_df()
)

num_components = wcc_df["component_id"].nunique()
print(f"\nConnected components: {num_components}")
if num_components == 1:
    print("UNIFIED NETWORK: All sites in a single connected component")
for comp_id in sorted(wcc_df["component_id"].unique()):
    comp_df = wcc_df[wcc_df["component_id"] == comp_id]
    size = int(comp_df["cluster_size"].iloc[0])
    regions = ", ".join(sorted(comp_df["region"].unique()))
    print(f"  Component {comp_id}: {size} sites ({regions})")

# Eigenvector centrality: identify most critical sites.
eigenvector = graph.eigenvector_centrality()
node_eig = graph.Node.ref("ne")
eig_score = Float.ref("es")

eig_df = (
    where(
        eigenvector(node_eig, eig_score),
        node_eig.site_type != "STORE",
        node_eig.site_type != "OFFICE",
    )
    .select(
        node_eig.id.alias("site_id"),
        node_eig.name.alias("site_name"),
        node_eig.site_type.alias("site_type"),
        node_eig.region.alias("region"),
        eig_score.alias("centrality_score"),
    )
    .to_df()
    .sort_values("centrality_score", ascending=False)
    .reset_index(drop=True)
)

print("\nTop critical sites (eigenvector centrality):")
for _, row in eig_df.head(8).iterrows():
    print(
        f"  {row['site_id']} {row['site_name']} ({row['site_type']}, {row['region']}): "
        f"centrality={row['centrality_score']:.4f}"
    )

# Store centrality on Site for use in optimization objective.
max_centrality = eig_df["centrality_score"].max()
if max_centrality == 0:
    max_centrality = 1.0
Site.centrality = model.Property(f"{Site} has centrality {Float:centrality}")
eig_df["normalized"] = eig_df["centrality_score"] / max_centrality
cent_data = model.data(eig_df[["site_id", "normalized"]])
model.where(Site.id == cent_data["site_id"]).define(
    Site.centrality(cent_data["normalized"])
)

# --------------------------------------------------
# Stage 2: Rules -- supplier risk classification
# --------------------------------------------------

print(f"\n{'=' * 70}")
print("STAGE 2: Rules -- Supplier Risk Classification")
print("=" * 70)

# Late shipment analysis (from pandas, not RAI — keeps model size manageable).
late_shipments = shipments_df[shipments_df["DELAY_DAYS"] > 0]
total_n = len(shipments_df)
late_n = len(late_shipments)
print(f"\nLate shipments: {late_n} of {total_n} ({100*late_n/total_n:.0f}%)")
late_by_supplier = (
    late_shipments.groupby("SUPPLIER_BUSINESS_ID")
    .size()
    .reset_index(name="late_count")
    .sort_values("late_count", ascending=False)
)
for _, row in late_by_supplier.head(5).iterrows():
    print(f"  {row['SUPPLIER_BUSINESS_ID']}: {row['late_count']} late shipments")

# Rule 2: Business is unreliable when reliability_score < threshold.
Business.is_unreliable = model.Relationship(f"{Business} is unreliable")
model.where(
    Business.reliability_score < RELIABILITY_THRESHOLD
).define(Business.is_unreliable())

# Rule 3: Business has high delay risk from ML predictions.
Business.has_high_delay_risk = model.Relationship(
    f"{Business} has high delay risk"
)
dp_ref = DelayPrediction.ref()
model.where(
    dp_ref.supplier_business(Business),
    dp_ref.fiscal_quarter == PREDICTION_QUARTER,
    dp_ref.predicted_delay_prob > DELAY_PROB_THRESHOLD,
).define(Business.has_high_delay_risk())

# Rule: Business is watch-level when it has either risk flag.
# "Avoid" businesses (both flags) are hard-blocked in Stage 3; watch-level
# businesses get a soft risk surcharge in the objective.
Business.is_watch_level = model.Relationship(f"{Business} is watch level")
model.where(Business.is_unreliable()).define(Business.is_watch_level())
model.where(Business.has_high_delay_risk()).define(Business.is_watch_level())

# Derive risk classification in Python from RAI flags.
# The optimization uses is_unreliable() and has_high_delay_risk() directly.
unreliable_df = (
    model.select(Business.id.alias("id"), Business.name.alias("name"),
                 Business.reliability_score.alias("reliability"))
    .where(Business.is_unreliable())
    .to_df()
)
high_delay_df = (
    model.select(Business.id.alias("id"))
    .where(Business.has_high_delay_risk())
    .to_df()
)
unreliable_ids = set(unreliable_df["id"]) if len(unreliable_df) > 0 else set()
high_delay_ids = set(high_delay_df["id"]) if len(high_delay_df) > 0 else set()

# Build risk classification from the two RAI-derived flags.
rel_score_ref = Float.ref()
all_biz_df = (
    model.select(Business.id.alias("id"), Business.name.alias("name"),
                 rel_score_ref.alias("reliability"))
    .where(Business.reliability_score(rel_score_ref))
    .to_df()
)

print("\nSupplier risk classification:")
avoid_ids = set()
for _, row in all_biz_df.sort_values("reliability").iterrows():
    biz_id = row["id"]
    is_unrel = biz_id in unreliable_ids
    is_delay = biz_id in high_delay_ids
    if is_unrel and is_delay:
        rc, marker = "avoid", "[X]"
        avoid_ids.add(biz_id)
    elif is_unrel or is_delay:
        rc, marker = "watch", "[!]"
    else:
        rc, marker = "reliable", "[ ]"
    print(
        f"  {marker} {biz_id} {row['name']}: "
        f"reliability={row['reliability']:.2f}, class={rc}"
    )

# Rule 4: Demand is escalated when priority is HIGH.
Demand.is_escalated = model.Relationship(f"{Demand} is escalated")
model.where(Demand.priority == "HIGH").define(Demand.is_escalated())

esc_df = (
    model.select(aggs.count(Demand).alias("count"))
    .where(Demand.is_escalated())
    .to_df()
)
esc_n = int(esc_df["count"].iloc[0]) if len(esc_df) > 0 else 0
print(f"\nEscalated demands (HIGH priority): {esc_n}")

# --------------------------------------------------
# Stage 3: Prescriptive -- risk-adjusted network flow
# --------------------------------------------------

print(f"\n{'=' * 70}")
print("STAGE 3: Prescriptive -- Risk-Adjusted Network Flow")
print("=" * 70)


# Define decision variable properties once, outside solve_flow().
Operation.x_flow = model.Property(f"{Operation} has {Float:flow}")
Demand.x_unmet = model.Property(f"{Demand} has {Float:unmet}")


def solve_flow(label, exclude_site_id=None, block_business_ids=None):
    """Solve the network flow, optionally disabling a site or blocking suppliers.

    Args:
        label: Display name for this scenario.
        exclude_site_id: Site ID string to take offline (all ops from this site get zero flow).
        block_business_ids: Set of Business ID strings whose source operations get zero flow.
    """
    if block_business_ids is None:
        block_business_ids = set()

    problem = Problem(model, Float)

    # Decision variable: flow on each operation.
    flow_var = problem.solve_for(
        Operation.x_flow,
        name=["x_flow", Operation.id],
        lower=0,
        upper=Operation.capacity_per_day,
        populate=False,
    )

    # Slack variable: unmet demand per demand order.
    unmet_var = problem.solve_for(
        Demand.x_unmet,
        name=["x_unmet", Demand.id],
        lower=0,
        populate=False,
    )

    # Constraint: demand satisfaction.
    # For each demand, inbound flow at the customer's site for the demanded
    # SKU, plus unmet slack, must cover the quantity.
    D = Demand.ref()
    Op = Operation.ref()
    B = Business.ref()
    problem.satisfy(
        model.require(
            sum(Op.x_flow).per(D) + D.x_unmet >= D.quantity
        ).where(
            D.business(B),
            B.site == Op.output_site,
            D.sku == Op.output_sku,
        ),
        name=["demand_sat", D.id],
    )

    # Constraint: block operations sourced from blocked businesses.
    # Uses explicit Python-side business IDs passed per scenario, so the
    # constraint is guaranteed to differ across scenarios.
    for biz_id in sorted(block_business_ids):
        biz_block = Business.ref()
        op_block = Operation.ref()
        problem.satisfy(
            model.require(op_block.x_flow == 0).where(
                op_block.source_business(biz_block),
                biz_block.id == biz_id,
            ),
            name=["block_biz", biz_id, op_block.id],
        )

    # Constraint (scenario): disable operations from a specific site.
    if exclude_site_id:
        excl_site = Site.ref()
        op_excl = Operation.ref()
        problem.satisfy(
            model.require(op_excl.x_flow == 0).where(
                op_excl.source_site(excl_site),
                excl_site.id == exclude_site_id,
            ),
            name=["site_offline", op_excl.id],
        )

    # Objective: minimize transport cost + risk surcharge + centrality penalty
    # + unmet demand penalty.
    transport_cost = sum(Operation.cost_per_unit * Operation.x_flow)

    # Risk surcharge: extra cost for "watch"-level supplier operations
    # (unreliable or high delay risk, but not necessarily blocked).
    op_watch = Operation.ref()
    biz_watch = Business.ref()
    risk_cost = RISK_SURCHARGE * sum(op_watch.x_flow).where(
        op_watch.source_business(biz_watch),
        biz_watch.is_watch_level(),
    )

    # Centrality penalty: discourage over-reliance on bottleneck sites.
    op_cent = Operation.ref()
    site_cent = Site.ref()
    cent_val = Float.ref()
    centrality_cost = CENTRALITY_WEIGHT * sum(
        op_cent.x_flow * cent_val
    ).where(
        op_cent.output_site(site_cent),
        site_cent.centrality(cent_val),
    )

    unmet_cost = UNMET_PENALTY * sum(Demand.x_unmet)

    problem.minimize(
        sum(model.union(transport_cost, risk_cost, centrality_cost, unmet_cost))
    )

    problem.solve("highs", time_limit_sec=120)
    si = problem.solve_info()
    si.display()

    status = si.termination_status
    obj = si.objective_value if status in ("OPTIMAL", "LOCALLY_SOLVED") else None

    # Extract active flows.
    if obj is not None:
        value_ref = Float.ref()
        flow_df = (
            model.select(
                flow_var.operation.id.alias("operation_id"),
                value_ref.alias("flow"),
            )
            .where(flow_var.values(0, value_ref), value_ref > 0.001)
            .to_df()
        )
        unmet_df = (
            model.select(
                unmet_var.demand.id.alias("demand_id"),
                value_ref.alias("unmet"),
            )
            .where(unmet_var.values(0, value_ref), value_ref > 0.001)
            .to_df()
        )
        n_active = len(flow_df)
        n_unmet = len(unmet_df)
        total_unmet = unmet_df["unmet"].sum() if len(unmet_df) > 0 else 0.0
    else:
        n_active, n_unmet, total_unmet = 0, 0, 0

    print(f"\n  [{label}]")
    print(f"  Status: {status}")
    if obj is not None:
        print(f"  Total cost: {obj:,.2f}")
        print(f"  Active flows: {n_active}")
        if total_unmet > 0:
            print(f"  Unmet demand: {total_unmet:,.0f} units across {n_unmet} orders")
        else:
            print("  All demand satisfied")

    return {"label": label, "status": status, "objective": obj, "unmet": total_unmet}


# Baseline solve: block only "avoid" suppliers (both unreliable AND high delay).
results = []
results.append(solve_flow("Baseline", block_business_ids=avoid_ids))
print(f"  Blocked businesses (avoid): {sorted(avoid_ids) if avoid_ids else 'none'}")

# --------------------------------------------------
# Scenario analysis
# --------------------------------------------------

print(f"\n{'=' * 70}")
print("SCENARIO ANALYSIS")
print("=" * 70)

# Scenario 1: Take the highest-centrality site offline.
top_site_id = eig_df.iloc[0]["site_id"]
top_site_name = eig_df.iloc[0]["site_name"]
print(f"\nScenario: {top_site_name} ({top_site_id}) goes offline")
results.append(
    solve_flow(
        f"Site {top_site_id} offline",
        exclude_site_id=top_site_id,
        block_business_ids=avoid_ids,
    )
)

# Scenario 2: Downgrade all "watch" suppliers to "avoid" — block any
# supplier that is unreliable OR has high delay risk.
watch_and_avoid_ids = unreliable_ids | high_delay_ids
print("\nScenario: All 'watch' suppliers downgraded to 'avoid'")
print(f"  Blocked businesses: {sorted(watch_and_avoid_ids)}")
results.append(
    solve_flow("Watch->Avoid", block_business_ids=watch_and_avoid_ids)
)

# Summary table.
print(f"\n{'=' * 70}")
print("SCENARIO COMPARISON")
print(f"{'=' * 70}")
print(f"  {'Scenario':<25} {'Status':<18} {'Cost':>12} {'Unmet':>10}")
print(f"  {'-' * 65}")
baseline_obj = results[0]["objective"]
for r in results:
    cost_str = f"{r['objective']:,.2f}" if r["objective"] else "N/A"
    unmet_str = f"{r['unmet']:,.0f}" if r["unmet"] else "0"
    delta = ""
    if r["objective"] and baseline_obj and r["label"] != "Baseline":
        pct = (r["objective"] - baseline_obj) / baseline_obj * 100
        delta = f" (+{pct:.1f}%)" if pct > 0 else f" ({pct:.1f}%)"
    print(
        f"  {r['label']:<25} {r['status']:<18} {cost_str:>12}{delta} {unmet_str:>10}"
    )
