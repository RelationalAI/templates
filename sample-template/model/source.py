"""Source mappings for the starter template."""

from .schema import Item, model


def load_sample_data() -> None:
    """Load a minimal in-memory record into the shared model."""
    model.define(Item.new(id=1, name="Example item"))


load_sample_data()
