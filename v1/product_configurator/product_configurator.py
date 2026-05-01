"""Product Configurator (constraint satisfaction, multi-solution) template.

For one target region, enumerate every feasible build of a configurable
product: pick one option per slot subject to implies/excludes feature-model
rules, regional regulations, and a total-price ceiling. Solve as constraint
satisfaction with `solution_limit=MAX_CONFIGURATIONS` (MiniZinc/Chuffed)
and surface every distinct build via `Variable.values(solution_index, value)`
-- a configurator UI rarely wants a single build; a buyer's quote, a sales
playbook, and a trade-off slider all need the population of configurations.

Run:
    `python product_configurator.py`

Output:
    Prints the configurator's solver info and every feasible build as a
    pivot table (one row per build, one column per slot, sorted ascending
    by total price).
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

TARGET_REGION = "EU"
PRICE_CEILING_CENTS = 2_000_000  # USD 20,000
# Solver solution-limit: cap how many distinct feasible builds to enumerate
# per run. The bundled demo's feasible set fits under this cap so the solver
# returns the full population with status OPTIMAL. Size this down on a
# production catalog and the solver returns SOLUTION_LIMIT when it's hit.
MAX_CONFIGURATIONS = 100

DATA_DIR = Path(__file__).parent / "data"

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

model = Model("product_configurator")

# Slot concept: a configurable position (engine, transmission, trim, sound,
# wheels, roof). Each option belongs to exactly one slot.
Slot = model.Concept("Slot", identify_by={"id": Integer})
Slot.name = model.Property(f"{Slot} has {String:name}")
slots_csv = read_csv(DATA_DIR / "slots.csv")
model.define(Slot.new(model.data(slots_csv).to_schema()))

# Option concept: one choice within a slot, priced in integer cents.
Option = model.Concept("Option", identify_by={"id": Integer})
Option.name = model.Property(f"{Option} has {String:name}")
Option.price_cents = model.Property(f"{Option} has {Integer:price_cents}")
Option.slot = model.Property(f"{Option} is in {Slot:slot}")
Option.allowed_in = model.Relationship(f"{Option} is allowed in {String:region}")

options_csv = read_csv(DATA_DIR / "options.csv")
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
regional_csv = read_csv(DATA_DIR / "regional_rules.csv")
regional_data = model.data(regional_csv)
model.define(Option.allowed_in(regional_data.region)).where(
    Option.id(regional_data.option_id),
)

# Implies concept: directional rule head -> tail. Named `Implies` (not
# `Requires`) to stay distinct from `model.require(...)`. `head_id`/`tail_id`
# avoid PyRel's "potential relationship typo" warning on similar key names.
Implies = model.Concept(
    "Implies",
    identify_by={"head_id": Integer, "tail_id": Integer},
)
implies_csv = read_csv(DATA_DIR / "implies.csv")
model.define(Implies.new(model.data(implies_csv).to_schema()))

# Excludes concept: symmetric rule -- at most one of left, right selected.
Excludes = model.Concept(
    "Excludes",
    identify_by={"left_id": Integer, "right_id": Integer},
)
excludes_csv = read_csv(DATA_DIR / "excludes.csv")
model.define(Excludes.new(model.data(excludes_csv).to_schema()))

# --------------------------------------------------
# Validate the regional catalog against TARGET_REGION
# --------------------------------------------------

# The constraint families below are scoped via
# `model.where(Option.allowed_in(TARGET_REGION), ...)`, which silently drops
# any IC whose options are not all region-allowed. See the README
# troubleshooting blocks for the two failure modes this guards against.
target_allowed_option_ids = set(
    int(r["option_id"]) for _, r in regional_csv.iterrows() if r["region"] == TARGET_REGION
)
slot_to_allowed_options: dict[int, list[int]] = {}
for _, r in options_csv.iterrows():
    if int(r["id"]) in target_allowed_option_ids:
        slot_to_allowed_options.setdefault(int(r["slot_id"]), []).append(int(r["id"]))
slots_missing_options = [
    int(r["id"]) for _, r in slots_csv.iterrows() if int(r["id"]) not in slot_to_allowed_options
]
if slots_missing_options:
    slot_names = {int(r["id"]): r["name"] for _, r in slots_csv.iterrows()}
    missing_names = [slot_names[s] for s in slots_missing_options]
    raise ValueError(
        f"No options are allowed in region {TARGET_REGION!r} for slot(s) "
        f"{missing_names}. The exactly-one IC will not bind on those slots; "
        "every slot must have at least one region-allowed option."
    )

dangling_implies = []
for _, r in implies_csv.iterrows():
    a_id, b_id = int(r["head_id"]), int(r["tail_id"])
    if a_id in target_allowed_option_ids and b_id not in target_allowed_option_ids:
        dangling_implies.append((a_id, b_id))
if dangling_implies:
    option_names = {int(r["id"]): r["name"] for _, r in options_csv.iterrows()}
    rendered = ", ".join(
        f"{option_names[a]} -> {option_names[b]}" for a, b in dangling_implies
    )
    raise ValueError(
        f"Region {TARGET_REGION!r} has implies rules whose target option is "
        f"not allowed in the region: {rendered}. The implies IC will not bind "
        "on these rules; ban the head option in the region or allow the "
        "tail option."
    )

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

# Decision variable: Option.selected (binary, only over region-allowed options)
Option.selected = model.Property(f"{Option} is selected if {Integer:selected}")

problem = Problem(model, Integer)

# `populate=True` (default) writes the first solution back into Option.selected
# so problem.verify(...) can re-evaluate ICs against it; multi-solution output
# below goes through `selected_var.values(sol_idx, ...)` regardless.
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

# Constraint: implies -- if option A (head) is selected, option B (tail) must be selected.
A = Option.ref()
B = Option.ref()
implies_ic = model.where(
    R := Implies,
    A.id(R.head_id),
    B.id(R.tail_id),
    A.allowed_in(TARGET_REGION),
    B.allowed_in(TARGET_REGION),
).require(A.selected <= B.selected)
problem.satisfy(implies_ic)

# Constraint: excludes -- at most one of options A (left) and B (right) may be selected.
excludes_ic = model.where(
    E := Excludes,
    A.id(E.left_id),
    B.id(E.right_id),
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
# Solve and check solution
# --------------------------------------------------

problem.display()
# `solution_limit=MAX_CONFIGURATIONS` asks the solver to enumerate up to that
# many distinct feasible builds; query each one via `.values(sol_idx, val)`.
problem.solve("minizinc", time_limit_sec=60, solution_limit=MAX_CONFIGURATIONS)
si = problem.solve_info()
si.display()

# `verify` re-evaluates each named IC against the populated property (the
# first solution). The model itself enforces the ICs across every solution.
problem.verify(exactly_one_ic, implies_ic, excludes_ic, price_ic)

if si.num_points is None or si.num_points == 0:
    print(
        f"\nNo feasible build for region {TARGET_REGION!r} under the encoded "
        "constraints. See the README troubleshooting section for likely causes."
    )
else:
    # ----------------------------------------------
    # Inspect every feasible configuration
    # ----------------------------------------------

    # `selected_var.values(sol_idx, 1)` indexes the per-solution outputs and
    # filters to the options the solver picked. Pivot to one row per build,
    # one column per slot, sorted ascending by total dollars.
    sol_idx = Integer.ref()
    selections_df = (
        model.select(
            sol_idx.alias("solution"),
            selected_var.option.slot.name.alias("slot"),
            selected_var.option.name.alias("option"),
            selected_var.option.price_cents.alias("price_cents"),
        )
        .where(selected_var.values(sol_idx, 1))
        .to_df()
        .astype({"solution": "int64", "price_cents": "int64"})
    )
    build_view = selections_df.pivot(index="solution", columns="slot", values="option")
    build_view["total_$"] = (
        selections_df.groupby("solution")["price_cents"].sum() // 100
    )
    build_view = build_view.sort_values("total_$").reset_index()
    build_view.columns.name = None
    print(
        f"\nFeasible builds for region {TARGET_REGION!r} "
        f"(ceiling ${PRICE_CEILING_CENTS // 100:,}, up to {MAX_CONFIGURATIONS} per run):"
    )
    print(build_view.to_string(index=False))
