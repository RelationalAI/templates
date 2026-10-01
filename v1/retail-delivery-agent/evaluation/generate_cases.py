"""Generate bounded held-out synthetic cases; no agent input includes the gold key."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from evaluation.check_oracle import evaluate


def generate(seed: int, count: int = 12) -> tuple[list[dict], list[dict]]:
    if not 1 <= count <= 100:
        raise ValueError("Generate 1..100 bounded cases")
    rng = random.Random(seed)
    cases, gold = [], []
    for index in range(count):
        depots = [
            {
                "depot_id": f"D{depot}",
                "node_id": f"D{depot}",
                "is_open": "true" if depot == 0 or rng.randrange(4) else "false",
                "stock_units": str(rng.randrange(1, 7)),
            }
            for depot in range(3)
        ]
        stores = [{"store_id": f"S{i}", "node_id": f"S{i}"} for i in range(4)]
        roads = []
        for source in ["D0", "D1", "D2", "HUB"]:
            for target in ["HUB", "S0", "S1", "S2", "S3"]:
                if source != target and rng.randrange(3):
                    roads.append(
                        {
                            "from_node_id": source, "to_node_id": target,
                            "travel_minutes": str(rng.randrange(2, 31)),
                        }
                    )
        orders = [
            {
                "order_id": f"O{i}",
                "store_id": f"S{rng.randrange(4)}",
                "units": str(rng.randrange(1, 5)),
                "deadline_minutes": str(rng.randrange(5, 45)),
            }
            for i in range(6)
        ]
        sources = {
            "depots": depots, "stores": stores, "roads": roads,
            "orders": orders, "demo_state": [{"revision": "1"}],
        }
        expected = evaluate(sources)
        case_id = f"synthetic-{seed}-{index:03d}"
        cases.append({"case_id": case_id, "sources": sources})
        gold.append(
            {
                "case_id": case_id,
                "store_states": expected.store_states,
                "optimal_count": expected.optimal_count,
                "optimal_plans": [
                    [list(pair) for pair in plan] for plan in sorted(expected.optimal_plans)
                ],
            }
        )
    return cases, gold


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=27631)
    parser.add_argument("--count", type=int, default=12)
    parser.add_argument("--cases-output", type=Path, required=True)
    parser.add_argument("--gold-output", type=Path, required=True)
    args = parser.parse_args()
    if (
        args.cases_output == args.gold_output
        or args.cases_output.exists()
        or args.gold_output.exists()
    ):
        raise FileExistsError("Use distinct unused paths; refusing to overwrite case data or gold")
    cases, gold = generate(args.seed, args.count)
    args.cases_output.write_text(json.dumps(cases, indent=2) + "\n")
    args.gold_output.write_text(json.dumps(gold, indent=2) + "\n")
    print(f"Wrote {args.count} cases and a separate gold key. Keep gold away from agents.")


if __name__ == "__main__":
    main()
