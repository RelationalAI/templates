---
title: "Attack Path Hardening"
description: "Find the cheapest set of security mitigations that breaks every attack path from entry points to crown jewels."
featured: false
experience_level: intermediate
industry: "Cybersecurity"
reasoning_types:
  - Graph
  - Rules
  - Prescriptive
tags:
  - attack-graph
  - paths
  - set-cover
  - constraint-programming
  - security
---

# Attack Path Hardening

## What this template is for

A security team has a model of their enterprise IT graph (workstations, jumpboxes, application servers, domain controllers, databases, backup systems). They know which hosts attackers can reach from outside ("entry points") and which hosts hold the crown-jewel data they must protect (finance database, executive mailbox, HR database). They have a budget of candidate mitigations -- patch a vulnerability, segment a VLAN, break a domain trust, gate a host with MFA, revoke a credential -- each with a deployment cost in $K and an operational kind. The question is: which subset of mitigations should we deploy so that every attack chain from an entry point to a crown jewel is broken, while staying within per-zone change budgets and per-kind operational caps?

This template formulates the problem as a three-pillar pipeline:

- **Rules** lift CSV rows into entified attack-step edges, pre-filtered by risk weight.
- **Paths** (the v1.1.0 paths library) enumerates every concrete attack chain from an entry point to a crown jewel up to a bounded hop count.
- **Prescriptive** (CSP, MiniZinc/Chuffed) selects the minimum-cost set-cover of mitigations such that each enumerated path is broken by at least one deployed mitigation, subject to a cardinality cap per kind and a cost-aggregation budget per segment.

The output is a deployable mitigation portfolio plus per-path attribution showing which deployed mitigation breaks which attack chain.

## Who this is for

- Security engineers exploring attack-graph-based hardening recommendations
- Risk analysts comparing portfolios of countermeasures under a fixed budget
- Developers learning how to combine the paths library with prescriptive reasoning in PyRel
- Anyone interested in a worked example of three-pillar (Graph + Rules + Prescriptive) modeling

## What you'll build

- An entified attack-step graph over 20 hosts and 30 directed steps with risk weights
- An enumeration of every attack chain from any entry point to any crown jewel up to 6 hops
- A CSP formulation that picks the cheapest mitigation portfolio breaking every chain, subject to per-kind operational limits and per-segment-class budget envelopes
- Post-solve verification of all three integrity constraints and a per-path attribution report

## What's included

- `attack_path_hardening.py` -- main script: ontology, paths enumeration, CSP set-cover, and inspection queries
- `data/hosts.csv` -- 20 hosts across 5 segments (user-vlan, dmz-vlan, server-vlan, dc-vlan, backup-vlan)
- `data/entry_points.csv` -- 4 attacker-reachable hosts (workstations + dev station)
- `data/crown_jewels.csv` -- 3 high-value assets (finance-db, executive-mailbox, hr-db)
- `data/attack_steps.csv` -- 30 directed attack steps with kinds (credential_reuse, phish_*, trust_traversal, vuln_exploit_*, delegation) and risk weights
- `data/mitigations.csv` -- 25 candidate mitigations with kind, target segment, and cost in $K
- `data/mitigation_covers.csv` -- 56 mitigation-to-attack-step coverage edges (broad mitigations cover many edges)
- `pyproject.toml` -- Python package configuration

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools
- Python >= 3.10

## Quickstart

1. Download ZIP:
   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/attack_path_hardening.zip
   unzip attack_path_hardening.zip
   cd attack_path_hardening
   ```
   > [!TIP]
   > You can also download the template ZIP using the "Download ZIP" button at the top of this page.

2. Create venv:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   ```

3. Install:
   ```bash
   python -m pip install .
   ```

4. Configure:
   ```bash
   rai init
   ```

5. Run:
   ```bash
   python attack_path_hardening.py
   ```

