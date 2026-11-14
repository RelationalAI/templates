"""Starter RelationalAI template.

This script demonstrates the standard template package layout:

- Declare stable concepts in model/schema.py.
- Load base facts in model/source.py.
- Keep queries, reasoning, solves, and reporting in the runner.

Run:
    `python template.py` deploys the model to the schema in raiconfig.yaml, waits
    for its first refresh, and prints the item from the deployed model.

Output:
    A small table containing the bundled example item.
"""

from model import Item, model


def inspect_items():
    """Select the items loaded by the model package."""
    item = Item.ref()
    return model.select(item.id, item.name)


def main() -> None:
    # Deploy and wait for the first refresh.
    model.deploy()

    print(inspect_items().to_df())


if __name__ == "__main__":
    main()
