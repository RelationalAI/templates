"""Synthetic Eligibility Records (constrained generative model, multi-solution) template.

This script demonstrates synthetic-data generation for healthcare payer / RegTech:

- Generate K distinct, internally consistent member eligibility records per
  solve. Each record is a tuple of three categorical decisions (age bucket,
  plan, primary care provider) that satisfies CMS Medicare-eligibility,
  age-by-plan-type cascading functional dependencies, and PCP-network
  attribution.
- Solve as constraint satisfaction with `solution_limit=K` (MiniZinc) and
  enumerate every feasible record via `Variable.values(solution_index, value)`.
  Synthetic-data tooling consumers (test-data generation, claim-engine
  fuzzing, RegTech rules certification) want a *batch* of records per solve,
  not one -- multi-solution is the right return shape.
- Age is encoded as a categorical decision (`age_bucket_id`) over a small
  reference table of representative ages rather than a per-year integer.
  Categorical age (combined with categorical plan and provider) keeps every
  decision domain compact and similar in size, so MiniZinc's search produces
  structurally diverse records across age, plan, and network -- a per-year
  age decision would let the solver enumerate K solutions that shift birth
  year by one and pin plan and provider, defeating batch diversity.

Run:
    `python synthetic_eligibility_records.py`

Output:
    Prints the formulation, the solver's status block, and every generated
    member record (one row per solution) with chosen age bucket, plan, and
    provider. Prints a no-records diagnostic when the reference data is
    over-constrained.
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Integer, Model, String
from relationalai.semantics.reasoners.prescriptive import Problem, implies

# Runner-level parameters.
# Senior status (age >= 65) drives the Medicare-Advantage CFD.
SENIOR_THRESHOLD_YEARS = 65
# Solver solution-limit: how many distinct feasible member records to
# enumerate per solve. The bundled reference data admits exactly 8
# feasible records under the encoded rules, so a cap above that lets the
# solver exhaust the search space and return status OPTIMAL with a
# stable set across runs. Production catalogs are much larger; size this
# down to the K records your downstream test fixture wants per solve and
# the solver returns SOLUTION_LIMIT once the cap is hit.
MAX_RECORDS = 16

model = Model("synthetic_eligibility_records")

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"


# Reference-data contract: integer IDs must be dense and contiguous so the
# solver's `lower=min(id), upper=max(id)` decision bounds line up exactly
# with the reference rows. Sparse IDs would let the solver pick a value
# with no matching reference row -- the relational-time `implies(...)` ICs
# gated on the matching row would never fire, and the post-solve display
# join would silently drop the record. Validate up front.
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


# Concept: insurance plan (reference data; one row per plan offering).
# Network determines which providers are in-network. `max_dependents` is
# loaded from the CSV but unused by the bundled rules -- declared here as
# a hook so the dependent-count extension shown in `## Customize` can
# reference `Plan.max_dependents` directly via a ref.
Plan = model.Concept("Plan", identify_by={"id": Integer})
Plan.plan_type = model.Property(f"{Plan} has {String:plan_type}")
Plan.network_id = model.Property(f"{Plan} has {Integer:network_id}")
Plan.max_dependents = model.Property(f"{Plan} has {Integer:max_dependents}")
plans_csv = read_csv(data_dir / "plans.csv")
_assert_dense_ids(plans_csv, "plans.csv")
model.define(Plan.new(model.data(plans_csv).to_schema()))

# Concept: primary care provider (reference data; one row per provider).
# Each provider belongs to exactly one network.
Provider = model.Concept("Provider", identify_by={"id": Integer})
Provider.name = model.Property(f"{Provider} has {String:name}")
Provider.network_id = model.Property(f"{Provider} has {Integer:network_id}")
providers_csv = read_csv(data_dir / "providers.csv")
_assert_dense_ids(providers_csv, "providers.csv")
model.define(Provider.new(model.data(providers_csv).to_schema()))

# Pre-solve coverage warnings. The PCP-network-attribution IC forbids
# cross-network (plan, provider) combinations, so a plan whose network has
# zero providers can never appear in a feasible record (the IC forbids
# every provider for it), and a provider whose network has zero plans is
# also unreachable. Neither case makes the model globally infeasible --
# other plans/providers on covered networks still admit feasible records --
# so warn rather than raise, and let the solver surface a 0-record result
# only if every plan ends up unreachable.
plan_networks = set(int(v) for v in plans_csv["network_id"].tolist())
provider_networks = set(int(v) for v in providers_csv["network_id"].tolist())
orphan_plan_networks = sorted(plan_networks - provider_networks)
if orphan_plan_networks:
    print(
        f"Warning: plan network(s) {orphan_plan_networks} have no providers "
        "in providers.csv; plans on those networks are unreachable and will "
        "never appear in generated records."
    )
orphan_provider_networks = sorted(provider_networks - plan_networks)
if orphan_provider_networks:
    print(
        f"Warning: provider network(s) {orphan_provider_networks} have no plans "
        "in plans.csv; providers in those networks are unreachable and will "
        "never appear in generated records."
    )

# Concept: representative age bucket. Each row maps an integer bucket id
# to a representative age (in years) used to drive the CFDs and to
# annotate the generated record. Four buckets span the adult/senior
# split: two under 65, two at or above. Solver enumeration over a
# small categorical age domain produces structurally diverse records;
# a per-year age decision would let the solver shift birth year by one
# across solutions and defeat batch diversity.
AgeBucket = model.Concept("AgeBucket", identify_by={"id": Integer})
AgeBucket.age_years = model.Property(f"{AgeBucket} has {Integer:age_years}")
age_buckets_csv = read_csv(data_dir / "age_buckets.csv")
_assert_dense_ids(age_buckets_csv, "age_buckets.csv")
model.define(AgeBucket.new(model.data(age_buckets_csv).to_schema()))

# Concept: synthesized member. There is no member CSV -- the ontology
# defines a single placeholder member directly via `Member.new(id=1)`.
# Every decision-valued property below describes that one slot, and each
# solution returned by the solver is a different feasible filling of it
# -- which is what gives us K records per solve.
Member = model.Concept("Member", identify_by={"id": Integer})
model.define(Member.new(id=1))

# --------------------------------------------------
# Decision-valued properties on Member
# --------------------------------------------------

Member.age_bucket_id = model.Property(f"{Member} in age bucket {Integer:age_bucket_id}")
Member.plan_id = model.Property(f"{Member} on plan {Integer:plan_id}")
Member.provider_id = model.Property(f"{Member} sees provider {Integer:provider_id}")

problem = Problem(model, Integer)
# Every output goes through `Variable.values(solution_index, value)` against
# the captured ProblemVariable handles, so the populated property path is
# unused. `populate=False` skips the first-solution write-back -- avoiding
# wasted work and the latent FDError that `populate=True` invites when
# MiniZinc returns multiple solutions via `solution_limit`.
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
P = Plan.ref()
PR = Provider.ref()
network_match_ic = model.where(P.network_id != PR.network_id).require(
    implies(Member.plan_id == P.id, Member.provider_id != PR.id)
)
problem.satisfy(network_match_ic)

# Medicare-Advantage CFD (senior arm). If the chosen age bucket represents
# a senior (age_years >= 65), the chosen plan must be Medicare-Advantage.
# Encoded as: for every (senior bucket, non-Medicare plan) pair in
# reference data, forbid the (member age_bucket, member plan) combination.
P = Plan.ref()
AB = AgeBucket.ref()
senior_must_medicare_ic = model.where(
    P.plan_type != "MedicareAdvantage",
    AB.age_years >= SENIOR_THRESHOLD_YEARS,
).require(
    implies(
        Member.age_bucket_id == AB.id,
        Member.plan_id != P.id,
    )
)
problem.satisfy(senior_must_medicare_ic)

# Medicare-Advantage CFD (non-senior arm). If the chosen age bucket
# represents a non-senior (age_years < 65), the chosen plan must NOT be
# Medicare-Advantage. Encoded as: for every (non-senior bucket, Medicare
# plan) pair, forbid the combination.
P = Plan.ref()
AB = AgeBucket.ref()
non_senior_no_medicare_ic = model.where(
    P.plan_type == "MedicareAdvantage",
    AB.age_years < SENIOR_THRESHOLD_YEARS,
).require(
    implies(
        Member.age_bucket_id == AB.id,
        Member.plan_id != P.id,
    )
)
problem.satisfy(non_senior_no_medicare_ic)

# --------------------------------------------------
# Solve and verify
# --------------------------------------------------

problem.display()
# `solution_limit=MAX_RECORDS` asks the solver to enumerate up to that
# many distinct feasible records; query each one via
# `Variable.values(idx, val)`. Without it, MiniZinc returns just the
# first feasible record and stops.
problem.solve("minizinc", time_limit_sec=60, solution_limit=MAX_RECORDS)
si = problem.solve_info()
si.display()

# Every IC in this model is `implies`-bodied (the two CFDs and the
# network-attribution forbidden-pair encoding) -- these are solver-only.
# The relational engine cannot re-evaluate them: passing implies-bodied
# ICs to `problem.verify()` returns silently-OK without actually
# checking them, so the convention is that they must NOT be passed.
# The CFD and network-attribution invariants are visible directly in
# the inspection output below: every record prints `age_years` next to
# `plan_type` (CFD check) and `plan_network` next to `provider_network`
# (network-attribution check) so a reader can verify by eye.
if si.num_points is None or si.num_points == 0:
    print(
        "\nNo feasible eligibility records under the encoded rules. "
        "Check the troubleshooting section in the README for likely causes "
        "(over-constrained reference data, mismatched plan/provider networks, "
        "or all age buckets on one side of the senior threshold)."
    )

# --------------------------------------------------
# Inspect every generated member record
# --------------------------------------------------

# `Variable.values(solution_index, value)` indexes the solver's outputs
# across every returned solution. Joining the three decision variables
# on a shared solution index reconstructs each record. Reference-data
# refs (`bucket_ref`, `plan_ref`, `provider_ref`) walk the chosen IDs
# back to their reference rows for display. The populated property
# reflects only the first solution; for multi-solution output we always
# go through `.values(...)`.

sol_idx = Integer.ref()
ab_v = Integer.ref()
pid_v = Integer.ref()
prv_v = Integer.ref()
bucket_ref = AgeBucket.ref()
plan_ref = Plan.ref()
provider_ref = Provider.ref()
records_df = (
    model.select(
        sol_idx.alias("solution"),
        bucket_ref.age_years.alias("age_years"),
        plan_ref.plan_type.alias("plan_type"),
        plan_ref.network_id.alias("plan_network"),
        provider_ref.network_id.alias("provider_network"),
        provider_ref.name.alias("provider"),
    )
    .where(
        age_bucket_var.values(sol_idx, ab_v),
        plan_id_var.values(sol_idx, pid_v),
        provider_id_var.values(sol_idx, prv_v),
        bucket_ref.id == ab_v,
        plan_ref.id == pid_v,
        provider_ref.id == prv_v,
    )
    .to_df()
    .sort_values("solution")
    .reset_index(drop=True)
)
print(f"\nGenerated member records (up to {MAX_RECORDS} per run):")
print(records_df.to_string(index=False))
