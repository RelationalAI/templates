"""Pod placement (pure CSP) template: the model.

This package demonstrates a multi-tenant Kubernetes-style pod-placement
problem in RelationalAI:

- Assign each ``Pod`` to a ``Node`` subject to per-node CPU, memory,
  and GPU bin-packing budgets.
- Tenant ``anti-affinity``: pods belonging to anti-affine tenants must
  not share a node (regulated multi-tenancy / isolation).
- Deployment co-location ``affinity``: deployments declared
  affinity-paired (e.g. shared storage class, low-latency RDMA
  peering) must co-locate (same node) when both placed.
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
- All ICs are pure relational arithmetic -- no ``implies`` bodies.

The model has three rule modules, and each imports the modules whose
declarations it reads: `zone_spread.py` (the zone count and each deployment's
spread cap), `pod_assignment.py` (decisions, constraints, objective, and
solve), and `node_usage.py` (the CPU, memory, and GPU each node carries).

Run:
    `rai models deploy --path model` deploys this package to the schemas in
    raiconfig.yaml and waits for its first refresh, which runs the solve.
    `python -m queries.placement_report` then prints the report from the deployed model.
"""

from .node_usage import NodeUsage
from .pod_assignment import PlacedDeployments, SolveStatus, problem, x
from .schema import Deployment, Node, Pod, Rack, Tenant, Zone, model
from .source import DATA_DIR

__all__ = [
    "DATA_DIR",
    "Deployment",
    "Node",
    "NodeUsage",
    "PlacedDeployments",
    "Pod",
    "Rack",
    "SolveStatus",
    "Tenant",
    "Zone",
    "model",
    "problem",
    "x",
]
