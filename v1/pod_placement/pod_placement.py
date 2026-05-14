"""Pod placement (pure CSP) template.

This script demonstrates a multi-tenant Kubernetes-style pod-placement
problem in RelationalAI:

- Assign each ``Pod`` to a ``Node`` subject to per-node CPU, memory,
  and GPU bin-packing budgets.
- Tenant ``anti-affinity``: pods belonging to anti-affine tenants must
  not share a node (regulated multi-tenancy / isolation).
- Storage-class ``affinity``: deployments declared affinity-paired
  must co-locate (same node) when both placed.
- Failure-domain ``spread``: replicas of one deployment are spread
  across zones (no more than ``ceil(replicas / num_zones)`` per zone,
  unless ``deployments.csv`` supplies an explicit
  ``max_per_zone_override`` for the row).
- ``Gang placement``: a deployment is either fully placed
  (all replicas) or fully unplaced (none).
- Topology ``rack-clique``: pods in a distributed-training group must
  land on hosts within the same rack (NVLink island).

The objective maximises the number of placed deployments under all
hard isolation, spread, and topology rules.

Modeling approach:
- The primary decision is a binary 2D matrix ``Pod.on_node(Node, x)``
  -- one bit per (pod, node) pair -- with a per-pod cardinality IC
  ``sum(x).per(Pod) == Pod.placed`` that pins the row sum to the
  ``Pod.placed`` 0/1 indicator. Targeting a binary 2D matrix lets
  every per-node aggregate (CPU / memory / GPU bin-packing,
  per-(deployment, zone) spread counts, pairwise anti-affinity sums)
  be expressed as plain relational sums; an integer-valued
  ``Pod.node_id`` decision would force decision-vs-data equalities
  inside ``where`` bindings that the prescriptive rewriter does not
  lower today (see the planogram template for the half-reified
  ``implies``-cascade workaround).
- ``Pod.placed`` and ``Deployment.placed`` are 0/1 indicators coupled
  by the gang-placement IC
  ``sum(Pod.placed).per(Deployment) == Deployment.replicas * Deployment.placed``
  -- a textbook reified-cardinality shape that pins every replica
  on-or-off together.
- ``Pod.deployment`` and ``Deployment.tenant`` are pure data
  properties; ``TenantAntiAffinity`` and ``DeploymentAffinity`` are
  symmetric data relationships closed at definition time so the ICs
  can use either argument order.
- All ICs are pure relational arithmetic -- no ``implies`` bodies --
  so ``problem.verify()`` re-evaluates every one in the returned
  solution.

Run:
    `python pod_placement.py`

Output:
    Prints the formulation, the solve-result block, per-node
    utilisation, the chosen (pod, node) placements, and any
    unplaced deployments.
"""

from math import ceil
from pathlib import Path

from pandas import isna, read_csv
from relationalai.semantics import Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

DATA_DIR = Path(__file__).parent / "data"

# --------------------------------------------------
# Load all CSVs upfront so pre-solve invariants can validate the data
# integrity before any model.define rules are installed.
# --------------------------------------------------

nodes_csv = read_csv(DATA_DIR / "nodes.csv")
tenants_csv = read_csv(DATA_DIR / "tenants.csv")
aa_csv = read_csv(DATA_DIR / "tenant_anti_affinity.csv")
deployments_csv = read_csv(DATA_DIR / "deployments.csv")
da_csv = read_csv(DATA_DIR / "deployment_affinity.csv")
pods_csv = read_csv(DATA_DIR / "pods.csv")
dt_csv = read_csv(DATA_DIR / "distributed_training.csv")

# Pre-compute per-deployment failure-domain spread caps. With N zones,
# at most ceil(replicas / N) replicas of any one deployment land in
# any single zone -- unless the row supplies an explicit
# `max_per_zone_override` (used for deployments where the operator
# has accepted a wider blast radius, e.g. distributed-training groups
# whose rack-clique requirement is incompatible with cross-zone
# spread). Computed in Python and joined onto Deployment as a data
# property so the spread IC reads as a plain relational inequality.
num_zones = nodes_csv["zone"].nunique()


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

# --------------------------------------------------
# Define semantic model
# --------------------------------------------------

model = Model("pod_placement")

