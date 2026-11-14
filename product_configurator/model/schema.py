"""Semantic schema for the product configurator template: slots, options, and feature rules."""

from relationalai.semantics import Integer, Model, String

model = Model("product_configurator")

# Slot concept: a configurable position (engine, transmission, trim, sound,
# wheels, roof). Each option belongs to exactly one slot.
Slot = model.Concept("Slot", identify_by={"id": Integer})
Slot.name = model.Property(f"{Slot} has {String:name}")

# Option concept: one choice within a slot, priced in integer cents.
Option = model.Concept("Option", identify_by={"id": Integer})
Option.name = model.Property(f"{Option} has {String:name}")
Option.price_cents = model.Property(f"{Option} has {Integer:price_cents}")
Option.slot = model.Property(f"{Option} is in {Slot:slot}")
Option.allowed_in = model.Relationship(f"{Option} is allowed in {String:region}")

# Implies concept: directional rule head -> tail. Note the contrast: `Implies`
# is rule *data* (a Concept holding the rule rows), `model.require(...)` is the
# *constraint method* that enforces them. `head_id`/`tail_id` avoid PyRel's
# "potential relationship typo" warning on similar key names.
Implies = model.Concept(
    "Implies",
    identify_by={"head_id": Integer, "tail_id": Integer},
)

# Excludes concept: symmetric rule -- at most one of left, right selected.
Excludes = model.Concept(
    "Excludes",
    identify_by={"left_id": Integer, "right_id": Integer},
)
