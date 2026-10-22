"""PyRel ontology and policy rules for a bus-bridge dispatch decision."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd
from decision_governance import add_decision_governance
from relationalai.config import create_config
from relationalai.semantics import Float, Integer, Model, String


def build_model(snapshot_dir: Path, config=None, history=None):
    """Build a fresh model from one immutable synthetic input snapshot."""
    snapshot_dir = Path(snapshot_dir)
    eager_config = (config if config is not None else create_config()).model_copy()
    eager_config.deployment = None
    model = Model("Transit Decision Network", config=eager_config)

    Case = model.Concept("DecisionCase", identify_by={"id": String})
    Event = model.Concept("InputEvent", identify_by={"id": String})
    Zone = model.Concept("Zone", identify_by={"id": String})
    Stop = model.Concept("Stop", identify_by={"id": String})
    RailLink = model.Concept("RailLink", identify_by={"id": String})
    RoadLink = model.Concept("RoadLink", identify_by={"id": String})
    Route = model.Concept("RouteOption", identify_by={"id": String})
    Vehicle = model.Concept("Vehicle", identify_by={"id": String})
    Driver = model.Concept("Driver", identify_by={"id": String})
    Option = model.Concept("AssignmentOption", identify_by={"id": String})

    Case.policy_version = model.Property(f"{Case} uses {String:policy_version}")
    Case.budget_usd = model.Property(f"{Case} has {Float:budget_usd}")
    Event.case = model.Property(f"{Event} belongs to {Case:case}")
    Event.event_time_utc = model.Property(f"{Event} happened at {String:event_time_utc}")
    Event.event_type = model.Property(f"{Event} has {String:event_type}")
    Event.object_id = model.Property(f"{Event} affects {String:object_id}")
    Event.actor = model.Property(f"{Event} came from {String:actor}")
    Event.reason = model.Property(f"{Event} has {String:reason}")
    Zone.demand = model.Property(f"{Zone} has {Float:demand}")
    Zone.min_service = model.Property(f"{Zone} requires {Float:min_service}")
    Zone.min_accessible = model.Property(f"{Zone} requires {Float:min_accessible}")
    Zone.unmet = model.Property(f"{Zone} has {Float:unmet}")
    Stop.zone = model.Property(f"{Stop} belongs to {Zone:zone}")
    RailLink.origin = model.Property(f"{RailLink} starts at {Stop:origin}")
    RailLink.destination = model.Property(f"{RailLink} ends at {Stop:destination}")
    RailLink.available = model.Property(f"{RailLink} has {Integer:available}")
    RoadLink.origin = model.Property(f"{RoadLink} starts at {Stop:origin}")
    RoadLink.destination = model.Property(f"{RoadLink} ends at {Stop:destination}")
    RoadLink.travel_min = model.Property(f"{RoadLink} takes {Float:travel_min}")
    Route.zone = model.Property(f"{Route} serves {Zone:zone}")
    Route.road_link = model.Property(f"{Route} uses {RoadLink:road_link}")
    Route.capacity = model.Property(f"{Route} serves at most {Float:capacity}")
    Route.cost = model.Property(f"{Route} costs {Float:cost}")
    Route.duration_min = model.Property(f"{Route} takes {Float:duration_min}")
    Route.accessible_service = model.Property(f"{Route} has {Integer:accessible_service}")
    Vehicle.capacity = model.Property(f"{Vehicle} carries {Float:capacity}")
    Vehicle.accessible = model.Property(f"{Vehicle} has {Integer:accessible}")
    Vehicle.available = model.Property(f"{Vehicle} has {Integer:available}")
    Driver.available = model.Property(f"{Driver} has {Integer:available}")
    Driver.accessible_qualified = model.Property(f"{Driver} has {Integer:accessible_qualified}")
    Driver.shift_remaining_min = model.Property(f"{Driver} has {Float:shift_remaining_min}")
    Option.route = model.Property(f"{Option} uses {Route:route}")
    Option.zone = model.Property(f"{Option} serves {Zone:zone}")
    Option.vehicle = model.Property(f"{Option} uses {Vehicle:vehicle}")
    Option.driver = model.Property(f"{Option} uses {Driver:driver}")
    Option.capacity = model.Property(f"{Option} serves {Float:capacity}")
    Option.accessible_capacity = model.Property(f"{Option} serves {Float:accessible_capacity} accessible riders")
    Option.cost = model.Property(f"{Option} costs {Float:cost}")
    Option.eligible = model.Relationship(f"{Option} is eligible")
    Option.selected = model.Property(f"{Option} has {Float:selected}")

    def source(name):
        return model.data(pd.read_csv(snapshot_dir / f"{name}.csv"))

    cases = source("cases")
    model.define(case := Case.new(id=cases.id), case.policy_version(cases.policy_version),
                 case.budget_usd(cases.budget_usd))
    events = source("events")
    model.define(event := Event.new(id=events.id), event.case(Case.lookup(id=events.case_id)),
                 event.event_time_utc(events.event_time_utc),
                 event.event_type(events.event_type), event.object_id(events.object_id),
                 event.actor(events.actor), event.reason(events.reason))
    zones = source("zones")
    model.define(zone := Zone.new(id=zones.id), zone.demand(zones.demand),
                 zone.min_service(zones.min_service), zone.min_accessible(zones.min_accessible))
    stops = source("stops")
    model.define(stop := Stop.new(id=stops.id), stop.zone(Zone.lookup(id=stops.zone_id)))
    rails = source("rail_links")
    model.define(rail := RailLink.new(id=rails.id),
                 rail.origin(Stop.lookup(id=rails.from_stop)),
                 rail.destination(Stop.lookup(id=rails.to_stop)),
                 rail.available(rails.available))
    roads = source("road_links")
    model.define(road := RoadLink.new(id=roads.id),
                 road.origin(Stop.lookup(id=roads.from_stop)),
                 road.destination(Stop.lookup(id=roads.to_stop)),
                 road.travel_min(roads.travel_min))
    routes = source("routes")
    model.define(route := Route.new(id=routes.id), route.zone(Zone.lookup(id=routes.zone_id)),
                 route.road_link(RoadLink.lookup(id=routes.road_link_id)),
                 route.capacity(routes.capacity), route.cost(routes.cost),
                 route.duration_min(routes.duration_min),
                 route.accessible_service(routes.accessible_service))
    vehicles = source("vehicles")
    model.define(vehicle := Vehicle.new(id=vehicles.id), vehicle.capacity(vehicles.capacity),
                 vehicle.accessible(vehicles.accessible), vehicle.available(vehicles.available))
    drivers = source("drivers")
    model.define(driver := Driver.new(id=drivers.id), driver.available(drivers.available),
                 driver.accessible_qualified(drivers.accessible_qualified),
                 driver.shift_remaining_min(drivers.shift_remaining_min))
    options = source("assignment_options")
    model.define(option := Option.new(id=options.id), option.route(Route.lookup(id=options.route_id)),
                 option.zone(Zone.lookup(id=options.zone_id)),
                 option.vehicle(Vehicle.lookup(id=options.vehicle_id)),
                 option.driver(Driver.lookup(id=options.driver_id)),
                 option.capacity(options.capacity),
                 option.accessible_capacity(options.accessible_capacity),
                 option.cost(options.cost))

    # These rules are shared by the query surface and the optimizer.
    model.where(Option.route == Route, Option.vehicle == Vehicle,
                Option.driver == Driver, Vehicle.available == 1, Driver.available == 1,
                Route.duration_min <= Driver.shift_remaining_min,
                Route.accessible_service == 0).define(Option.eligible())
    model.where(Option.route == Route, Option.vehicle == Vehicle,
                Option.driver == Driver, Vehicle.available == 1, Driver.available == 1,
                Route.duration_min <= Driver.shift_remaining_min,
                Route.accessible_service == 1, Vehicle.accessible == 1,
                Driver.accessible_qualified == 1).define(Option.eligible())

    governance = add_decision_governance(model, Case, Event, history)
    return SimpleNamespace(model=model, Case=Case, Event=Event,
                           Zone=Zone, Stop=Stop, RailLink=RailLink,
                           RoadLink=RoadLink, Route=Route, Vehicle=Vehicle,
                           Driver=Driver, Option=Option, **vars(governance))
