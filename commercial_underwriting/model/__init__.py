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
    `rai models deploy --path model` deploys this package to the schemas in
    raiconfig.yaml and waits for its first refresh; `python -m
    queries.underwriting_report` then prints the report from the deployed model.
"""

from .reasoning import (
    ITV_THRESHOLD,
    MAX_FP_CLASS_FOR_ELIGIBILITY,
    MIN_YEAR_BUILT,
    RiskTier_Decline,
    RiskTier_NonStandard,
    RiskTier_Preferred,
    RiskTier_Standard,
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
    "model",
]
