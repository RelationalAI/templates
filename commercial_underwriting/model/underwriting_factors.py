"""Insured-entity underwriting factors: entity-level decline and marginal flags, the location and
coverage flags rolled up to the insured, and the any-decline and any-marginal rollups."""

# Declares the location and coverage flags rolled up here.
from . import eligibility_flags  # noqa: F401
from .schema import Coverage, InsuredEntity, Location, Policy, model

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

MIN_YEARS_IN_BUSINESS = 3       # below this -> insufficient history -> decline

# Industry classifications.
RESTRICTED_INDUSTRIES = ("CANNABIS", "NUCLEAR", "EXPLOSIVES", "ASBESTOS_REMEDIATION")
MARGINAL_INDUSTRIES = ("MANUFACTURING_HEAVY", "AUTO_REPAIR")

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
