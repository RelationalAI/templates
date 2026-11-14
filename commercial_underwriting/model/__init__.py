"""Commercial Underwriting (rules-based reasoning) template.

This model declares a rules-based underwriting workflow in RelationalAI
on a four-level commercial property/casualty hierarchy:

InsuredEntity -> Policy -> Location -> Coverage

- Load sample CSVs describing insured entities, policies, locations, and
  coverages.
- Define declarative rules as derived Relationships using `define()` + `where()`:
  - Eligibility flags at the entity level (restricted industry, insufficient
    history) and the location level (old construction, poor fire protection,
    high-risk occupancy).
  - Building-coverage adequacy flag (insurance-to-value < 80%).
- Roll those flags up into entity-level decline and marginal indicators.
- Classify each insured entity into a risk tier (Decline / NonStandard /
  Standard / Preferred) using mutually exclusive subtype concepts.

The whole pipeline is declarative — there are no procedural rule chains.
PyRel resolves dependencies automatically.

Run:
    `rai models deploy --path model` deploys this model to the schema in
    raiconfig.yaml and waits for its first refresh; `python -m
    queries.underwriting_report` then prints the report from the deployed model.
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Float, Integer, Model, String

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# Eligibility thresholds (typical commercial-lines underwriting guardrails).
MIN_YEARS_IN_BUSINESS = 3       # below this -> insufficient history -> decline
MAX_FP_CLASS_FOR_ELIGIBILITY = 6  # ISO Public Protection Class 1=best, 10=worst
MIN_YEAR_BUILT = 1950             # construction older than this -> decline
ITV_THRESHOLD = 0.80              # building coverage limit must reach 80% of replacement value

# Industry classifications.
RESTRICTED_INDUSTRIES = ("CANNABIS", "NUCLEAR", "EXPLOSIVES", "ASBESTOS_REMEDIATION")
MARGINAL_INDUSTRIES = ("MANUFACTURING_HEAVY", "AUTO_REPAIR")
HIGH_RISK_OCCUPANCIES = ("GAS_STATION", "CANNABIS_RETAIL", "RESTAURANT_FAST_FOOD", "HABITATIONAL")

# Preferred-tier criteria.
PREFERRED_MIN_YEARS = 15          # must have at least this many years in business
PREFERRED_MAX_FP_CLASS = 3        # all locations must be at FP class 3 or better

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

model = Model("commercial_underwriting")

# InsuredEntity concept: the named insured business at the top of the hierarchy.
InsuredEntity = model.Concept("InsuredEntity", identify_by={"id": Integer})
InsuredEntity.name = model.Property(f"{InsuredEntity} has {String:name}")
InsuredEntity.industry_code = model.Property(f"{InsuredEntity} has {String:industry_code}")
InsuredEntity.years_in_business = model.Property(f"{InsuredEntity} has {Integer:years_in_business}")
InsuredEntity.annual_revenue = model.Property(f"{InsuredEntity} has {Float:annual_revenue}")

# Load insured entities from CSV.
ie_csv = read_csv(DATA_DIR / "insured_entities.csv")
model.define(InsuredEntity.new(model.data(ie_csv).to_schema()))

# Policy concept: a commercial property/casualty policy bound to one insured entity.
Policy = model.Concept("Policy", identify_by={"id": Integer})
Policy.insured_entity = model.Relationship(f"{Policy} bound to {InsuredEntity}")
Policy.policy_type = model.Property(f"{Policy} has {String:policy_type}")
Policy.effective_date = model.Property(f"{Policy} has {String:effective_date}")
Policy.total_premium = model.Property(f"{Policy} has {Float:total_premium}")

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

# Location concept: a physical location/building scheduled on a policy.
Location = model.Concept("Location", identify_by={"id": Integer})
Location.policy = model.Relationship(f"{Location} scheduled on {Policy}")
Location.address = model.Property(f"{Location} at {String:address}")
Location.occupancy_class = model.Property(f"{Location} has {String:occupancy_class}")
Location.year_built = model.Property(f"{Location} has {Integer:year_built}")
Location.square_feet = model.Property(f"{Location} has {Integer:square_feet}")
Location.fire_protection_class = model.Property(f"{Location} has {Integer:fire_protection_class}")
Location.replacement_value = model.Property(f"{Location} has {Float:replacement_value}")

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

# Coverage concept: a coverage line scheduled on a location.
Coverage = model.Concept("Coverage", identify_by={"id": Integer})
Coverage.location = model.Relationship(f"{Coverage} scheduled on {Location}")
Coverage.coverage_type = model.Property(f"{Coverage} has {String:coverage_type}")
Coverage.coverage_limit = model.Property(f"{Coverage} has {Float:coverage_limit}")
Coverage.deductible = model.Property(f"{Coverage} has {Float:deductible}")

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

# --------------------------------------------------
# Stage 1: location- and coverage-level eligibility flags
# --------------------------------------------------

# Rule (eligibility flag): a location has poor fire protection if its ISO
# Public Protection Class exceeds the eligibility ceiling.
Location.has_poor_fire_protection = model.Relationship(
    f"{Location} has poor fire protection"
)
model.where(
    Location.fire_protection_class > MAX_FP_CLASS_FOR_ELIGIBILITY,
).define(Location.has_poor_fire_protection())

# Rule (eligibility flag): a location has old construction if its build year
# predates the eligibility floor.
Location.has_old_construction = model.Relationship(f"{Location} has old construction")
model.where(
    Location.year_built < MIN_YEAR_BUILT,
).define(Location.has_old_construction())

# Rule (marginal flag): a location has a high-risk occupancy class.
Location.has_high_risk_occupancy = model.Relationship(
    f"{Location} has high-risk occupancy"
)
for occ in HIGH_RISK_OCCUPANCIES:
    model.where(Location.occupancy_class == occ).define(
        Location.has_high_risk_occupancy()
    )

# Rule (marginal flag): a building coverage is underinsured if its limit is
# below the insurance-to-value (ITV) threshold of the location's replacement
# value. Only applies to BUILDING coverages.
Coverage.is_underinsured = model.Relationship(f"{Coverage} is underinsured")
model.where(
    Coverage.coverage_type == "BUILDING",
    Coverage.coverage_limit < ITV_THRESHOLD * Coverage.location.replacement_value,
).define(Coverage.is_underinsured())

# --------------------------------------------------
# Stage 2: roll flags up to insured-entity decline and marginal indicators
# --------------------------------------------------

# Rule (decline factor): restricted industry.
InsuredEntity.has_restricted_industry = model.Relationship(
    f"{InsuredEntity} has restricted industry"
)
for industry in RESTRICTED_INDUSTRIES:
    model.where(InsuredEntity.industry_code == industry).define(
        InsuredEntity.has_restricted_industry()
    )

# Rule (decline factor): insufficient operating history.
InsuredEntity.has_insufficient_history = model.Relationship(
    f"{InsuredEntity} has insufficient history"
)
model.where(
    InsuredEntity.years_in_business < MIN_YEARS_IN_BUSINESS,
).define(InsuredEntity.has_insufficient_history())

# Rule (decline factor): any scheduled location has poor fire protection.
InsuredEntity.has_unprotected_location = model.Relationship(
    f"{InsuredEntity} has unprotected location"
)
model.where(
    Policy.insured_entity(InsuredEntity),
    Location.policy(Policy),
    Location.has_poor_fire_protection(),
).define(InsuredEntity.has_unprotected_location())

# Rule (decline factor): any scheduled location has old construction.
InsuredEntity.has_old_construction_location = model.Relationship(
    f"{InsuredEntity} has old construction location"
)
model.where(
    Policy.insured_entity(InsuredEntity),
    Location.policy(Policy),
    Location.has_old_construction(),
).define(InsuredEntity.has_old_construction_location())

# Rule (rollup): any decline factor.
InsuredEntity.has_decline_factor = model.Relationship(
    f"{InsuredEntity} has any decline factor"
)
model.where(InsuredEntity.has_restricted_industry()).define(
    InsuredEntity.has_decline_factor()
)
model.where(InsuredEntity.has_insufficient_history()).define(
    InsuredEntity.has_decline_factor()
)
model.where(InsuredEntity.has_unprotected_location()).define(
    InsuredEntity.has_decline_factor()
)
model.where(InsuredEntity.has_old_construction_location()).define(
    InsuredEntity.has_decline_factor()
)

# Rule (marginal factor): industry on the marginal-but-acceptable list.
InsuredEntity.has_marginal_industry = model.Relationship(
    f"{InsuredEntity} has marginal industry"
)
for industry in MARGINAL_INDUSTRIES:
    model.where(InsuredEntity.industry_code == industry).define(
        InsuredEntity.has_marginal_industry()
    )

# Rule (marginal factor): any scheduled location has a high-risk occupancy.
InsuredEntity.has_high_risk_occupancy_location = model.Relationship(
    f"{InsuredEntity} has high-risk occupancy location"
)
model.where(
    Policy.insured_entity(InsuredEntity),
    Location.policy(Policy),
    Location.has_high_risk_occupancy(),
).define(InsuredEntity.has_high_risk_occupancy_location())

# Rule (marginal factor): any building coverage is underinsured.
InsuredEntity.has_underinsured_coverage = model.Relationship(
    f"{InsuredEntity} has underinsured coverage"
)
model.where(
    Policy.insured_entity(InsuredEntity),
    Location.policy(Policy),
    Coverage.location(Location),
    Coverage.is_underinsured(),
).define(InsuredEntity.has_underinsured_coverage())

# Rule (rollup): any marginal factor.
InsuredEntity.has_marginal_factor = model.Relationship(
    f"{InsuredEntity} has any marginal factor"
)
model.where(InsuredEntity.has_marginal_industry()).define(
    InsuredEntity.has_marginal_factor()
)
model.where(InsuredEntity.has_high_risk_occupancy_location()).define(
    InsuredEntity.has_marginal_factor()
)
model.where(InsuredEntity.has_underinsured_coverage()).define(
    InsuredEntity.has_marginal_factor()
)

# --------------------------------------------------
# Stage 3: risk-tier classification (mutually exclusive subtypes)
# --------------------------------------------------
# An InsuredEntity always falls into exactly one of these four tiers.
# Conditions are written so the four sets partition the InsuredEntity set.

RiskTier_Decline = model.Concept("RiskTier_Decline", extends=[InsuredEntity])
RiskTier_NonStandard = model.Concept("RiskTier_NonStandard", extends=[InsuredEntity])
RiskTier_Standard = model.Concept("RiskTier_Standard", extends=[InsuredEntity])
RiskTier_Preferred = model.Concept("RiskTier_Preferred", extends=[InsuredEntity])

# Decline: any decline factor.
model.where(
    InsuredEntity.has_decline_factor(),
).define(RiskTier_Decline(InsuredEntity))

# NonStandard: no decline factor AND has at least one marginal factor.
model.where(
    model.not_(InsuredEntity.has_decline_factor()),
    InsuredEntity.has_marginal_factor(),
).define(RiskTier_NonStandard(InsuredEntity))

# Preferred eligibility: no decline factor, no marginal factor, long history,
# and every scheduled location at FP class <= PREFERRED_MAX_FP_CLASS.
# Encoded as: NOT (entity has any location whose FP class exceeds the cap).
InsuredEntity.has_non_preferred_location = model.Relationship(
    f"{InsuredEntity} has non-preferred location"
)
model.where(
    Policy.insured_entity(InsuredEntity),
    Location.policy(Policy),
    Location.fire_protection_class > PREFERRED_MAX_FP_CLASS,
).define(InsuredEntity.has_non_preferred_location())

# Preferred: meets all preferred criteria.
model.where(
    model.not_(InsuredEntity.has_decline_factor()),
    model.not_(InsuredEntity.has_marginal_factor()),
    model.not_(InsuredEntity.has_non_preferred_location()),
    InsuredEntity.years_in_business >= PREFERRED_MIN_YEARS,
).define(RiskTier_Preferred(InsuredEntity))

# Standard: not Decline, not NonStandard, not Preferred (the residual).
model.where(
    model.not_(InsuredEntity.has_decline_factor()),
    model.not_(InsuredEntity.has_marginal_factor()),
    model.not_(RiskTier_Preferred(InsuredEntity)),
).define(RiskTier_Standard(InsuredEntity))
