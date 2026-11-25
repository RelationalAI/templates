"""Build enumeration: every feasible build of the product for the target region, and the price of each."""

from relationalai.semantics import Integer, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

from .schema import Excludes, Implies, Option, Slot, model
from .source import TARGET_REGION

PRICE_CEILING_CENTS = 2_000_000  # USD 20,000

# Solver solution-limit: cap how many distinct feasible builds to enumerate
# per run. The bundled demo's feasible set fits under this cap so the solver
# returns the full population with status OPTIMAL. Size this down on a
# production catalog and the solver returns SOLUTION_LIMIT when it's hit.
MAX_CONFIGURATIONS = 100

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

# Decision variable: Option.selected (binary, only over region-allowed options)
Option.selected = model.Property(f"{Option} is selected if {Integer:selected}")

problem = Problem(model, Integer, name="product_configurator")

# `populate=True` (default) writes the first solution back into Option.selected;
# multi-solution output goes through `selected_var.values(sol_idx, ...)`
# regardless.
#
# `where=[Option.allowed_in(TARGET_REGION)]` filters the decision domain so
# banned options never get a decision variable at all. The ICs below re-assert
# the region filter so they stay correctly scoped if you later parameterize
# this model over multiple regions in one solve.
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
# Solve
# --------------------------------------------------

# Each refresh of the deployed model runs this solve.
# `solution_limit=MAX_CONFIGURATIONS` asks the solver to enumerate up to that
# many distinct feasible builds; `.values(sol_idx, val)` reads each one.
problem.configure("minizinc", time_limit_sec=60, solution_limit=MAX_CONFIGURATIONS)

# The solve's status and number of solutions, which the deployed model publishes for the queries.
SolveStatus = model.Relationship(f"product configurator solve status is {String:status}")
NumPoints = model.Relationship(f"product configurator number of solutions is {Integer:count}")
model.define(SolveStatus(problem.termination_status()), NumPoints(problem.num_points()))

# The region, price ceiling, and solution cap the solve ran with, which the deployed model
# publishes so the report labels the deployed builds with the settings that produced them.
SolveSettings = model.Relationship(
    f"product configurator solves region {String:region} under {Integer:price_ceiling_cents} "
    f"cents for up to {Integer:max_configurations} builds"
)
model.define(SolveSettings(TARGET_REGION, PRICE_CEILING_CENTS, MAX_CONFIGURATIONS))

# The solutions, which the deployed model publishes for the queries: the options each
# solution selects.
solution = Integer.ref()
SelectedOption = model.Relationship(
    f"product configurator solution {Integer:solution} selects {Option:option}"
)
model.where(selected_var.values(solution, 1)).define(SelectedOption(solution, selected_var.option))

# --------------------------------------------------
# Price each build
# --------------------------------------------------

# The price of each build: the sum of its selected options' prices, in cents.
BuildTotal = model.Relationship(
    f"product configurator solution {Integer:solution} costs {Integer:total_cents} cents"
)
_in_build, _priced = Option.ref(), Option.ref()
model.where(SelectedOption(solution, _in_build)).define(
    BuildTotal(
        solution,
        sum(_priced, _priced.price_cents).per(solution).where(SelectedOption(solution, _priced)),
    )
)
