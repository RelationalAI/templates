"""Offline contracts only; these tests do not claim a Snowflake/PyRel solve."""

from __future__ import annotations

import copy
import subprocess
import sys
import unittest
from pathlib import Path

from evaluation.check_oracle import evaluate, read_fixture
from evaluation.generate_cases import generate
from scripts.change_state import change_state
from scripts.check_results import compare_snapshot
from scripts.load_fixture import load_fixture
from scripts.teardown_sources import teardown

ROOT = Path(__file__).resolve().parents[1]


def with_north_closed(sources: dict, revision: int = 2) -> dict:
    result = copy.deepcopy(sources)
    for depot in result["depots"]:
        if depot["depot_id"] == "North":
            depot["is_open"] = "false"
    result["demo_state"] = [{"revision": str(revision)}]
    return result


def snapshot_double(sources: dict) -> dict:
    """Test-only synthetic rows for testing *rejection*, never PyRel output."""
    expected = evaluate(sources)
    plan = sorted(expected.optimal_plans)[0]
    assignment = {oid: depot for depot, oid in plan}
    orders = []
    for order in sources["orders"]:
        oid = order["order_id"]
        depot = assignment.get(oid)
        orders.append(
            {
                **order,
                "state": "SELECTED" if depot else expected.order_states[oid],
                "depot_id": depot,
                "arrival_minutes": (
                    expected.routes[depot, order["store_id"]] if depot else None
                ),
                "revision": expected.revision,
            }
        )
    return {
        "sources": copy.deepcopy(sources),
        "routes": [
            {"depot_id": did, "store_id": sid, "minutes": minutes}
            for (did, sid), minutes in expected.routes.items()
        ],
        "store_route_status": [
            {"store_id": sid, "state": state, "revision": expected.revision}
            for sid, state in expected.store_states.items()
        ],
        "order_decision": orders,
        "plan_summary": [
            {
                "id": "current", "revision": expected.revision,
                "solver_status": "OPTIMAL", "completed_orders": expected.optimal_count,
            }
        ],
    }


