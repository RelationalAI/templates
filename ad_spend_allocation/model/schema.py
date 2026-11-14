"""Semantic schema for the ad spend allocation template: channels, campaigns, and budget scenarios."""

from relationalai.semantics import Float, Integer, Model, String

model = Model("ad_spend")
Concept, Property = model.Concept, model.Property

# Channel concept: marketing channels with spend bounds and ROI coefficient.
Channel = Concept("Channel", identify_by={"id": Integer})
Channel.name = Property(f"{Channel} has {String:name}")
Channel.min_spend = Property(f"{Channel} has {Float:min_spend}")
Channel.max_spend = Property(f"{Channel} has {Float:max_spend}")
Channel.roi_coefficient = Property(f"{Channel} has {Float:roi_coefficient}")

# Campaign concept: campaigns with budgets and conversion targets.
Campaign = Concept("Campaign", identify_by={"id": Integer})
Campaign.name = Property(f"{Campaign} has {String:name}")
Campaign.budget = Property(f"{Campaign} has {Float:budget}")
Campaign.target_conversions = Property(f"{Campaign} has {Integer:target_conversions}")

# Effectiveness concept: conversion rate for each channel-campaign pair.
Effectiveness = Concept("Effectiveness", identify_by={"channel_id": Integer, "campaign_id": Integer})
Effectiveness.channel = Property(f"{Effectiveness} via {Channel}")
Effectiveness.campaign = Property(f"{Effectiveness} for {Campaign}")
Effectiveness.conversion_rate = Property(f"{Effectiveness} has {Float:conversion_rate}")

# Scenario concept: total_budget parameter variations.
Scenario = Concept("Scenario", identify_by={"name": String})
Scenario.total_budget = Property(f"{Scenario} has {Float:total_budget}")

# Decision concept: spend allocation per channel-campaign pair
Allocation = Concept("Allocation", identify_by={"effectiveness": Effectiveness})
