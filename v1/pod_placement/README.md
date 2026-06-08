---
title: "Pod Placement"
description: "Assign pods to nodes in a Kubernetes-style cluster subject to per-node CPU / memory / GPU bin-packing, pairwise tenant anti-affinity, deployment co-location affinity, failure-domain spread, gang-placement atomicity, and topology rack-clique rules. Pure CSP via MiniZinc / Chuffed."
featured: false
experience_level: intermediate
industry: "Technology & Telecom"
reasoning_types:
  - Prescriptive
tags:
  - constraint-programming
  - cluster-scheduling
  - anti-affinity
  - gang-placement
  - topology-clique
  - kubernetes
---

# Pod Placement

## What this template is for

Multi-tenant Kubernetes / SaaS / HPC platform teams place pods (containerised workloads) onto cluster nodes against a stack of rules that don't fit a clean linear program:

- **Resource bin-packing** -- each node has fixed CPU / memory / GPU capacity, and the sum of pod demands on a node can't exceed it.
- **Tenant anti-affinity** -- regulated workloads (SEC / OCC / NAIC / FedRAMP) require pairs of tenants to never share a host, so a single noisy-neighbour or compromised node can't span the isolation boundary.
- **Deployment co-location affinity** -- deployments declared affinity-paired (e.g. shared storage class, low-latency RDMA peering) must co-locate (same node) or share their unplaced state: the `xi == xj` IC forces both to agree on every node's assignment bit, which means they share a single node when placed and are simultaneously unplaced otherwise.
- **Failure-domain spread** -- replicas of one deployment fan out across zones so a single-zone outage can't take down a quorum.
- **Gang-placement atomicity** -- a multi-replica deployment is either fully placed (every replica scheduled) or fully unplaced; a partial schedule is worse than nothing for stateful systems with leader elections, quorums, and shared-state protocols.
- **Topology rack-clique** -- distributed-training pods need NVLink-class bandwidth between every pair, so the whole group must land on hosts within the same rack.

This template encodes that stack as a pure constraint satisfaction / optimisation problem: the **Prescriptive** reasoner (MiniZinc / Chuffed) maximises the number of placed deployments subject to all six rules as hard constraints. The shape applies to every multi-tenant K8s shop, financial-services regulated multi-tenancy, defence / FedRAMP-cleared environments, telco 5G network slicing, and HPC + AI infrastructure that runs gang-scheduled distributed training.

## Who this is for

- Platform / infrastructure engineers running multi-tenant Kubernetes, Mesos, or Volcano clusters
- Site-reliability engineers designing failure-domain spread policies and gang-scheduling rules
- HPC / ML-platform teams placing distributed-training jobs across NVLink islands
- Operations researchers learning pure-CSP encodings of pairwise anti-affinity, reified cardinality (the all-or-nothing gang-placement constraint, encoded as a 0/1 deployment-level indicator), and topology-clique constraints

## What you'll build

- A semantic model with `Node`, `Pod`, `Deployment`, `Tenant`, `Zone`, `Rack` concepts, plus three symmetric data relationships: `TenantAntiAffinity`, `DeploymentAffinity`, and `DistributedTraining`
- A binary 2D assignment matrix decision `Pod.on_node(Node, x)` paired with two 0/1 indicators (`Pod.placed`, `Deployment.placed`) that pin each pod's row sum and each deployment's gang state
- Three bin-packing ICs (`sum(Pod.cpu_millicores * x).per(Node) <= Node.cpu_millicores`, and analogues for memory and GPU)
- A pairwise tenant anti-affinity IC -- `xi + xj <= 1` per node for every (Pi, Pj) pair whose deployments' tenants are anti-affine -- expressed directly over the matrix without big-M reformulation
- A pairwise deployment co-location affinity IC that forces affinity-paired pods to agree on every node's assignment bit
- A per-(deployment, zone) failure-domain spread IC bounded by `Deployment.max_per_zone` -- by default `ceil(replicas / num_zones)`, with a per-row `max_per_zone_override` column in `deployments.csv` for deployments (e.g. distributed-training groups) that need a wider blast radius to remain feasible
- A reified-cardinality gang-placement IC `sum(Pod.placed).per(Deployment) == Deployment.replicas * Deployment.placed`
- A pairwise topology rack-clique IC for distributed-training groups -- `xa + xb <= 1` for every (Pa, Pb, Na, Nb) tuple where the pods are in the same training group and the nodes are in different racks
- A linear `maximize(sum(Deployment.placed))` objective the CSP optimises
- Post-solve verification via `problem.verify()` confirming every IC holds in the returned solution, plus a `termination_status() == "OPTIMAL"` assertion