class TestFixtureOracle(unittest.TestCase):
    def setUp(self) -> None:
        self.base = read_fixture()

    def test_exact_questions_and_directed_shortest_times(self) -> None:
        open_result = evaluate(self.base)
        self.assertEqual(open_result.revision, 1)
        self.assertEqual(set(open_result.store_states.values()), {"REACHABLE"})
        self.assertEqual(open_result.optimal_count, 3)
        self.assertEqual(
            open_result.optimal_plans,
            {tuple(sorted((("North", "A1"), ("South", "C1"), ("South", "C2"))))},
        )
        self.assertEqual(
            open_result.routes,
            {
                ("North", "A"): 10, ("North", "B"): 20,
                ("South", "B"): 25, ("South", "C"): 25,
            },
        )
        self.assertEqual(open_result.order_states["B1"], "REACHABLE_NOT_SELECTED")

        closed = evaluate(with_north_closed(self.base))
        self.assertEqual(closed.revision, 2)
        self.assertEqual(closed.store_states, {"A": "NO_ROUTE", "B": "REACHABLE", "C": "REACHABLE"})
        self.assertEqual(closed.routes, {("South", "B"): 25, ("South", "C"): 25})
        self.assertEqual(closed.optimal_count, 2)
        self.assertEqual(closed.optimal_plans, {(("South", "C1"), ("South", "C2"))})
        self.assertEqual(closed.order_states["A1"], "NO_ROUTE")
        self.assertEqual(closed.order_states["B1"], "REACHABLE_NOT_SELECTED")

    def test_zero_one_and_all_closed_depots(self) -> None:
        case = copy.deepcopy(self.base)
        case["depots"] = []
        self.assertEqual(evaluate(case).store_states, {"A": "NO_ROUTE", "B": "NO_ROUTE", "C": "NO_ROUTE"})
        self.assertEqual(evaluate(case).optimal_count, 0)
        case["depots"] = [self.base["depots"][0]]
        self.assertEqual(evaluate(case).optimal_count, 1)
        case = copy.deepcopy(self.base)
        for depot in case["depots"]:
            depot["is_open"] = "false"
        self.assertEqual(evaluate(case).optimal_count, 0)
        self.assertFalse(evaluate(case).routes)

    def test_missing_reversed_road_and_late_orders(self) -> None:
        case = copy.deepcopy(self.base)
        case["roads"] = [
            row for row in case["roads"]
            if (row["from_node_id"], row["to_node_id"]) != ("NORTH", "A")
        ]
        case["roads"].append({"from_node_id": "A", "to_node_id": "NORTH", "travel_minutes": "1"})
        self.assertEqual(evaluate(case).store_states["A"], "NO_ROUTE")
        self.assertNotIn(("North", "A"), evaluate(case).routes)
        case = copy.deepcopy(self.base)
        case["orders"][0]["deadline_minutes"] = "9"
        self.assertEqual(evaluate(case).order_states["A1"], "LATE_ONLY")
        self.assertEqual(evaluate(case).optimal_count, 2)

    def test_competing_stock_non_split_and_ties(self) -> None:
        case = copy.deepcopy(self.base)
        case["orders"].append(
            {"order_id": "C3", "store_id": "C", "units": "2", "deadline_minutes": "60"}
        )
        expected = evaluate(case)
        self.assertEqual(expected.optimal_count, 3)
        self.assertEqual(len(expected.optimal_plans), 3)
        case["orders"].append(
            {"order_id": "HUGE", "store_id": "B", "units": "8", "deadline_minutes": "60"}
        )
        self.assertEqual(evaluate(case).order_states["HUGE"], "INSUFFICIENT_STOCK")
        self.assertEqual(evaluate(case).optimal_count, 3)

    def test_source_validation_rejects_invalid_rows(self) -> None:
        bad = copy.deepcopy(self.base)
        bad["roads"][0]["travel_minutes"] = "-1"
        with self.assertRaisesRegex(ValueError, "nonnegative"):
            evaluate(bad)
        bad = copy.deepcopy(self.base)
        bad["orders"][1]["store_id"] = "UNKNOWN"
        with self.assertRaisesRegex(ValueError, "existing store"):
            evaluate(bad)
        bad = copy.deepcopy(self.base)
        bad["demo_state"].append({"revision": "2"})
        with self.assertRaisesRegex(ValueError, "exactly one"):
            evaluate(bad)
        bad = copy.deepcopy(self.base)
        bad["orders"] = [
            {**bad["orders"][index % 4], "order_id": f"ORDER_{index}"}
            for index in range(11)
        ]
        with self.assertRaisesRegex(ValueError, "unbounded"):
            evaluate(bad)

    def test_held_out_generator_is_bounded_reproducible_and_separates_gold(self) -> None:
        cases, key = generate(672, 3)
        self.assertEqual((cases, key), generate(672, 3))
        self.assertEqual(len(cases), 3)
        self.assertNotIn("gold", cases[0])
        self.assertIn("optimal_count", key[0])
        self.assertTrue(all(evaluate(case["sources"]).optimal_count >= 0 for case in cases))
        with self.assertRaises(ValueError):
            generate(672, 101)