6. Expected output (truncated):
   ```text
   Solve result:
   • status: OPTIMAL
   • objective: 139
   • solve time: 0.09s
   • num_points: 1
   • solver: MiniZinc_nothing

   Deployed mitigation portfolio (minimum-cost set cover):
     mitigation_id                 mitigation_name  ... target_segment cost_kdollars
   0            19  fileserver-jumpbox-trust-break  ...       dmz-vlan             7
   1            20       disable-dc-delegation-fin  ...        dc-vlan            18
   2            21      disable-dc-delegation-mail  ...        dc-vlan            18
   3            22        disable-dc-delegation-hr  ...        dc-vlan            18
   4            23       broad-credential-rotation  ...        dc-vlan            28
   5            24             broad-vuln-patching  ...    server-vlan            38
   6            25                   broad-dmz-mfa  ...       dmz-vlan            12

   Per-segment-class spend (capped per SEGMENT_BUDGET_KDOLLARS):
        segment cap_kdollars spend_kdollars
   0  backup-vlan           15              0
   1      dc-vlan           90             82
   2     dmz-vlan           25             19
   3  server-vlan           40             38
   4    user-vlan           30              0
   ```

   The optimal portfolio costs $139K and deploys 7 mitigations: 1 trust-break,
   3 delegation disablements per crown jewel, plus three "broad" mitigations
   (credential rotation, vulnerability patching, DMZ MFA) that each cover
   many attack steps simultaneously. The dc-vlan budget binds tightest
   ($82K of $90K), since the crown jewels live there.

## Template structure
```text
.
├── README.md
├── pyproject.toml
├── attack_path_hardening.py
└── data/
    ├── hosts.csv
    ├── entry_points.csv
    ├── crown_jewels.csv
    ├── attack_steps.csv
    ├── mitigations.csv
    └── mitigation_covers.csv
```

## How it works

**1. Entified attack-step graph.** Each row of `attack_steps.csv` becomes an `AttackStep` entity carrying a `kind` and `risk_weight`. The traversal edge `Host.attack_step_to(src, step, dst)` is a 3-arity relationship with the `AttackStep` entity in the middle slot, so step properties survive the graph walk:

```python
AttackStep = model.Concept("AttackStep", identify_by={"id": Integer})
AttackStep.kind = model.Property(f"{AttackStep} has {String:kind}")
AttackStep.risk_weight = model.Property(f"{AttackStep} has {Integer:risk_weight}")

Host.attack_step_to = model.Relationship(
    f"{Host:src} via {AttackStep:step} reaches {Host:dst}",
    short_name="attack_step_to",
)
```

`EntryPoint` and `CrownJewel` are predicate sub-concepts of `Host`, so downstream rules say `EntryPoint(host)` rather than testing a Boolean property.

**2. Enumerate attack paths.** The paths library walks the bounded edge with `repeat(1, MAX_HOPS)`. Using the bare-BFS form (no explicit endpoints in `path()`) returns a callable Relationship; we then post-filter in `define()` so only paths starting at an entry point and ending at a crown jewel become `AttackPath` entities:

```python
all_paths_bare = model.path(
    Host.attack_step_to.repeat(1, MAX_HOPS),
).all_paths()

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
```

**3. Recover the attack steps along each path.** `p.nodes(i, host)` exposes only the Host endpoints of each hop -- the middle `AttackStep` entities are not in `p.nodes`. We recover them by joining consecutive Host pairs back through `attack_step_to`:

```python
model.define(PathContainsStep(ap_ref, step_along)).where(
    ap_ref.nodes(idx, src_h_along),
    ap_ref.nodes(idx + 1, dst_h_along),
    Host.attack_step_to(src_h_along, step_along, dst_h_along),
)
```

`PathMitigator(path, mitigation)` is then derived as the join of `PathContainsStep` and `MitigationCovers` -- a path is broken by a mitigation if the mitigation covers any step on the path.

**4. CSP set-cover with three integrity constraints.** `Mitigation.deploy` is a binary decision variable. The objective minimises the total deployment cost. Three ICs:

```python
# Coverage: every enumerated attack path must be broken by at least one
# deployed mitigation.
coverage_ic = model.where(PathMitigator(ap3, Mitigation)).require(
    sum(Mitigation.deploy).per(ap3) >= 1
)

# Per-kind operational limit: at most MAX_PER_KIND mitigations of any one kind.
per_kind_limit_ic = model.require(
    sum(Mitigation.deploy).per(Mitigation.kind) <= MAX_PER_KIND
)

# Per-segment-class budget envelope: each zone has its own change-control
# spend authority, expressed as a cost-weighted aggregation IC.
per_segment_budget_ic = model.where(
    seg_ref.segment == Mitigation.target_segment,
).require(
    sum(Mitigation.cost_kdollars * Mitigation.deploy).per(seg_ref)
    <= seg_ref.cap_kdollars
)
```

