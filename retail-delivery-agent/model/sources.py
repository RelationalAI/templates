"""Bind Snowflake source tables to schema facts; never load local CSV on import."""

from relationalai.semantics import Boolean, Float, Integer, String

from .schema import DemoState, Depot, Node, Order, Road, Store, model

depots = model.Table(
    "DEPOTS",
    schema={
        "DEPOT_ID": String,
        "NODE_ID": String,
        "IS_OPEN": Boolean,
        "STOCK_UNITS": Integer,
    },
)
stores = model.Table("STORES", schema={"STORE_ID": String, "NODE_ID": String})
roads = model.Table(
    "ROADS",
    schema={"FROM_NODE_ID": String, "TO_NODE_ID": String, "TRAVEL_MINUTES": Float},
)
orders = model.Table(
    "ORDERS",
    schema={
        "ORDER_ID": String,
        "STORE_ID": String,
        "UNITS": Integer,
        "DEADLINE_MINUTES": Float,
    },
)
state = model.Table("DEMO_STATE", schema={"REVISION": Integer})

model.define(
    Node.new(id=depots.NODE_ID),
    Node.new(id=stores.NODE_ID),
    Node.new(id=roads.FROM_NODE_ID),
    Node.new(id=roads.TO_NODE_ID),
)
model.define(
    depot := Depot.new(id=depots.DEPOT_ID),
    depot.node(Node.lookup(id=depots.NODE_ID)),
    depot.is_open(depots.IS_OPEN),
    depot.stock_units(depots.STOCK_UNITS),
)
model.define(
    store := Store.new(id=stores.STORE_ID),
    store.node(Node.lookup(id=stores.NODE_ID)),
)
model.define(
    road := Road.new(from_id=roads.FROM_NODE_ID, to_id=roads.TO_NODE_ID),
    road.source(Node.lookup(id=roads.FROM_NODE_ID)),
    road.destination(Node.lookup(id=roads.TO_NODE_ID)),
    road.travel_minutes(roads.TRAVEL_MINUTES),
)
model.define(
    order := Order.new(id=orders.ORDER_ID),
    order.store(Store.lookup(id=orders.STORE_ID)),
    order.units(orders.UNITS),
    order.deadline_minutes(orders.DEADLINE_MINUTES),
)
model.define(
    demo := DemoState.new(id="current"),
    demo.revision(state.REVISION),
)