# Concept: Zone (failure domain, e.g. us-east-1a). Defined first so
# Node can reference it via a Property. Zones are derived from the
# unique values in `nodes.csv` rather than committed as a separate
# CSV -- a node always belongs to exactly one zone, and the zone
# column on nodes.csv is the single source of truth.
Zone = model.Concept("Zone", identify_by={"name": String})
_zones_df = nodes_csv[["zone"]].drop_duplicates().rename(columns={"zone": "name"})
_zone_data = model.data(_zones_df)
model.define(Zone.new(name=_zone_data.name))

# Concept: Rack (NVLink-island granularity). One rack belongs to one
# zone; the same name never appears in two zones in the bundled data.
Rack = model.Concept("Rack", identify_by={"name": String})
_racks_df = nodes_csv[["rack"]].drop_duplicates().rename(columns={"rack": "name"})
_rack_data = model.data(_racks_df)
model.define(Rack.new(name=_rack_data.name))
Rack.zone = model.Property(f"{Rack} is in {Zone:zone}")
_rack_zone_df = nodes_csv[["rack", "zone"]].drop_duplicates()
_rack_zone_data = model.data(_rack_zone_df)
model.define(Rack.zone(Zone)).where(
    Rack.name == _rack_zone_data.rack,
    Zone.name == _rack_zone_data.zone,
)

# Concept: Node (the cluster's compute hosts).
Node = model.Concept("Node", identify_by={"id": Integer})
Node.name = model.Property(f"{Node} has {String:name}")
Node.cpu_millicores = model.Property(f"{Node} has {Integer:cpu_millicores}")
Node.memory_mib = model.Property(f"{Node} has {Integer:memory_mib}")
Node.gpu_units = model.Property(f"{Node} has {Integer:gpu_units}")
Node.zone = model.Property(f"{Node} is in {Zone:zone}")
Node.rack = model.Property(f"{Node} is in {Rack:rack}")
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

# Concept: Tenant.
Tenant = model.Concept("Tenant", identify_by={"id": Integer})
Tenant.name = model.Property(f"{Tenant} has {String:name}")
tenant_data = model.data(tenants_csv)
model.define(
    Tenant.new(
        id=tenant_data.tenant_id,
        name=tenant_data.name,
    )
)

# Concept: Deployment.
Deployment = model.Concept("Deployment", identify_by={"id": Integer})
Deployment.name = model.Property(f"{Deployment} has {String:name}")
Deployment.replicas = model.Property(f"{Deployment} has {Integer:replicas}")
Deployment.max_per_zone = model.Property(f"{Deployment} has {Integer:max_per_zone}")
Deployment.tenant = model.Property(f"{Deployment} belongs to {Tenant:tenant}")
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

# Concept: Pod.
Pod = model.Concept("Pod", identify_by={"id": Integer})
Pod.cpu_millicores = model.Property(f"{Pod} has {Integer:cpu_millicores}")
Pod.memory_mib = model.Property(f"{Pod} has {Integer:memory_mib}")
Pod.gpu_units = model.Property(f"{Pod} has {Integer:gpu_units}")
Pod.deployment = model.Property(f"{Pod} belongs to {Deployment:deployment}")
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

# Symmetric tenant anti-affinity relation: pods of two anti-affine
# tenants must not share a node. The CSV stores each pair once; the
# define rules below close the relation symmetrically so the ICs can
# match in either argument order. Each `.ref()` call returns a fresh
# ref, so the second tenant is bound to a name (`T2`) and reused in
# both the head and the where body.
TenantAntiAffinity = model.Relationship(f"{Tenant:a} is anti-affine to {Tenant:b}")
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

# Symmetric deployment affinity relation: deployments declared
# affinity-paired (e.g. shared storage class) must co-locate (same
# node) when both placed. Closed symmetrically for the same reason.
DeploymentAffinity = model.Relationship(f"{Deployment:a} is affinity-paired with {Deployment:b}")
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

# Symmetric distributed-training relation: pods in the same training
# group must land on hosts within the same rack (NVLink island).
DistributedTraining = model.Relationship(f"{Pod:a} trains-distributed with {Pod:b}")
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

# --------------------------------------------------
# Decision variables
# --------------------------------------------------

