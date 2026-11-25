"""Pod assignment: binary pod-to-node assignments that maximize the number of placed deployments."""

from relationalai.semantics import Integer, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

# Declares Deployment.max_per_zone, the spread cap the spread constraint reads.
from . import zone_spread  # noqa: F401
from .schema import (
    Deployment,
    DeploymentAffinity,
    DistributedTraining,
    Node,
    Pod,
    TenantAntiAffinity,
    Zone,
    model,
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

problem = Problem(model, Integer, name="pod_placement")

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
placement_coupling_ic = model.where(Pod.on_node(Node, x)).require(sum(Node, x).per(Pod) == Pod.placed)
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

# Deployment co-location affinity: for every ordered pair (Pi, Pj)
# whose deployments are affinity-paired, the pods must agree on every
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
    Pod.deployment == Deployment,
    Node.zone == Zone,
).require(sum(Pod, Node, x).where(Pod.on_node(Node, x)).per(Deployment, Zone) <= Deployment.max_per_zone)
problem.satisfy(spread_ic)

# Distributed-training rack-clique: every pair of pods in a
# DistributedTraining group lands on hosts within the same rack.
# Encoded as the pairwise "no different-rack co-placement" sum
# constraint: at most one of (Pa, Pb) is on any (Na, Nb) pair of
# nodes that are in different racks. The IC fires once per
# `DistributedTraining` edge and binds only pods that are both placed,
# so the input relation enumerates ALL pairs of pods in each training
# group (the bundled CSV does: C(4,2)=6 rows for pods 27-30). A
# connected spanning tree also forces one rack when every pod in the
# group is placed, as gang placement does for a single deployment, but
# an unplaced intermediate pod would let its neighbours split.
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
# Solve
# --------------------------------------------------

# Each refresh of the deployed model runs this solve.
problem.configure("minizinc", time_limit_sec=60)

# The solve's status and objective, which the deployed model publishes for the queries.
SolveStatus = model.Relationship(f"pod placement solve status is {String:status}")
PlacedDeployments = model.Relationship(f"pod placement placed deployments is {Integer:placed}")
model.define(SolveStatus(problem.termination_status()), PlacedDeployments(problem.objective_value()))