class TestModelPackage(unittest.TestCase):
    def test_release_imports_declarations_sources_without_io_or_solve(self) -> None:
        code = """
from unittest.mock import patch
import snowflake.connector
from relationalai.semantics.reasoners.prescriptive import Problem
with patch.object(Problem, 'solve', side_effect=AssertionError('eager solve')), \\
     patch.object(snowflake.connector, 'connect', side_effect=AssertionError('network')):
    from model import model, Depot, Store, Order, sources
    from model.schema import model as schema_model
    assert model is schema_model
    assert model.name == 'retail_delivery_agent'
    assert all(item is not None for item in (Depot, Store, Order))
    assert {t for t in ('DEPOTS', 'STORES', 'ROADS', 'ORDERS', 'DEMO_STATE')} == {
        sources.depots._name, sources.stores._name, sources.roads._name,
        sources.orders._name, sources.state._name,
    }
"""
        result = subprocess.run(
            [sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_pinned_cli_directory_loader_registers_one_model(self) -> None:
        result = subprocess.run(
            [
                sys.executable, "-c",
                "from relationalai.oplog.loader import load_model; "
                "m=load_model('model', None); "
                "assert m.name == 'retail_delivery_agent'; "
                "assert len(m._reasoner_bindings) == 1; "
                "assert m._reasoner_bindings[0].name == 'delivery_plan'",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


class FakeCursor:
    def __init__(self, *, open_: bool = True, revision: int = 1) -> None:
        self.open, self.revision = open_, revision
        self.description = []
        self.rowcount = 0
        self.result = []
        self.calls = []
        self.pending = None
        self.fail_revision = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, query, parameters=()):
        self.calls.append(query)
        if query.startswith("SHOW SCHEMAS"):
            self.description = [("name",), ("comment",)]
            self.result = [("DELIVERY_SOURCES", "rai-retail-delivery-agent-owned:1")]
        elif query.startswith("SELECT DEPOT_ID"):
            self.result = [("North", self.open)]
        elif query.startswith("SELECT REVISION"):
            self.result = [(self.revision,)]
        elif query == "BEGIN":
            self.pending = (self.open, self.revision)
        elif query.startswith("UPDATE") and ".DEPOTS" in query:
            self.rowcount = int(self.open == parameters[2])
            if self.rowcount:
                self.open = parameters[0]
        elif query.startswith("UPDATE") and ".DEMO_STATE" in query:
            self.rowcount = int(self.revision == parameters[0] and not self.fail_revision)
            if self.rowcount:
                self.revision += 1
        elif query == "ROLLBACK":
            self.open, self.revision = self.pending
        elif query.startswith("DROP") or query.startswith("CREATE"):
            raise AssertionError("mutation did not require DDL")
        return self

    def fetchall(self):
        return self.result


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self.fake = cursor

    def cursor(self):
        return self.fake


class TestMutationAndSnapshot(unittest.TestCase):
    def test_close_reopen_repeat_and_failed_revision_rolls_back(self) -> None:
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        self.assertEqual(change_state(connection, "DEMO", "DELIVERY_SOURCES", close=True), 2)
        self.assertFalse(cursor.open)
        with self.assertRaisesRegex(RuntimeError, "already"):
            change_state(connection, "DEMO", "DELIVERY_SOURCES", close=True)
        self.assertEqual(cursor.revision, 2)
        cursor.fail_revision = True
        with self.assertRaisesRegex(RuntimeError, "Revision changed"):
            change_state(connection, "DEMO", "DELIVERY_SOURCES", close=False)
        self.assertEqual((cursor.open, cursor.revision), (False, 2))
        cursor.fail_revision = False
        self.assertEqual(change_state(connection, "DEMO", "DELIVERY_SOURCES", close=False), 3)
        self.assertEqual((cursor.open, cursor.revision), (True, 3))

    def test_loader_fails_on_existing_target_without_inserts(self) -> None:
        cursor = FakeCursor()
        with self.assertRaisesRegex(RuntimeError, "already exists"):
            load_fixture(FakeConnection(cursor), "DEMO", "DELIVERY_SOURCES")
        self.assertFalse(any(q.startswith("INSERT") for q in cursor.calls))
        with self.assertRaisesRegex(ValueError, "unquoted Snowflake identifier"):
            load_fixture(FakeConnection(cursor), "DEMO; DROP DATABASE DEMO", "DELIVERY_SOURCES")
        self.assertFalse(any(q.startswith("DROP") for q in cursor.calls))
        with self.assertRaisesRegex(ValueError, "exact target"):
            teardown(FakeConnection(cursor), "DEMO", "DELIVERY_SOURCES", "OTHER.SCHEMA")
        self.assertFalse(any(q.startswith("DROP") for q in cursor.calls))

    def test_snapshot_rejects_missing_rows_bad_status_and_stale_refresh(self) -> None:
        base = read_fixture()
        snapshot = snapshot_double(base)
        compare_snapshot(snapshot, closed=False)
        bad = copy.deepcopy(snapshot)
        bad["plan_summary"][0]["solver_status"] = "TIME_LIMIT"
        with self.assertRaisesRegex(ValueError, "optimality"):
            compare_snapshot(bad, closed=False)
        bad = copy.deepcopy(snapshot)
        bad["store_route_status"].pop()
        with self.assertRaisesRegex(ValueError, "reachability"):
            compare_snapshot(bad, closed=False)
        bad = copy.deepcopy(snapshot)
        bad["order_decision"][1]["depot_id"] = "South"
        with self.assertRaisesRegex(ValueError, "null"):
            compare_snapshot(bad, closed=False)
        closed = snapshot_double(with_north_closed(base))
        compare_snapshot(closed, closed=True, prior_revision=1)
        with self.assertRaisesRegex(ValueError, "did not advance"):
            compare_snapshot(closed, closed=True, prior_revision=2)
        bad = copy.deepcopy(closed)
        bad["order_decision"][0]["revision"] = 1
        with self.assertRaisesRegex(ValueError, "revision"):
            compare_snapshot(bad, closed=True, prior_revision=1)


if __name__ == "__main__":
    unittest.main()
