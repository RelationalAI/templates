"""Item report: reads the deployed starter model.

Run after `rai models deploy --path model`:
    python -m queries.item_report

Prints a small table containing the bundled example item.
"""

from model import Item, model


def inspect_items():
    """Select the items loaded by the model package."""
    item = Item.ref()
    return model.select(item.id, item.name)


def main() -> None:
    print(inspect_items().to_df())


if __name__ == "__main__":
    main()