# Decision properties below are declared with `Integer` type but
# solved as `type="bin"` -- the prescriptive reasoner narrows the
# domain to {0, 1} at solve time, so the per-pod cardinality IC
# `sum(x).per(Pod) == Pod.placed` and the gang-placement IC are
# guaranteed to hold under binary arithmetic.

# Binary 2D matrix decision: Pod.on_node(Node, 1) iff this pod runs
# on this node. Per-node aggregates (CPU / memory / GPU bin-packing,
# spread counts, pairwise anti-affinity / clique sums) read as plain
# relational sums over this matrix.
Pod.on_node = model.Property(f"{Pod} runs on {Node} if {Integer:assigned}")
# 0/1 per-pod placement indicator: 1 iff the pod is placed on some
# node. Coupled to the matrix by `placement_coupling_ic`.
Pod.placed = model.Property(f"{Pod} has {Integer:placed}")
# 0/1 per-deployment placement indicator. Coupled to per-pod placed
# by `gang_placement_ic`.
Deployment.placed = model.Property(f"{Deployment} has {Integer:placed}")

problem = Problem(model, Integer)

# Per (Pod, Node) binary assignment matrix.
x = Integer.ref()
problem.solve_for(Pod.on_node(Node, x), type="bin", name=["x", Pod.id, Node.id])
problem.solve_for(Pod.placed, type="bin", name=["placed", Pod.id])
problem.solve_for(Deployment.placed, type="bin", name=["dep_placed", Deployment.id])

# --------------------------------------------------
# Constraints
# --------------------------------------------------

# Per-pod cardinality: a pod assigns to exactly Pod.placed nodes
# (0 if unplaced, 1 if placed). Pins the row sum of the assignment
# matrix to the placement indicator.
placement_coupling_ic = model.where(Pod.on_node(Node, x)).require(sum(x).per(Pod) == Pod.placed)
problem.satisfy(placement_coupling_ic)

# Gang placement: all replicas of a deployment placed or none.
# `sum(Pod.placed).per(Deployment)` is the placed-replica count;
# the IC pins it to `replicas * Deployment.placed` -- which is
# either 0 (deployment unplaced) or `replicas` (all placed).
gang_placement_ic = model.where(Pod.deployment == Deployment).require(
    sum(Pod.placed).per(Deployment) == Deployment.replicas * Deployment.placed
)
problem.satisfy(gang_placement_ic)

# CPU bin-packing per node.
cpu_capacity_ic = model.where(Pod.on_node(Node, x)).require(
    sum(Pod.cpu_millicores * x).per(Node) <= Node.cpu_millicores
)
problem.satisfy(cpu_capacity_ic)

# Memory bin-packing per node.
memory_capacity_ic = model.where(Pod.on_node(Node, x)).require(
    sum(Pod.memory_mib * x).per(Node) <= Node.memory_mib
)
problem.satisfy(memory_capacity_ic)

# GPU bin-packing per node.
gpu_capacity_ic = model.where(Pod.on_node(Node, x)).require(
    sum(Pod.gpu_units * x).per(Node) <= Node.gpu_units
)
problem.satisfy(gpu_capacity_ic)

# Tenant anti-affinity: for every ordered pair (Pi, Pj) with
# Pi.id < Pj.id whose deployments' tenants are anti-affine, at most
# one of (Pi, Pj) is on any given node. With the per-pod cardinality
# IC already pinning each pod to at most one node, this is the
# textbook CP pairwise no-co-location shape -- O(1) propagator per
# pair, no big-M.
Pi = Pod
Pj = Pod.ref()
xi = Integer.ref()
xj = Integer.ref()
anti_affinity_ic = model.where(
    Pi.id < Pj.id,
    TenantAntiAffinity(Pi.deployment.tenant, Pj.deployment.tenant),
    Pi.on_node(Node, xi),
    Pj.on_node(Node, xj),
).require(xi + xj <= 1)
problem.satisfy(anti_affinity_ic)

