"""Blast radius: the directed graph of who ships to whom, the high-priority customers, and the
suppliers each of them transitively depends on."""

from relationalai.semantics import Integer
from relationalai.semantics.reasoners.graph import Graph

from .schema import Business, Demand, Shipment, model

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

# --------------------------------------------------
# Stage 0: Blast-radius pre-analysis (directed Business graph)
# --------------------------------------------------
# Trace every supplier each high-priority customer transitively depends on.
# This surfaces the exposure footprint BEFORE the MILP runs, so the
# scenario analysis in Stage 3 can be read in context: "if supplier X is
# downgraded, the optimizer is rerouting around the demands listed here."

biz_graph = Graph(model, directed=True, weighted=False, node_concept=Business, name="business_graph")
b_src, b_dst = Business.ref(), Business.ref()
model.where(Business.ships_to(b_src, b_dst)).define(
    biz_graph.Edge.new(src=b_src, dst=b_dst)
)

# The business graph's size, which the deployed model publishes for the queries.
biz_node_count, biz_edge_count = Integer.ref(), Integer.ref()
biz_num_nodes = model.Relationship(f"the business graph has {Integer:num_nodes} nodes")
biz_num_edges = model.Relationship(f"the business graph has {Integer:num_edges} edges")
model.where(biz_graph.num_nodes()(biz_node_count)).define(biz_num_nodes(biz_node_count))
model.where(biz_graph.num_edges()(biz_edge_count)).define(biz_num_edges(biz_edge_count))

# Upstream reachability: which suppliers do high-priority customers depend on?
target_customer = model.Relationship(f"target customer {Business}")
model.where(Business.is_high_priority_customer()).define(target_customer(Business))

reachable_to = biz_graph.reachable(to=target_customer)
# Attach it to Business, so the deployed model publishes it for the queries.
Business.reaches_target_customer = reachable_to

# Each high-priority customer's upstream suppliers: the SUPPLIER-type businesses that reach it
# through shipments.
Business.upstream_supplier = model.Relationship(
    f"{Business:customer} depends on supplier {Business:supplier}"
)
customer_node, supplier_node = Business.ref(), Business.ref()
model.where(
    reachable_to(supplier_node, customer_node),
    supplier_node.business_type == "SUPPLIER",
).define(Business.upstream_supplier(customer_node, supplier_node))
