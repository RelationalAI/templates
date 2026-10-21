"""Local smoke test for telco agent query functions."""

from relationalai.semantics import Model

from queries import build_tool_registry


def main() -> None:
    model = Model("Telco Network Recovery Agent Query Smoke")
    registry = build_tool_registry(model)
    for tool in registry._tools:
        queries = getattr(tool, "_queries", None)
        if queries is None:
            continue
        for query_info in queries._queries.values():
            query = query_info["f"]
            print(f"\n== {query.__name__}")
            result = query()
            print(result.head(10).to_string(index=False) if hasattr(result, "head") else result)


if __name__ == "__main__":
    main()
