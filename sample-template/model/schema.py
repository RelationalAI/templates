"""Stable schema declarations for the starter template."""

from relationalai.semantics import Integer, Model, String

model = Model("Template", use_lqp=False)

Item = model.Concept("Item", identify_by={"id": Integer})
Item.name = model.Property(f"{Item} has {String:name}")
