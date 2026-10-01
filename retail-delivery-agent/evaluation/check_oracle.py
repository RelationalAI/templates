"""Independent, bounded fixture oracle; does not import PyRel or model code."""

from __future__ import annotations

import csv
import heapq
import itertools
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_ORDERS = 10
MAX_DEPOTS = 4
MAX_ASSIGNMENTS = 100_000


@dataclass(frozen=True)
class Expected:
    revision: int
    routes: dict[tuple[str, str], float]
    store_states: dict[str, str]
    order_states: dict[str, str]
    optimal_count: int
    optimal_plans: frozenset[tuple[tuple[str, str], ...]]


def read_fixture(directory: Path = ROOT / "data") -> dict[str, list[dict[str, str]]]:
    """Read only the five expected local CSVs; reject empty or malformed files."""
    sources = {}
    for name, required in {
        "depots": {"depot_id", "node_id", "is_open", "stock_units"},
        "stores": {"store_id", "node_id"},
        "roads": {"from_node_id", "to_node_id", "travel_minutes"},
        "orders": {"order_id", "store_id", "units", "deadline_minutes"},
        "demo_state": {"revision"},
    }.items():
        with (directory / f"{name}.csv").open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames is None or set(reader.fieldnames) != required:
                raise ValueError(f"{name}: expected columns {sorted(required)}")
            rows = list(reader)
            if not rows or any(
                value is None or value == "" for row in rows for value in row.values()
            ):
                raise ValueError(f"{name}: empty or incomplete rows")
            sources[name] = rows
    validate_sources(sources)
    return sources


def validate_sources(sources: dict[str, list[dict[str, str]]]) -> None:
    """Validate identifiers, foreign keys and nonnegative inputs before loading."""
    required = {"depots", "stores", "roads", "orders", "demo_state"}
    if set(sources) != required:
        raise ValueError(f"Expected exactly five source tables: {sorted(required)}")
    if len(sources["demo_state"]) != 1 or int(sources["demo_state"][0]["revision"]) < 1:
        raise ValueError("DEMO_STATE must have exactly one positive revision")
    for name, key in (("depots", "depot_id"), ("stores", "store_id"), ("orders", "order_id")):
        values = [row[key] for row in sources[name]]
        if len(set(values)) != len(values):
            raise ValueError(f"{name}: duplicate {key}")
    depot_nodes = [row["node_id"] for row in sources["depots"]]
    store_nodes = [row["node_id"] for row in sources["stores"]]
    if len(set(depot_nodes + store_nodes)) != len(depot_nodes + store_nodes):
        raise ValueError("Depot and store node IDs must be unique")
    stores = {row["store_id"] for row in sources["stores"]}
    roads = set()
    for row in sources["roads"]:
        pair = (row["from_node_id"], row["to_node_id"])
        if pair in roads or float(row["travel_minutes"]) < 0:
            raise ValueError("Roads must be unique and have nonnegative weights")
        roads.add(pair)
    for row in sources["depots"]:
        if row["is_open"].lower() not in {"true", "false"} or int(row["stock_units"]) < 0:
            raise ValueError("Depots need boolean availability and nonnegative stock")
    for row in sources["orders"]:
        if (
            row["store_id"] not in stores
            or int(row["units"]) <= 0
            or float(row["deadline_minutes"]) < 0
        ):
            raise ValueError("Orders need an existing store, positive units, and a deadline")


def shortest_paths(start: str, roads: list[dict[str, str]]) -> dict[str, float]:
    """Dijkstra over directed, nonnegative roads; source code is independent of PyRel."""
    edges: dict[str, list[tuple[float, str]]] = {}
    for road in roads:
        edges.setdefault(road["from_node_id"], []).append(
            (float(road["travel_minutes"]), road["to_node_id"])
        )
    distances = {start: 0.0}
    pending = [(0.0, start)]
    while pending:
        minutes, node = heapq.heappop(pending)
        if minutes > distances[node]:
            continue
        for travel, neighbor in edges.get(node, []):
            candidate = minutes + travel
            if candidate < distances.get(neighbor, float("inf")):
                distances[neighbor] = candidate
                heapq.heappush(pending, (candidate, neighbor))
    return distances


