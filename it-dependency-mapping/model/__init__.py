"""IT dependency mapping (graph paths) template.

Maps the downstream dependency structure of a software / data-pipeline estate
by enumerating variable-length traversal paths over an acyclic dependency DAG:

- Loads Feature nodes (services, pipelines, jobs, dashboards) and a
  contributes_to self-relationship (feeds / contributes to) from CSV.
- Enumerates every downstream dependency path with
  ``model.path(Feature.contributes_to.repeat(1, N)).all().paths()`` -- because the
  estate is acyclic, every enumerated path is simple.
- Reduces the full path set to its maximal chains (longest non-extendable
  dependency chains, with shorter sub-chains dropped).
- Persists each feature's longest downstream depth back to the ontology as
  Feature.max_downstream_depth, then reports per-feature path counts, the
  deepest dependency chains, and the owners that sit along the longest chain.

Run:
    `rai models deploy --path model` deploys this model to the schema in
    raiconfig.yaml and waits for its first refresh; `python -m
    queries.dependency_chain_report` then prints the report from the deployed model.
"""

from pathlib import Path

import pandas as pd
from relationalai.semantics import Integer, Model, String
from relationalai.semantics.std import aggregates as aggs

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# Maximum traversal depth (in edges) when enumerating downstream paths. The
# estate is acyclic, so this only needs to cover the longest real chain.
MAX_DEPTH = 8


def load_csv(path):
    return pd.read_csv(path)


# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

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

# Load feature data from CSV.
feature_data = model.data(load_csv(DATA_DIR / "features.csv"))
model.define(Feature.new(id=feature_data["id"]))
model.where(Feature.id == feature_data["id"]).define(
    Feature.name(feature_data["name"]),
    Feature.owner(feature_data["owner"]),
    Feature.deploy_tier(feature_data["deploy_tier"]),
)

# Load dependency edges from CSV (upstream feature -> downstream feature).
dependency_data = model.data(load_csv(DATA_DIR / "dependencies.csv"))
upstream, downstream = Feature.ref(), Feature.ref()
model.where(
    upstream.id == dependency_data["from_feature"],
    downstream.id == dependency_data["to_feature"],
).define(upstream.contributes_to(downstream))

# --------------------------------------------------
# Paths: enumerate downstream dependency paths
#   PREVIEW capability; requires relationalai>=1.15.
# --------------------------------------------------
# model.path(src, Feature.contributes_to.repeat(1, MAX_DEPTH)) describes a
# variable-length traversal of 1..MAX_DEPTH contributes_to edges starting from a
# typed source endpoint `src`. .all().paths() enumerates every such path; because
# contributes_to is acyclic, each path is simple. The result is one PathTraversal
# per path -- p.length is its hop count, p.nodes is the ordered sequence of
# Feature nodes it visits, and src is auto-unified with p.nodes(0) (the start).

src = Feature.ref()
p = model.path(src, Feature.contributes_to.repeat(1, MAX_DEPTH)).all().paths()

# Persist each feature's longest downstream depth back to the ontology so a
# downstream query can rank features by reach without re-enumerating paths.
# aggregates.max(p.length).per(src) takes the max hop count over the paths rooted
# at each src and defines it directly onto Feature -- no pandas groupby and no
# model.data round-trip. Kept SEPARATE from the node projection. It is a
# Relationship, not a Property: deploying this rule as a Property fails planning
# on relationalai 2.1.1.
Feature.max_downstream_depth = model.Relationship(
    f"{Feature} has {Integer:max_downstream_depth}"
)
model.define(src.max_downstream_depth(aggs.max(p.length).per(src))).where(p)
