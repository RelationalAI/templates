"""Generate the small, deterministic source snapshots for the transit decision demo."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from copy import deepcopy
from pathlib import Path

STAGES = ("closure", "vehicle_veto", "traffic_update")
DEFAULT_OUT = Path(__file__).resolve().parent / "out"

FOLLOW_UP = [
    dict(stage="closure", actor_id="ACT-AVERY", actor_name="Avery Tran",
         actor_role="dispatcher", action="approved",
         action_at_utc="2026-10-22T07:31:00Z",
         action_reason="Accessible bridge coverage preserved",
         window_start_utc="2026-10-22T07:31:00Z",
         window_end_utc="2026-10-22T07:42:00Z",
         observed_at_utc="2026-10-22T07:43:00Z",
         modeled_baseline_loss_usd=5000.0, simulated_observed_loss_usd=2600.0,
         simulated_incremental_spend_usd=1200.0),
    dict(stage="vehicle_veto", actor_id="ACT-MORGAN", actor_name="Morgan Vale",
         actor_role="supervisor", action="approved",
         action_at_utc="2026-10-22T07:44:00Z",
         action_reason="B07 unavailable; B08 preserves accessible capacity",
         window_start_utc="2026-10-22T07:44:00Z",
         window_end_utc="2026-10-22T08:00:00Z",
         observed_at_utc="2026-10-22T08:01:00Z",
         modeled_baseline_loss_usd=5600.0, simulated_observed_loss_usd=4000.0,
         simulated_incremental_spend_usd=1700.0),
    dict(stage="traffic_update", actor_id="ACT-MORGAN", actor_name="Morgan Vale",
         actor_role="supervisor", action="approved",
         action_at_utc="2026-10-22T08:02:00Z",
         action_reason="R5 road delay; R6 is policy-compliant within budget",
         window_start_utc="2026-10-22T08:02:00Z",
         window_end_utc="2026-10-22T10:00:00Z",
         observed_at_utc="2026-10-22T10:01:00Z",
         modeled_baseline_loss_usd=39000.0, simulated_observed_loss_usd=7000.0,
         simulated_incremental_spend_usd=12600.0),
]


def base_tables() -> dict[str, list[dict]]:
    cases = [dict(id="CASE-001", opened_at_utc="2026-10-22T07:30:00Z",
                  policy_version="P1", budget_usd=18000.0,
                  penalty_per_unmet_rider_usd=250.0)]
    events = [dict(id="E1", case_id="CASE-001", event_time_utc="2026-10-22T07:30:00Z",
                   event_type="rail_closure", object_id="RA08", actor="synthetic_sensor",
                   reason="Rail link S08-S09 closed", value="closed")]
    zones = [
        dict(id="Z1", name="North", demand=60.0, min_service=40.0, min_accessible=0.0),
        dict(id="Z2", name="Central", demand=50.0, min_service=35.0, min_accessible=0.0),
        dict(id="Z3", name="South", demand=40.0, min_service=30.0, min_accessible=30.0),
    ]
    stops = [
        dict(id=f"S{n:02d}", zone_id=("Z1" if n <= 7 else "Z2" if n <= 9 else "Z3"))
        for n in range(5, 13)
    ]
    rail_links = [
        dict(id=f"RA{n:02d}", from_stop=f"S{n:02d}", to_stop=f"S{n + 1:02d}",
             available=0 if n == 8 else 1)
        for n in range(5, 12)
    ]
    routes = [
        dict(id="R1", zone_id="Z1", from_stop="S05", to_stop="S08", road_link_id="RD1", capacity=60.0, cost=5000.0, duration_min=55.0, accessible_service=0),
        dict(id="R2", zone_id="Z1", from_stop="S06", to_stop="S08", road_link_id="RD2", capacity=50.0, cost=4300.0, duration_min=65.0, accessible_service=0),
        dict(id="R3", zone_id="Z2", from_stop="S08", to_stop="S10", road_link_id="RD3", capacity=50.0, cost=4900.0, duration_min=60.0, accessible_service=0),
        dict(id="R4", zone_id="Z2", from_stop="S08", to_stop="S09", road_link_id="RD4", capacity=45.0, cost=4300.0, duration_min=70.0, accessible_service=0),
        dict(id="R5", zone_id="Z3", from_stop="S09", to_stop="S12", road_link_id="RD5", capacity=40.0, cost=5500.0, duration_min=60.0, accessible_service=1),
        dict(id="R6", zone_id="Z3", from_stop="S10", to_stop="S12", road_link_id="RD6", capacity=35.0, cost=4500.0, duration_min=70.0, accessible_service=1),
        dict(id="R7", zone_id="Z3", from_stop="S09", to_stop="S12", road_link_id="RD7", capacity=40.0, cost=3000.0, duration_min=50.0, accessible_service=0),
    ]
    road_links = [
        dict(id=route["road_link_id"], from_stop=route["from_stop"], to_stop=route["to_stop"],
             travel_min=route["duration_min"])
        for route in routes
    ]
    vehicles = [
        dict(id="B01", capacity=60.0, accessible=0, available=1, premium=0.0),
        dict(id="B02", capacity=50.0, accessible=0, available=1, premium=150.0),
        dict(id="B07", capacity=40.0, accessible=1, available=1, premium=0.0),
        dict(id="B08", capacity=40.0, accessible=1, available=1, premium=800.0),
        dict(id="B09", capacity=45.0, accessible=0, available=1, premium=0.0),
    ]
    drivers = [
        dict(id=f"D{n:02d}", available=1, accessible_qualified=1 if n >= 3 else 0,
             shift_remaining_min=120.0)
        for n in range(1, 5)
    ]
    return dict(cases=cases, events=events, zones=zones, stops=stops,
                rail_links=rail_links, road_links=road_links,
                routes=routes, vehicles=vehicles, drivers=drivers)


def snapshot(stage: str) -> dict[str, list[dict]]:
    if stage not in STAGES:
        raise ValueError(f"Unknown stage: {stage}")
    tables = deepcopy(base_tables())
    if stage in ("vehicle_veto", "traffic_update"):
        next(v for v in tables["vehicles"] if v["id"] == "B07")["available"] = 0
        tables["events"].append(dict(
            id="E2", case_id="CASE-001", event_time_utc="2026-10-22T07:42:00Z",
            event_type="vehicle_veto", object_id="B07", actor="demo_dispatcher",
            reason="Accessible bus reported unavailable", value="unavailable",
        ))
    if stage == "traffic_update":
        route = next(r for r in tables["routes"] if r["id"] == "R5")
        route.update(capacity=25.0, cost=6800.0, duration_min=90.0)
        next(link for link in tables["road_links"] if link["id"] == "RD5")["travel_min"] = 90.0
        tables["events"].append(dict(
            id="E3", case_id="CASE-001", event_time_utc="2026-10-22T08:00:00Z",
            event_type="traffic_update", object_id="RD5", actor="synthetic_partner_feed",
            reason="Bridge route travel time increased", value="90 minutes",
        ))
    tables["assignment_options"] = [
        dict(id=f'{route["id"]}_{vehicle["id"]}_{driver["id"]}',
             route_id=route["id"], zone_id=route["zone_id"],
             vehicle_id=vehicle["id"], driver_id=driver["id"],
             capacity=float(min(route["capacity"], vehicle["capacity"])),
             accessible_capacity=float(min(route["capacity"], vehicle["capacity"]))
             if route["accessible_service"] and vehicle["accessible"] else 0.0,
             cost=float(route["cost"] + vehicle["premium"]))
        for route in tables["routes"]
        for vehicle in tables["vehicles"]
        for driver in tables["drivers"]
    ]
    validate(tables)
    return tables


def validate(tables: dict[str, list[dict]]) -> None:
    def require(condition: bool, message: str) -> None:
        if not condition:
            raise ValueError(message)

    ids = {}
    for name, rows in tables.items():
        keys = [row["id"] for row in rows]
        if len(keys) != len(set(keys)):
            raise ValueError(f"Duplicate ID in {name}")
        ids[name] = set(keys)
    for stop in tables["stops"]:
        require(stop["zone_id"] in ids["zones"], f"Unknown zone on {stop['id']}")
    for event in tables["events"]:
        require(event["case_id"] in ids["cases"], f"Unknown case on {event['id']}")
        target = {"rail_closure": "rail_links", "vehicle_veto": "vehicles",
                  "traffic_update": "road_links"}[event["event_type"]]
        require(event["object_id"] in ids[target], f"Unknown target on {event['id']}")
    for name in ("rail_links", "road_links"):
        for link in tables[name]:
            require(link["from_stop"] in ids["stops"], f"Unknown origin on {link['id']}")
            require(link["to_stop"] in ids["stops"], f"Unknown destination on {link['id']}")
    for route in tables["routes"]:
        require(route["zone_id"] in ids["zones"], f"Unknown zone on {route['id']}")
        require(route["road_link_id"] in ids["road_links"], f"Unknown road link on {route['id']}")
    routes = {row["id"]: row for row in tables["routes"]}
    vehicles = {row["id"]: row for row in tables["vehicles"]}
    for option in tables["assignment_options"]:
        route = routes[option["route_id"]]
        vehicle = vehicles[option["vehicle_id"]]
        require(option["zone_id"] == route["zone_id"], f"Wrong zone on {option['id']}")
        require(option["driver_id"] in ids["drivers"], f"Unknown driver on {option['id']}")
        require(option["capacity"] == min(route["capacity"], vehicle["capacity"]),
                f"Wrong capacity on {option['id']}")
        require(option["cost"] == route["cost"] + vehicle["premium"],
                f"Wrong cost on {option['id']}")
        accessible = option["capacity"] if route["accessible_service"] and vehicle["accessible"] else 0.0
        require(option["accessible_capacity"] == accessible,
                f"Wrong accessible capacity on {option['id']}")


def snapshot_hash(tables: dict[str, list[dict]]) -> str:
    payload = json.dumps(tables, sort_keys=True, separators=(",", ":")).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def write_snapshots(out_dir: Path = DEFAULT_OUT) -> None:
    for stage in STAGES:
        tables = snapshot(stage)
        target = out_dir / stage
        target.mkdir(parents=True, exist_ok=True)
        file_hashes = {}
        for name, rows in tables.items():
            path = target / f"{name}.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            file_hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        case = tables["cases"][0]
        manifest = dict(stage=stage, case_id=case["id"],
                        trigger_event_id=tables["events"][-1]["id"],
                        policy_version=case["policy_version"],
                        budget_usd=case["budget_usd"],
                        penalty_per_unmet_rider_usd=case["penalty_per_unmet_rider_usd"],
                        input_hash=snapshot_hash(tables), file_sha256=file_hashes)
        (target / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    with (out_dir / "decision_follow_up.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(FOLLOW_UP[0]))
        writer.writeheader()
        writer.writerows(FOLLOW_UP)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    write_snapshots(args.out)
    print(f"Wrote {', '.join(STAGES)} to {args.out}")
