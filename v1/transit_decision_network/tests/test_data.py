"""Deterministic fixture and intended-trade-off checks, independent of RAI."""

from __future__ import annotations

import itertools
import json
import tempfile
import unittest
from pathlib import Path

from data.generate import STAGES, snapshot, snapshot_hash, write_snapshots
from decision_history import load_history
from dispatch import formulate_dispatch
from relationalai.semantics import inspect
from run_demo import verified_manifest
from transit_model import build_model


def reference_plan(stage: str, enforce_accessibility: bool = True):
    """Enumerate route/vehicle pairs for the tiny fixture, not a demo optimizer."""
    tables = snapshot(stage)
    zones = tables["zones"]
    routes = {row["id"]: row for row in tables["routes"]}
    vehicles = {row["id"]: row for row in tables["vehicles"]}
    per_zone = {
        zone["id"]: [
            option for option in tables["assignment_options"]
            if option["zone_id"] == zone["id"]
            and option["driver_id"] == ("D03" if routes[option["route_id"]]["accessible_service"] else "D01")
            and vehicles[option["vehicle_id"]]["available"]
            and (
                not routes[option["route_id"]]["accessible_service"]
                or vehicles[option["vehicle_id"]]["accessible"]
            )
            and option["capacity"] >= zone["min_service"]
            and (
                not enforce_accessibility
                or option["accessible_capacity"] >= zone["min_accessible"]
            )
        ] for zone in zones
    }
    best = None
    for chosen in itertools.product(*(per_zone[zone["id"]] for zone in zones)):
        if len({row["vehicle_id"] for row in chosen}) != len(chosen):
            continue
        if sum(row["cost"] for row in chosen) > 18000:
            continue
        score = sum(row["cost"] for row in chosen) + 250 * sum(
            max(0, zone["demand"] - option["capacity"])
            for zone, option in zip(zones, chosen)
        )
        key = (score, tuple((row["route_id"], row["vehicle_id"]) for row in chosen))
        if best is None or key < best[0]:
            best = (key, chosen)
    if best is None:
        raise AssertionError("Fixture has no feasible plan")
    return {row["zone_id"]: (row["route_id"], row["vehicle_id"]) for row in best[1]}


class FixtureTests(unittest.TestCase):
    def make_governance_ledger(self, root: Path) -> Path:
        rows = []
        for stage in STAGES:
            manifest = verified_manifest(root / stage)
            event = snapshot(stage)["events"][-1]
            for kind in (("policy_constrained", "accessibility_relaxed_counterfactual")
                         if stage == "closure" else ("policy_constrained",)):
                enforce = kind == "policy_constrained"
                rows.append(dict(
                    case_id=manifest["case_id"], source_stage=stage,
                    decision_point_id=f"DP-{stage}", run_id=f"DR-{stage}-{kind}",
                    run_kind=kind, input_hash=manifest["input_hash"],
                    source_file_sha256=manifest["file_sha256"],
                    trigger_event_id=event["id"], known_at_utc=event["event_time_utc"],
                    trigger_reason=event["reason"], model_source_sha256="a" * 64,
                    solver_source_sha256="b" * 64, policy_version="P1",
                    budget_usd=18000.0, penalty_per_unmet_rider_usd=250.0,
                    applied_rule_ids=(["budget_limit", "south_accessible_floor"] if enforce
                                      else ["budget_limit"]),
                    accessibility_enforced=enforce, status="OPTIMAL", solver="highs",
                    solver_version="test", objective_value=100.0, total_cost=100.0,
                    assignments=[], unmet=[],
                ))
        path = root / "runs.jsonl"
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        return path

    def test_snapshot_is_deterministic_and_has_valid_links(self):
        for stage in STAGES:
            self.assertEqual(snapshot_hash(snapshot(stage)), snapshot_hash(snapshot(stage)))
            self.assertEqual(len(snapshot(stage)["assignment_options"]), 7 * 5 * 4)
        self.assertEqual(len({snapshot_hash(snapshot(stage)) for stage in STAGES}), 3)

    def test_pyrel_schema_registers_decision_concepts_and_rules(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_snapshots(root)
            ontology = build_model(root / "closure")
            schema = inspect.schema(ontology.model)
            self.assertIn("AssignmentOption", schema)
            self.assertIn("RouteOption", schema)
            self.assertIn("DecisionCase", schema)
            self.assertIn("InputEvent", schema)
            self.assertIn("eligible", [rel.name for rel in schema["AssignmentOption"].relationships])
            problem = formulate_dispatch(ontology)
            self.assertEqual(len(problem.variables), 2)
            self.assertEqual(len(problem.constraints), 8)
            self.assertEqual(len(problem.objectives), 1)

    def test_source_manifests_detect_tampering(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_snapshots(root)
            self.assertEqual(verified_manifest(root / "closure")["stage"], "closure")
            with (root / "closure" / "vehicles.csv").open("a", encoding="utf-8") as stream:
                stream.write("tampered\n")
            with self.assertRaisesRegex(ValueError, "Source snapshot changed"):
                verified_manifest(root / "closure")

    def test_invalid_source_reference_is_rejected(self):
        from data.generate import validate

        tables = snapshot("closure")
        tables["events"][0]["object_id"] = "NOT-A-LINK"
        with self.assertRaisesRegex(ValueError, "Unknown target"):
            validate(tables)

    def test_policy_and_events_change_the_choice(self):
        self.assertEqual(reference_plan("closure"), {
            "Z1": ("R1", "B01"), "Z2": ("R3", "B02"), "Z3": ("R5", "B07")
        })
        self.assertEqual(reference_plan("closure", enforce_accessibility=False)["Z3"][0], "R7")
        self.assertEqual(reference_plan("vehicle_veto")["Z3"], ("R5", "B08"))
        self.assertEqual(reference_plan("traffic_update")["Z3"], ("R6", "B08"))

    def test_decision_points_link_runs_reviews_outcomes_and_source_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_snapshots(root)
            ledger = self.make_governance_ledger(root)
            history = load_history(ledger, root)
            self.assertEqual(len(history["points"]), 3)
            self.assertEqual(len(history["runs"]), 4)
            self.assertEqual(len(history["source_files"]), 30)
            self.assertEqual(len(history["actions"]), 3)
            self.assertEqual(len(history["outcomes"]), 3)
            relaxed = history["runs"].query("kind == 'accessibility_relaxed_counterfactual'")
            self.assertFalse(relaxed.iloc[0]["accessibility_enforced"])
            self.assertNotIn(relaxed.iloc[0]["id"], set(history["actions"]["run_id"]))
            ontology = build_model(root / "traffic_update", history=history)
            schema = inspect.schema(ontology.model)
            for name in ("DecisionPoint", "DecisionRun", "DecisionAction",
                         "OutcomeObservation", "InputSnapshot", "DecisionRule"):
                self.assertIn(name, schema)

    def test_governance_rejects_temporal_and_hash_errors(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_snapshots(root)
            ledger = self.make_governance_ledger(root)
            follow_up = root / "decision_follow_up.csv"
            original = follow_up.read_text(encoding="utf-8")
            follow_up.write_text(original.replace("2026-10-22T07:31:00Z",
                                                  "2026-10-22T07:29:00Z"), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Follow-up order invalid"):
                load_history(ledger, root)
            follow_up.write_text(original, encoding="utf-8")
            rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
            rows[0]["input_hash"] = "0" * 64
            ledger.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "source evidence does not match"):
                load_history(ledger, root)


if __name__ == "__main__":
    unittest.main()
