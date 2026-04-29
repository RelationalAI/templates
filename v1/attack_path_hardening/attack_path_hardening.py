"""Attack-path hardening (Graph paths + Rules + CSP set cover) template.

This script demonstrates a three-pillar pipeline in RelationalAI:

- A security team has a model of the enterprise IT graph (hosts,
  services, vulnerabilities, credentials, segment trust). They know
  which hosts attackers can reach from outside ("entry points") and
  which hosts hold their crown-jewel data (domain controller,
  finance database, executive mailbox). They have a budget of
  candidate mitigations -- patch a vulnerability, segment a network,
  break a trust, gate a host with MFA, revoke a credential -- each
  with a dollar cost. They must pick the smallest-cost subset of
  mitigations such that every attack path from any entry point to
  any crown jewel is broken (i.e., at least one of its edges is
  covered by a deployed mitigation), subject to per-kind operational
  caps and per-segment change-budget envelopes.
- The encoding is split across three pillars: the **Rules** pillar
  defines which directed attack steps exist and what their risk
  weight is; the **Paths** library enumerates concrete attack paths
  from entry points to crown jewels with bounded depth; the
  **Prescriptive** reasoner (CSP, MiniZinc/Chuffed) selects the
  minimum-cost set-cover of mitigations under cardinality and
  cost-aggregation integrity constraints.

Modeling approach:
- Attack steps are entified: ``AttackStep`` is a Concept whose
  identity is the integer id of the (src, dst, kind) row. The
  traversal edge ``Host.attack_step_to`` is a 3-arity relationship
  with the ``AttackStep`` entity in the middle slot. The paths
  library walks ``Host.attack_step_to.repeat(1, MAX_HOPS)`` and
  returns ``PathTraversal`` entities; ``p.nodes`` exposes only the
  Host endpoints of each hop -- the middle ``AttackStep`` entities
  are recovered separately via a consecutive-host-pair join back
  through ``attack_step_to``.
- Mitigations cover individual ``AttackStep`` entities through a
  ``MitigationCovers`` relation. A path is "broken by" a mitigation
  if the mitigation covers at least one of the path's attack steps.
- ``PathMitigator(path, mitigation)`` is a derived relation that
  pairs each enumerated attack path with every mitigation that could
  break it. The set-cover IC then says: for every attack path ``p``,
  the sum of ``Mitigation.deploy`` over the mitigations in
  ``PathMitigator(p, _)`` is at least 1.
- Decision variables: ``Mitigation.deploy`` is a binary per-mitigation
  property. The objective minimises the total deployment cost (in $K).
  Two additional CSP-natural ICs over decision variables:
  ``sum(deploy).per(kind) <= MAX_PER_KIND`` (cardinality cap per kind)
  and ``sum(cost * deploy).per(target_segment) <= cap_kdollars``
  (per-zone budget envelope). Backend is MiniZinc/Chuffed: cardinality
  + weighted-sum constraints lift natively without big-M.

Run:
    `python attack_path_hardening.py`

Output:
    Prints the formulation, the enumerated attack paths, the chosen
    mitigation portfolio, per-kind counts, per-segment spend, and the
    per-path break attribution, plus post-solve constraint verification.
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.std.paths import PathTraversal

# Runner-level parameters.
# Maximum number of attack-step hops between an entry point and a
# crown jewel that the paths library will enumerate. 6 hops covers
# realistic lateral-movement chains (e.g. workstation -> fileserver
# -> jumpbox -> app-server -> domain-controller -> finance-db) while
# keeping the candidate path set tractable on a small graph.
MAX_HOPS = 6
# Minimum per-edge risk weight for an attack step to count as
# "high-risk" and be enumerated as part of an attack path. The
# Rules pillar pre-filters at edge construction so the paths library
# only sees edges worth covering. 30 is the lower bound on the bundled
# data; raise it to shrink the candidate path set further.
MIN_EDGE_RISK_WEIGHT = 30
# Operational policy: change windows let the security team deploy at
# most this many mitigations of any single kind in one cycle. Caps
# the cumulative blast radius if any one mitigation kind regresses
# (e.g. one bad patch is recoverable; ten bad patches in flight is
# not). Demonstrates `count.per(Mitigation.kind)` over decision
# variables -- a CSP-natural cardinality constraint.
MAX_PER_KIND = 4
# Per-segment-class change budgets (in $K). Different segments are
# owned by different change-control teams (workstation ops vs DMZ
# ops vs DC ops vs backup ops), each with their own quarterly
# spend authority. Demonstrates `sum(cost * deploy).per(target_segment)`
# multi-axis cost ICs over decision variables. Set deliberately tight
# so the optimizer is forced to choose between narrow-and-many or
# broad-and-few alternatives within each segment.
SEGMENT_BUDGET_KDOLLARS = {
    "user-vlan": 30,
    "dmz-vlan": 25,
    "server-vlan": 40,
    "dc-vlan": 90,
    "backup-vlan": 15,
}

model = Model("attack_path_hardening")

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Concept: host (a node in the IT graph -- workstation, server, DC, ...).
Host = model.Concept("Host", identify_by={"id": Integer})
Host.name = model.Property(f"{Host} has {String:name}")
Host.segment = model.Property(f"{Host} in {String:segment}")
Host.role = model.Property(f"{Host} has {String:role}")
hosts_csv = read_csv(data_dir / "hosts.csv")
model.define(Host.new(model.data(hosts_csv).to_schema()))

# Predicate sub-concepts: EntryPoint and CrownJewel are sub-concepts
# of Host whose membership is the "is an attacker entry" / "is a
# crown jewel" predicate. Following the patient_cohort_query idiom of
# using sub-concepts for predicate markers (cleaner than Boolean
# indicator properties; downstream rules say `EntryPoint(Host)` to
# test the predicate).
EntryPoint = model.Concept("EntryPoint", extends=[Host])
entry_csv = read_csv(data_dir / "entry_points.csv")
ep_data = model.data(entry_csv)
model.define(EntryPoint(Host)).where(Host.id == ep_data.host_id)

CrownJewel = model.Concept("CrownJewel", extends=[Host])
cj_csv = read_csv(data_dir / "crown_jewels.csv")
cj_data = model.data(cj_csv)
model.define(CrownJewel(Host)).where(Host.id == cj_data.host_id)

# Concept: AttackStep -- an entified directed edge in the attack
# graph. Identity is the integer id of the (src, dst, kind) row in
# the input CSV. Carrying `risk_weight` and `kind` as properties lets
# us pre-filter at the Rules pillar and lets mitigations target a
# specific edge by id.
AttackStep = model.Concept("AttackStep", identify_by={"id": Integer})
AttackStep.kind = model.Property(f"{AttackStep} has {String:kind}")
AttackStep.risk_weight = model.Property(f"{AttackStep} has {Integer:risk_weight}")
attack_steps_csv = read_csv(data_dir / "attack_steps.csv")
as_data = model.data(attack_steps_csv)
model.define(
    AttackStep.new(id=as_data.id, kind=as_data.kind, risk_weight=as_data.risk_weight)
)

# 3-arity traversal relationship: Host.attack_step_to(src, step, dst).
# The middle slot is the entified AttackStep, so step properties
# (kind, risk_weight) survive into derived rules. When paths walks
# this edge, `p.nodes` exposes ONLY the Host endpoints of each hop
# -- the middle AttackStep entities are not in p.nodes. The
# prescriptive layer recovers them separately by joining consecutive
# Host pairs back through attack_step_to (see the `# Bridge:` block
# below).
Host.attack_step_to = model.Relationship(
    f"{Host:src} via {AttackStep:step} reaches {Host:dst}",
    short_name="attack_step_to",
)

# --------------------------------------------------
# Rules pillar: lift CSV rows to attack-step edges.
# Pre-filtered to risk_weight >= MIN_EDGE_RISK_WEIGHT so the paths
# library only enumerates over high-risk edges. Pre-filtering at the
# Rules layer (rather than via a path-pattern .where() post-filter)
# is the recommended idiom for v1.1.0 paths -- post-filters apply on
# top of the BFS result and can blow up on dense graphs.
# --------------------------------------------------

src_h, dst_h, step = Host.ref(), Host.ref(), AttackStep.ref()
model.define(Host.attack_step_to(src_h, step, dst_h)).where(
    src_h.id == as_data.src_host_id,
    dst_h.id == as_data.dst_host_id,
    step.id == as_data.id,
    step.risk_weight >= MIN_EDGE_RISK_WEIGHT,
)

# --------------------------------------------------
# Paths pillar: enumerate attack paths via the v1.1.0 paths library.
# `path(src, edge.repeat(1, MAX_HOPS), dst).all_paths()` runs a
# bounded BFS and returns a relation of PathTraversal entities --
# one entity per concrete attack chain. Endpoints are unified with
# the EntryPoint / CrownJewel predicates so only realistic
# attacker-to-jewel chains are enumerated.
# --------------------------------------------------

# Use bare-BFS form (no explicit endpoints in path()) so all_paths()
# returns a callable Relationship rather than a Fragment column --
# enables the natural `m.define(AttackPath(p_ref)).where(all_paths(p_ref), ...)`
# pattern below. Confirmed via `tests/end2end/paths/api/test_all_paths.py`
# and the source at `src/relationalai/semantics/std/paths/api.py:322-323`:
# bare BFS returns the underlying Relationship; explicit endpoints or
# .where() filters wrap the result in a non-callable Fragment column.
all_paths_bare = model.path(
    Host.attack_step_to.repeat(1, MAX_HOPS),
).all_paths()

# Persist matching paths as AttackPath: paths whose first node is an
# EntryPoint and whose last node (at index path.length) is a
# CrownJewel. p.nodes(i, host) is the relational form of "path p has
# host at index i" -- length == hop count, indexed 0..length over the
# Host endpoints of each hop (the AttackStep middle entities are NOT
# in p.nodes; they're recovered separately via the attack_step_to
# join below).
AttackPath = model.Concept("AttackPath", extends=[PathTraversal])
ap_pre = PathTraversal.ref()
ep, cj = Host.ref(), Host.ref()
model.define(AttackPath(ap_pre)).where(
    all_paths_bare(ap_pre),
    ap_pre.nodes(0, ep),
    ap_pre.nodes(ap_pre.length, cj),
    EntryPoint(ep),
    CrownJewel(cj),
)

# --------------------------------------------------
# Bridge: derive PathContainsStep(path, step). p.nodes only stores
# Hosts (the src/dst endpoints of each hop) -- AttackStep entities
# live in the middle slot of `Host.attack_step_to(src, step, dst)`
# and are not exposed via p.nodes. We recover them by iterating
# consecutive Host pairs at indices (i, i+1) along each path and
# joining back to attack_step_to.
# --------------------------------------------------

ap_ref = AttackPath.ref()
idx = Integer.ref()
src_h_along = Host.ref()
dst_h_along = Host.ref()
step_along = AttackStep.ref()
PathContainsStep = model.Relationship(
    f"{AttackPath:path} contains {AttackStep:step}",
    short_name="path_contains_step",
)
model.define(PathContainsStep(ap_ref, step_along)).where(
    ap_ref.nodes(idx, src_h_along),
    ap_ref.nodes(idx + 1, dst_h_along),
    Host.attack_step_to(src_h_along, step_along, dst_h_along),
)

# Concept: Mitigation -- a candidate countermeasure. Each mitigation
# has a `kind` (patch_vuln / network_segment / mfa_gate /
# revoke_credential / disable_delegation / trust_break), a
# `target_segment` indicating which network zone
# it primarily protects (used for per-zone change-budget envelopes),
# and a `cost_kdollars` deployment cost in thousands of dollars.
# Mitigation-to-attack-step coverage is a separate many-to-many
# relation (`MitigationCovers`) so a single broad mitigation can
# cover many edges (e.g. a credential-rotation policy covers every
# credential_reuse edge).
Mitigation = model.Concept("Mitigation", identify_by={"id": Integer})
Mitigation.name = model.Property(f"{Mitigation} has {String:name}")
Mitigation.kind = model.Property(f"{Mitigation} has {String:kind}")
Mitigation.target_segment = model.Property(
    f"{Mitigation} protects {String:target_segment}"
)
Mitigation.cost_kdollars = model.Property(f"{Mitigation} costs {Integer:cost_kdollars}")
mit_csv = read_csv(data_dir / "mitigations.csv")
mit_data = model.data(mit_csv)
model.define(
    Mitigation.new(
        id=mit_data.id,
        name=mit_data.name,
        kind=mit_data.kind,
        target_segment=mit_data.target_segment,
        cost_kdollars=mit_data.cost_kdollars,
    )
)

# MitigationCovers(mitigation, attack_step): which mitigations
# break which edges. Loaded from a separate CSV because mitigations
# can cover many edges (e.g. broad credential rotation covers every
# credential_reuse edge in the graph) and a single edge can be
# covered by multiple mitigations (e.g. either patching the SMB
# vulnerability OR network-segmenting the path; the optimizer
# picks whichever is cheapest given the rest of the portfolio).
MitigationCovers = model.Relationship(
    f"{Mitigation:mit} covers {AttackStep:step}",
    short_name="mitigation_covers",
)
mit_covers_csv = read_csv(data_dir / "mitigation_covers.csv")
mc_data = model.data(mit_covers_csv)
mit_ref = Mitigation.ref()
step_for_mit = AttackStep.ref()
model.define(MitigationCovers(mit_ref, step_for_mit)).where(
    mit_ref.id == mc_data.mitigation_id,
    step_for_mit.id == mc_data.attack_step_id,
)

# Derived relation: PathMitigator(path, mitigation). A path is
# "broken by" a mitigation if the mitigation covers at least one
# attack step on the path. Pre-aggregating to (path, mitigation)
# pairs (rather than (path, step, mitigation) triples) is the right
# shape for the set-cover IC -- a single mitigation covering two
# steps in the same path should count once, not twice.
PathMitigator = model.Relationship(
    f"{AttackPath:path} broken by {Mitigation:mit}",
    short_name="path_mitigator",
)
ap2 = AttackPath.ref()
mit2 = Mitigation.ref()
step2 = AttackStep.ref()
model.define(PathMitigator(ap2, mit2)).where(
    PathContainsStep(ap2, step2),
    MitigationCovers(mit2, step2),
)

# --------------------------------------------------
# Prescriptive pillar: minimum-cost set cover (CSP, MiniZinc/Chuffed).
# --------------------------------------------------

Mitigation.deploy = model.Property(f"{Mitigation} is deployed if {Integer:d}")

problem = Problem(model, Integer)

# Decision variable: one binary per mitigation.
problem.solve_for(
    Mitigation.deploy,
    type="bin",
    name=["deploy", Mitigation.id],
)

# Set-cover IC: every enumerated attack path must be broken by at
# least one deployed mitigation. The aggregation iterates over
# `PathMitigator(path, mitigation)` pairs and groups by path; the
# `>= 1` lower bound forces at least one mitigation per path to
# carry `deploy = 1`. Pure relational arithmetic, so `verify`
# re-evaluates the IC on the returned solution.
ap3 = AttackPath.ref()
coverage_ic = model.where(PathMitigator(ap3, Mitigation)).require(
    sum(Mitigation.deploy).per(ap3) >= 1
)
problem.satisfy(coverage_ic)

# Per-kind operational limit: at most MAX_PER_KIND mitigations of any
# single kind can be deployed. Caps blast radius if any one kind
# regresses (e.g. a bad patch in one window). The `sum.per(kind)`
# aggregates `deploy` over each kind and bounds it -- a CSP-natural
# cardinality constraint over decision variables, lifted naturally
# by MiniZinc/Chuffed without big-M reformulation.
per_kind_limit_ic = model.require(
    sum(Mitigation.deploy).per(Mitigation.kind) <= MAX_PER_KIND
)
problem.satisfy(per_kind_limit_ic)

# Per-segment-class budget envelopes: each network zone (user-vlan,
# dmz-vlan, server-vlan, dc-vlan, backup-vlan) has its own
# change-control budget owned by a different ops team. The
# `sum(cost * deploy).per(target_segment)` IC is a multi-axis cost
# bound over decision variables. Bounds come from a `SegmentBudget`
# Concept whose membership is loaded from `SEGMENT_BUDGET_KDOLLARS`.
# A second CSP-natural shape (cost-weighted aggregation) on top of
# the `count.per(kind)` cardinality IC above.
SegmentBudget = model.Concept("SegmentBudget", identify_by={"segment": String})
SegmentBudget.cap_kdollars = model.Property(
    f"{SegmentBudget} has cap {Integer:cap_kdollars}"
)
for seg, cap in SEGMENT_BUDGET_KDOLLARS.items():
    model.define(SegmentBudget.new(segment=seg, cap_kdollars=cap))

seg_ref = SegmentBudget.ref()
per_segment_budget_ic = model.where(
    seg_ref.segment == Mitigation.target_segment,
).require(
    sum(Mitigation.cost_kdollars * Mitigation.deploy).per(seg_ref)
    <= seg_ref.cap_kdollars
)
problem.satisfy(per_segment_budget_ic)

# Objective: minimise total deployment cost (in $K).
problem.minimize(sum(Mitigation.cost_kdollars * Mitigation.deploy))

# --------------------------------------------------
# Solve and verify
# --------------------------------------------------

problem.display()
problem.solve("minizinc", time_limit_sec=60)
problem.solve_info().display()

problem.verify(coverage_ic, per_kind_limit_ic, per_segment_budget_ic)
model.require(problem.termination_status() == "OPTIMAL")

# --------------------------------------------------
# Inspect results
# --------------------------------------------------

print("\nEntry points (attacker-reachable hosts):")
model.select(
    EntryPoint.id.alias("host_id"),
    EntryPoint.name.alias("host_name"),
).inspect()

print("\nCrown jewels (high-value assets):")
model.select(
    CrownJewel.id.alias("host_id"),
    CrownJewel.name.alias("host_name"),
).inspect()

print(
    f"\nEnumerated attack paths (length 1 to {MAX_HOPS}, edge risk >= {MIN_EDGE_RISK_WEIGHT}):"
)
model.select(
    AttackPath.alias("path"),
    AttackPath.length.alias("hops"),
    AttackPath.nodes["index"].alias("step_index"),
    Host(AttackPath.nodes).name.alias("host"),
).inspect()

print("\nDeployed mitigation portfolio (minimum-cost set cover):")
model.select(
    Mitigation.id.alias("mitigation_id"),
    Mitigation.name.alias("mitigation_name"),
    Mitigation.kind.alias("kind"),
    Mitigation.target_segment.alias("target_segment"),
    Mitigation.cost_kdollars.alias("cost_kdollars"),
).where(Mitigation.deploy == 1).inspect()

print("\nPer-kind deployment counts (capped at MAX_PER_KIND):")
model.select(
    Mitigation.kind.alias("kind"),
    sum(Mitigation.deploy).per(Mitigation.kind).alias("n_deployed"),
).inspect()

print("\nPer-segment-class spend (capped per SEGMENT_BUDGET_KDOLLARS):")
seg_disp = SegmentBudget.ref()
model.select(
    seg_disp.segment.alias("segment"),
    seg_disp.cap_kdollars.alias("cap_kdollars"),
    sum(Mitigation.cost_kdollars * Mitigation.deploy)
    .per(seg_disp)
    .where(seg_disp.segment == Mitigation.target_segment)
    .alias("spend_kdollars"),
).inspect()

print("\nPer-path break attribution (which deployed mitigations break each path):")
mit5 = Mitigation.ref()
model.select(
    AttackPath.alias("path"),
    mit5.id.alias("mitigation_id"),
    mit5.name.alias("mitigation_name"),
).where(
    PathMitigator(AttackPath, mit5),
    mit5.deploy == 1,
).inspect()
