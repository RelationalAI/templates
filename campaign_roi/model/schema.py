"""Semantic schema for the campaign ROI template: marketing campaigns."""

from relationalai.semantics import Float, Integer, Model, String

model = Model("campaign_roi")

# Campaign concept: a marketing campaign with a current budget, region tag,
# and an empirical conversion rate (conversions per $K of spend).
Campaign = model.Concept("Campaign", identify_by={"id": Integer})
Campaign.name = model.Property(f"{Campaign} has {String:name}")
Campaign.region = model.Property(f"{Campaign} in {String:region}")
Campaign.current_budget = model.Property(f"{Campaign} has {Float:current_budget}")
Campaign.conversion_rate = model.Property(f"{Campaign} has {Float:conversion_rate}")
