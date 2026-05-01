"""Synthetic Eligibility Records (constrained generation, multi-solution) template.

Generate K distinct, internally consistent member eligibility records per
solve. Each record is a tuple of three categorical decisions (age bucket,
plan, primary care provider) that satisfies CMS Medicare-eligibility,
age-by-plan-type cascading functional dependencies, and PCP-network
attribution. Solve as constraint satisfaction with `solution_limit=K`
(MiniZinc) and enumerate every feasible record via
`Variable.values(solution_index, value)` -- synthetic-data tooling consumers
(test-data generation, claim-engine fuzzing, RegTech rules certification)
want a batch of records per solve, not one.

Run:
    `python synthetic_eligibility_records.py`

Output:
    Prints the formulation, the solver's status block, and every generated
    member record (one row per solution). Prints a no-records diagnostic
    when the reference data is over-constrained.
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Integer, Model, String
from relationalai.semantics.reasoners.prescriptive import Problem, implies

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

# Senior status (age >= 65) drives the Medicare-Advantage CFD.
SENIOR_THRESHOLD_YEARS = 65
# Solver solution-limit: how many distinct feasible member records to
# enumerate per solve. The bundled reference data admits exactly 8
# feasible records, so a cap above that lets the solver exhaust the search
# and return status OPTIMAL. Production catalogs are larger -- size this
# to the K records your downstream test fixture wants per solve.
MAX_RECORDS = 16

DATA_DIR = Path(__file__).parent / "data"

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

model = Model("synthetic_eligibility_records")


# Reference-data IDs must be dense and contiguous so the solver's
# `lower=min(id), upper=max(id)` decision bounds line up with the rows
# the implies ICs iterate over. See the README troubleshooting block.
def _assert_dense_ids(df, name):
    ids = sorted(int(v) for v in df["id"].tolist())
    if not ids:
        raise ValueError(
            f"{name} has no rows; at least one row is required to set the "
            "decision-variable bounds (`lower=min(id), upper=max(id)`)."
        )
    expected = list(range(ids[0], ids[-1] + 1))
    if ids != expected:
        raise ValueError(
            f"{name} `id` column must be dense and contiguous; got {ids}. "
            "Renumber the rows or add explicit ID-membership ICs before solving."
        )


# Plan concept: an insurance plan offering. `max_dependents` is an optional
# extension hook -- the bundled rules don't use it, but declaring it here
# lets the dependent-count extension in `## Customize this template`
# reference `Plan.max_dependents` directly.
Plan = model.Concept("Plan", identify_by={"id": Integer})
Plan.plan_type = model.Property(f"{Plan} has {String:plan_type}")
Plan.network_id = model.Property(f"{Plan} has {Integer:network_id}")
Plan.max_dependents = model.Property(f"{Plan} has {Integer:max_dependents}")
plans_csv = read_csv(DATA_DIR / "plans.csv")
_assert_dense_ids(plans_csv, "plans.csv")
model.define(Plan.new(model.data(plans_csv).to_schema()))

# Provider concept: a primary-care provider in exactly one network.
Provider = model.Concept("Provider", identify_by={"id": Integer})
Provider.name = model.Property(f"{Provider} has {String:name}")
Provider.network_id = model.Property(f"{Provider} has {Integer:network_id}")
providers_csv = read_csv(DATA_DIR / "providers.csv")
_assert_dense_ids(providers_csv, "providers.csv")
model.define(Provider.new(model.data(providers_csv).to_schema()))

# Pre-solve coverage warnings: a plan whose network has zero providers
# (or a provider whose network has zero plans) is locally unreachable but
# leaves the model globally feasible, so warn rather than raise.


def _warn_orphan_networks(plans_csv, providers_csv):
    plan_networks = {int(v) for v in plans_csv["network_id"].tolist()}
    provider_networks = {int(v) for v in providers_csv["network_id"].tolist()}
    orphan_plans = sorted(plan_networks - provider_networks)
    if orphan_plans:
        print(
            f"Warning: plan network(s) {orphan_plans} have no providers in "
            "providers.csv; plans on those networks are unreachable and will "
            "never appear in generated records."
        )
    orphan_providers = sorted(provider_networks - plan_networks)
    if orphan_providers:
        print(
            f"Warning: provider network(s) {orphan_providers} have no plans in "
            "plans.csv; providers in those networks are unreachable and will "
            "never appear in generated records."
        )


_warn_orphan_networks(plans_csv, providers_csv)

# AgeBucket concept: representative age (years) keyed by integer bucket id.
# Four buckets span the adult/senior split (two under 65, two at or above).
# Categorical age keeps every decision domain compact and similar in size,
# so solver enumeration produces structurally diverse records across all
# three slots; a per-year age would let the solver shift birth year by one
# across solutions and defeat batch diversity.
AgeBucket = model.Concept("AgeBucket", identify_by={"id": Integer})
AgeBucket.age_years = model.Property(f"{AgeBucket} has {Integer:age_years}")
age_buckets_csv = read_csv(DATA_DIR / "age_buckets.csv")
_assert_dense_ids(age_buckets_csv, "age_buckets.csv")
model.define(AgeBucket.new(model.data(age_buckets_csv).to_schema()))

# Member concept: one singleton placeholder. The solver enumerates K
# feasible fillings of this member's three decision slots (age bucket,
# plan, provider); each filling = one synthetic record.
Member = model.Concept("Member", identify_by={"id": Integer})
model.define(Member.new(id=1))

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

Member.age_bucket_id = model.Property(f"{Member} in age bucket {Integer:age_bucket_id}")
Member.plan_id = model.Property(f"{Member} on plan {Integer:plan_id}")
Member.provider_id = model.Property(f"{Member} sees provider {Integer:provider_id}")

problem = Problem(model, Integer)
# All output goes through `Variable.values(sol_idx, value)`, so the
# populated property is unused. `populate=False` skips the first-solution
# write-back to avoid the latent FDError it invites under `solution_limit`.
age_bucket_var = problem.solve_for(
    Member.age_bucket_id,
    type="int",
    name=["age_bucket", Member.id],
    lower=int(age_buckets_csv["id"].min()),
    upper=int(age_buckets_csv["id"].max()),
    populate=False,
)
plan_id_var = problem.solve_for(
    Member.plan_id,
    type="int",
    name=["plan_id", Member.id],
    lower=int(plans_csv["id"].min()),
    upper=int(plans_csv["id"].max()),
    populate=False,
)
provider_id_var = problem.solve_for(
    Member.provider_id,
    type="int",
    name=["provider_id", Member.id],
    lower=int(providers_csv["id"].min()),
    upper=int(providers_csv["id"].max()),
    populate=False,
)

# --------------------------------------------------
# Constraints
# --------------------------------------------------

# PCP-network attribution. The chosen provider's network must equal the
# chosen plan's network. Encoded as a forbidden-pair iteration: for every
# (Plan, Provider) pair in *different* networks, if the member picks that
# plan, then the member must not pick that provider.
network_match_ic = model.where(Plan.network_id != Provider.network_id).require(
    implies(Member.plan_id == Plan.id, Member.provider_id != Provider.id)
)
problem.satisfy(network_match_ic)

# Medicare-Advantage CFD (senior arm). If the chosen age bucket represents
# a senior (age_years >= 65), the chosen plan must be Medicare-Advantage.
# Encoded as: for every (senior bucket, non-Medicare plan) pair in
# reference data, forbid the (member age_bucket, member plan) combination.
senior_must_medicare_ic = model.where(
    Plan.plan_type != "MedicareAdvantage",
    AgeBucket.age_years >= SENIOR_THRESHOLD_YEARS,
).require(
    implies(
        Member.age_bucket_id == AgeBucket.id,
        Member.plan_id != Plan.id,
    )
)
problem.satisfy(senior_must_medicare_ic)

# Medicare-Advantage CFD (non-senior arm). If the chosen age bucket
# represents a non-senior (age_years < 65), the chosen plan must NOT be
# Medicare-Advantage. Encoded as: for every (non-senior bucket, Medicare
# plan) pair, forbid the combination.
non_senior_no_medicare_ic = model.where(
    Plan.plan_type == "MedicareAdvantage",
    AgeBucket.age_years < SENIOR_THRESHOLD_YEARS,
).require(
    implies(
        Member.age_bucket_id == AgeBucket.id,
        Member.plan_id != Plan.id,
    )
)
problem.satisfy(non_senior_no_medicare_ic)

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

problem.display()
# `solution_limit=MAX_RECORDS` asks the solver to enumerate up to that
# many distinct feasible records; query each one via `.values(idx, val)`.
problem.solve("minizinc", time_limit_sec=60, solution_limit=MAX_RECORDS)
si = problem.solve_info()
si.display()

# No `problem.verify(...)` call: every IC here is implies-bodied, which is
# solver-only -- verify() would return silently-OK without re-evaluating.
# The invariants are visible by eye in the table below: every row prints
# `age_years` next to `plan_type` (CFD check) and `plan_network` next to
# `provider_network` (network-attribution check).
if si.num_points is None or si.num_points == 0:
    print(
        "\nThe solver returned no eligibility records. See the printed solve status "
        "above and the troubleshooting section in the README for likely causes "
        "(over-constrained reference data, mismatched plan/provider networks, or "
        "the search budget expired before a record was found)."
    )

# --------------------------------------------------
# Inspect every generated member record
# --------------------------------------------------

# `Variable.values(sol_idx, value)` indexes the solver's outputs across
# every returned solution; binding the value slot to a reference Concept's
# `.id` walks the chosen ID back to that record's columns in one step.

sol_idx = Integer.ref()
records_df = (
    model.select(
        sol_idx.alias("solution"),
        AgeBucket.age_years.alias("age_years"),
        Plan.plan_type.alias("plan_type"),
        Plan.network_id.alias("plan_network"),
        Provider.network_id.alias("provider_network"),
        Provider.name.alias("provider"),
    )
    .where(
        age_bucket_var.values(sol_idx, AgeBucket.id),
        plan_id_var.values(sol_idx, Plan.id),
        provider_id_var.values(sol_idx, Provider.id),
    )
    .to_df()
    .sort_values("solution")
    .reset_index(drop=True)
)
print(f"\nGenerated member records (up to {MAX_RECORDS} per run):")
print(records_df.to_string(index=False))
