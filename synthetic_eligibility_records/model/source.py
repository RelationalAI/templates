"""Load and check the reference plans, providers, and age buckets."""

from pathlib import Path

from pandas import read_csv

from .schema import AgeBucket, Plan, Provider, model

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


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


plans_csv = read_csv(DATA_DIR / "plans.csv")
_assert_dense_ids(plans_csv, "plans.csv")
model.define(Plan.new(model.data(plans_csv).to_schema()))

providers_csv = read_csv(DATA_DIR / "providers.csv")
_assert_dense_ids(providers_csv, "providers.csv")
model.define(Provider.new(model.data(providers_csv).to_schema()))

_warn_orphan_networks(plans_csv, providers_csv)

age_buckets_csv = read_csv(DATA_DIR / "age_buckets.csv")
_assert_dense_ids(age_buckets_csv, "age_buckets.csv")
model.define(AgeBucket.new(model.data(age_buckets_csv).to_schema()))
