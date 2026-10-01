"""Delivery ontology, directed routes, and the maximum whole-order plan.

This module declares the model without connecting to Snowflake or solving it.
The public output contracts still require a live deployment/refresh test.
"""

from relationalai.semantics import Boolean, Float, Integer, Model, String, not_, sum
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.std.aggregates import count

model = Model("retail_delivery_agent")

Node = model.Concept("Node", identify_by={"id": String})

Depot = model.Concept("Depot", identify_by={"id": String})
Depot.node = model.Relationship(f"{Depot} is at {Node:node}")
Depot.is_open = model.Property(f"{Depot} is open {Boolean:is_open}")
Depot.stock_units = model.Property(f"{Depot} has {Integer:stock_units} units")

Store = model.Concept("Store", identify_by={"id": String})
Store.node = model.Relationship(f"{Store} is at {Node:node}")

Road = model.Concept("Road", identify_by={"from_id": String, "to_id": String})
Road.source = model.Relationship(f"{Road} starts at {Node:source}")
Road.destination = model.Relationship(f"{Road} ends at {Node:destination}")
Road.travel_minutes = model.Property(f"{Road} takes {Float:travel_minutes} minutes")

Order = model.Concept("Order", identify_by={"id": String})
Order.store = model.Relationship(f"{Order} goes to {Store:store}")
Order.units = model.Property(f"{Order} needs {Integer:units} units")
Order.deadline_minutes = model.Property(f"{Order} is due in {Float:deadline_minutes} minutes")

DemoState = model.Concept("DemoState", identify_by={"id": String})
DemoState.revision = model.Property(f"{DemoState} has {Integer:revision}")

graph = Graph(model, directed=True, weighted=True, node_concept=Node)
model.define(
    graph.Edge.new(
        src=Road.source,
        dst=Road.destination,
        weight=Road.travel_minutes,
    )
)
distance = graph.distance(full=True)

DepotStoreTime = model.Relationship(
    f"{Depot:depot} can reach {Store:store} in {Float:minutes} minutes"
)
origin, destination = Node.ref(), Node.ref()
depot, store = Depot.ref(), Store.ref()
model.where(
    depot.node(origin),
    store.node(destination),
    depot.is_open == True,
    distance(origin, destination, Float),
).define(DepotStoreTime(depot, store, Float))

ReachableStore = model.Relationship(f"{Store} is reachable from an open depot")
model.where(DepotStoreTime(Depot, Store, Float)).define(ReachableStore(Store))

OnTimeRoute = model.Relationship(
    f"{Depot:depot} can reach {Order:order} on time in {Float:minutes} minutes"
)
depot, order = Depot.ref(), Order.ref()
model.where(
    DepotStoreTime(depot, order.store, Float),
    Float <= order.deadline_minutes,
).define(OnTimeRoute(depot, order, Float))

EligiblePair = model.Relationship(f"{Depot:depot} can complete {Order:order} in full")
depot, order = Depot.ref(), Order.ref()
model.where(
    OnTimeRoute(depot, order, Float),
    depot.stock_units >= order.units,
).define(EligiblePair(depot, order))

Assignment = model.Relationship(
    f"{Depot:depot} sends {Order:order} with {Integer:assigned}"
)
problem = Problem(model, Integer, name="delivery_plan")
depot, order, chosen = Depot.ref(), Order.ref(), Integer.ref()
problem.solve_for(
    Assignment(depot, order, chosen),
    where=[EligiblePair(depot, order)],
    type="bin",
    lower=0,
    upper=1,
    name=["send", depot.id, order.id],
)
depot, order, chosen = Depot.ref(), Order.ref(), Integer.ref()
problem.satisfy(
    model.where(Assignment(depot, order, chosen)).require(
        sum(chosen).per(order) <= 1
    )
)
depot, order, chosen = Depot.ref(), Order.ref(), Integer.ref()
problem.satisfy(
    model.where(Assignment(depot, order, chosen)).require(
        sum(order.units * chosen).per(depot) <= depot.stock_units
    )
)
depot, order, chosen = Depot.ref(), Order.ref(), Integer.ref()
problem.maximize(
    sum(chosen).where(Assignment(depot, order, chosen)),
    name="completed_whole_orders",
)
problem.configure("highs", time_limit_sec=120)

