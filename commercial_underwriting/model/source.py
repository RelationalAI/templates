"""Load the sample insured entities, policies, locations, and coverages into the underwriting model."""

from pathlib import Path

from pandas import read_csv

from .schema import Coverage, InsuredEntity, Location, Policy, model

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# Load insured entities from CSV.
ie_csv = read_csv(DATA_DIR / "insured_entities.csv")
model.define(InsuredEntity.new(model.data(ie_csv).to_schema()))

# Load policies from CSV and bind each to its insured entity.
policy_csv = read_csv(DATA_DIR / "policies.csv")
policy_data = model.data(policy_csv)
model.define(
    p := Policy.new(id=policy_data.id),
    p.insured_entity(InsuredEntity.lookup(id=policy_data.insured_entity_id)),
    p.policy_type(policy_data.policy_type),
    p.effective_date(policy_data.effective_date),
    p.total_premium(policy_data.total_premium),
)

# Load locations from CSV.
loc_csv = read_csv(DATA_DIR / "locations.csv")
loc_data = model.data(loc_csv)
model.define(
    loc := Location.new(id=loc_data.id),
    loc.policy(Policy.lookup(id=loc_data.policy_id)),
    loc.address(loc_data.address),
    loc.occupancy_class(loc_data.occupancy_class),
    loc.year_built(loc_data.year_built),
    loc.square_feet(loc_data.square_feet),
    loc.fire_protection_class(loc_data.fire_protection_class),
    loc.replacement_value(loc_data.replacement_value),
)

# Load coverages from CSV.
cov_csv = read_csv(DATA_DIR / "coverages.csv")
cov_data = model.data(cov_csv)
model.define(
    cov := Coverage.new(id=cov_data.id),
    cov.location(Location.lookup(id=cov_data.location_id)),
    cov.coverage_type(cov_data.coverage_type),
    cov.coverage_limit(cov_data.coverage_limit),
    cov.deductible(cov_data.deductible),
)
