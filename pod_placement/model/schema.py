"""Semantic schema for the pod placement template: zones, racks, nodes, tenants, deployments, and pods."""

from relationalai.semantics import Integer, Model, String

model = Model("pod_placement")

# Concept: Zone (failure domain, e.g. us-east-1a). Defined first so
# Node can reference it via a Property.
Zone = model.Concept("Zone", identify_by={"name": String})

# Concept: Rack (NVLink-island granularity). One rack belongs to one
# zone; the same name never appears in two zones in the bundled data.
Rack = model.Concept("Rack", identify_by={"name": String})
Rack.zone = model.Property(f"{Rack} is in {Zone:zone}")

# Concept: Node (the cluster's compute hosts).
Node = model.Concept("Node", identify_by={"id": Integer})
Node.name = model.Property(f"{Node} has {String:name}")
Node.cpu_millicores = model.Property(f"{Node} has {Integer:cpu_millicores}")
Node.memory_mib = model.Property(f"{Node} has {Integer:memory_mib}")
Node.gpu_units = model.Property(f"{Node} has {Integer:gpu_units}")
Node.zone = model.Property(f"{Node} is in {Zone:zone}")
Node.rack = model.Property(f"{Node} is in {Rack:rack}")

# Concept: Tenant.
Tenant = model.Concept("Tenant", identify_by={"id": Integer})
Tenant.name = model.Property(f"{Tenant} has {String:name}")

# Concept: Deployment.
Deployment = model.Concept("Deployment", identify_by={"id": Integer})
Deployment.name = model.Property(f"{Deployment} has {String:name}")
Deployment.replicas = model.Property(f"{Deployment} has {Integer:replicas}")
Deployment.max_per_zone = model.Property(f"{Deployment} has {Integer:max_per_zone}")
Deployment.tenant = model.Property(f"{Deployment} belongs to {Tenant:tenant}")

# Concept: Pod.
Pod = model.Concept("Pod", identify_by={"id": Integer})
Pod.cpu_millicores = model.Property(f"{Pod} has {Integer:cpu_millicores}")
Pod.memory_mib = model.Property(f"{Pod} has {Integer:memory_mib}")
Pod.gpu_units = model.Property(f"{Pod} has {Integer:gpu_units}")
Pod.deployment = model.Property(f"{Pod} belongs to {Deployment:deployment}")

# Symmetric tenant anti-affinity relation: pods of two anti-affine
# tenants must not share a node.
TenantAntiAffinity = model.Relationship(f"{Tenant:a} is anti-affine to {Tenant:b}")

# Symmetric deployment affinity relation: deployments declared
# affinity-paired (e.g. shared storage class) must co-locate (same
# node) when both placed.
DeploymentAffinity = model.Relationship(f"{Deployment:a} is affinity-paired with {Deployment:b}")

# Symmetric distributed-training relation: pods in the same training
# group must land on hosts within the same rack (NVLink island).
DistributedTraining = model.Relationship(f"{Pod:a} trains-distributed with {Pod:b}")