Selected = model.Relationship(f"{Depot:depot} is selected for {Order:order}")
model.where(
    problem.termination_status()("OPTIMAL"),
    Assignment(Depot, Order, 1),
).define(Selected(Depot, Order))
HasSelectedOrder = model.Relationship(f"{Order} has a selected depot")
model.where(Selected(Depot, Order)).define(HasSelectedOrder(Order))
HasOnTimeRoute = model.Relationship(f"{Order} has an on-time route")
model.where(OnTimeRoute(Depot, Order, Float)).define(HasOnTimeRoute(Order))
HasEligiblePair = model.Relationship(f"{Order} has a full-stock on-time depot")
model.where(EligiblePair(Depot, Order)).define(HasEligiblePair(Order))

StoreRouteStatus = model.Concept("StoreRouteStatus", identify_by={"store_id": String})
StoreRouteStatus.state = model.Property(f"{StoreRouteStatus} has {String:state}")
StoreRouteStatus.revision = model.Property(
    f"{StoreRouteStatus} has {Integer:revision}"
)
model.define(StoreRouteStatus.new(store_id=Store.id))
model.where(ReachableStore(Store)).define(
    StoreRouteStatus.state(Store.id, "REACHABLE")
)
model.where(Store, not_(ReachableStore(Store))).define(
    StoreRouteStatus.state(Store.id, "NO_ROUTE")
)
model.where(StoreRouteStatus, DemoState.id == "current").define(
    StoreRouteStatus.revision(StoreRouteStatus, DemoState.revision)
)

OrderDecision = model.Concept("OrderDecision", identify_by={"order_id": String})
OrderDecision.store_id = model.Property(f"{OrderDecision} goes to {String:store_id}")
OrderDecision.units = model.Property(f"{OrderDecision} needs {Integer:units} units")
OrderDecision.deadline_minutes = model.Property(
    f"{OrderDecision} is due in {Float:deadline_minutes} minutes"
)
OrderDecision.state = model.Property(f"{OrderDecision} has {String:state}")
OrderDecision.depot_id = model.Property(f"{OrderDecision} uses {String:depot_id}")
OrderDecision.arrival_minutes = model.Property(
    f"{OrderDecision} arrives in {Float:arrival_minutes} minutes"
)
OrderDecision.revision = model.Property(f"{OrderDecision} has {Integer:revision}")

model.where(Order, problem.termination_status()("OPTIMAL")).define(
    decision := OrderDecision.new(order_id=Order.id),
    decision.store_id(Order.store.id),
    decision.units(Order.units),
    decision.deadline_minutes(Order.deadline_minutes),
)
depot, order = Depot.ref(), Order.ref()
model.where(Selected(depot, order)).define(
    OrderDecision.state(order.id, "SELECTED"),
    OrderDecision.depot_id(order.id, depot.id),
)
model.where(Selected(depot, order), OnTimeRoute(depot, order, Float)).define(
    OrderDecision.arrival_minutes(order.id, Float)
)
order = Order.ref()
model.where(
    order,
    problem.termination_status()("OPTIMAL"),
    not_(ReachableStore(order.store)),
).define(OrderDecision.state(order.id, "NO_ROUTE"))
order = Order.ref()
model.where(
    order,
    problem.termination_status()("OPTIMAL"),
    ReachableStore(order.store),
    not_(HasOnTimeRoute(order)),
).define(OrderDecision.state(order.id, "LATE_ONLY"))
order = Order.ref()
model.where(
    order,
    problem.termination_status()("OPTIMAL"),
    HasOnTimeRoute(order),
    not_(HasEligiblePair(order)),
).define(OrderDecision.state(order.id, "INSUFFICIENT_STOCK"))
order = Order.ref()
model.where(
    order,
    problem.termination_status()("OPTIMAL"),
    HasEligiblePair(order),
    not_(HasSelectedOrder(order)),
).define(OrderDecision.state(order.id, "REACHABLE_NOT_SELECTED"))
model.where(
    OrderDecision, DemoState.id == "current", problem.termination_status()("OPTIMAL")
).define(
    OrderDecision.revision(OrderDecision, DemoState.revision)
)

PlanSummary = model.Concept("PlanSummary", identify_by={"id": String})
PlanSummary.revision = model.Property(f"{PlanSummary} has {Integer:revision}")
PlanSummary.solver_status = model.Property(f"{PlanSummary} has {String:solver_status}")
PlanSummary.completed_orders = model.Property(
    f"{PlanSummary} has {Integer:completed_orders} completed orders"
)
model.define(PlanSummary.new(id="current"))
status = String.ref()
model.where(problem.termination_status()(status)).define(
    PlanSummary.solver_status("current", status)
)
model.where(DemoState.id == "current").define(
    PlanSummary.revision("current", DemoState.revision)
)
model.where(problem.termination_status()("OPTIMAL")).define(
    PlanSummary.completed_orders(
        "current", count(Order).where(Selected(Depot, Order)) | 0
    )
)
