"""Execute the three transit decision snapshots with RelationalAI and compare plans."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from data.generate import DEFAULT_OUT, STAGES
from dispatch import POLICY_RULE_IDS, solve_dispatch
from transit_model import build_model


def verified_manifest(snapshot_dir: Path) -> dict:
    manifest = json.loads((snapshot_dir / "manifest.json").read_text(encoding="utf-8"))
    for filename, expected in manifest["file_sha256"].items():
        actual = hashlib.sha256((snapshot_dir / filename).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"Source snapshot changed: {snapshot_dir / filename}")
    return manifest


def run_stage(stage: str, source_dir: Path, enforce_accessibility: bool = True,
              label: str | None = None) -> dict:
    snapshot_dir = source_dir / stage
    manifest = verified_manifest(snapshot_dir)
    model_path = Path(__file__).parent / "transit_model.py"
    solver_path = Path(__file__).parent / "dispatch.py"
    model_hash = hashlib.sha256(model_path.read_bytes()).hexdigest()
    solver_hash = hashlib.sha256(solver_path.read_bytes()).hexdigest()
    ontology = build_model(snapshot_dir)
    info, selected, unmet = solve_dispatch(
        ontology,
        budget_usd=manifest["budget_usd"],
        penalty_per_unmet_rider_usd=manifest["penalty_per_unmet_rider_usd"],
        enforce_accessibility=enforce_accessibility,
    )
    assignments = selected.to_dict(orient="records")
    unmet_rows = unmet.to_dict(orient="records")
    total_cost = sum(float(row["cost"]) for row in assignments)
    if total_cost > manifest["budget_usd"] + 1e-6:
        raise AssertionError("Solver result exceeds budget")
    if len({row["route_id"] for row in assignments}) != len(assignments):
        raise AssertionError("Route assigned more than once")
    if len({row["vehicle_id"] for row in assignments}) != len(assignments):
        raise AssertionError("Vehicle assigned more than once")
    if len({row["driver_id"] for row in assignments}) != len(assignments):
        raise AssertionError("Driver assigned more than once")
    with (snapshot_dir / "zones.csv").open(newline="", encoding="utf-8") as stream:
        zones = list(csv.DictReader(stream))
    unmet_by_zone = {row["zone_id"]: float(row["unmet"]) for row in unmet_rows}
    for zone in zones:
        zone_id = zone["id"]
        rows = [row for row in assignments if row["zone_id"] == zone_id]
        if len(rows) > 1:
            raise AssertionError(f"Multiple routes selected for {zone_id}")
        served = sum(float(row["capacity"]) for row in rows)
        accessible = sum(float(row["accessible_capacity"]) for row in rows)
        if served + 1e-6 < float(zone["min_service"]):
            raise AssertionError(f"Service floor violated in {zone_id}")
        if enforce_accessibility and accessible + 1e-6 < float(zone["min_accessible"]):
            raise AssertionError(f"Accessible service violated in {zone_id}")
        if abs(unmet_by_zone[zone_id] - max(0, float(zone["demand"]) - served)) > 1e-5:
            raise AssertionError(f"Unmet demand inconsistent in {zone_id}")
    expected_objective = total_cost + manifest["penalty_per_unmet_rider_usd"] * sum(unmet_by_zone.values())
    if abs(float(info.objective_value) - expected_objective) > 1e-4:
        raise AssertionError("Objective components do not reconcile")
    if verified_manifest(snapshot_dir) != manifest:
        raise ValueError("Source manifest changed during the solve")
    if (hashlib.sha256(model_path.read_bytes()).hexdigest() != model_hash
            or hashlib.sha256(solver_path.read_bytes()).hexdigest() != solver_hash):
        raise ValueError("Decision logic changed during the solve")
    with (snapshot_dir / "events.csv").open(newline="", encoding="utf-8") as stream:
        trigger = next(row for row in csv.DictReader(stream)
                       if row["id"] == manifest["trigger_event_id"])
    point_id = "DP-" + hashlib.sha256(
        f'{manifest["case_id"]}:{stage}:{manifest["input_hash"]}'.encode("ascii")
    ).hexdigest()[:12]
    run_kind = label or "policy_constrained"
    run_fingerprint = json.dumps({
        "point_id": point_id, "kind": run_kind, "model_hash": model_hash,
        "solver_hash": solver_hash, "solver_version": info.solver_version,
        "assignments": assignments, "objective": float(info.objective_value),
    }, sort_keys=True, default=str).encode("utf-8")
    run_id = "DR-" + hashlib.sha256(run_fingerprint).hexdigest()[:12]
    return dict(
        case_id=manifest["case_id"], decision_point_id=point_id, run_id=run_id,
        stage=label or stage, source_stage=stage, run_kind=run_kind,
        trigger_event_id=manifest["trigger_event_id"],
        known_at_utc=trigger["event_time_utc"], trigger_reason=trigger["reason"],
        input_hash=manifest["input_hash"], source_file_sha256=manifest["file_sha256"],
        model_version="0.1.0", model_source_sha256=model_hash,
        solver_source_sha256=solver_hash,
        policy_version=manifest["policy_version"],
        budget_usd=manifest["budget_usd"],
        penalty_per_unmet_rider_usd=manifest["penalty_per_unmet_rider_usd"],
        applied_rule_ids=[rule for rule in POLICY_RULE_IDS
                          if enforce_accessibility or rule != "south_accessible_floor"],
        accessibility_enforced=enforce_accessibility,
        solver="highs", solver_version=info.solver_version,
        status=info.termination_status,
        objective_value=float(info.objective_value), total_cost=total_cost,
        assignments=assignments, unmet=unmet_rows,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--ledger", type=Path,
                        help="Append successful run records to this JSONL file")
    args = parser.parse_args()
    runs = [run_stage(stage, args.source) for stage in STAGES]
    runs.insert(1, run_stage("closure", args.source, enforce_accessibility=False,
                             label="accessibility_relaxed_counterfactual"))
    for run in runs:
        print(json.dumps(run, sort_keys=True, default=str))
    if args.ledger:
        args.ledger.parent.mkdir(parents=True, exist_ok=True)
        with args.ledger.open("a", encoding="utf-8") as stream:
            for run in runs:
                record = dict(run, recorded_at=datetime.now(timezone.utc).isoformat())
                stream.write(json.dumps(record, sort_keys=True, default=str) + "\n")


if __name__ == "__main__":
    main()
