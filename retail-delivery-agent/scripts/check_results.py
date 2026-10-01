"""Fail-closed comparison of a *real exported snapshot* with the independent oracle.

Snapshot collection/column mapping is an account-gated step, not simulated here.
This validator does not call PyRel's query engine or compute its output.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluation.check_oracle import evaluate, read_fixture
from model import Depot, Order, Store, model

EXPECTED_SECTIONS = {
    "sources",
    "routes",
    "store_route_status",
    "order_decision",
    "plan_summary",
}
ROUTE_COLUMNS = {"depot_id", "store_id", "minutes"}
STORE_COLUMNS = {"store_id", "state", "revision"}
ORDER_COLUMNS = {
    "order_id", "store_id", "units", "deadline_minutes", "state",
    "depot_id", "arrival_minutes", "revision",
}
SUMMARY_COLUMNS = {"id", "revision", "solver_status", "completed_orders"}


def _rows(snapshot: dict, section: str, columns: set[str], key: str | None) -> list[dict]:
    rows = snapshot[section]
    if not isinstance(rows, list) or any(
        not isinstance(row, dict) or set(row) != columns for row in rows
    ):
        raise ValueError(f"{section}: expected rows with exactly {sorted(columns)}")
    if key is not None and len({row[key] for row in rows}) != len(rows):
        raise ValueError(f"{section}: duplicate {key}")
    return rows


def compare_snapshot(snapshot: dict, *, closed: bool, prior_revision: int | None = None) -> None:
    """Compare all observed rows/keys with an independent fixture computation."""
    if set(snapshot) != EXPECTED_SECTIONS:
        raise ValueError(f"Snapshot requires exactly {sorted(EXPECTED_SECTIONS)}")
    if model.name != "retail_delivery_agent" or any(
        item is None for item in (Depot, Store, Order)
    ):
        raise AssertionError("The deployed model package did not load")
    baseline = read_fixture()
    expected_sources = {
        **baseline,
        "depots": [
            {**depot, "is_open": "false" if closed else "true"}
            if depot["depot_id"] == "North" else depot
            for depot in baseline["depots"]
        ],
    }
    actual_sources = snapshot["sources"]
    if not isinstance(actual_sources, dict) or set(actual_sources) != set(expected_sources):
        raise ValueError("Snapshot must include all five source tables")
    revisions = actual_sources["demo_state"]
    if len(revisions) != 1 or set(revisions[0]) != {"revision"}:
        raise ValueError("Source revision must be one row")
    revision = int(revisions[0]["revision"])
    if prior_revision is None and (closed or revision != 1):
        raise ValueError("Initial snapshot must be open at revision 1; supply prior revision after a change")
    if prior_revision is not None and revision <= prior_revision:
        raise ValueError("Source revision did not advance after the earlier refresh")
    expected_sources["demo_state"] = [{"revision": str(revision)}]
    for table, rows in expected_sources.items():
        if sorted(actual_sources[table], key=str) != sorted(rows, key=str):
            raise ValueError(f"Source {table} differs from the approved fixture")
    expected = evaluate(expected_sources)

    routes = _rows(snapshot, "routes", ROUTE_COLUMNS, None)
    actual_routes = {}
    for row in routes:
        pair = row["depot_id"], row["store_id"]
        if pair in actual_routes:
            raise ValueError(f"Duplicate route {pair}")
        actual_routes[pair] = float(row["minutes"])
    if actual_routes != expected.routes:
        raise ValueError(f"Route pairs/times disagree: {actual_routes} != {expected.routes}")

    store_rows = _rows(snapshot, "store_route_status", STORE_COLUMNS, "store_id")
    if {row["store_id"]: row["state"] for row in store_rows} != expected.store_states:
        raise ValueError("Missing, extra, or incorrect store reachability rows")
    if any(int(row["revision"]) != revision for row in store_rows):
        raise ValueError("Store results do not all carry the current source revision")

    summary = _rows(snapshot, "plan_summary", SUMMARY_COLUMNS, "id")
    if len(summary) != 1 or summary[0]["id"] != "current":
        raise ValueError("Expected one PlanSummary row")
    if summary[0]["solver_status"] != "OPTIMAL":
        raise ValueError("Solver did not prove optimality: do not publish a recommendation")
    if (
        int(summary[0]["revision"]) != revision
        or int(summary[0]["completed_orders"]) != expected.optimal_count
    ):
        raise ValueError("PlanSummary count or revision is inconsistent with the sources")

    order_rows = _rows(snapshot, "order_decision", ORDER_COLUMNS, "order_id")
    base_orders = {row["order_id"]: row for row in expected_sources["orders"]}
    if {row["order_id"] for row in order_rows} != set(base_orders):
        raise ValueError("OrderDecision must contain exactly one row for each source order")
    selected = []
    for row in order_rows:
        oid = row["order_id"]
        original = base_orders[oid]
        if (
            int(row["revision"]) != revision
            or row["store_id"] != original["store_id"]
            or int(row["units"]) != int(original["units"])
            or float(row["deadline_minutes"]) != float(original["deadline_minutes"])
        ):
            raise ValueError(f"{oid}: order fields or revision disagree with sources")
        if row["state"] == "SELECTED":
            depot_id = row["depot_id"]
            pair = depot_id, oid
            travel = expected.routes.get((depot_id, row["store_id"]))
            if travel is None or row["arrival_minutes"] is None:
                raise ValueError(f"{oid}: selected order lacks a reachable route/arrival")
            if float(row["arrival_minutes"]) != travel:
                raise ValueError(f"{oid}: arrival differs from shortest directed path")
            selected.append(pair)
        elif row["state"] != (
            "REACHABLE_NOT_SELECTED"
            if expected.order_states[oid] == "OPTIONALLY_SELECTED"
            else expected.order_states[oid]
        ):
            raise ValueError(f"{oid}: incorrect unselected state {row['state']}")
        elif row["depot_id"] is not None or row["arrival_minutes"] is not None:
            raise ValueError(f"{oid}: unselected decision must have null depot/arrival")
    if tuple(sorted(selected)) not in expected.optimal_plans:
        raise ValueError("Selected assignments are not a maximum-count feasible whole-order plan")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True, type=Path, help="Actual Snowflake export in JSON")
    parser.add_argument("--state", required=True, choices=["open", "closed"])
    parser.add_argument("--prior-revision", type=int, help="Require revision newer than prior state")
    args = parser.parse_args()
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    compare_snapshot(snapshot, closed=args.state == "closed", prior_revision=args.prior_revision)
    print(f"Snapshot matches fixture, optimum, and revision ({args.state}).")


if __name__ == "__main__":
    main()
