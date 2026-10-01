"""Opt-in contract on *exported live evidence*, not an offline simulated solve.

The approved operator must export real rows and a refresh-plan trace from the
pinned release in an account enabled for the combined graph/solver workflow.
"""

from __future__ import annotations

import json
import os
import unittest
from datetime import datetime
from pathlib import Path

from scripts.check_results import compare_snapshot


def _read_env_json(name: str) -> dict:
    path = os.environ.get(name)
    if not path:
        raise RuntimeError(f"{name} required for approved live chain validation")
    return json.loads(Path(path).read_text(encoding="utf-8"))


@unittest.skipUnless(os.environ.get("RAI_LIVE_APPROVED") == "1", "No approved live account/evidence")
class TestApprovedLiveChain(unittest.TestCase):
    def test_graph_solver_public_rows_and_later_refresh(self) -> None:
        open_snapshot = _read_env_json("RAI_LIVE_OPEN_SNAPSHOT")
        closed_snapshot = _read_env_json("RAI_LIVE_CLOSED_SNAPSHOT")
        repeat_snapshot = _read_env_json("RAI_LIVE_REPEAT_SNAPSHOT")
        evidence = _read_env_json("RAI_LIVE_PLAN_AND_REFRESH_EVIDENCE")

        compare_snapshot(open_snapshot, closed=False)
        compare_snapshot(closed_snapshot, closed=True, prior_revision=1)
        compare_snapshot(repeat_snapshot, closed=True, prior_revision=1)
        if set(evidence) != {"plan", "refreshes", "source_mutation_at"}:
            self.fail("Need live plan, three refreshes, and source mutation timestamp")
        plan = evidence["plan"]
        entries = {str(item["id"]): item for item in plan}
        if len(entries) != len(plan):
            self.fail("Duplicate refresh-plan entry IDs")
        graph_entries = [item for item in plan if item["kind"] == "graph"]
        if not graph_entries:
            self.fail("No graph computation in the live refresh plan")
        for kind in ("prescriptive", "public_decisions"):
            if sum(item["kind"] == kind for item in plan) != 1:
                self.fail(f"Expected exactly one {kind} plan entry")
        solver = next(item for item in plan if item["kind"] == "prescriptive")
        decisions = next(item for item in plan if item["kind"] == "public_decisions")

        def depends_on(entry: dict, target_id: str) -> bool:
            pending = [str(value) for value in entry["dependency_ids"]]
            seen = set()
            while pending:
                dependency = pending.pop()
                if dependency == target_id:
                    return True
                if dependency not in seen:
                    seen.add(dependency)
                    if dependency not in entries:
                        self.fail(f"Missing dependency entry {dependency}")
                    pending.extend(str(value) for value in entries[dependency]["dependency_ids"])
            return False

        if not any(depends_on(solver, str(graph["id"])) for graph in graph_entries):
            self.fail("No verified graph→prescriptive refresh dependency")
        if not depends_on(decisions, str(solver["id"])):
            self.fail("No verified prescriptive→public-decision refresh dependency")
        if len(evidence["refreshes"]) != 3:
            self.fail("Need initial, post-closure, and repeated NEW refresh evidence")
        first, second, repeated = evidence["refreshes"]
        if any(
            int(snapshot["sources"]["demo_state"][0]["revision"]) != refresh["source_revision"]
            for snapshot, refresh in zip(
                (open_snapshot, closed_snapshot, repeat_snapshot),
                (first, second, repeated),
                strict=True,
            )
        ):
            self.fail("A snapshot revision differs from its corresponding refresh trace")
        if (
            first["status"] != "SUCCEEDED"
            or second["status"] != "SUCCEEDED"
            or repeated["status"] != "SUCCEEDED"
            or len({first["run_id"], second["run_id"], repeated["run_id"]}) != 3
            or first["source_revision"] != 1
            or second["source_revision"] != 2
            or repeated["source_revision"] != 2
            or not (
                datetime.fromisoformat(first["completed_at"])
                < datetime.fromisoformat(evidence["source_mutation_at"])
                <= datetime.fromisoformat(second["started_at"])
                < datetime.fromisoformat(second["completed_at"])
                < datetime.fromisoformat(repeated["started_at"])
                < datetime.fromisoformat(repeated["completed_at"])
            )
        ):
            self.fail("Refresh trace is stale, incomplete, or lacks a later repeated NEW run")


if __name__ == "__main__":
    unittest.main()
