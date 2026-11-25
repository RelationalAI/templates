"""Load the sample cluster, tenants, deployments, and pods, and check the topology."""

from pathlib import Path

from pandas import read_csv

from .schema import (
    Deployment,
    DeploymentAffinity,
    DistributedTraining,
    Node,
    Pod,
    Rack,
    Tenant,
    TenantAntiAffinity,
    Zone,
    model,
)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# --------------------------------------------------
# Load CSVs. The failure-domain spread cap of each deployment is a rule
# over its replicas, the zone count, and the optional
# `max_per_zone_override` (see `zone_spread.py`).
# --------------------------------------------------

nodes_csv = read_csv(DATA_DIR / "nodes.csv")
tenants_csv = read_csv(DATA_DIR / "tenants.csv")
aa_csv = read_csv(DATA_DIR / "tenant_anti_affinity.csv")
deployments_csv = read_csv(DATA_DIR / "deployments.csv")
da_csv = read_csv(DATA_DIR / "deployment_affinity.csv")
pods_csv = read_csv(DATA_DIR / "pods.csv")
dt_csv = read_csv(DATA_DIR / "distributed_training.csv")

if nodes_csv["zone"].nunique() == 0:
    raise ValueError("nodes.csv must contain at least one row to define the cluster topology.")

# Zones and racks are derived from the values in `nodes.csv` rather than
# committed as separate CSVs -- a node always belongs to exactly one
# zone and rack, and the zone and rack columns on nodes.csv are the
# single source of truth.
node_data = model.data(nodes_csv)
model.define(Zone.new(name=node_data.zone))
model.define(Rack.new(name=node_data.rack))
model.define(Rack.zone(Zone)).where(
    Rack.name == node_data.rack,
    Zone.name == node_data.zone,
)

# Nodes.
model.define(
    Node.new(
        id=node_data.node_id,
        name=node_data.name,
        cpu_millicores=node_data.cpu_millicores,
        memory_mib=node_data.memory_mib,
        gpu_units=node_data.gpu_units,
    )
)
model.define(Node.zone(Zone)).where(Node.id == node_data.node_id, Zone.name == node_data.zone)
model.define(Node.rack(Rack)).where(Node.id == node_data.node_id, Rack.name == node_data.rack)

# Tenants.
tenant_data = model.data(tenants_csv)
model.define(
    Tenant.new(
        id=tenant_data.tenant_id,
        name=tenant_data.name,
    )
)

# Deployments. The override column is loaded as a table of its own: rows with NaN in any
# column get silently filtered by model.data, so leaving it in (where it is NaN for most
# rows) would drop those Deployment rows from the model -- breaking the gang IC and the
# objective.
dep_data = model.data(deployments_csv.drop(columns=["max_per_zone_override"]))
model.define(
    Deployment.new(
        id=dep_data.deployment_id,
        name=dep_data.name,
        replicas=dep_data.replicas,
    )
)
overrides_csv = (
    deployments_csv[["deployment_id", "max_per_zone_override"]].dropna().astype(int)
)
if not overrides_csv.empty:
    override_data = model.data(overrides_csv)
    model.define(Deployment.max_per_zone_override(override_data.max_per_zone_override)).where(
        Deployment.id == override_data.deployment_id
    )
model.define(Deployment.tenant(Tenant)).where(
    Deployment.id == dep_data.deployment_id,
    Tenant.id == dep_data.tenant_id,
)

# Pods.
pod_data = model.data(pods_csv)
model.define(
    Pod.new(
        id=pod_data.pod_id,
        cpu_millicores=pod_data.cpu_millicores,
        memory_mib=pod_data.memory_mib,
        gpu_units=pod_data.gpu_units,
    )
)
model.define(Pod.deployment(Deployment)).where(
    Pod.id == pod_data.pod_id,
    Deployment.id == pod_data.deployment_id,
)

# Tenant anti-affinity. The CSV stores each pair once; the define rules
# below close the relation symmetrically so the ICs can match in either
# argument order. Each `.ref()` call returns a fresh ref, so the second
# tenant is bound to a name (`T2`) and reused in both the head and the
# where body.
aa_data = model.data(aa_csv)
T2 = Tenant.ref()
model.define(TenantAntiAffinity(Tenant, T2)).where(
    Tenant.id == aa_data.tenant_a,
    T2.id == aa_data.tenant_b,
)
T2_sym = Tenant.ref()
model.define(TenantAntiAffinity(Tenant, T2_sym)).where(
    Tenant.id == aa_data.tenant_b,
    T2_sym.id == aa_data.tenant_a,
)

# Deployment affinity, closed symmetrically for the same reason.
da_data = model.data(da_csv)
D2 = Deployment.ref()
model.define(DeploymentAffinity(Deployment, D2)).where(
    Deployment.id == da_data.deployment_a,
    D2.id == da_data.deployment_b,
)
D2_sym = Deployment.ref()
model.define(DeploymentAffinity(Deployment, D2_sym)).where(
    Deployment.id == da_data.deployment_b,
    D2_sym.id == da_data.deployment_a,
)

# Distributed-training groups, closed symmetrically for the same reason.
dt_data = model.data(dt_csv)
P2 = Pod.ref()
model.define(DistributedTraining(Pod, P2)).where(
    Pod.id == dt_data.pod_a,
    P2.id == dt_data.pod_b,
)
P2_sym = Pod.ref()
model.define(DistributedTraining(Pod, P2_sym)).where(
    Pod.id == dt_data.pod_b,
    P2_sym.id == dt_data.pod_a,
)
