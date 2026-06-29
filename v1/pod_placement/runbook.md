# Pod Placement — Analyst Runbook

A platform team running a multi-tenant cluster needs to place every workload pod onto a node while satisfying a stack of rules that don't reduce to a clean linear program: CPU / memory / GPU bin-packing, tenant isolation, deployment co-location, spread across failure zones, all-or-nothing placement of multi-replica deployments, and rack-locality for distributed-training jobs. The dataset is 8 nodes (2 with GPUs), 50 pods across 12 deployments and 4 tenants, plus the affinity/anti-affinity/training rules. The analysis encodes all six rule families as hard constraints and solves a constraint problem that maximizes the number of placed deployments.

```text
8 nodes (2 GPU) · 50 pods · 12 deployments · 4 tenants · affinity / anti-affinity / training-clique rules
      │
      ▼
/rai-prescriptive-problem-formulation + /rai-prescriptive-solver-management
   • decisions: binary pod-to-node assignment · pod placed? · deployment placed?
   • constraints: per-node CPU/mem/GPU capacity; tenant anti-affinity; deployment affinity;
     zone spread; gang (all replicas or none); distributed-training pods share a rack
   • objective: maximize placed deployments
   • MiniZinc constraint solver                  -> OPTIMAL, all 12 deployments placed
      │
      ▼
/rai-prescriptive-results-interpretation
   • all 50 pods + 12 deployments placed, every rule satisfied
   • the 4-pod training clique pins GPU node 7 to exactly 100% on CPU, memory, and GPU
```

Each prompt is pasted into a fresh agent session loaded with the named `/rai-*` skill (named at the start of each prompt). They run in order in a single session — the formulate step reads the `Node`/`Pod`/`Deployment`/`Tenant` concepts and rule relationships the build step created, and the interpret step reads the placement decisions the solve wrote back.

---

## 1. Build the ontology

**Prompt:** /rai-build-starter-ontology Build an ontology from `data/nodes.csv` (each node has CPU, memory, and GPU capacity plus a zone and rack), `data/pods.csv` (each pod belongs to a deployment and requests CPU, memory, and GPU), `data/deployments.csv` (each deployment belongs to a tenant and has a replica count), `data/tenants.csv`, and the rule files `data/tenant_anti_affinity.csv` (tenant pairs that must not share a node), `data/deployment_affinity.csv` (deployment pairs that must co-locate), and `data/distributed_training.csv` (pod pairs that must share a rack). Derive zones and racks from the node data.

**Response:** Loads `Node` (8: 6 general-purpose, 2 with 4 GPUs each), `Pod` (50, each with CPU/memory/GPU requests, linked to a deployment), `Deployment` (12, linked to a tenant with a replica count), `Tenant` (4), and `Zone`/`Rack` derived from the nodes — plus the three rule relationships (2 anti-affinity pairs, 1 affinity pair, the 6-pair distributed-training clique).

## 2. Examine the ontology

**Prompt:** /rai-querying What concepts and relationships does the ontology have, and how many of each?

**Response:** Concepts: 8 `Node` (CPU/memory/GPU, zone, rack), 50 `Pod` (resource requests), 12 `Deployment` (replicas, tenant), 4 `Tenant`, plus derived `Zone` (2) and `Rack` (4). Rule relationships: tenant anti-affinity (2 pairs), deployment affinity (1 pair), and distributed-training (the C(4,2) clique over the 4 training pods).

## 3. Place the pods under all rules

**Prompt:** /rai-prescriptive-problem-formulation + /rai-prescriptive-solver-management Assign pods to nodes to place as many deployments as possible, treating every rule as hard: a pod goes on at most one node; a deployment is placed only if all its replicas are; per node, total CPU, memory, and GPU requests can't exceed capacity; pods of anti-affine tenants can't share a node; affinity-paired deployments must share a node; each deployment's pods are spread so no zone holds more than its share; and the distributed-training pods must all land on the same rack. Maximize the number of placed deployments and persist the assignment to the ontology.

**Response:** OPTIMAL (MiniZinc constraint solver), objective **12 — all 12 deployments placed**. The model is a binary pod-to-node assignment matrix plus placed indicators (hundreds of variables and constraints across the six rule families); the assignment, `Pod.placed`, and `Deployment.placed` are written back to the ontology and re-verified against every rule.

## 4. Read the placement

**Prompt:** /rai-prescriptive-results-interpretation Are all deployments placed, which node is the tightest, and what makes it the binding one?

**Response:** Every deployment is placed — all 50 pods land on a node with no rule violated. The binding node is **GPU node 7**, pinned to **exactly 100% on all three resources** (8000/8000 millicores, 32768 MiB, 4/4 GPU): the 4-pod distributed-training clique must share one rack and each pod needs a GPU, so it consumes a GPU node entirely. The other nodes carry general-purpose pods with headroom, and the affinity-paired caches co-locate as required — so the GPU/rack-locality rule, not raw cluster capacity, is what's tight.

## Data

Bundled CSVs in `data/`: 8 nodes, 50 pods, 12 deployments, 4 tenants, plus the anti-affinity, affinity, and distributed-training rule files. Full model in `pod_placement.py`.
