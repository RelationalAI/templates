"""Semantic schema for the cybersecurity attack-path template: assets and the technique edges between them."""

from relationalai.semantics import Integer, Model, String

model = Model("cybersecurity_attack_paths")

# Asset concept: a host, service, or account in the enterprise estate.
Asset = model.Concept("Asset", identify_by={"id": String})
Asset.name = model.Property(f"{Asset} has {String:name}")
Asset.zone = model.Property(f"{Asset} sits in {String:zone}")
Asset.internet_facing = model.Property(f"{Asset} is internet facing {String:internet_facing}")
Asset.crown_jewel = model.Property(f"{Asset} is crown jewel {String:crown_jewel}")
Asset.exposure_score = model.Property(f"{Asset} has exposure score {Integer:exposure_score}")

# One directed self-relationship per attacker technique. An edge means "an attacker
# on the source asset can reach the destination asset by this technique".
Asset.exploit_to = model.Relationship(f"{Asset} exploits to {Asset}", short_name="exploit_to")
Asset.cred_to = model.Relationship(f"{Asset} reuses credentials to {Asset}", short_name="cred_to")
Asset.pivot_to = model.Relationship(f"{Asset} pivots to {Asset}", short_name="pivot_to")
# Technique-agnostic union edge: an attacker can move from src to dst by SOME
# technique. Used for the point query (any route between two named assets).
Asset.can_reach = model.Relationship(f"{Asset} can reach {Asset}", short_name="can_reach")
