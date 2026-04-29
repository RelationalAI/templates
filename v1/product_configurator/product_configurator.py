"""Product Configurator (constraint satisfaction) template.

This script demonstrates a feature-model configuration problem in RelationalAI:

- Load slots, options, requires/excludes rules, and regional availability from CSV.
- For one target region, decide which option to select in each slot.
- Enforce: exactly one option per slot, requires/excludes rules,
  region-allowed options only, and a total-price ceiling.
- Solve as constraint satisfaction (MiniZinc / Chuffed) and inspect the chosen build.

Modeling approach:
- Option.selected is a binary decision variable, one per option (region-filtered).
- Per-slot exactly-one is sum(Option.selected).per(Slot) == 1.
- Requires (a -> b) becomes selected[a] <= selected[b].
- Excludes (a, b) becomes selected[a] + selected[b] <= 1.
- Prices are integer cents to keep the model purely discrete.

Run:
    `python product_configurator.py`

Output:
    Prints the configurator's solver info, the chosen option per slot,
    the total price in cents, and post-solve constraint verification.
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

# Runner-level parameters.
# One solve = one configuration for one region. Change TARGET_REGION and re-run
# to configure for a different market.
TARGET_REGION = "EU"
PRICE_CEILING_CENTS = 2_000_000  # USD 20,000

model = Model("product_configurator")

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Concept: slots (engine, transmission, trim, sound, wheels, roof)
Slot = model.Concept("Slot", identify_by={"id": Integer})
Slot.name = model.Property(f"{Slot} has {String:name}")
slots_csv = read_csv(data_dir / "slots.csv")
model.define(Slot.new(model.data(slots_csv).to_schema()))

# Concept: options (one row per choice within a slot, price in integer cents)
Option = model.Concept("Option", identify_by={"id": Integer})
Option.name = model.Property(f"{Option} has {String:name}")
Option.price_cents = model.Property(f"{Option} has {Integer:price_cents}")
Option.slot = model.Relationship(f"{Option} is in {Slot}")
Option.allowed_in = model.Relationship(f"{Option} is allowed in {String:region}")

options_csv = read_csv(data_dir / "options.csv")
options_data = model.data(options_csv)
model.define(
    o := Option.new(id=options_data.id),
    o.name(options_data.name),
    o.price_cents(options_data.price_cents),
)
model.define(Option.slot(Slot)).where(
    Option.id(options_data.id),
    Slot.id(options_data.slot_id),
)

# Regional availability: an option is allowed in a region iff a row is present.
regional_csv = read_csv(data_dir / "regional_rules.csv")
regional_data = model.data(regional_csv)
model.define(Option.allowed_in(regional_data.region)).where(
    Option.id(regional_data.option_id),
)

# Concept: requires rule (option_a requires option_b -- if a is selected, b must be too)
Requires = model.Concept(
    "Requires",
    identify_by={"option_a_id": Integer, "option_b_id": Integer},
)
requires_csv = read_csv(data_dir / "requires.csv")
model.define(Requires.new(model.data(requires_csv).to_schema()))

# Concept: excludes rule (at most one of option_a / option_b may be selected)
Excludes = model.Concept(
    "Excludes",
    identify_by={"option_a_id": Integer, "option_b_id": Integer},
)
excludes_csv = read_csv(data_dir / "excludes.csv")
model.define(Excludes.new(model.data(excludes_csv).to_schema()))

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

# Decision variable: Option.selected (binary, only over region-allowed options)
Option.selected = model.Property(f"{Option} is selected if {Integer:selected}")

problem = Problem(model, Integer)

problem.solve_for(
    Option.selected,
    type="bin",
    name=["selected", Option.name],
    where=[Option.allowed_in(TARGET_REGION)],
)

# Constraint: exactly one option per slot, over the region-filtered domain.
exactly_one_ic = model.where(
    Option.allowed_in(TARGET_REGION),
    Option.slot(Slot),
).require(sum(Option.selected).per(Slot) == 1)
problem.satisfy(exactly_one_ic)

# Constraint: requires -- if option A is selected, option B must be selected.
A = Option.ref()
B = Option.ref()
requires_ic = model.where(
    R := Requires,
    A.id(R.option_a_id),
    B.id(R.option_b_id),
    A.allowed_in(TARGET_REGION),
    B.allowed_in(TARGET_REGION),
).require(A.selected <= B.selected)
problem.satisfy(requires_ic)

# Constraint: excludes -- at most one of options A and B may be selected.
excludes_ic = model.where(
    E := Excludes,
    A.id(E.option_a_id),
    B.id(E.option_b_id),
    A.allowed_in(TARGET_REGION),
    B.allowed_in(TARGET_REGION),
).require(A.selected + B.selected <= 1)
problem.satisfy(excludes_ic)

# Constraint: total price (cents) of selected options must not exceed ceiling.
price_ic = model.where(
    Option.allowed_in(TARGET_REGION),
).require(sum(Option.price_cents * Option.selected) <= PRICE_CEILING_CENTS)
problem.satisfy(price_ic)

# --------------------------------------------------
# Solve and verify
# --------------------------------------------------

problem.display()
problem.solve("minizinc", time_limit_sec=60)
problem.solve_info().display()

# Confirm constraints hold in the solver's solution.
problem.verify(exactly_one_ic, requires_ic, excludes_ic, price_ic)

# Note on termination-status gating: this is a pure satisfaction problem,
# so MiniZinc/Chuffed returns a feasibility status rather than "OPTIMAL".
# After confirming the exact status string from solve_info().display() above,
# add e.g. model.require(problem.termination_status() == "FEASIBLE") to gate.

# --------------------------------------------------
# Inspect the chosen configuration
# --------------------------------------------------

print(
    f"\nSelected configuration for region {TARGET_REGION!r} "
    f"(ceiling ${PRICE_CEILING_CENTS // 100:,}):"
)
sel = Integer.ref()
model.select(
    Slot.name.alias("slot"),
    Option.name.alias("option"),
    Option.price_cents.alias("price_cents"),
).where(
    Option.selected(sel),
    sel == 1,
    Option.slot(Slot),
).inspect()

print("\nTotal price (cents):")
model.select(
    sum(Option.price_cents * Option.selected).alias("total_cents"),
).inspect()
