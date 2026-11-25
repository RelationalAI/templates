"""Zone spread: the number of zones in the cluster and each deployment's cap on replicas per zone."""

from relationalai.semantics import Integer
from relationalai.semantics.std import aggregates as aggs

from .schema import Deployment, Zone, model

# --------------------------------------------------
# Failure-domain spread caps
# --------------------------------------------------
# With N zones, at most ceil(replicas / N) replicas of any one deployment land in
# any single zone -- unless the deployment has an explicit `max_per_zone_override`
# (used for deployments where the operator has accepted a wider blast radius, e.g.
# distributed-training groups whose rack-clique requirement is incompatible with
# cross-zone spread). The cap is a data property of the deployment so the spread IC
# reads as a plain relational inequality.

num_zones = model.Relationship(f"the cluster has {Integer:num_zones} zones")
model.define(num_zones(aggs.count(Zone)))

# The ceiling of replicas / zones, in integer arithmetic.
_zones = Integer.ref()
model.where(num_zones(_zones)).define(
    Deployment.max_per_zone(
        Deployment.max_per_zone_override | ((Deployment.replicas + _zones - 1) // _zones)
    )
)