## What's included

The bundled CSVs are illustrative, fully synthetic demo data tuned so multiple ICs bind at the optimum -- rack-clique forces the distributed-training group onto one rack, CPU / memory / GPU bin-packing then pin it to a single node at exact 100% utilisation on all three resources, anti-affinity partitions the alpha-beta and gamma-delta tenant pods across disjoint node sets, deployment co-location affinity co-locates the cache pair, and the spread cap binds for every multi-replica non-overridden deployment. Swap in your own cluster topology and workload to apply the template to a real cluster.

- `pod_placement.py` -- main script with concepts, decisions, constraints, the solver call, and the post-solve inspection
- `data/nodes.csv` -- 8 nodes across 2 zones (`us-east-1a`, `us-east-1b`) and 4 racks; six general-purpose nodes (12000 millicores, 49152 MiB) and two GPU nodes (8000 millicores, 32768 MiB, 4 GPUs each). Total cluster: 88000 millicores, 360448 MiB, 8 GPUs
- `data/tenants.csv` -- 4 tenants (`tenant_alpha`, `tenant_beta`, `tenant_gamma`, `tenant_delta`)
- `data/tenant_anti_affinity.csv` -- 2 anti-affine pairs (`tenant_alpha` x `tenant_beta`, `tenant_gamma` x `tenant_delta`)
- `data/deployments.csv` -- 12 deployments across the 4 tenants: 8-replica web services, 4-replica api services, single-replica caches, a 6-replica database (`db_gamma`), and a 4-pod distributed-training job (`ml_gamma_train`). One column, `max_per_zone_override`, is a nullable per-row spread cap; the bundled data sets it to `4` for `ml_gamma_train` so the same-rack training group can land entirely in one zone (the GPU nodes are concentrated there)
- `data/deployment_affinity.csv` -- 1 affinity-paired pair (`cache_alpha` x `cache_delta`, motivated by a shared storage class)
- `data/pods.csv` -- 50 pods with per-pod CPU / memory / GPU demands aligned to deployment role (web 1000m / 2048 MiB, api 1500m / 3072 MiB, cache 500m / 1024 MiB, db 2000m / 4096 MiB, ml 2000m / 8192 MiB / 1 GPU)
- `data/distributed_training.csv` -- 6 pairs forming the 4-pod NVLink clique for `ml_gamma_train`
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
   curl -O https://docs.relational.ai/templates/zips/v1/pod_placement.zip
   unzip pod_placement.zip
   cd pod_placement
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
   python pod_placement.py
   ```

6. Expected output (the solver maximises the number of placed deployments; the specific (pod, node) tuples and per-node utilisation may vary across solver versions when multiple placements tie at the optimum). The script first prints the formulation (a few thousand lines for the bundled data, omitted here for brevity), then the solve-result block, then the per-node utilisation, the per-pod placement, and any unplaced deployments. A representative run looks like:
   ```text
   Solve result:
   • status: OPTIMAL
   • objective: 12
   • solve time: ~1s
   • num_points: 1
   • solver: MiniZinc_unknown

   Per-node utilization:
     node_id       node  cpu_used  cpu_cap  memory_used  gpu_used
   0       1  gen-a1-n1      5500    12000        11264         0
   1       2  gen-a1-n2     11000    12000        22528         0
   2       3  gen-a2-n1      8500    12000        17408         0
   3       4  gen-a2-n2      3500    12000         7168         0
   4       5  gpu-b1-n1      5500     8000        11264         0
   5       6  gen-b1-n2     11000    12000        22528         0
   6       7  gpu-b2-n1      8000     8000        32768         4
   7       8  gen-b2-n2     11000    12000        22528         0

   Placed pods (pod_id -> node_id):
       pod_id  node_id
   ...

   Unplaced deployments (if any):
   (empty)
   ```

   The optimum places all `12` deployments and binds **four** ICs at the chosen GPU node: rack-clique pins `ml_gamma_train`'s 4 pods onto a single rack, and CPU / memory / GPU bin-packing then pin them all to one node within that rack at exactly 100% utilisation on every resource (`gpu-b2-n1` here: 4 × 2000m = 8000m CPU = the node's CPU cap, 4 × 8192 MiB = 32768 MiB memory = the node's memory cap, 4 × 1 = 4 GPUs = the node's GPU cap -- a tight three-resource fit). The training group could equivalently land on `gpu-b1-n1` (same shape, other GPU rack) and the solver may tie-break either way across versions; what's solver-invariant is "all 4 pods on the same rack on a single node, 100% utilised on three resources". The `max_per_zone_override = 4` in `deployments.csv` is what unlocks this: without it, the default spread cap `ceil(4 / 2) = 2` plus the all-or-nothing gang rule plus the rack-clique requirement plus the GPU racks all sitting in `us-east-1b` (a rack belongs to exactly one zone, so all-pods-on-one-rack implies all-pods-in-one-zone) would make `ml_gamma_train` fully unplaced and the objective `11`. The override is the operator's explicit acceptance of a wider blast radius for the training group: a single-zone outage takes the whole training job, which is the standard tradeoff for an NVLink-tight ML deployment. The other bound counts that remain solver-invariant across the optimum: each multi-replica non-overridden deployment lands at exactly `ceil(replicas / 2)` pods per zone (the spread cap binds for `web_*` at 4+4, `api_*` at 2+2, `db_gamma` at 3+3), the affinity-paired caches (`cache_alpha`, `cache_delta`) co-locate on a single node, and alpha/beta and gamma/delta tenant pods partition the cluster into disjoint node sets.

## Template structure
```text
.
├── README.md
├── pyproject.toml
├── pod_placement.py
└── data/
    ├── nodes.csv
    ├── tenants.csv
    ├── tenant_anti_affinity.csv
    ├── deployments.csv
    ├── deployment_affinity.csv
    ├── pods.csv
    └── distributed_training.csv