def evaluate(sources: dict[str, list[dict[str, str]]]) -> Expected:
    """Enumerate all whole-order assignments; reject cases beyond the declared bound."""
    validate_sources(sources)
    depots = [row for row in sources["depots"] if row["is_open"].lower() == "true"]
    stores = {row["store_id"]: row["node_id"] for row in sources["stores"]}
    orders = sorted(sources["orders"], key=lambda row: row["order_id"])
    if len(orders) > MAX_ORDERS or len(depots) > MAX_DEPOTS:
        raise ValueError("Optimal-count grading is unbounded for this case; mark it ungraded")
    distances = {
        depot["depot_id"]: shortest_paths(depot["node_id"], sources["roads"])
        for depot in depots
    }
    routes = {
        (depot["depot_id"], store_id): distances[depot["depot_id"]][node]
        for depot in depots
        for store_id, node in stores.items()
        if node in distances[depot["depot_id"]]
    }
    store_states = {
        store_id: (
            "REACHABLE" if any((depot["depot_id"], store_id) in routes for depot in depots)
            else "NO_ROUTE"
        )
        for store_id in stores
    }
    candidates: dict[str, list[str]] = {}
    order_states = {}
    for order in orders:
        oid, sid = order["order_id"], order["store_id"]
        reachable = [depot for depot in depots if (depot["depot_id"], sid) in routes]
        on_time = [
            depot for depot in reachable
            if routes[depot["depot_id"], sid] <= float(order["deadline_minutes"])
        ]
        candidates[oid] = [
            depot["depot_id"] for depot in on_time
            if int(depot["stock_units"]) >= int(order["units"])
        ]
        order_states[oid] = (
            "NO_ROUTE" if not reachable else
            "LATE_ONLY" if not on_time else
            "INSUFFICIENT_STOCK" if not candidates[oid] else
            "REACHABLE_NOT_SELECTED"
        )
    combinations = 1
    for order in orders:
        combinations *= 1 + len(candidates[order["order_id"]])
    if combinations > MAX_ASSIGNMENTS:
        raise ValueError("Oracle search exceeds 100,000 plans; mark optimal-count grading ungraded")
    stock = {depot["depot_id"]: int(depot["stock_units"]) for depot in depots}
    best = -1
    plans: set[tuple[tuple[str, str], ...]] = set()
    for choice in itertools.product(*([None, *candidates[row["order_id"]]] for row in orders)):
        assignments = tuple(
            (depot_id, order["order_id"])
            for order, depot_id in zip(orders, choice, strict=True)
            if depot_id is not None
        )
        assignments = tuple(sorted(assignments))
        used = {
            depot_id: sum(
                int(order["units"])
                for order, chosen in zip(orders, choice, strict=True)
                if chosen == depot_id
            )
            for depot_id in stock
        }
        if any(used[depot_id] > available for depot_id, available in stock.items()):
            continue
        if len(assignments) > best:
            best, plans = len(assignments), {assignments}
        elif len(assignments) == best:
            plans.add(assignments)
    if best < 0:
        raise AssertionError("The empty assignment must always be feasible")
    for order in orders:
        order_id = order["order_id"]
        if all(any(oid == order_id for _, oid in plan) for plan in plans):
            order_states[order_id] = "SELECTED"
        elif any(any(oid == order_id for _, oid in plan) for plan in plans):
            order_states[order_id] = "OPTIONALLY_SELECTED"
    return Expected(
        revision=int(sources["demo_state"][0]["revision"]),
        routes=routes,
        store_states=store_states,
        order_states=order_states,
        optimal_count=best,
        optimal_plans=frozenset(plans),
    )


if __name__ == "__main__":
    baseline = read_fixture()
    for name, case in (
        ("open", baseline),
        (
            "closed",
            {
                **baseline,
                "depots": [
                    {**depot, "is_open": "false"} if depot["depot_id"] == "North" else depot
                    for depot in baseline["depots"]
                ],
                "demo_state": [{"revision": "2"}],
            },
        ),
    ):
        expected = evaluate(case)
        print(
            f"{name}: revision={expected.revision}; "
            f"unreachable={sorted(k for k, v in expected.store_states.items() if v == 'NO_ROUTE')}; "
            f"maximum complete orders={expected.optimal_count}"
        )