**5. Solve and verify.** MiniZinc/Chuffed handles cardinality and weighted-sum aggregations natively. After solving, `problem.verify()` re-evaluates the named ICs against the returned solution:

```python
problem.solve("minizinc", time_limit_sec=60)
problem.verify(coverage_ic, per_kind_limit_ic, per_segment_budget_ic)
model.require(problem.termination_status() == "OPTIMAL")
```

## Customize this template

- **Tighten or loosen segment budgets** by editing `SEGMENT_BUDGET_KDOLLARS`. The dc-vlan cap binds tightest in the bundled scenario; lower it to force the optimizer onto narrower-and-many alternatives.
- **Change the per-kind cap** by adjusting `MAX_PER_KIND`. With `MAX_PER_KIND=1` the problem may become infeasible; with very large values, the per-kind IC becomes inactive.
- **Raise the risk-weight threshold** (`MIN_EDGE_RISK_WEIGHT`) to prune low-risk attack steps from the path enumeration. This shrinks the candidate path set and the resulting set-cover.
- **Add coverage edges** by appending to `mitigation_covers.csv`. A new "broad" mitigation that covers many steps cheaply often dominates several narrow per-edge mitigations.
- **Switch to maximum-coverage** by replacing the cost objective with `problem.maximize(sum(...n_paths_broken...))` under a hard total-cost cap -- the dual framing of set cover.
- **Add severity-weighted coverage** by attaching an `AttackPath.severity` property and requiring `sum(Mitigation.deploy).per(AttackPath) >= AttackPath.severity` for high-severity chains.

## Troubleshooting

<details>
  <summary>Solver returns INFEASIBLE</summary>

- The bundled segment caps are loose enough to admit the cost-optimal portfolio. If you tighten `SEGMENT_BUDGET_KDOLLARS["dc-vlan"]` below ~$80K, no portfolio can break every dc-vlan-bound chain within budget -- the problem becomes infeasible.
- Likewise, `MAX_PER_KIND=1` only allows one mitigation per kind. For kinds with many narrow per-target mitigations (e.g. the three `disable-dc-delegation-{fin,mail,hr}` mitigations), this can force the optimizer onto upstream broad mitigations to break crown-jewel-bound paths; if no upstream broad coverage exists for a given path, the problem becomes infeasible.
- Verify the `mitigation_covers.csv` rows actually map to existing `mitigation_id` and `attack_step_id` values.

</details>

<details>
  <summary>"Expected '<entity>', got 'Anything'" or ungrounded variable errors</summary>

- The paths library returns `PathTraversal` entities. When deriving sub-concepts (`AttackPath`) or joining `p.nodes(i, x)`, ensure `x` is typed as `Host.ref()` -- not `AnyEntity` -- so downstream rules type-check cleanly.
- The middle slot of `Host.attack_step_to(src, step, dst)` is `AttackStep`, not `Host`. Don't try to read `AttackStep` properties directly off `p.nodes(...)` -- use the consecutive-host-pair join shown in step 3.

</details>

<details>
  <summary>Path enumeration is slow or memory-heavy</summary>

- The paths library performs a bounded BFS; the enumerated set grows with `MAX_HOPS`. Lower `MAX_HOPS` (default 6) or raise `MIN_EDGE_RISK_WEIGHT` to prune the edge set first.
- Pre-filtering at the Rules layer (only lifting high-risk steps into `attack_step_to`) is cheaper than post-filtering paths, since the BFS sees fewer edges.

</details>

<details>
  <summary>Import error for <code>relationalai</code></summary>

- Confirm your virtual environment is active: `which python` should point to `.venv`.
- Reinstall dependencies: `python -m pip install .`.

</details>

<details>
  <summary>Authentication or configuration errors</summary>

- Run `rai init` to create or update your RelationalAI/Snowflake configuration.
- If you have multiple profiles, set `export RAI_PROFILE=<your_profile>`.

</details>

<details>
  <summary>MiniZinc solver not available</summary>

- This template uses the MiniZinc constraint solver. Ensure the RAI Native App version supports MiniZinc.
- HiGHS targets linear/MIP problems; switching backends would require reformulating the cardinality and cost-aggregation ICs into a 0-1 integer program.

</details>
