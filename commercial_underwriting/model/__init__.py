"""Commercial Underwriting (rules-based reasoning) template.

This model declares a rules-based underwriting workflow in RelationalAI
on a four-level commercial property/casualty hierarchy:

InsuredEntity -> Policy -> Location -> Coverage

- Load sample CSVs describing insured entities, policies, locations, and
  coverages (`source.py`).
- Define declarative rules as derived Relationships using `define()` + `where()`:
  - Eligibility flags at the location level (old construction, poor fire
    protection, high-risk occupancy) and the building-coverage adequacy flag
    (insurance-to-value < 80%) (`eligibility_flags.py`).
  - Entity-level flags (restricted industry, insufficient history) and the
    roll-up of every flag into entity-level decline and marginal indicators
    (`underwriting_factors.py`).
- Classify each insured entity into a risk tier (Decline / NonStandard /
  Standard / Preferred) using mutually exclusive subtype concepts, label it,
  and total the premium per tier (`risk_tiers.py`).

The whole pipeline is declarative — there are no procedural rule chains.
PyRel resolves dependencies automatically.

Run:
    `rai models deploy --path model` deploys this package to the schemas in
    raiconfig.yaml and waits for its first refresh; `python -m
    queries.underwriting_report` then prints the report from the deployed model.
"""

from .eligibility_flags import ITV_THRESHOLD, MAX_FP_CLASS_FOR_ELIGIBILITY, MIN_YEAR_BUILT
from .risk_tiers import (
    RiskTier_Decline,
    RiskTier_NonStandard,
    RiskTier_Preferred,
    RiskTier_Standard,
    TierPremium,
)
from .schema import Coverage, InsuredEntity, Location, Policy, model
from .source import DATA_DIR

__all__ = [
    "DATA_DIR",
    "ITV_THRESHOLD",
    "MAX_FP_CLASS_FOR_ELIGIBILITY",
    "MIN_YEAR_BUILT",
    "Coverage",
    "InsuredEntity",
    "Location",
    "Policy",
    "RiskTier_Decline",
    "RiskTier_NonStandard",
    "RiskTier_Preferred",
    "RiskTier_Standard",
    "TierPremium",
    "model",
]