```

## How it works

The CSP picks a node for each pod via a binary 2D assignment matrix; everything else is plain relational arithmetic over that matrix. The script consists of these patterns:

**Binary 2D matrix as the primary decision.** Each pod gets one binary `x` per node, materialised as `Pod.on_node(Node, x)`. A per-pod cardinality IC pins the row sum to a 0/1 placement indicator:

```python
Pod.on_node = model.Property(f"{Pod} runs on {Node} if {Integer:assigned}")
Pod.placed = model.Property(f"{Pod} has {Integer:placed}")

x = Integer.ref()
problem.solve_for(Pod.on_node(Node, x), type="bin", name=["x", Pod.id, Node.id])
problem.solve_for(Pod.placed, type="bin", name=["placed", Pod.id])

placement_coupling_ic = model.where(Pod.on_node(Node, x)).require(
    sum(x).per(Pod) == Pod.placed
)
```

An integer-valued `Pod.node_id` decision would read more naturally for the "different-node" pairwise pattern (`Pi.node_id != Pj.node_id`), but per-node aggregates would then force a `where(Pod.node_id == Node.id)`-shaped binding that mixes a decision variable with a data property -- the prescriptive rewriter does not lower that form today (the planogram template's `implies`-cascade table lookup is the canonical workaround). The 2D matrix sidesteps the rewriter limitation: every aggregate becomes a plain relational sum over `x`.

**Bin-packing is one `sum(... * x).per(Node)` per resource.** Three near-identical ICs, one for each of CPU / memory / GPU:

```python
cpu_capacity_ic = model.where(Pod.on_node(Node, x)).require(
    sum(Pod.cpu_millicores * x).per(Node) <= Node.cpu_millicores
)
```

**Pairwise anti-affinity is the CSP signature.** For every ordered pod-pair `(Pi, Pj)` whose deployments' tenants are anti-affine, at most one of `(Pi, Pj)` is on any given node:

```python
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
```

The ordered `Pi.id < Pj.id` filter canonicalises each pair so the IC fires once per `{Pi, Pj}` unordered pair. `TenantAntiAffinity` is closed symmetrically at definition time (the two `model.define` rules), so the predicate matches in either argument order. The same pairwise-pod / pairwise-node shape encodes the deployment co-location affinity IC (`xi == xj` on every node) and the topology rack-clique IC (`xa + xb <= 1` whenever the two pods are in a distributed-training group and the two nodes are in different racks).

**Gang placement is a reified cardinality IC.** A deployment is either fully placed (`sum(Pod.placed).per(Deployment) == Deployment.replicas`) or fully unplaced (`sum(Pod.placed).per(Deployment) == 0`). The unified form uses a 0/1 deployment-level indicator:

```python
Deployment.placed = model.Property(f"{Deployment} has {Integer:placed}")
problem.solve_for(Deployment.placed, type="bin", name=["dep_placed", Deployment.id])

