"""Validate run evidence and prepare decision-governance source tables."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
from run_demo import verified_manifest

RULES = (
    ("resource_availability", "eligibility", "Vehicle and driver are available"),
    ("driver_shift", "eligibility", "Route fits remaining driver shift"),
    ("accessible_qualification", "eligibility", "Accessible route uses qualified resources"),
    ("budget_limit", "constraint", "Selected operating cost is within budget"),
    ("one_use_per_resource", "constraint", "Route, bus, driver, and zone are used at most once"),
    ("zone_service_floor", "constraint", "Every zone receives minimum capacity"),
    ("south_accessible_floor", "constraint", "South receives 30 accessible places"),
    ("unmet_rider_penalty", "objective", "Unmet riders add a fixed dollar penalty"),
)


def _time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_history(ledger_path: Path, source_dir: Path) -> dict[str, pd.DataFrame]:
    """Build one immutable decision point per snapshot and one run per variant."""
    ledger_path, source_dir = Path(ledger_path), Path(source_dir)
    records = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines()
               if line.strip()]
    if not records:
        raise ValueError("Decision ledger is empty")
    by_variant = {}
    for record in records:
        key = (record["source_stage"], record["run_kind"])
        prior = by_variant.get(key)
        if prior and prior["run_id"] != record["run_id"]:
            raise ValueError(f"Multiple versions for {key}; use a fresh ledger for this demo")
        by_variant[key] = record
    records = list(by_variant.values())
    required = {("closure", "policy_constrained"),
                ("closure", "accessibility_relaxed_counterfactual"),
                ("vehicle_veto", "policy_constrained"),
                ("traffic_update", "policy_constrained")}
    if set(by_variant) != required:
        raise ValueError(f"Expected four demo variants, got {set(by_variant)}")

    points, snapshots, files, assets, policies = {}, {}, {}, {}, {}
    runs, selections, run_rules = [], [], []
    known_rules = {row[0] for row in RULES}
    for record in records:
        stage = record["source_stage"]
        manifest = verified_manifest(source_dir / stage)
        if (record["input_hash"] != manifest["input_hash"]
                or record["source_file_sha256"] != manifest["file_sha256"]):
            raise ValueError(f"Run source evidence does not match {stage}")
        with (source_dir / stage / "events.csv").open(newline="", encoding="utf-8") as stream:
            events = {row["id"]: row for row in csv.DictReader(stream)}
        event = events[record["trigger_event_id"]]
        if record["known_at_utc"] != event["event_time_utc"]:
            raise ValueError(f"Decision time differs from trigger for {stage}")
        snapshot_id = f'SS-{stage}-{record["input_hash"][:12]}'
        point_id = record["decision_point_id"]
        model_asset_id = "CODE-" + record["model_source_sha256"][:16]
        solver_asset_id = "CODE-" + record["solver_source_sha256"][:16]
        assets[model_asset_id] = dict(id=model_asset_id, kind="pyrel_model",
                                      path="transit_model.py",
                                      sha256=record["model_source_sha256"])
        assets[solver_asset_id] = dict(id=solver_asset_id, kind="solver_logic",
                                       path="dispatch.py",
                                       sha256=record["solver_source_sha256"])
        snapshots[snapshot_id] = dict(id=snapshot_id, stage=stage,
                                      input_hash=record["input_hash"],
                                      source_path=str(source_dir / stage))
        for filename, sha in manifest["file_sha256"].items():
            file_id = f"{snapshot_id}:{filename}"
            files[file_id] = dict(id=file_id, snapshot_id=snapshot_id,
                                  filename=filename, sha256=sha)
        policy_id = record["policy_version"]
        policy_row = dict(id=policy_id, budget_usd=float(record["budget_usd"]),
                          penalty_per_unmet_rider_usd=float(record["penalty_per_unmet_rider_usd"]))
        if policy_id in policies and policies[policy_id] != policy_row:
            raise ValueError(f"Policy parameters changed without a new version: {policy_id}")
        policies[policy_id] = policy_row
        point_row = dict(id=point_id, case_id=record["case_id"],
                         event_id=record["trigger_event_id"], snapshot_id=snapshot_id,
                         model_asset_id=model_asset_id, solver_asset_id=solver_asset_id,
                         policy_id=policy_id, known_at_utc=record["known_at_utc"],
                         trigger_reason=record["trigger_reason"])
        if point_id in points and points[point_id] != point_row:
            raise ValueError(f"Conflicting decision point: {point_id}")
        points[point_id] = point_row
        if set(record["applied_rule_ids"]) - known_rules:
            raise ValueError(f"Unknown rule on {record['run_id']}")
        if record["accessibility_enforced"] != ("south_accessible_floor" in record["applied_rule_ids"]):
            raise ValueError(f"Accessibility rule flag differs on {record['run_id']}")
        runs.append(dict(id=record["run_id"], point_id=point_id,
                         kind=record["run_kind"], status=record["status"],
                         solver=record["solver"], solver_version=record["solver_version"],
                         objective_value=float(record["objective_value"]),
                         plan_cost_usd=float(record["total_cost"]),
                         unmet_riders=sum(float(row["unmet"]) for row in record["unmet"]),
                         accessibility_enforced=int(record["accessibility_enforced"])))
        for row in record["assignments"]:
            selections.append(dict(id=f'{record["run_id"]}:{row["option_id"]}',
                                   run_id=record["run_id"], route_id=row["route_id"],
                                   zone_id=row["zone_id"], vehicle_id=row["vehicle_id"],
                                   driver_id=row["driver_id"], capacity=float(row["capacity"]),
                                   accessible_capacity=float(row["accessible_capacity"]),
                                   cost=float(row["cost"])))
        run_rules.extend(dict(run_id=record["run_id"], rule_id=rule)
                         for rule in record["applied_rule_ids"])

    actors, actions, outcomes = {}, [], []
    follow_up_path = source_dir / "decision_follow_up.csv"
    with follow_up_path.open(newline="", encoding="utf-8") as stream:
        follow_up = list(csv.DictReader(stream))
    windows = []
    for row in follow_up:
        stage = row["stage"]
        run = by_variant[(stage, "policy_constrained")]
        if row["action"] != "approved" or run["status"] != "OPTIMAL":
            raise ValueError(f"Only optimal, approved policy runs have outcomes: {stage}")
        if not (_time(run["known_at_utc"]) <= _time(row["action_at_utc"])
                <= _time(row["window_start_utc"]) < _time(row["window_end_utc"])
                <= _time(row["observed_at_utc"])):
            raise ValueError(f"Follow-up order invalid for {stage}")
        spend = float(row["simulated_incremental_spend_usd"])
        if spend <= 0:
            raise ValueError(f"ROI denominator must be positive: {stage}")
        actors[row["actor_id"]] = dict(id=row["actor_id"], name=row["actor_name"],
                                       role=row["actor_role"])
        actions.append(dict(id=f'ACT-{stage}', run_id=run["run_id"],
                            actor_id=row["actor_id"], action=row["action"],
                            action_at_utc=row["action_at_utc"], reason=row["action_reason"]))
        outcomes.append(dict(id=f'OUT-{stage}', run_id=run["run_id"],
                             window_start_utc=row["window_start_utc"],
                             window_end_utc=row["window_end_utc"],
                             observed_at_utc=row["observed_at_utc"],
                             modeled_baseline_loss_usd=float(row["modeled_baseline_loss_usd"]),
                             simulated_observed_loss_usd=float(row["simulated_observed_loss_usd"]),
                             simulated_incremental_spend_usd=spend,
                             evidence_kind="synthetic_follow_up"))
        windows.append((_time(row["window_start_utc"]), _time(row["window_end_utc"])))
    if len(follow_up) != 3 or len({row["stage"] for row in follow_up}) != 3:
        raise ValueError("Expected one follow-up per policy-constrained stage")
    windows.sort()
    if any(left[1] > right[0] for left, right in zip(windows, windows[1:])):
        raise ValueError("Outcome windows overlap; actor ROI would double count")

    tables = dict(points=list(points.values()), snapshots=list(snapshots.values()),
                  source_files=list(files.values()), code_assets=list(assets.values()),
                  policies=list(policies.values()), runs=runs, selections=selections,
                  actors=list(actors.values()), actions=actions, outcomes=outcomes,
                  rules=[dict(id=id, kind=kind, description=description)
                         for id, kind, description in RULES], run_rules=run_rules)
    return {name: pd.DataFrame(rows) for name, rows in tables.items()}
