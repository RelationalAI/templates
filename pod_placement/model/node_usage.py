"""Node usage: the CPU, memory, and GPU each node carries under the chosen placement."""

from relationalai.semantics import Integer
from relationalai.semantics.std import aggregates as aggs

# Declares Pod.on_node, the placement decision the usage totals read.
from . import pod_assignment  # noqa: F401
from .schema import Node, Pod, model

# Values computed from the solution live on a concept of their own, not on Node: such a property
# on a concept the solve reads fails the deploy.
NodeUsage = model.Concept("NodeUsage", identify_by={"node_id": Integer})
NodeUsage.cpu_used = model.Property(f"{NodeUsage} has {Integer:cpu_used}")
NodeUsage.memory_used = model.Property(f"{NodeUsage} has {Integer:memory_used}")
NodeUsage.gpu_used = model.Property(f"{NodeUsage} has {Integer:gpu_used}")
model.define(NodeUsage.new(node_id=Node.id))

# Each node's CPU, memory, and GPU demand summed over the pods placed on it.
_assigned = Integer.ref()
_on_node = (Pod.on_node(Node, _assigned), Node.id == NodeUsage.node_id)
model.define(
    NodeUsage.cpu_used(aggs.sum(Pod, Pod.cpu_millicores * _assigned).per(NodeUsage).where(*_on_node)),
    NodeUsage.memory_used(aggs.sum(Pod, Pod.memory_mib * _assigned).per(NodeUsage).where(*_on_node)),
    NodeUsage.gpu_used(aggs.sum(Pod, Pod.gpu_units * _assigned).per(NodeUsage).where(*_on_node)),
)
