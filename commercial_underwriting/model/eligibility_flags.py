"""Location- and coverage-level eligibility flags: fire protection, construction age, occupancy,
and insurance-to-value adequacy of building coverages."""

from relationalai.semantics import Float

from .schema import Coverage, Location, model

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

# Eligibility thresholds (typical commercial-lines underwriting guardrails).
MAX_FP_CLASS_FOR_ELIGIBILITY = 6  # ISO Public Protection Class 1=best, 10=worst
MIN_YEAR_BUILT = 1950             # construction older than this -> decline
ITV_THRESHOLD = 0.80              # building coverage limit must reach 80% of replacement value

HIGH_RISK_OCCUPANCIES = ("GAS_STATION", "CANNABIS_RETAIL", "RESTAURANT_FAST_FOOD", "HABITATIONAL")

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

# Insurance to value (ITV) of a BUILDING coverage, as the report shows it: its
# limit as a fraction of the location's replacement value.
Coverage.insurance_to_value = model.Property(f"{Coverage} has {Float:insurance_to_value}")
model.where(
    Coverage.coverage_type == "BUILDING",
    Coverage.location.replacement_value > 0,
).define(
    Coverage.insurance_to_value(Coverage.coverage_limit / Coverage.location.replacement_value)
)
