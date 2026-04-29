"""Attack-path hardening (Graph paths + Rules + CSP set cover) template.

Three-pillar pipeline: Rules lift CSV rows to attack-step edges; the
v1.1.0 paths library enumerates entry-point -> crown-jewel chains
with bounded depth; the prescriptive CSP layer (MiniZinc/Chuffed)
picks the minimum-cost subset of mitigations such that every attack
path is broken, subject to per-kind operational caps and per-segment
change-budget envelopes. See README for the full story and data.

Run: `python attack_path_hardening.py`
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.std.paths import PathTraversal

# Bounded BFS depth: 6 covers realistic lateral-movement chains
# (e.g. workstation -> fileserver -> jumpbox -> app -> DC -> finance-db).
MAX_HOPS = 6
# Pre-filter low-risk edges at the Rules layer (post-filtering on path
# results blows up on dense graphs). 30 is the lower bound on the
# bundled data; raise to shrink the candidate path set.
MIN_EDGE_RISK_WEIGHT = 30
# Operational policy: caps blast radius from a regression in any one
# mitigation kind per change window.
MAX_PER_KIND = 4
# Per-segment change-control budgets in $K, each owned by a different
# ops team. Set tight to force narrow-vs-broad portfolio tradeoffs.
SEGMENT_BUDGET_KDOLLARS = {
    "user-vlan": 30,
    "dmz-vlan": 25,
    "server-vlan": 40,
    "dc-vlan": 90,
    "backup-vlan": 15,
}

model = Model("attack_path_hardening")
data_dir = Path(__file__).parent / "data"

# --- Schema and data -------------------------------------------------

Host = model.Concept("Host", identify_by={"id": Integer})
Host.name = model.Property(f"{Host} has {String:name}")
Host.segment = model.Property(f"{Host} in {String:segment}")
Host.role = model.Property(f"{Host} has {String:role}")
hosts_csv = read_csv(data_dir / "hosts.csv")
model.define(Host.new(model.data(hosts_csv).to_schema()))

# Predicate sub-concepts (idiomatic alternative to Boolean indicator
# properties): downstream rules write `EntryPoint(Host)` to test.
EntryPoint = model.Concept("EntryPoint", extends=[Host])
ep_data = model.data(read_csv(data_dir / "entry_points.csv"))
model.define(EntryPoint(Host)).where(Host.id == ep_data.host_id)

CrownJewel = model.Concept("CrownJewel", extends=[Host])
cj_data = model.data(read_csv(data_dir / "crown_jewels.csv"))
model.define(CrownJewel(Host)).where(Host.id == cj_data.host_id)

# AttackStep: entified directed edge. Identity is the (src, dst, kind)
# row id; properties survive into derived rules.
AttackStep = model.Concept("AttackStep", identify_by={"id": Integer})
AttackStep.kind = model.Property(f"{AttackStep} has {String:kind}")
AttackStep.risk_weight = model.Property(f"{AttackStep} has {Integer:risk_weight}")
as_data = model.data(read_csv(data_dir / "attack_steps.csv"))
model.define(
    AttackStep.new(id=as_data.id, kind=as_data.kind, risk_weight=as_data.risk_weight)
)

# 3-arity traversal with the AttackStep entity in the middle slot.
# When paths walks this edge, p.nodes exposes ONLY the Host endpoints
# of each hop; AttackStep entities are recovered downstream by joining
# consecutive Host pairs back through attack_step_to.
Host.attack_step_to = model.Relationship(
    f"{Host:src} via {AttackStep:step} reaches {Host:dst}",
    short_name="attack_step_to",
)

# Mitigation kinds in the bundled data: patch_vuln / network_segment /
# mfa_gate / revoke_credential / disable_delegation / trust_break.
Mitigation = model.Concept("Mitigation", identify_by={"id": Integer})
Mitigation.name = model.Property(f"{Mitigation} has {String:name}")
Mitigation.kind = model.Property(f"{Mitigation} has {String:kind}")
Mitigation.target_segment = model.Property(
    f"{Mitigation} protects {String:target_segment}"
)
Mitigation.cost_kdollars = model.Property(f"{Mitigation} costs {Integer:cost_kdollars}")
mit_data = model.data(read_csv(data_dir / "mitigations.csv"))
model.define(
    Mitigation.new(
        id=mit_data.id,
        name=mit_data.name,
        kind=mit_data.kind,
        target_segment=mit_data.target_segment,
        cost_kdollars=mit_data.cost_kdollars,
    )
)

MitigationCovers = model.Relationship(
    f"{Mitigation:mit} covers {AttackStep:step}",
    short_name="mitigation_covers",
)
mc_data = model.data(read_csv(data_dir / "mitigation_covers.csv"))
model.define(MitigationCovers(Mitigation, AttackStep)).where(
    Mitigation.id == mc_data.mitigation_id,
    AttackStep.id == mc_data.attack_step_id,
)

# Lift the per-segment budget table into a Concept so the per-segment
# IC stays declarative as a single multi-axis aggregation.
SegmentBudget = model.Concept("SegmentBudget", identify_by={"segment": String})
SegmentBudget.cap_kdollars = model.Property(
    f"{SegmentBudget} has cap {Integer:cap_kdollars}"
)
for seg, cap in SEGMENT_BUDGET_KDOLLARS.items():
    model.define(SegmentBudget.new(segment=seg, cap_kdollars=cap))

# --- Rules: lift CSV rows to attack-step edges (pre-filtered) -------

src_h, dst_h = Host.ref(), Host.ref()
model.define(Host.attack_step_to(src_h, AttackStep, dst_h)).where(
    src_h.id == as_data.src_host_id,
    dst_h.id == as_data.dst_host_id,
    AttackStep.id == as_data.id,
    AttackStep.risk_weight >= MIN_EDGE_RISK_WEIGHT,
)

# --- Paths: enumerate entry-point -> crown-jewel chains -------------

# Bare-BFS form (no explicit endpoints) returns a callable Relationship
# usable directly inside `.where()`; the explicit-endpoint form returns
# a non-callable Fragment column that doesn't compose this way.
all_paths_bare = model.path(
    Host.attack_step_to.repeat(1, MAX_HOPS),
).all_paths()

# v1.1.0 quirk: sub-concept extension over PathTraversal does NOT
# auto-scope inherited `.nodes` access by sub-concept membership, so
# every downstream rule that walks AttackPath.nodes must re-apply the
# EP/CJ filter inline.
AttackPath = model.Concept("AttackPath", extends=[PathTraversal])
ep, cj = Host.ref(), Host.ref()
model.define(AttackPath(PathTraversal)).where(
    all_paths_bare(PathTraversal),
    PathTraversal.nodes(0, ep),
    PathTraversal.nodes(PathTraversal.length, cj),
    EntryPoint(ep),
    CrownJewel(cj),
)

# Recover AttackStep entities along each path. EP/CJ filter inline per
# the AttackPath quirk above.
PathContainsStep = model.Relationship(
    f"{AttackPath:path} contains {AttackStep:step}",
    short_name="path_contains_step",
)
idx = Integer.ref()
src_h_along, dst_h_along = Host.ref(), Host.ref()
ep_filt, cj_filt = Host.ref(), Host.ref()
model.define(PathContainsStep(AttackPath, AttackStep)).where(
    AttackPath.nodes(0, ep_filt),
    AttackPath.nodes(AttackPath.length, cj_filt),
    EntryPoint(ep_filt),
    CrownJewel(cj_filt),
    AttackPath.nodes(idx, src_h_along),
    AttackPath.nodes(idx + 1, dst_h_along),
    Host.attack_step_to(src_h_along, AttackStep, dst_h_along),
)

# Pre-aggregate to (path, mitigation) pairs so a single mitigation
# covering two steps in the same path counts once, not twice.
PathMitigator = model.Relationship(
    f"{AttackPath:path} broken by {Mitigation:mit}",
    short_name="path_mitigator",
)
model.define(PathMitigator(AttackPath, Mitigation)).where(
    PathContainsStep(AttackPath, AttackStep),
    MitigationCovers(Mitigation, AttackStep),
)

# --- Prescriptive: minimum-cost set cover (CSP, MiniZinc/Chuffed) ---

Mitigation.deploy = model.Property(f"{Mitigation} is deployed if {Integer:d}")

problem = Problem(model, Integer)
problem.solve_for(
    Mitigation.deploy,
    type="bin",
    name=["deploy", Mitigation.id],
)

# Set cover: every attack path must be broken by at least one deployed mitigation.
coverage_ic = model.where(PathMitigator(AttackPath, Mitigation)).require(
    sum(Mitigation.deploy).per(AttackPath) >= 1
)
problem.satisfy(coverage_ic)

# Per-kind cardinality cap (CSP-natural, no big-M lift).
per_kind_limit_ic = model.require(
    sum(Mitigation.deploy).per(Mitigation.kind) <= MAX_PER_KIND
)
problem.satisfy(per_kind_limit_ic)

# Per-segment cost envelope (multi-axis weighted-sum aggregation).
per_segment_budget_ic = model.where(
    SegmentBudget.segment == Mitigation.target_segment,
).require(
    sum(Mitigation.cost_kdollars * Mitigation.deploy).per(SegmentBudget)
    <= SegmentBudget.cap_kdollars
)
problem.satisfy(per_segment_budget_ic)

problem.minimize(sum(Mitigation.cost_kdollars * Mitigation.deploy))

# --- Solve and verify -----------------------------------------------

problem.display()
problem.solve("minizinc", time_limit_sec=60)
problem.solve_info().display()

problem.verify(coverage_ic, per_kind_limit_ic, per_segment_budget_ic)
model.require(problem.termination_status() == "OPTIMAL")

# --- Inspect results ------------------------------------------------

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
# Inline EP/CJ filter required (AttackPath quirk above).
idx_disp = Integer.ref()
host_disp, ep_disp, cj_disp = Host.ref(), Host.ref(), Host.ref()
model.select(
    AttackPath.alias("path"),
    AttackPath.length.alias("hops"),
    idx_disp.alias("step_index"),
    host_disp.name.alias("host"),
).where(
    AttackPath.nodes(0, ep_disp),
    AttackPath.nodes(AttackPath.length, cj_disp),
    EntryPoint(ep_disp),
    CrownJewel(cj_disp),
    AttackPath.nodes(idx_disp, host_disp),
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
model.select(
    SegmentBudget.segment.alias("segment"),
    SegmentBudget.cap_kdollars.alias("cap_kdollars"),
    sum(Mitigation.cost_kdollars * Mitigation.deploy)
    .per(SegmentBudget)
    .where(SegmentBudget.segment == Mitigation.target_segment)
    .alias("spend_kdollars"),
).inspect()

print("\nPer-path break attribution (which deployed mitigations break each path):")
model.select(
    AttackPath.alias("path"),
    Mitigation.id.alias("mitigation_id"),
    Mitigation.name.alias("mitigation_name"),
).where(
    PathMitigator(AttackPath, Mitigation),
    Mitigation.deploy == 1,
).inspect()
