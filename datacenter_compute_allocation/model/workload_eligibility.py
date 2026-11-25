"""Workload eligibility: each workload's priority tier and weights, the hardware compatibility of
workloads with GPU pools, and the workload count per priority tier."""

from relationalai.semantics import Float, Integer, String
from relationalai.semantics.std import aggregates as aggs

from .schema import GpuPool, Workload, WorkloadGpuCompat, model

# --------------------------------------------------
# Stage 2: Rules -- eligibility + priority classification
#   Hardware compatibility (memory + GPU-type allowlist) + priority tier
#   from contract_tier. Asymmetric failure-mode pricing: under-provisioning
#   an anchor (P0) carries an SLA / contract / reputational penalty that is
#   a multiple of the raw foregone revenue; Stage 4 multiplies the
#   assignment reward by (1 + under_provisioning_penalty).
# --------------------------------------------------

# The priority tiers assigned below.
PRIORITY_TIERS = ("P0", "P1", "P2")

# Rule family 1: hardware compatibility
# `is_eligible` is defined with positive conditions directly (PyRel
# does not support `~` negation on relationship-application expressions).
# Failure flags are still derived for reporting/queryability:
Workload.fails_memory = model.Relationship(
    f"{Workload} fails memory check on {GpuPool}"
)
model.where(
    Workload.mem_required_gb > GpuPool.mem_per_gpu_gb,
).define(Workload.fails_memory(GpuPool))

# Rule family 2: priority tier + numeric weight (lex-emulating spread)
Workload.priority_tier = model.Property(
    f"{Workload} has priority tier {String:priority_tier}"
)
Workload.priority_weight = model.Property(
    f"{Workload} has {Float:priority_weight} priority weight"
)
model.where(Workload.lab.contract_tier == "anchor_reserved").define(
    Workload.priority_tier("P0"))
model.where(Workload.lab.contract_tier == "committed").define(
    Workload.priority_tier("P1"))
model.where(Workload.lab.contract_tier == "on_demand").define(
    Workload.priority_tier("P2"))

model.where(Workload.priority_tier == "P0").define(Workload.priority_weight(100.0))
model.where(Workload.priority_tier == "P1").define(Workload.priority_weight(10.0))
model.where(Workload.priority_tier == "P2").define(Workload.priority_weight(1.0))

# Asymmetric failure mode: unfilled P0 seats hurt more than unfilled P2.
Workload.under_provisioning_penalty = model.Property(
    f"{Workload} has {Float:under_provisioning_penalty} under-provisioning penalty"
)
model.where(Workload.priority_tier == "P0").define(
    Workload.under_provisioning_penalty(1.0))
model.where(Workload.priority_tier == "P1").define(
    Workload.under_provisioning_penalty(0.3))
model.where(Workload.priority_tier == "P2").define(
    Workload.under_provisioning_penalty(0.0))

# Workloads per priority tier; a tier without workloads has no row.
PriorityTierCount = model.Relationship(
    f"{Integer:n_workloads} workloads have priority tier {String:priority_tier}"
)
_tier = String.ref()
model.where(Workload.priority_tier == _tier).define(
    PriorityTierCount(aggs.count(Workload).per(_tier), _tier)
)

# Composite eligibility: positive form of (passes_gpu_type AND passes_memory).
Workload.is_eligible = model.Relationship(
    f"{Workload} is eligible on {GpuPool}"
)
model.where(
    WorkloadGpuCompat.workload == Workload,
    WorkloadGpuCompat.gpu_type == GpuPool.gpu_type,
    Workload.mem_required_gb <= GpuPool.mem_per_gpu_gb,
).define(Workload.is_eligible(GpuPool))

# Compatibility precompute -- keeps the Stage 4 MIP linear and small.
Compatibility = model.Concept(
    "Compatibility",
    identify_by={"workload": Workload, "gpu_pool": GpuPool},
)
model.where(
    Workload.is_eligible(GpuPool),
).define(
    Compatibility.new(workload=Workload, gpu_pool=GpuPool)
)
