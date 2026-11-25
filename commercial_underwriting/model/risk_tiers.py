"""Risk tiers: the four mutually exclusive tier subtypes of an insured, each insured's tier label,
and the premium each tier carries."""

from relationalai.semantics import Float, Integer, String
from relationalai.semantics.std import aggregates as aggs

# Declares the decline and marginal rollups the tiers read.
from . import underwriting_factors  # noqa: F401
from .schema import InsuredEntity, Location, Policy, model

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

# Preferred-tier criteria.
PREFERRED_MIN_YEARS = 15          # must have at least this many years in business
PREFERRED_MAX_FP_CLASS = 3        # all locations must be at FP class 3 or better

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

# Tier label: the first tier, in this priority order, that the insured is in;
# an insured in no tier is UNCLASSIFIED.
TIER_LABELS = (
    (RiskTier_Decline, "DECLINE"),
    (RiskTier_NonStandard, "NON-STANDARD"),
    (RiskTier_Preferred, "PREFERRED"),
    (RiskTier_Standard, "STANDARD"),
)
InsuredEntity.tier = model.Property(f"{InsuredEntity} has risk tier {String:tier}")
for priority, (tier, label) in enumerate(TIER_LABELS):
    model.where(
        tier(InsuredEntity),
        *(model.not_(higher(InsuredEntity)) for higher, _ in TIER_LABELS[:priority]),
    ).define(InsuredEntity.tier(label))
model.where(
    *(model.not_(tier(InsuredEntity)) for tier, _ in TIER_LABELS),
).define(InsuredEntity.tier("UNCLASSIFIED"))

# --------------------------------------------------
# Premium by tier
# --------------------------------------------------

# Premium per insured: the sum of its policies' premiums, zero without a policy.
InsuredEntity.premium = model.Property(f"{InsuredEntity} has total premium {Float:premium}")
model.define(InsuredEntity.premium(
    aggs.sum(Policy, Policy.total_premium)
    .per(InsuredEntity)
    .where(Policy.insured_entity(InsuredEntity))
    | 0.0
))

# Each tier's insured count, total premium, and mean premium per insured.
TierPremium = model.Concept("TierPremium", identify_by={"tier": String})
TierPremium.n_insureds = model.Property(f"{TierPremium} has {Integer:n_insureds} insureds")
TierPremium.total_premium = model.Property(f"{TierPremium} has {Float:total_premium}")
TierPremium.mean_premium = model.Property(f"{TierPremium} has {Float:mean_premium}")
model.define(TierPremium.new(tier=InsuredEntity.tier))
_in_tier = InsuredEntity.tier == TierPremium.tier
model.define(
    TierPremium.n_insureds(aggs.count(InsuredEntity).per(TierPremium).where(_in_tier)),
    TierPremium.total_premium(
        aggs.sum(InsuredEntity, InsuredEntity.premium).per(TierPremium).where(_in_tier)
    ),
    TierPremium.mean_premium(
        aggs.avg(InsuredEntity, InsuredEntity.premium).per(TierPremium).where(_in_tier)
    ),
)