# Storage-class affinity: for every ordered pair (Pi, Pj) whose
# deployments are affinity-paired, the pods must agree on every
# node's assignment bit -- i.e. they share the same single node when
# both placed, and are simultaneously unplaced otherwise. For
# multi-replica affinity-paired deployments, the per-node `xi == xj`
# constraint applied to every cross-deployment pod pair forces all
# replicas of both deployments onto the same single node -- which is
# the intended "co-locate" semantics, just tighter than necessary
# (you may want to relax to "share a rack" for that case).
affinity_ic = model.where(
    Pi.id < Pj.id,
    DeploymentAffinity(Pi.deployment, Pj.deployment),
    Pi.on_node(Node, xi),
    Pj.on_node(Node, xj),
).require(xi == xj)
problem.satisfy(affinity_ic)

# Failure-domain spread: per (deployment, zone), at most
# `max_per_zone` of the deployment's pods land in that zone. With
# `max_per_zone = ceil(replicas / num_zones)`, no zone holds more
# than its fair share -- a single-zone outage cannot take down more
# than that many replicas.
spread_ic = model.where(
    Pod.on_node(Node, x),
    Pod.deployment == Deployment,
    Node.zone == Zone,
).require(sum(x).per(Deployment, Zone) <= Deployment.max_per_zone)
problem.satisfy(spread_ic)

# Distributed-training rack-clique: every pair of pods in a
# DistributedTraining group lands on hosts within the same rack.
# Encoded as the pairwise "no different-rack co-placement" sum
# constraint: at most one of (Pa, Pb) is on any (Na, Nb) pair of
# nodes that are in different racks. The IC fires once per
# `DistributedTraining` edge -- so the input relation must enumerate
# ALL pairs of pods in each training group (the bundled CSV does:
# C(4,2)=6 rows for pods 27-30). A spanning-tree of edges would only
# constrain adjacent pods to share a rack; non-adjacent pairs would
# be free to land on different racks, silently weakening the clique
# guarantee.
Pa = Pod
Pb = Pod.ref()
Na = Node
Nb = Node.ref()
xa = Integer.ref()
xb = Integer.ref()
rack_clique_ic = model.where(
    Pa.id < Pb.id,
    DistributedTraining(Pa, Pb),
    Pa.on_node(Na, xa),
    Pb.on_node(Nb, xb),
    Na.rack != Nb.rack,
).require(xa + xb <= 1)
problem.satisfy(rack_clique_ic)

# --------------------------------------------------
# Objective: maximize the number of placed deployments.
# --------------------------------------------------

problem.maximize(sum(Deployment.placed))

# --------------------------------------------------
# Solve and verify
# --------------------------------------------------

problem.display()
problem.solve("minizinc", time_limit_sec=60)
problem.solve_info().display()

# Every IC is pure relational arithmetic, so verify() re-evaluates
# all nine in the returned solution. The post-solve
# `model.require(... == "OPTIMAL")` below is a hard assertion: if
# you raise `time_limit_sec` and the solver returns a feasible-but-
# not-proven-optimal result, the script will raise rather than print
# a partial solution. Soften to a `print(...)` warning if you want
# the inspection blocks to run on partial solutions.
problem.verify(
    placement_coupling_ic,
    gang_placement_ic,
    cpu_capacity_ic,
    memory_capacity_ic,
    gpu_capacity_ic,
    anti_affinity_ic,
    affinity_ic,
    spread_ic,
    rack_clique_ic,
)
model.require(problem.termination_status() == "OPTIMAL")

# --------------------------------------------------
# Inspect results
# --------------------------------------------------

print("\nPer-node utilization:")
model.select(
    Node.id.alias("node_id"),
    Node.name.alias("node"),
    sum(Pod.cpu_millicores * x).where(Pod.on_node(Node, x)).per(Node).alias("cpu_used"),
    Node.cpu_millicores.alias("cpu_cap"),
    sum(Pod.memory_mib * x).where(Pod.on_node(Node, x)).per(Node).alias("memory_used"),
    sum(Pod.gpu_units * x).where(Pod.on_node(Node, x)).per(Node).alias("gpu_used"),
).inspect()

print("\nPlaced pods (pod_id -> node_id):")
model.select(
    Pod.id.alias("pod_id"),
    Node.id.alias("node_id"),
).where(Pod.on_node(Node, 1)).inspect()

print("\nUnplaced deployments (if any):")
model.select(
    Deployment.id.alias("deployment_id"),
    Deployment.name.alias("deployment"),
    Deployment.replicas.alias("replicas"),
).where(Deployment.placed == 0).inspect()
