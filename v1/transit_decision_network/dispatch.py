"""Run one RelationalAI dispatch solve and inspect its selected assignments."""

from __future__ import annotations

from relationalai.semantics import Float
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.std import aggregates as aggs

POLICY_RULE_IDS = (
    "resource_availability", "driver_shift", "accessible_qualification",
    "budget_limit", "one_use_per_resource", "zone_service_floor",
    "south_accessible_floor", "unmet_rider_penalty",
)


def formulate_dispatch(ontology, budget_usd=18000, penalty_per_unmet_rider_usd=250,
                       enforce_accessibility=True):
    if budget_usd <= 0 or penalty_per_unmet_rider_usd <= 0:
        raise ValueError("Budget and unmet-rider penalty must be positive")
    model = ontology.model
    Zone, Route = ontology.Zone, ontology.Route
    Vehicle, Driver, Option = ontology.Vehicle, ontology.Driver, ontology.Option
    problem = Problem(model, Float)
    problem.solve_for(Option.selected, where=[Option.eligible()],
                      name=["route_id", "vehicle_id", "driver_id"], type="bin")
    problem.solve_for(Zone.unmet, name=["zone_id"], lower=0.0, type="cont")

    problem.satisfy(model.require(aggs.sum(Option.selected * Option.cost) <= budget_usd))
    problem.satisfy(model.where(Option.vehicle == Vehicle).require(
        aggs.sum(Option.selected).per(Vehicle) <= 1))
    problem.satisfy(model.where(Option.driver == Driver).require(
        aggs.sum(Option.selected).per(Driver) <= 1))
    problem.satisfy(model.where(Option.route == Route).require(
        aggs.sum(Option.selected).per(Route) <= 1))
    problem.satisfy(model.where(Option.zone == Zone).require(
        aggs.sum(Option.selected).per(Zone) <= 1))
    problem.satisfy(model.where(Option.zone == Zone).require(
        aggs.sum(Option.selected * Option.capacity).per(Zone) + Zone.unmet >= Zone.demand))
    problem.satisfy(model.where(Option.zone == Zone).require(
        aggs.sum(Option.selected * Option.capacity).per(Zone) >= Zone.min_service))
    if enforce_accessibility:
        problem.satisfy(model.where(Option.zone == Zone).require(
            aggs.sum(Option.selected * Option.accessible_capacity).per(Zone)
            >= Zone.min_accessible))

    problem.minimize(aggs.sum(Option.selected * Option.cost)
                     + penalty_per_unmet_rider_usd * aggs.sum(Zone.unmet))
    return problem


def solve_dispatch(ontology, budget_usd=18000, penalty_per_unmet_rider_usd=250,
                   enforce_accessibility=True):
    problem = formulate_dispatch(ontology, budget_usd, penalty_per_unmet_rider_usd,
                                 enforce_accessibility)
    problem.solve("highs", time_limit_sec=60)
    info = problem.solve_info()
    if info.termination_status != "OPTIMAL":
        raise RuntimeError(f"Dispatch solve ended {info.termination_status}: {info.error}")

    model = ontology.model
    Zone, Route = ontology.Zone, ontology.Route
    Vehicle, Driver, Option = ontology.Vehicle, ontology.Driver, ontology.Option
    selected = model.where(Option.selected > 0.5,
                           Option.route == Route, Option.zone == Zone,
                           Option.vehicle == Vehicle, Option.driver == Driver).select(
        Option.id.alias("option_id"), Route.id.alias("route_id"),
        Zone.id.alias("zone_id"), Vehicle.id.alias("vehicle_id"),
        Driver.id.alias("driver_id"), Option.capacity.alias("capacity"),
        Option.accessible_capacity.alias("accessible_capacity"),
        Option.cost.alias("cost"),
    ).to_df()
    unmet = model.select(Zone.id.alias("zone_id"), Zone.unmet.alias("unmet")).to_df()
    return info, selected, unmet