gang_placement_ic = model.where(Pod.deployment == Deployment).require(
    sum(Pod.placed).per(Deployment) == Deployment.replicas * Deployment.placed
)
```

`Deployment.placed == 0` forces every replica's `Pod.placed == 0` (sum == 0); `Deployment.placed == 1` forces every replica's `Pod.placed == 1` (sum == replicas). No big-M, no aux indicator stack.

**Failure-domain spread is a two-key `sum(x).per(Deployment, Zone)`.** With `max_per_zone` pre-computed (default `ceil(replicas / num_zones)`, or the `max_per_zone_override` value when set on the row) and joined onto `Deployment`, the IC reads as a plain relational inequality:

```python
spread_ic = model.where(
    Pod.on_node(Node, x),
    Pod.deployment == Deployment,
    Node.zone == Zone,
).require(sum(x).per(Deployment, Zone) <= Deployment.max_per_zone)
```

The override is a deployment-level escape hatch for cases where the default spread cap collides with another constraint -- the bundled data uses it on `ml_gamma_train` so the rack-clique IC (which forces all distributed-training pods onto a single rack, and therefore into a single zone) doesn't make the deployment infeasible.

**All nine ICs are pure relational arithmetic.** None of them carry an `implies` body, so `problem.verify()` re-evaluates every constraint in the returned solution. The post-solve assertion `model.require(problem.termination_status() == "OPTIMAL")` then guarantees the solver actually proved optimality rather than timing out.

## Customize this template

- **Use your own data** by replacing the seven CSV files with your cluster topology and workload. The constraint structure does not change. The data requirements are: primary keys must be unique across `nodes.csv` / `tenants.csv` / `deployments.csv` / `pods.csv`; every foreign key (`deployments.tenant_id`, `pods.deployment_id`, `tenant_anti_affinity.tenant_*`, etc.) must resolve; node capacities must be positive; `pods.csv` row counts per `deployment_id` must equal `deployments.csv`.`replicas` (the gang IC pins them); each rack belongs to exactly one zone; and any `max_per_zone_override` value, when present, must be a positive integer no greater than the row's `replicas`.
- **Change the objective.** `problem.maximize(sum(Deployment.placed))` maximises the number of placed deployments. Swap for `problem.maximize(sum(Deployment.replicas * Deployment.placed))` to weight by replica count, `problem.minimize(...)` over a per-node fragmentation cost (sum-of-squared-utilisation-gaps), or pure satisfaction (`problem.satisfy()` with a `Deployment.placed == 1` hard floor) when every deployment must run.
- **Tier-aware placement.** Mark pods with `gpu_units > 0` and add an IC forcing them onto GPU-capable nodes only -- e.g. `model.where(Pod.on_node(Node, 1), Pod.gpu_units >= 1).require(Node.gpu_units >= 1)` (matches the `model.where(...).require(...)` chaining used by every IC in `pod_placement.py`). Conversely, mark some nodes as "general-purpose only" and forbid GPU workloads there.
- **Migration cost under churn.** Add a `Pod.current_node` data property reflecting the existing assignment, then introduce a per-pod "moved" indicator (`moved = (1 - Pod.on_node(current_node, x))`) and minimise the total move count -- multi-solution then enumerates the N least-disruptive placements.
- **NVLink-clique with explicit edges.** The bundled `data/distributed_training.csv` lists every pair in the training group, encoding rack-clique implicitly via the pairwise IC. To model a true edge-restricted clique (e.g. NVLink-2 connectivity between specific GPU pairs only), pre-compute the set of `(node_a, node_b)` pairs that lack a direct NVLink edge in Python and load them as a `NoNVLink` data relationship; then drop the `Na.rack != Nb.rack` clause from `rack_clique_ic` and replace it with `NoNVLink(Na, Nb)` to forbid co-placement on any pair of hosts without a direct NVLink path.
- **Spot / preemptible tier.** Mark a subset of pods as preemptible (`Pod.is_preemptible == 1`) and let them displace lower-priority workloads when capacity is tight. Express as a per-node tiered capacity: preemptible pods consume "remaining" capacity, on-demand pods consume the primary allotment.
- **Tighten or loosen the spread cap.** The default `max_per_zone = ceil(replicas / num_zones)` is the loosest spread that still admits a placement when replicas fan out evenly across zones. For a strict 1-per-zone policy (so even a hot zone can't host two replicas of the same service), set `max_per_zone_override = 1` for that row in `deployments.csv`. For a deployment whose other ICs force same-zone placement (the bundled `ml_gamma_train` is the canonical example -- rack-clique plus all-GPU-racks-in-one-zone), set `max_per_zone_override = replicas` to opt out of spread for that deployment alone, leaving the cluster-wide default intact for everything else.
- **Multi-cluster (federated placement).** Add a `Cluster` concept above `Zone` and an outer `Pod.on_cluster(Cluster)` decision; spread / anti-affinity then have to lift to cluster-level constraints. Karmada-style multi-cluster placement is the standard precedent.

## Learn more

**Production cluster managers** (the field this template models):
- Verma et al., [*Large-scale cluster management at Google with Borg*](https://research.google/pubs/large-scale-cluster-management-at-google-with-borg/), EuroSys 2015. Constraint-driven cluster scheduling at scale; affinity / anti-affinity / failure-domain spread as first-class concepts.
- Hindman et al., [*Mesos: A Platform for Fine-Grained Resource Sharing in the Data Center*](https://www.usenix.org/legacy/event/nsdi11/tech/full_papers/Hindman_new.pdf), NSDI 2011. Two-level resource scheduling -- the conceptual predecessor of every modern cluster manager.
- [Volcano](https://volcano.sh/en/docs/), open-source batch scheduler for Kubernetes (CNCF incubating) with first-class gang-scheduling, queue fairness, and topology-aware placement.

**Kubernetes scheduling surface** (the canonical vocabulary):
- [Kubernetes scheduler framework: affinity & anti-affinity](https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/). Official documentation of `nodeAffinity`, `podAffinity`, `podAntiAffinity`.
- [Kubernetes topology-spread constraints](https://kubernetes.io/docs/concepts/scheduling-eviction/topology-spread-constraints/). Failure-domain spread as a first-class Kubernetes API.
- [Kueue documentation](https://kueue.sigs.k8s.io/docs/concepts/). Kubernetes-native queueing with placement constraints.
- [Karmada multi-cluster placement](https://karmada.io/docs/userguide/scheduling/cluster-affinity/). Cluster-affinity scheduling for multi-cluster Kubernetes deployments.

**Constraint-programming background** (the academic backbone for the encoding choices):
- [CSPLib problem 057 -- RCPSP](https://www.csplib.org/Problems/prob057/). Resource-constrained project scheduling -- the closest classical CSP benchmark to multi-resource bin-packing with side constraints.
- Mehta & van Beek, [*Mapping Problems with Side Constraints to SAT*](https://cs.uwaterloo.ca/~vanbeek/Publications/cp07.pdf), CP 2007. Academic precedent for mapping placement problems with pairwise / clique / cardinality side constraints to discrete satisfaction.

## Troubleshooting

<details>
  <summary>Solver returns INFEASIBLE</summary>

- A deployment's replica count may exceed what the failure-domain spread allows. With two zones and a replica count of 5, the default `max_per_zone = ceil(5/2) = 3` requires at least one zone to host 3 replicas of that deployment -- if no three-node subset in any zone fits them, the model is infeasible.
- Tenant anti-affinity may over-partition the cluster. If `tenant_a` and `tenant_b` are anti-affine and your cluster has only enough capacity for one of them on each node, the model can't fit both. Loosen by adding more nodes, dropping the anti-affinity pair, or shrinking workload demands.
- The bundled affinity-paired deployments must be able to land on a single node. If `cache_alpha` and `cache_delta` have a combined demand that doesn't fit on any one node, the affinity IC is unsatisfiable. Check the affinity-paired demands against the largest node's capacity.
- Distributed-training rack-cliques interact with failure-domain spread when the GPU racks all sit in the same zone. On the bundled data, both GPU racks (`rack-b1`, `rack-b2`) are in zone `us-east-1b`, so a 4-pod training job that must share a rack also ends up sharing that zone -- but the default `max_per_zone = ceil(4/2) = 2` allows only 2 of the 4 replicas in any one zone. Combined with gang placement (all 4 or none), the deployment would be left fully unplaced and the objective would drop to `11`. The bundled `deployments.csv` sets `max_per_zone_override = 4` on `ml_gamma_train` to opt out of spread for the training group only, which is what lets the bundled solve hit `objective = 12`. To reproduce the infeasibility for the training deployment, blank that override and re-run; to widen the fix to your own workload, raise `max_per_zone_override` on the training row, or drop the rack-clique IC AND spread the GPU nodes across zones (so the 4 pods can split across racks in different zones and still satisfy spread). Note that simply spreading the GPU nodes across zones is not enough on its own: a rack belongs to exactly one zone, so as long as rack-clique forces all 4 pods onto a single rack, those 4 pods still share a zone.

</details>

<details>
  <summary>One deployment is unplaced; how do I find out why?</summary>

- The optimal solution can leave a deployment unplaced if placing it would require violating another IC. Check the printed "Unplaced deployments" block. Common binding constraints: failure-domain spread (a deployment's GPU/CPU demand is concentrated in fewer zones than `max_per_zone` allows -- raise the row's `max_per_zone_override` if that's the right operational tradeoff); rack-clique (a distributed-training group's GPU requirement exceeds any single rack's capacity, or all GPU racks sit in one zone so a single-rack placement collides with spread -- the bundled `ml_gamma_train` lives at this exact intersection, which is why its row sets the override); gang placement (the deployment's replicas can't all fit somewhere, so the all-or-none rule leaves it fully unplaced).
- To isolate which IC is binding, drop one IC at a time and re-solve: comment out `problem.satisfy(rack_clique_ic)`, run, and see whether the deployment then places. Repeat with the spread and gang ICs. The first IC whose removal allows placement is the binding one.

</details>

<details>
  <summary>The `Pod.deployment.tenant` chained navigation produces a runtime error on inspection</summary>

- Multi-hop property navigation inside `model.select(...)` combined with a decision-variable filter (`where(Pod.on_node(Node, 1))`) can produce a query the engine refuses to evaluate within its runtime budget. The bundled inspection avoids the issue by keeping each query to single-hop navigation (`Node.id`, `Pod.id`).
- If you need richer post-solve reporting (e.g. a `(pod, deployment_name, tenant_name, node, zone, rack)` table), pull the placement into pandas and join in Python: `placements = model.select(Pod.id, Node.id).where(Pod.on_node(Node, 1)).to_df()`, then `placements.merge(pods_csv, on="pod_id").merge(deployments_csv, on="deployment_id")...`.

</details>

<details>
  <summary>Import error or AttributeError on <code>relationalai</code></summary>

- Confirm your virtual environment is active: `which python` should point to `.venv`.
- Reinstall dependencies: `python -m pip install .`. The pinned version (`relationalai==1.1.0`) ships the `solve_info()`, `verify()`, and `where().require()` APIs this template uses; older versions lack them and produce attribute errors.

</details>

<details>
  <summary>FileNotFoundError on a CSV</summary>

- The script resolves data paths as `Path(__file__).parent / "data"`. Run `python pod_placement.py` from the unzipped template root, not from a parent directory.
- Confirm `data/` contains `nodes.csv`, `tenants.csv`, `tenant_anti_affinity.csv`, `deployments.csv`, `deployment_affinity.csv`, `pods.csv`, and `distributed_training.csv`.

</details>

<details>
  <summary>Authentication or configuration errors</summary>

- Run `rai init` to create or update your RelationalAI/Snowflake configuration.
- If you have multiple profiles, set `export RAI_PROFILE=<your_profile>`.

</details>

<details>
  <summary>MiniZinc solver not available</summary>

- This template uses the MiniZinc / Chuffed constraint solver. Ensure the RAI Native App version supports MiniZinc.

</details>

<details>
  <summary>Solver hits the time limit (status is not `OPTIMAL`) and the script crashes</summary>

- The post-solve `model.require(problem.termination_status() == "OPTIMAL")` is a hard assertion: if you raise `time_limit_sec` and the solver returns a feasible-but-not-proven-optimal result (`SOLUTION_LIMIT` or `LOCALLY_SOLVED`), the script raises rather than print a partial solution.
- For a tutorial run on the bundled data this is the right posture (the oracle is "the solver proved 11/12"). For larger user data, either (a) raise `time_limit_sec` until the solver proves optimality, or (b) replace `model.require(...)` with a `print(...)` warning and let the inspection blocks run on the best feasible placement found.

</details>

<details>
  <summary>A distributed-training group is silently splitting across racks</summary>

- The `rack_clique_ic` fires once per row in `distributed_training.csv`. The IC enforces "same rack" only for the pairs of pods listed there -- it does NOT close the relation transitively. The bundled CSV provides all `C(4, 2) = 6` pairs for the 4-pod `ml_gamma_train` group, so every pair is constrained. If you supply only a spanning tree (e.g. 3 edges instead of 6 for a 4-pod group), non-adjacent pods can legally land on different racks.
- To model an N-pod training group, enumerate all `C(N, 2)` pairs in `distributed_training.csv`. Alternatively, pre-compute the transitive closure of the group graph in Python before passing it to `model.data(...)`.

</details>
