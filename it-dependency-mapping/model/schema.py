"""Semantic schema for the IT dependency mapping template: features and their contributes_to edges."""

from relationalai.semantics import Model, String

model = Model("it_dependency_mapping")

# Feature concept: a service, data pipeline, feature job, or dashboard.
Feature = model.Concept("Feature", identify_by={"id": String})
Feature.name = model.Property(f"{Feature} has {String:name}")
Feature.owner = model.Property(f"{Feature} owned by {String:owner}")
Feature.deploy_tier = model.Property(f"{Feature} has deploy tier {String:deploy_tier}")

# Feature.contributes_to: a self-relationship -- the upstream feature feeds /
# contributes to the downstream feature, forming an acyclic dependency DAG.
Feature.contributes_to = model.Relationship(
    f"{Feature} contributes to {Feature}", short_name="contributes_to"
)
