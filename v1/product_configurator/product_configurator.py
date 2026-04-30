"""Product Configurator (constraint satisfaction, multi-solution) template.

This script demonstrates a feature-model configuration problem in RelationalAI:

- Load slots, options, requires/excludes rules, and regional availability from CSV.
- For one target region, enumerate every feasible build: which option to
  select in each slot under requires/excludes rules, region-allowed
  options only, and a total-price ceiling.
- Solve as constraint satisfaction with `solution_limit=MAX_CONFIGURATIONS`
  (MiniZinc/Chuffed) and surface every distinct build via
  `Variable.values(solution_index, value)`. A configurator UI rarely
  wants a single build -- a buyer's quote, a sales playbook, and a
  trade-off slider all need the population of feasible configurations.

Modeling approach:
- Option.selected is a binary decision variable, one per option (region-filtered).
- Per-slot exactly-one is sum(Option.selected).per(Slot) == 1.
- Requires (a -> b) becomes selected[a] <= selected[b].
- Excludes (a, b) becomes selected[a] + selected[b] <= 1.
- Prices are integer cents to keep the model purely discrete.

Run:
    `python product_configurator.py`

Output:
    Prints the configurator's solver info, every feasible build (one
    row per selected option per solution) with per-solution total
    price, and post-solve constraint verification.
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

# Runner-level parameters.
# One solve enumerates up to MAX_CONFIGURATIONS feasible builds for one
# region. Change TARGET_REGION and re-run to configure for a different
# market.
TARGET_REGION = "EU"
PRICE_CEILING_CENTS = 2_000_000  # USD 20,000
# Solver solution-limit: cap how many distinct feasible builds to
# enumerate per run. The bundled demo intentionally has a small feasible
# set so the output is readable; production catalogues can be enormous,
# so size accordingly.
MAX_CONFIGURATIONS = 5

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

# Capture the variable subconcept so we can query per-solution values
# via `Variable.values(solution_index, value)` after the solve.
selected_var = problem.solve_for(
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
# `solution_limit=MAX_CONFIGURATIONS` asks the solver to enumerate up to
# that many distinct feasible builds; query each one via
# `Variable.values(idx, val)`. Without it, MiniZinc returns just the
# first feasible build and stops.
problem.solve("minizinc", time_limit_sec=60, solution_limit=MAX_CONFIGURATIONS)
problem.solve_info().display()

# Confirm constraints hold in the returned solution. `verify` inspects
# only the first solution (the populated property), but the constraint
# structure is shared across every solution the solver returns.
problem.verify(exactly_one_ic, requires_ic, excludes_ic, price_ic)
# At least one feasible build must have been found. We do not gate on
# `termination_status`: with `solution_limit`, MiniZinc reports OPTIMAL
# only when search has exhausted the space within the time limit, so
# partial enumeration is the expected mode for large catalogues.
model.require(problem.num_points() >= 1)

# --------------------------------------------------
# Inspect every feasible configuration
# --------------------------------------------------

# `Variable.values(solution_index, value)` indexes the solver's outputs
# across every returned solution. Filtering on `value == 1` surfaces just
# the options the solver picked into each build. The populated property
# (`Option.selected`) reflects only the first solution; for multi-solution
# output we always go through `.values(...)`.

print(
    f"\nFeasible configurations for region {TARGET_REGION!r} "
    f"(ceiling ${PRICE_CEILING_CENTS // 100:,}, up to {MAX_CONFIGURATIONS} per run):"
)
sol_idx = Integer.ref()
val = Integer.ref()
model.select(
    sol_idx.alias("solution"),
    selected_var.option.slot.name.alias("slot"),
    selected_var.option.name.alias("option"),
    selected_var.option.price_cents.alias("price_cents"),
).where(selected_var.values(sol_idx, val), val == 1).inspect()

print("\nTotal price per configuration (cents):")
sol_idx = Integer.ref()
val = Integer.ref()
model.select(
    sol_idx.alias("solution"),
    sum(selected_var.option.price_cents * val).per(sol_idx).alias("total_cents"),
).where(selected_var.values(sol_idx, val)).inspect()
