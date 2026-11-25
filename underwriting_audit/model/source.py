"""Load the age-bucket and coverage-band reference data into the underwriting_audit model."""

from pathlib import Path

from pandas import read_csv

from .schema import AgeBucket, CoverageBand, model

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# --------------------------------------------------
# Reference data
# --------------------------------------------------


# Reference-data contract: integer `id` columns must be dense and
# contiguous so the solver's `lower=min(id), upper=max(id)` decision
# bounds line up exactly with the reference rows. Sparse IDs would let
# the solver pick a missing value: the relational-time `implies(...)`
# ICs gated on the matching reference row would never fire, leaving the
# indicator decisions unconstrained for that solution.
def _assert_dense_ids(df, name):
    ids = sorted(int(v) for v in df["id"].tolist())
    if not ids:
        raise ValueError(f"{name} has no rows; at least one reference row is required.")
    expected = list(range(ids[0], ids[-1] + 1))
    if ids != expected:
        missing = sorted(set(expected) - set(ids))
        raise ValueError(
            f"{name} `id` column must be dense and contiguous integers; "
            f"missing ids {missing} between {ids[0]} and {ids[-1]}."
        )


age_buckets_csv = read_csv(DATA_DIR / "age_buckets.csv")
_assert_dense_ids(age_buckets_csv, "age_buckets.csv")
model.define(AgeBucket.new(model.data(age_buckets_csv).to_schema()))

coverage_bands_csv = read_csv(DATA_DIR / "coverage_bands.csv")
_assert_dense_ids(coverage_bands_csv, "coverage_bands.csv")
model.define(CoverageBand.new(model.data(coverage_bands_csv).to_schema()))
