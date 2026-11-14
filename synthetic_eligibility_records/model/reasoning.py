"""Member-record generation problem: every distinct record the eligibility rules allow."""

from relationalai.semantics import Integer, String
from relationalai.semantics.reasoners.prescriptive import Problem, implies

from .schema import AgeBucket, Plan, Provider, model
from .source import age_buckets_csv, plans_csv, providers_csv

# Senior status (age >= 65) drives the Medicare-Advantage CFD.
SENIOR_THRESHOLD_YEARS = 65
# Solver solution-limit: how many distinct feasible member records to
# enumerate per solve. The bundled reference data admits exactly 8
# feasible records, so a cap above that lets the solver exhaust the search
# and return status OPTIMAL. Production catalogs are larger -- size this
# to the K records your downstream test fixture wants per solve.
MAX_RECORDS = 16

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

# Free decisions: the three categorical slots the solver fills on every
# solution. Each is a scalar `model.Relationship` (one Integer slot) --
# the unparented scalar shape. No singleton Member concept is required
# because there is exactly one member slot; the solver picks values
# for these scalars on every solution. To extend to a fleet of N
# members, reintroduce a `Member` concept and lift each scalar to a
# `model.Property(f"{Member} has {Integer:foo}")`, then scope every IC
# below with `model.where(Member)` (or a tighter filter).
age_bucket_id = model.Relationship(f"{Integer:age_bucket_id}")
plan_id = model.Relationship(f"{Integer:plan_id}")
provider_id = model.Relationship(f"{Integer:provider_id}")

problem = Problem(model, Integer, name="synthetic_eligibility_records")
# All output goes through `Variable.values(sol_idx, value)`, so the
# populated property is unused. `populate=False` skips the first-solution
# write-back to avoid the latent FDError it invites under `solution_limit`.
age_bucket_var = problem.solve_for(
    age_bucket_id,
    type="int",
    name="age_bucket",
    lower=int(age_buckets_csv["id"].min()),
    upper=int(age_buckets_csv["id"].max()),
    populate=False,
)
plan_id_var = problem.solve_for(
    plan_id,
    type="int",
    name="plan_id",
    lower=int(plans_csv["id"].min()),
    upper=int(plans_csv["id"].max()),
    populate=False,
)
provider_id_var = problem.solve_for(
    provider_id,
    type="int",
    name="provider_id",
    lower=int(providers_csv["id"].min()),
    upper=int(providers_csv["id"].max()),
    populate=False,
)

# PCP-network attribution. The chosen provider's network must equal the
# chosen plan's network. Encoded as a forbidden-pair iteration: for every
# (Plan, Provider) pair in *different* networks, if the member picks that
# plan, then the member must not pick that provider.
network_match_ic = model.where(Plan.network_id != Provider.network_id).require(
    implies(plan_id == Plan.id, provider_id != Provider.id)
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
        age_bucket_id == AgeBucket.id,
        plan_id != Plan.id,
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
        age_bucket_id == AgeBucket.id,
        plan_id != Plan.id,
    )
)
problem.satisfy(non_senior_no_medicare_ic)

# --------------------------------------------------
# Solve
# --------------------------------------------------

# Each refresh of the deployed model runs this solve.
# `solution_limit=MAX_RECORDS` asks the solver to enumerate up to that
# many distinct feasible records; query each one via `.values(idx, val)`.
problem.configure("minizinc", time_limit_sec=60, solution_limit=MAX_RECORDS)

# The solve's status and number of solutions, which the deployed model publishes for the queries.
SolveStatus = model.Relationship(f"synthetic eligibility solve status is {String:status}")
NumPoints = model.Relationship(f"synthetic eligibility number of solutions is {Integer:count}")
model.define(SolveStatus(problem.termination_status()), NumPoints(problem.num_points()))
