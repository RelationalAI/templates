"""Load the sample cluster, tenants, deployments, and pods, and check the topology."""

from math import ceil
from pathlib import Path

from pandas import isna, read_csv

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
# Load CSVs and pre-compute per-deployment failure-domain spread caps.
# With N zones, at most ceil(replicas / N) replicas of any one
# deployment land in any single zone -- unless the row supplies an
# explicit `max_per_zone_override` (used for deployments where the
# operator has accepted a wider blast radius, e.g. distributed-
# training groups whose rack-clique requirement is incompatible with
# cross-zone spread). Computed in Python and joined onto Deployment
# as a data property so the spread IC reads as a plain relational
# inequality.
# --------------------------------------------------

nodes_csv = read_csv(DATA_DIR / "nodes.csv")
tenants_csv = read_csv(DATA_DIR / "tenants.csv")
aa_csv = read_csv(DATA_DIR / "tenant_anti_affinity.csv")
deployments_csv = read_csv(DATA_DIR / "deployments.csv")
da_csv = read_csv(DATA_DIR / "deployment_affinity.csv")
pods_csv = read_csv(DATA_DIR / "pods.csv")
dt_csv = read_csv(DATA_DIR / "distributed_training.csv")

num_zones = nodes_csv["zone"].nunique()
if num_zones == 0:
    raise ValueError("nodes.csv must contain at least one row to define the cluster topology.")


def _compute_max_per_zone(replicas, override):
    if override is not None and not isna(override):
        return int(override)
    return int(ceil(int(replicas) / num_zones))


deployments_csv = deployments_csv.assign(
    max_per_zone=[
        _compute_max_per_zone(r, o)
        for r, o in zip(
            deployments_csv["replicas"].tolist(),
            deployments_csv["max_per_zone_override"].tolist(),
        )
    ]
).drop(columns=["max_per_zone_override"])
# Drop the override column before passing to model.data: rows with NaN
# in any column get silently filtered, so leaving the override column
# in (where it is NaN for most rows) would drop those Deployment rows
# from the model -- breaking the gang IC and the objective.


# Zones are derived from the unique values in `nodes.csv` rather than
# committed as a separate CSV -- a node always belongs to exactly one
# zone, and the zone column on nodes.csv is the single source of truth.
_zones_df = nodes_csv[["zone"]].drop_duplicates().rename(columns={"zone": "name"})
_zone_data = model.data(_zones_df)
model.define(Zone.new(name=_zone_data.name))

# Racks and the zone each belongs to.
_racks_df = nodes_csv[["rack"]].drop_duplicates().rename(columns={"rack": "name"})
_rack_data = model.data(_racks_df)
model.define(Rack.new(name=_rack_data.name))
_rack_zone_df = nodes_csv[["rack", "zone"]].drop_duplicates()
_rack_zone_data = model.data(_rack_zone_df)
model.define(Rack.zone(Zone)).where(
    Rack.name == _rack_zone_data.rack,
    Zone.name == _rack_zone_data.zone,
)

# Nodes.
node_data = model.data(nodes_csv)
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

# Deployments.
dep_data = model.data(deployments_csv)
model.define(
    Deployment.new(
        id=dep_data.deployment_id,
        name=dep_data.name,
        replicas=dep_data.replicas,
        max_per_zone=dep_data.max_per_zone,
    )
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
